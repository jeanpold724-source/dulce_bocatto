# accounts/views_pedidos.py
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, connection
from django.shortcuts import get_object_or_404, redirect, render

from .permissions import requiere_permiso
from .models_db import Pedido, Producto, Sabor

# Utilidad: leer detalle (con nombres) desde la PK compuesta
def _fetch_detalle(pedido_id: int):
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
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows

def _recalcular_total(pedido_id: int):
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

@login_required
@requiere_permiso("PEDIDO_READ")
def pedidos_pendientes(request):
    qs = (Pedido.objects
          .select_related("cliente")
          .filter(estado="PENDIENTE")
          .order_by("-created_at", "-id"))
    return render(request, "accounts/pedidos_pendientes.html", {"pedidos": qs})

@login_required
@requiere_permiso("PEDIDO_READ")
def pedido_detalle(request, pedido_id):
    pedido = get_object_or_404(Pedido, pk=pedido_id)

    # detalle items (tu helper actual)
    detalle = _fetch_detalle(pedido.id)

    # pagos del pedido
    pagos = list(Pago.objects
                 .filter(pedido_id=pedido.id)
                 .select_related('registrado_por')
                 .order_by('-created_at')
                 .values('id', 'metodo', 'monto', 'referencia', 'created_at',
                         'registrado_por__nombre'))

    total_pagado = _total_pagado(pedido.id)
    queda = (pedido.total or 0) - total_pagado

    return render(request, "accounts/pedido_detalle.html", {
        "pedido": pedido,
        "detalle": detalle,
        "pagos": pagos,
        "total_pagado": total_pagado,
        "saldo_pendiente": queda,
    })


@login_required
@requiere_permiso("PEDIDO_WRITE")
def pedido_editar(request, pedido_id):
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    if pedido.estado != "PENDIENTE":
        messages.info(request, "Solo se pueden editar pedidos en estado PENDIENTE.")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    # Catálogo para los selects
    productos = list(Producto.objects.filter(activo=True).order_by("nombre").values("id","nombre","precio_unitario"))
    sabores   = list(Sabor.objects.filter(activo=True).order_by("nombre").values("id","nombre"))

    if request.method == "POST":
        filas = int(request.POST.get("filas", "0"))
        items = []
        for i in range(filas):
            pid  = request.POST.get(f"p_{i}")
            sid  = request.POST.get(f"s_{i}")
            cant = request.POST.get(f"c_{i}")
            prec = request.POST.get(f"u_{i}")
            if not (pid and sid and cant and prec):
                continue
            try:
                pid = int(pid); sid = int(sid)
                cant = Decimal(cant); prec = Decimal(prec)
            except Exception:
                messages.error(request, "Hay valores inválidos en el detalle.")
                return redirect("pedido_editar", pedido_id=pedido.id)
            if cant <= 0 or prec < 0:
                messages.error(request, "Cantidad y precio unitario deben ser positivos.")
                return redirect("pedido_editar", pedido_id=pedido.id)
            items.append((pid, sid, cant, prec))

        # Aplicar cambios (upsert por PK compuesta)
        with transaction.atomic():
            with connection.cursor() as cur:
                # 1) Borrar combos que ya no vienen en el POST
                if items:
                    cur.execute(
                        """
                        DELETE FROM detalle_pedido
                        WHERE pedido_id=%s
                          AND (producto_id, sabor_id) NOT IN (
                              """ + ",".join(["(%s,%s)"]*len(items)) + """
                          )
                        """,
                        [pedido.id] + [x for t in [(p,s) for p,s,_,_ in items] for x in t],
                    )
                else:
                    # Si no hay items enviados, vaciamos el detalle
                    cur.execute("DELETE FROM detalle_pedido WHERE pedido_id=%s", [pedido.id])

                # 2) UPSERT (INSERT ... ON DUPLICATE KEY UPDATE)
                for (p_id, s_id, cant, pu) in items:
                    cur.execute(
                        """
                        INSERT INTO detalle_pedido (pedido_id, producto_id, sabor_id, cantidad, precio_unitario)
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

    # GET: pintar formulario con el detalle actual
    detalle = _fetch_detalle(pedido.id)
    return render(request, "accounts/pedido_editar.html", {
        "pedido": pedido,
        "detalle": detalle,
        "productos": productos,
        "sabores": sabores,
    })


# --- CU15: Consultar estado de pedidos confirmados ---------------------------
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q, F, Value
from django.db.models.functions import Coalesce, Concat, Trim, NullIf
from django.shortcuts import render

from .permissions import requiere_permiso
from .models_db import Pedido, Usuario


@login_required
@requiere_permiso("PEDIDO_READ")
def pedidos_confirmados(request):
    """
    CU15 – Consultar estado de pedidos confirmados.
    Cliente ve solo sus pedidos; recepcionista/admin ve todos.
    """
    ESTADOS_CONFIRMADOS = ["CONFIRMADO", "EN_PRODUCCION", "LISTO_ENTREGA", "ENTREGADO"]

    # 1) Base queryset
    qs = (Pedido.objects
          .filter(estado__in=ESTADOS_CONFIRMADOS)
          .order_by("-created_at", "-id"))

    # 2) Filtro por actor
    es_admin = request.user.is_staff or request.user.is_superuser
    if not es_admin:
        # Mapea auth.User -> accounts.Usuario usando el email del login
        try:
            app_user = Usuario.objects.get(email=request.user.email)
        except Usuario.DoesNotExist:
            page_obj = Paginator(Pedido.objects.none(), 15).get_page(1)
            return render(request, "accounts/pedidos_confirmados.html", {
                "pedidos": page_obj.object_list,
                "page_obj": page_obj,
                "q": "",
                "estados_confirmados": ESTADOS_CONFIRMADOS,
            })
        else:
            qs = qs.filter(cliente__usuario=app_user)

    # 3) Joins y alias de nombre del cliente con fallbacks
    #    - Usa cliente.nombre si no está vacío ('' -> NULL con NullIf(Trim(...), ''))
    #    - Si no, usa cliente.usuario.nombre
    #    - Si no, usa cliente.usuario.email
    qs = (qs.select_related("cliente", "cliente__usuario")
            .annotate(
                cliente_nombre=Coalesce(
                    NullIf(Trim(F("cliente__nombre")), Value("")),
                    NullIf(Trim(F("cliente__usuario__nombre")), Value("")),
                    F("cliente__usuario__email"),
                    output_field=models.CharField(),
                )
            ))

    # 4) Búsqueda opcional
    q = request.GET.get("q", "").strip()
    if q:
        if q.isdigit():
            qs = qs.filter(Q(id=int(q)) | Q(cliente_nombre__icontains=q))
        else:
            qs = qs.filter(cliente_nombre__icontains=q)

    # 5) Paginación y render
    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "accounts/pedidos_confirmados.html", {
        "pedidos": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "estados_confirmados": ESTADOS_CONFIRMADOS,
    })


from decimal import Decimal
from django.db import connection
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum

from .permissions import requiere_permiso
from .models_db import Pedido, Usuario, Pago


def _total_pagado(pedido_id: int) -> Decimal:
    """Suma de pagos registrados para un pedido."""
    with connection.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(monto),0) FROM pago WHERE pedido_id=%s", [pedido_id])
        (suma,) = cur.fetchone()
    return Decimal(suma or 0)



@login_required
def pago_registrar(request, pedido_id):
    """
    CU16 – Registrar pago de un pedido.
    Permite a recepcionista/admin; opcionalmente cliente si es su pedido.
    """
    pedido = get_object_or_404(Pedido, pk=pedido_id)

    # ¿quién puede pagar?
    es_admin = request.user.is_staff or request.user.is_superuser
    puede_cliente = False
    try:
        app_user = Usuario.objects.get(email=request.user.email)
        puede_cliente = (pedido.cliente_id == getattr(app_user, "cliente_id", None)
                         or pedido.cliente_id is None)  # fallback
    except Usuario.DoesNotExist:
        app_user = None

    if not es_admin and not puede_cliente:
        messages.error(request, "No tienes permisos para registrar pago de este pedido.")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    if request.method == "POST":
        metodo = (request.POST.get("metodo") or "").upper()
        monto  = request.POST.get("monto")
        ref    = (request.POST.get("referencia") or "").strip()

        METODOS = {"EFECTIVO", "QR", "TRANSFERENCIA"}
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

        # Si no encontramos Usuario app, intenta asignar el primero como fallback
        if not app_user:
            app_user = Usuario.objects.order_by("id").first()

        # Insertar pago
        with connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pago (pedido_id, metodo, monto, referencia, registrado_por_id, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                """,
                [pedido.id, metodo, str(monto), ref or None, app_user.id if app_user else None],
            )

        # Mensaje según suma
        total_pagado = _total_pagado(pedido.id)
        if (pedido.total or 0) <= total_pagado:
            messages.success(request, f"Pago registrado. El pedido ya está totalmente pagado ({total_pagado:.2f} Bs.).")
        else:
            faltante = (pedido.total or 0) - total_pagado
            messages.success(request, f"Pago registrado. Saldo pendiente: {faltante:.2f} Bs.")

        return redirect("pedido_detalle", pedido_id=pedido.id)

    # GET: pintar formulario
    total_pagado = _total_pagado(pedido.id)
    saldo = (pedido.total or 0) - total_pagado

    return render(request, "accounts/pago_form.html", {
        "pedido": pedido,
        "total_pagado": total_pagado,
        "saldo_pendiente": saldo,
    })
