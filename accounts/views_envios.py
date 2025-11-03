# accounts/views_envios.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models_db import Pedido


# --- helpers -------------------------------------------------

def _envio_by_pedido(pid: int):
    with connection.cursor() as cur:
        cur.execute("""
          SELECT id, pedido_id, estado, nombre_repartidor, telefono_repartidor, created_at
          FROM envio WHERE pedido_id=%s
        """, [pid])
        row = cur.fetchone()
        if not row:
            return None
        cols = [c[0] for c in cur.description]
        return dict(zip(cols, row))


def _total_pagado(pid: int):
    with connection.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(monto),0) FROM pago WHERE pedido_id=%s", [pid])
        (suma,) = cur.fetchone()
        return float(suma or 0)


def _pedidos_listos():
    """
    Precondición CU24:
    - pedido.estado IN ('CONFIRMADO')
    - suma(pago.monto) >= pedido.total
    - sin registro en envio
    """
    with connection.cursor() as cur:
        cur.execute("""
          SELECT p.id, c.nombre AS cliente, p.metodo_envio, p.direccion_entrega,
                 p.total, COALESCE(SUM(pg.monto),0) AS pagado
          FROM pedido p
          JOIN cliente c ON c.id = p.cliente_id
          LEFT JOIN pago pg ON pg.pedido_id = p.id
          LEFT JOIN envio e ON e.pedido_id = p.id
          WHERE e.id IS NULL
            AND p.estado IN ('CONFIRMADO')
          GROUP BY p.id, c.nombre, p.metodo_envio, p.direccion_entrega, p.total
          HAVING pagado >= p.total
          ORDER BY p.id DESC
        """)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# --- vistas --------------------------------------------------

@login_required
def envio_list(request):
    """
    Lista de pedidos listos para gestionar envío.
    """
    rows = _pedidos_listos()
    return render(request, "accounts/envio_list.html", {"rows": rows})


@login_required
def envio_crear_editar(request, pedido_id: int):
    """
    Paso 2 del flujo: seleccionar pedido y asignar repartidor.
    También permite editar si ya existe el envío.
    """
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    envio = _envio_by_pedido(pedido.id)
    pagado = _total_pagado(pedido.id)

    metodo_envio = (pedido.metodo_envio or "").strip().upper()
    is_delivery = (metodo_envio == "DELIVERY")

    if pagado < float(pedido.total or 0):
        messages.error(request, "El pedido no está listo: aún tiene saldo pendiente.")
        return redirect("envio_list")

    if request.method == "POST":
        nombre = (request.POST.get("nombre_repartidor") or "").strip()
        fono = (request.POST.get("telefono_repartidor") or "").strip()

        # Validación solo para delivery
        if is_delivery and not nombre:
            messages.error(request, "Debes asignar un repartidor para DELIVERY.")
            return redirect("envio_crear_editar", pedido_id=pedido.id)

        with transaction.atomic():
            with connection.cursor() as cur:
                if envio:
                    cur.execute("""
                      UPDATE envio
                         SET nombre_repartidor=%s, telefono_repartidor=%s
                       WHERE pedido_id=%s
                    """, [nombre, fono, pedido.id])
                    messages.success(request, "Datos de envío actualizados.")
                else:
                    cur.execute("""
                      INSERT INTO envio (pedido_id, estado, nombre_repartidor, telefono_repartidor)
                      VALUES (%s, 'PENDIENTE', %s, %s)
                    """, [pedido.id, nombre, fono])
                    messages.success(request, "Envío registrado correctamente.")
        return redirect("envio_crear_editar", pedido_id=pedido.id)

    return render(request, "accounts/envio_form.html", {
        "pedido": pedido,
        "envio": envio,
        "pagado": pagado,
        "is_delivery": is_delivery,
    })


@login_required
def envio_marcar_entregado(request, pedido_id: int):
    """
    Paso 3: marcar ENTREGADO (delivery realizado o retiro en tienda).
    """
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    envio = _envio_by_pedido(pedido.id)

    if not envio:
        messages.error(request, "Primero registra el envío (repartidor / retiro).")
        return redirect("envio_crear_editar", pedido_id=pedido.id)

    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("UPDATE envio SET estado='ENTREGADO' WHERE pedido_id=%s", [pedido.id])
            cur.execute("UPDATE pedido SET estado='ENTREGADO' WHERE id=%s", [pedido.id])

    messages.success(request, "El pedido fue marcado como ENTREGADO.")
    return redirect("envio_crear_editar", pedido_id=pedido.id)
