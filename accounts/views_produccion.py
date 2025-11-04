from django.contrib.auth.decorators import login_required, permission_required
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages


from .models_db import Pedido, DetallePedido, Producto, Sabor, Insumo, Kardex
from .models_recetas import Receta


# Util: verificar stock de insumos para un producto
from decimal import Decimal
from django.db import connection

def _insumos_necesarios(producto_id: int, cantidad_producto: int):
    """
    Devuelve los insumos requeridos para producir `cantidad_producto` unidades del producto,
    junto con stock por kardex y faltante.
    Requiere tablas: receta(producto_id, insumo_id, cantidad), insumo, kardex.
    """
    with connection.cursor() as cur:
        cur.execute("""
            SELECT
                r.insumo_id                                AS insumo_id,
                i.nombre                                   AS insumo,
                i.unidad_medida                            AS um,
                i.cantidad_disponible                      AS stock_db,
                -- Stock por movimientos: entradas - salidas ± ajustes
                COALESCE(SUM(
                    CASE
                        WHEN k.tipo = 'ENTRADA' THEN k.cantidad
                        WHEN k.tipo = 'SALIDA'  THEN -k.cantidad
                        WHEN k.tipo = 'AJUSTE'  THEN k.cantidad
                        ELSE 0
                    END
                ), 0)                                       AS stock_kardex,
                (r.cantidad * %s)                          AS necesario
            FROM receta r
            JOIN insumo i   ON i.id = r.insumo_id
            LEFT JOIN kardex k ON k.insumo_id = r.insumo_id
            WHERE r.producto_id = %s
            GROUP BY r.insumo_id, i.nombre, i.unidad_medida, i.cantidad_disponible, r.cantidad
            ORDER BY i.nombre
        """, [cantidad_producto, producto_id])

        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    # Calcula faltante (usa el mejor stock disponible)
    for r in rows:
        stock_ref = r["stock_kardex"] if r["stock_kardex"] is not None else 0
        if not stock_ref:  # si kardex aún no tiene movimientos, usa el stock_db
            stock_ref = r["stock_db"] or 0
        r["faltante"] = max(Decimal(r["necesario"]) - Decimal(stock_ref), Decimal("0"))

    return rows


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models_db import Pedido

@login_required
def pedidos_para_produccion(request):
    pedidos = (
        Pedido.objects
        .filter(estado='CONFIRMADO')
        .select_related('cliente')
        .order_by('fecha_entrega_programada', 'created_at')  # <- aquí el cambio
    )
    return render(request, 'produccion/pedidos_para_produccion.html', {'pedidos': pedidos})

from decimal import Decimal
@login_required
def gestionar_produccion(request, pedido_id: int):
    """
    Muestra los ítems del pedido y permite cambiar a EN_PRODUCCION / LISTO_ENTREGA
    """
    pedido = get_object_or_404(Pedido, id=pedido_id)
    # Detalles del pedido
    items = (DetallePedido.objects
             .filter(pedido_id=pedido_id)
             .select_related('producto', 'sabor')
             .order_by('producto_id', 'sabor_id'))

    # Verificar insumos por cada ítem (agregamos un atributo calculado)
    verificados = []
    for it in items:
        checks = _insumos_necesarios(it.producto_id, it.cantidad)
        ok = all(Decimal(ch.get("faltante", 0)) <= 0 for ch in checks)
        verificados.append((it, ok, checks))

    # Acciones de estado
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'en_produccion' and pedido.estado == 'CONFIRMADO':
            Pedido.objects.filter(id=pedido.id).update(estado='EN_PRODUCCION')
            messages.success(request, 'Pedido pasado a EN_PRODUCCION.')
            return redirect('gestionar_produccion', pedido_id=pedido.id)

        if accion == 'listo_entrega' and pedido.estado in ['CONFIRMADO', 'EN_PRODUCCION']:
            # Requiere que TODOS los ítems estén OK
            if all(ok for _, ok, _ in verificados):
                Pedido.objects.filter(id=pedido.id).update(estado='LISTO_ENTREGA')
                messages.success(request, 'Pedido marcado como LISTO_ENTREGA.')
                return redirect('gestionar_produccion', pedido_id=pedido.id)
            else:
                messages.error(request, 'Faltan insumos para al menos un ítem.')

    return render(request, 'produccion/gestionar_produccion.html', {
        'pedido': pedido,
        'verificados': verificados,  # [(detalle, ok_bool, [(insumo_id,nombre,req,stock,ok), ...])]
    })

# accounts/views_produccion.py
from decimal import Decimal
from django.contrib import messages
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, redirect

@login_required
def producir_item(request, pedido_id: int, producto_id: int, sabor_id: int):
    """
    Descuenta del stock (kardex SALIDA/CONSUMO) los insumos requeridos
    para el ítem (producto_id, sabor_id) del pedido indicado.
    Soporta tanto 'checks' como lista de tuplas o de diccionarios.
    """
    # 1) Obtener el item (único por pedido/producto/sabor)
    item = get_object_or_404(
        DetallePedido,
        pedido_id=pedido_id,
        producto_id=producto_id,
        sabor_id=sabor_id,
    )

    # 2) Calcular insumos necesarios (ya incluye la cantidad del item)
    checks = _insumos_necesarios(producto_id, item.cantidad)

    # 3) Si falta algo, no descontamos
    def hay_faltante(c):
        if isinstance(c, dict):
            # si viene como dict (nuestro formato nuevo)
            return Decimal(str(c.get("faltante", "0"))) > 0
        else:
            # si viene como tupla: (id, nombre, [um], requerido, stock, ok, ...)
            # tomamos requerido y stock de posiciones seguras
            try:
                requerido = Decimal(str(c[2]))  # si el formato era (id, nombre, requerido, stock, ok)
                stock = Decimal(str(c[3]))
            except Exception:
                # formato extendido: (id, nombre, um, requerido, stock, ok, ...)
                requerido = Decimal(str(c[3]))
                stock = Decimal(str(c[4]))
            return (requerido - stock) > 0

    if any(hay_faltante(c) for c in checks):
        messages.error(request, "No se puede descontar: hay insumos con faltantes.")
        return redirect("gestionar_produccion", pedido_id=pedido_id)

    # 4) Descontar en una transacción
    with transaction.atomic():
        with connection.cursor() as cur:
            for c in checks:
                # Normalizar a (insumo_id, requerido)
                if isinstance(c, dict):
                    # Formato dict
                    insumo_id = c.get("insumo_id")
                    if not insumo_id:
                        # Si no vino el id, buscamos por nombre (último recurso)
                        cur.execute("SELECT id FROM insumo WHERE nombre=%s LIMIT 1", [c["insumo"]])
                        row = cur.fetchone()
                        if not row:
                            raise ValueError(f"No existe insumo '{c['insumo']}' en la base de datos.")
                        insumo_id = row[0]
                    requerido = Decimal(str(c["necesario"]))
                else:
                    # Formato tupla
                    # Puede ser (id, nombre, requerido, stock, ok)  -> len>=5
                    # o (id, nombre, um, requerido, stock, ok, ...) -> len>=6
                    if len(c) >= 5:
                        try:
                            insumo_id, _nombre, requerido, _stock, _ok = c[:5]
                            requerido = Decimal(str(requerido))
                        except Exception:
                            # Versión con 'um'
                            insumo_id, _nombre, _um, requerido, _stock, *_rest = c
                            requerido = Decimal(str(requerido))
                    else:
                        raise ValueError("Formato de 'checks' no reconocido.")

                # Insertar movimiento en kardex (SALIDA / CONSUMO)
                cur.execute(
                    """
                    INSERT INTO kardex(insumo_id, fecha, tipo, motivo, cantidad, observacion)
                    VALUES (%s, NOW(), 'SALIDA', 'CONSUMO', %s, %s)
                    """,
                    [
                        insumo_id,
                        requerido,
                        f"Pedido {pedido_id} – prod {producto_id}/{sabor_id} x{item.cantidad}",
                    ],
                )

                # Actualizar stock del insumo
                cur.execute(
                    "UPDATE insumo SET cantidad_disponible = cantidad_disponible - %s WHERE id = %s",
                    [requerido, insumo_id],
                )

    messages.success(request, "Insumos descontados correctamente.")
    return redirect("gestionar_produccion", pedido_id=pedido_id)
