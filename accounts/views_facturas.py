# accounts/views_facturas.py
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models_db import Pedido, Pago, Factura

def _total_pagado(pedido_id: int) -> Decimal:
    with connection.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(monto),0) FROM pago WHERE pedido_id=%s", [pedido_id])
        (suma,) = cur.fetchone()
    return Decimal(suma or 0)

@login_required
def factura_emitir(request, pedido_id: int):
    """
    CU17 — Emitir factura.
    Precondición: el pedido debe estar totalmente pagado y sin factura previa.
    """
    pedido = get_object_or_404(Pedido, pk=pedido_id)

    # ¿ya tiene factura?
    ya = Factura.objects.filter(pedido_id=pedido.id).exists()
    if ya:
        messages.info(request, "Este pedido ya tiene factura emitida.")
        return redirect("factura_detalle", pedido_id=pedido.id)

    total_pagado = _total_pagado(pedido.id)
    if (pedido.total or 0) > total_pagado:
        messages.error(request, "El pedido aún no está totalmente pagado.")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    if request.method == "POST":
        nit = (request.POST.get("nit_cliente") or "").strip()
        razon = (request.POST.get("razon_social") or "").strip()

        if not nit:
            messages.error(request, "Debes ingresar el NIT/CI.")
            return redirect("factura_emitir", pedido_id=pedido.id)
        if not razon:
            messages.error(request, "Debes ingresar la Razón social / Nombre.")
            return redirect("factura_emitir", pedido_id=pedido.id)

        # Nro de factura: seguimos tu patrón existente "F-<pedido_id>"
        nro = f"F-{pedido.id}"

        with transaction.atomic():
            # defensa por si dos clicks rápidos
            if Factura.objects.filter(pedido_id=pedido.id).exists():
                messages.info(request, "Este pedido ya tiene factura emitida.")
                return redirect("factura_detalle", pedido_id=pedido.id)

            # Insert a tabla legada (puedes usar ORM también; dejo SQL explícito como en pagos)
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO factura (pedido_id, nro, fecha, nit_cliente, razon_social, total)
                    VALUES (%s, %s, NOW(), %s, %s, %s)
                    """,
                    [pedido.id, nro, nit, razon, str(pedido.total or 0)],
                )

        messages.success(request, f"Factura {nro} generada correctamente.")
        return redirect("factura_detalle", pedido_id=pedido.id)

    # GET: formulario simple + previsualización
    return render(request, "accounts/factura_emitir.html", {
        "pedido": pedido,
        "total_pagado": total_pagado,
    })


@login_required
def factura_detalle(request, pedido_id: int):
    pedido = get_object_or_404(Pedido, pk=pedido_id)
    factura = get_object_or_404(Factura, pedido_id=pedido.id)
    items = _items_pedido(pedido.id)      # <--- NUEVO
    return render(request, "accounts/factura_detalle.html", {
        "pedido": pedido,
        "factura": factura,
        "items": items,                   # <--- NUEVO
    })



# ---- agrega al inicio del archivo (import ya existente) ----
from django.db import connection

# ---- agrega debajo de _total_pagado() ----
def _items_pedido(pedido_id: int):
    """Devuelve el detalle del pedido para imprimir en factura."""
    with connection.cursor() as cur:
        cur.execute("""
            SELECT pr.nombre AS producto,
                   s.nombre  AS sabor,
                   dp.cantidad,
                   dp.precio_unitario,
                   dp.sub_total
            FROM detalle_pedido dp
            JOIN producto pr ON pr.id = dp.producto_id
            JOIN sabor    s  ON s.id = dp.sabor_id
            WHERE dp.pedido_id = %s
            ORDER BY pr.nombre, s.nombre
        """, [pedido_id])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


from datetime import datetime

@login_required
def factura_list(request):
    q      = (request.GET.get("q") or "").strip()           # nro, nombre o email
    desde  = (request.GET.get("desde") or "").strip()
    hasta  = (request.GET.get("hasta") or "").strip()

    where  = ["1=1"]
    params = []

    if q:
        where.append("(f.nro LIKE %s OR u.email LIKE %s OR c.nombre LIKE %s)")
        like = f"%{q}%"
        params += [like, like, like]

    if desde:
        where.append("DATE(f.fecha) >= %s")
        params.append(desde)
    if hasta:
        where.append("DATE(f.fecha) <= %s")
        params.append(hasta)

    sql = f"""
      SELECT f.id, f.nro, f.fecha, f.total,
             p.id AS pedido_id,
             c.nombre AS cliente, u.email
      FROM factura f
      JOIN pedido  p ON p.id = f.pedido_id
      JOIN cliente c ON c.id = p.cliente_id
      JOIN usuario u ON u.id = c.usuario_id
      WHERE {' AND '.join(where)}
      ORDER BY f.fecha DESC, f.id DESC
      LIMIT 500
    """
    with connection.cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    return render(request, "accounts/factura_list.html", {
        "rows": rows,
        "q": q, "desde": desde, "hasta": hasta,
    })
