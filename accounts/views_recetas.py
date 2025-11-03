# accounts/views_recetas.py (solo cabecera de imports)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError, connection
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models_db import Producto, Insumo      # <- Importa aquí
from .models_recetas import Receta           # <- Y aquí solo Receta
from .forms_recetas import AddRecipeItemForm, RecipeItemForm




def _ultimo_costo_unitario(insumo_id: int) -> float:
    """
    Retorna el costo_unitario más reciente del insumo según compra_detalle/compra.
    Si no hay compras, retorna 0.0
    """
    with connection.cursor() as cur:
        cur.execute("""
            SELECT COALESCE((
                SELECT cd.costo_unitario
                FROM compra_detalle cd
                JOIN compra c ON c.id = cd.compra_id
                WHERE cd.insumo_id = %s
                ORDER BY c.fecha DESC, cd.compra_id DESC
                LIMIT 1
            ), 0)
        """, [insumo_id])
        row = cur.fetchone()
    return float(row[0]) if row else 0.0

@login_required
def recetas_list(request):
    productos_qs = Producto.objects.filter(activo=True).order_by('nombre')
    productos = []
    for p in productos_qs:
        cnt = Receta.objects.filter(producto=p).count()
        productos.append({'id': p.id, 'nombre': p.nombre, 'items': cnt})
    return render(request, 'accounts/recetas_list.html', {'productos': productos})

@login_required
def receta_edit(request, producto_id: int):
    producto = get_object_or_404(Producto, pk=producto_id)

    usados_ids = Receta.objects.filter(producto=producto).values_list('insumo_id', flat=True)
    add_form = AddRecipeItemForm()
    add_form.fields['insumo_id'].queryset = Insumo.objects.exclude(id__in=usados_ids).order_by('nombre')

    # Agregar ítem
    if request.method == 'POST' and 'add_item' in request.POST:
        add_form = AddRecipeItemForm(request.POST)
        add_form.fields['insumo_id'].queryset = Insumo.objects.exclude(id__in=usados_ids).order_by('nombre')
        if add_form.is_valid():
            insumo = add_form.cleaned_data['insumo_id']
            cantidad = add_form.cleaned_data['cantidad']
            try:
                with transaction.atomic():
                    Receta.objects.create(producto=producto, insumo=insumo, cantidad=cantidad)
                messages.success(request, f'Se agregó {insumo.nombre} a la receta.')
                return redirect(reverse('receta_edit', args=[producto.id]))
            except IntegrityError:
                messages.error(request, 'Ese insumo ya está en la receta.')
        else:
            messages.error(request, 'Revisa los datos del nuevo insumo.')

    # Actualizar cantidad
    if request.method == 'POST' and request.POST.get('action') == 'update':
        insumo_id = request.POST.get('receta_id')
        receta_obj = get_object_or_404(Receta, producto=producto, insumo_id=insumo_id)
        form = RecipeItemForm(request.POST, instance=receta_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cantidad actualizada.')
            return redirect(reverse('receta_edit', args=[producto.id]))
        else:
            messages.error(request, 'Cantidad inválida.')

    # Eliminar ítem
    if request.method == 'POST' and request.POST.get('action') == 'delete':
        insumo_id = request.POST.get('receta_id')
        Receta.objects.filter(producto=producto, insumo_id=insumo_id).delete()
        messages.success(request, 'Insumo eliminado de la receta.')
        return redirect(reverse('receta_edit', args=[producto.id]))

    # Grilla
    items = Receta.objects.filter(producto=producto).select_related('insumo').order_by('insumo__nombre')
    row_forms = [(r, RecipeItemForm(instance=r, prefix=str(r.insumo_id))) for r in items]

    # Costo aprox por unidad
    costo_total = 0.0
    for r in items:
        costo_total += float(r.cantidad) * _ultimo_costo_unitario(r.insumo_id)

    ctx = {
        'producto': producto,
        'row_forms': row_forms,
        'add_form': add_form,
        'costo_por_unidad': round(costo_total, 4)
    }
    return render(request, 'accounts/recetas_edit.html', ctx)
