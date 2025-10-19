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
    detalle = _fetch_detalle(pedido.id)
    return render(request, "accounts/pedido_detalle.html", {
        "pedido": pedido,
        "detalle": detalle,
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
