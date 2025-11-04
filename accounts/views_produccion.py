from django.contrib.auth.decorators import login_required, permission_required
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages


from .models_db import Pedido, DetallePedido, Producto, Sabor, Insumo, Kardex
from .models_recetas import Receta


# Util: verificar stock de insumos para un producto
def _insumos_necesarios(producto_id, cantidad):
    """
    Devuelve lista de (insumo_id, nombre, requerido, stock_actual, ok_bool)
    requerido = sum(receta.cantidad) * cantidad
    stock_actual = sum(kardex) (entradas - salidas)
    """
    with connection.cursor() as cur:
        # cantidades por receta (ya están en unidades base)
        cur.execute("""
            SELECT r.insumo_id, i.nombre, SUM(r.cantidad) AS por_unidad
            FROM receta r
            JOIN insumo i ON i.id = r.insumo_id
            WHERE r.producto_id = %s
            GROUP BY r.insumo_id, i.nombre
        """, [producto_id])
        filas = cur.fetchall()

    resultados = []
    for insumo_id, nombre, por_unidad in filas:
        requerido = (por_unidad or 0) * cantidad
        # stock de kardex
        with connection.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(entrada - salida), 0)
                FROM kardex WHERE insumo_id = %s
            """, [insumo_id])
            stock = cur.fetchone()[0] or 0
        resultados.append((insumo_id, nombre, float(requerido), float(stock), stock >= requerido))
    return resultados

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
        ok = all(c[-1] for c in checks)  # todos con stock suficiente
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

@login_required
@transaction.atomic
def producir_item(request, pedido_id: int, producto_id: int, sabor_id: int):
    """
    Descuenta insumos en Kardex para un ítem específico del pedido.
    (Movimiento de salida por la cantidad del ítem)
    """
    item = get_object_or_404(
        DetallePedido,
        pedido_id=pedido_id, producto_id=producto_id, sabor_id=sabor_id
    )
    # Verificación rápida
    checks = _insumos_necesarios(producto_id, item.cantidad)
    if not all(ok for *_, ok in checks):
        messages.error(request, 'No hay stock suficiente de insumos.')
        return redirect('gestionar_produccion', pedido_id=pedido_id)

    # Registrar salidas en kardex
    for insumo_id, _nombre, requerido, _stock, _ok in checks:
        Kardex.objects.create(
            insumo_id=insumo_id,
            entrada=0,
            salida=requerido,
            motivo=f'PRODUCCION PEDIDO #{pedido_id}'
        )

    messages.success(request, 'Insumos descontados para el ítem.')
    return redirect('gestionar_produccion', pedido_id=pedido_id)
