# accounts/views_pedidos.py
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection, models, transaction
from django.db.models import F, Q, Value
from django.db.models.functions import Coalesce, NullIf, Trim
from django.shortcuts import get_object_or_404, redirect, render

from .models_db import (
    Pedido,
    Producto,
    Sabor,
    Usuario,
    Pago,
)
from .permissions import requiere_permiso, owner_or_staff_pedido


# ----------------------------
# Helpers SQL
# ----------------------------
def _fetch_detalle(pedido_id: int):
    """Detalle del pedido con nombres de producto/sabor."""
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT dp.producto_id, p.nombre AS producto,
                   dp.sabor_id, s.nombre AS sabor,
                   dp.cantidad, dp.precio_unitario,
                   dp.sub_total
            FROM detalle_pedido dp
            JOIN producto p ON p.id = dp.producto_id
            JOIN sabor s    ON s.id = dp.sabor_id
            WHERE dp.pedido_id = %s
            ORDER BY p.nombre, s.nombre
            """,
            [pedido_id],
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def _recalcular_total(pedido_id: int):
    """Recalcula total (items + costo_envio)."""
    with connection.cursor() as cur:
        cur.execute(
            """
            UPDATE pedido p
            JOIN (
              SELECT pedido_id, SUM(cantidad*precio_unitario) AS items
              FROM detalle_pedido
              WHERE pedido_id=%s
              GROUP BY pedido_id
            ) x ON x.pedido_id=p.id
            SET p.total = x.items + p.costo_envio
            WHERE p.id=%s
            """,
            [pedido_id, pedido_id],
        )


def _total_pagado(pedido_id: int) -> Decimal:
    """Suma de pagos registrados para un pedido."""
    with connection.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(monto),0) FROM pago WHERE pedido_id=%s", [pedido_id])
        (suma,) = cur.fetchone()
    return Decimal(suma or 0)


# ----------------------------
# CUxx – Pedidos pendientes
# ----------------------------
@login_required
@requiere_permiso("PEDIDO_READ")
def pedidos_pendientes(request):
    qs = (
        Pedido.objects.select_related("cliente")
        .filter(estado="PENDIENTE")
        .order_by("-created_at", "-id")
    )
    return render(request, "accounts/pedidos_pendientes.html", {"pedidos": qs})


# ----------------------------
# Detalle de pedido
# ----------------------------
@login_required
@requiere_permiso("PEDIDO_READ")
def pedido_detalle(request, pedido_id):
    pedido = get_object_or_404(Pedido, pk=pedido_id)

    # Detalle e importes
    detalle = _fetch_detalle(pedido.id)
    pagos = list(
        Pago.objects.filter(pedido_id=pedido.id)
        .select_related("registrado_por")
        .order_by("-created_at")
        .values(
            "id",
            "metodo",
            "monto",
            "referencia",
            "created_at",
            "registrado_por__nombre",
        )
    )
    total_pagado = _total_pagado(pedido.id)
    saldo = (pedido.total or 0) - total_pagado

    # Flags de permisos/acciones (para que el template esté limpio)
    es_duenio = False
    try:
        # Emparejamos por email app_user <-> cliente.usuario
        if request.user.is_authenticated and pedido.cliente and pedido.cliente.usuario:
            es_duenio = (pedido.cliente.usuario.email or "").lower() == (request.user.email or "").lower()
    except Exception:
        es_duenio = False

    puede_editar = es_duenio and (saldo or 0) > 0 and pedido.estado not in ("ENTREGADO", "CANCELADO")

    return render(
        request,
        "accounts/pedido_detalle.html",
        {
            "pedido": pedido,
            "detalle": detalle,
            "pagos": pagos,
            "total_pagado": total_pagado,
            "saldo_pendiente": saldo,
            "es_duenio": es_duenio,
            "puede_editar": puede_editar,
        },
    )


# ----------------------------
# Editar pedido (dueño o staff)
# ----------------------------
@login_required
@owner_or_staff_pedido
def pedido_editar(request, pedido_id):
    pedido = get_object_or_404(Pedido, pk=pedido_id)

    # Catálogo para selects
    productos = list(
        Producto.objects.filter(activo=True)
        .order_by("nombre")
        .values("id", "nombre", "precio_unitario")
    )
    sabores = list(Sabor.objects.filter(activo=True).order_by("nombre").values("id", "nombre"))

    if request.method == "POST":
        filas = int(request.POST.get("filas", "0"))
        items = []
        for i in range(filas):
            pid = request.POST.get(f"p_{i}")
            sid = request.POST.get(f"s_{i}")
            cant = request.POST.get(f"c_{i}")
            prec = request.POST.get(f"u_{i}")
            if not (pid and sid and cant and prec):
                continue
            try:
                pid = int(pid)
                sid = int(sid)
                cant = Decimal(cant)
                prec = Decimal(prec)
            except Exception:
                messages.error(request, "Hay valores inválidos en el detalle.")
                return redirect("pedido_editar", pedido_id=pedido.id)
            if cant <= 0 or prec < 0:
                messages.error(request, "Cantidad y precio unitario deben ser positivos.")
                return redirect("pedido_editar", pedido_id=pedido.id)
            items.append((pid, sid, cant, prec))

        # Aplicar cambios con upsert
        with transaction.atomic():
            with connection.cursor() as cur:
                if items:
                    cur.execute(
                        """
                        DELETE FROM detalle_pedido
                        WHERE pedido_id=%s
                          AND (producto_id, sabor_id) NOT IN (
                              """
                        + ",".join(["(%s,%s)"] * len(items))
                        + """
                          )
                        """,
                        [pedido.id]
                        + [x for t in [(p, s) for p, s, _, _ in items] for x in t],
                    )
                else:
                    cur.execute("DELETE FROM detalle_pedido WHERE pedido_id=%s", [pedido.id])

                for (p_id, s_id, cant, pu) in items:
                    cur.execute(
                        """
                        INSERT INTO detalle_pedido
                          (pedido_id, producto_id, sabor_id, cantidad, precio_unitario)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                           cantidad=VALUES(cantidad),
                           precio_unitario=VALUES(precio_unitario)
                        """,
                        [pedido.id, p_id, s_id, str(cant), str(pu)],
                    )

            _recalcular_total(pedido.id)

        messages.success(request, "Pedido actualizado.")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    # GET: formulario con el detalle actual
    detalle = _fetch_detalle(pedido.id)
    return render(
        request,
        "accounts/pedido_editar.html",
        {
            "pedido": pedido,
            "detalle": detalle,
            "productos": productos,
            "sabores": sabores,
        },
    )


# ----------------------------
# CU15 – Consultar pedidos confirmados
# ----------------------------
@login_required
@requiere_permiso("PEDIDO_READ")
def pedidos_confirmados(request):
    ESTADOS_CONFIRMADOS = ["CONFIRMADO", "EN_PRODUCCION", "LISTO_ENTREGA", "ENTREGADO"]

    qs = Pedido.objects.filter(estado__in=ESTADOS_CONFIRMADOS).order_by("-created_at", "-id")

    es_admin = request.user.is_staff or request.user.is_superuser
    if not es_admin:
        try:
            app_user = Usuario.objects.get(email=request.user.email)
        except Usuario.DoesNotExist:
            page_obj = Paginator(Pedido.objects.none(), 15).get_page(1)
            return render(
                request,
                "accounts/pedidos_confirmados.html",
                {
                    "pedidos": page_obj.object_list,
                    "page_obj": page_obj,
                    "q": "",
                    "estados_confirmados": ESTADOS_CONFIRMADOS,
                },
            )
        else:
            qs = qs.filter(cliente__usuario=app_user)

    qs = qs.select_related("cliente", "cliente__usuario").annotate(
        cliente_nombre=Coalesce(
            NullIf(Trim(F("cliente__nombre")), Value("")),
            NullIf(Trim(F("cliente__usuario__nombre")), Value("")),
            F("cliente__usuario__email"),
            output_field=models.CharField(),
        )
    )

    q = request.GET.get("q", "").strip()
    if q:
        if q.isdigit():
            qs = qs.filter(Q(id=int(q)) | Q(cliente_nombre__icontains=q))
        else:
            qs = qs.filter(cliente_nombre__icontains=q)

    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/pedidos_confirmados.html",
        {
            "pedidos": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "estados_confirmados": ESTADOS_CONFIRMADOS,
        },
    )


# ----------------------------
# CU16 – Registrar pago (manual)
# ----------------------------
@login_required
def pago_registrar(request, pedido_id):
    """
    Permite a recepcionista/admin; opcionalmente cliente si es su pedido.
    """
    pedido = get_object_or_404(Pedido, pk=pedido_id)

    es_admin = request.user.is_staff or request.user.is_superuser
    puede_cliente = False
    try:
        app_user = Usuario.objects.get(email=request.user.email)
        # si tu modelo Cliente tiene FK a Usuario, puedes comparar con cliente__usuario_id
        puede_cliente = pedido.cliente.usuario_id == app_user.id
    except Usuario.DoesNotExist:
        app_user = None

    if not es_admin and not puede_cliente:
        messages.error(request, "No tienes permisos para registrar pago de este pedido.")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    if request.method == "POST":
        metodo = (request.POST.get("metodo") or "").upper()
        monto = request.POST.get("monto")
        ref = (request.POST.get("referencia") or "").strip()

        METODOS = {"EFECTIVO", "QR", "TRANSFERENCIA", "STRIPE"}
        if metodo not in METODOS:
            messages.error(request, "Método de pago inválido.")
            return redirect("pago_registrar", pedido_id=pedido.id)

        try:
            monto = Decimal(monto)
        except Exception:
            messages.error(request, "Monto inválido.")
            return redirect("pago_registrar", pedido_id=pedido.id)

        if monto <= 0:
            messages.error(request, "El monto debe ser mayor a cero.")
            return redirect("pago_registrar", pedido_id=pedido.id)

        if not app_user:
            app_user = Usuario.objects.order_by("id").first()

        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pago (pedido_id, metodo, monto, referencia, registrado_por_id, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                [pedido.id, metodo, str(monto), ref or None, app_user.id if app_user else None],
            )

        total_pagado = _total_pagado(pedido.id)
        if (pedido.total or 0) <= total_pagado:
            messages.success(
                request,
                f"Pago registrado. El pedido ya está totalmente pagado ({total_pagado:.2f} Bs.).",
            )
        else:
            faltante = (pedido.total or 0) - total_pagado
            messages.success(request, f"Pago registrado. Saldo pendiente: {faltante:.2f} Bs.")

        return redirect("pedido_detalle", pedido_id=pedido.id)

    total_pagado = _total_pagado(pedido.id)
    saldo = (pedido.total or 0) - total_pagado

    return render(
        request,
        "accounts/pago_form.html",
        {
            "pedido": pedido,
            "total_pagado": total_pagado,
            "saldo_pendiente": saldo,
        },
    )
