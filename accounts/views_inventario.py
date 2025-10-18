# accounts/views_inventario.py
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .permissions import requiere_permiso
from .models_db import Insumo, Kardex
from .forms_inventario import MovimientoInventarioForm

@login_required
@requiere_permiso("INVENTARIO_WRITE")
def movimiento_crear(request):
    form = MovimientoInventarioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        insumo = form.cleaned_data["insumo"]
        tipo = form.cleaned_data["tipo"]
        motivo = form.cleaned_data["motivo"]
        cantidad = Decimal(form.cleaned_data["cantidad"])
        observacion = (form.cleaned_data.get("observacion") or "").strip()
        fecha = form.get_fecha()

        with transaction.atomic():
            obj = Insumo.objects.select_for_update().get(pk=insumo.pk)

            if tipo == "ENTRADA":
                Insumo.objects.filter(pk=obj.pk).update(
                    cantidad_disponible=F("cantidad_disponible") + cantidad
                )
            elif tipo == "SALIDA":
                # si quieres permitir negativo, elimina este if:
                if obj.cantidad_disponible - cantidad < 0:
                    messages.error(request, "Stock insuficiente.")
                    return render(request, "accounts/movimiento_form.html", {"form": form})
                Insumo.objects.filter(pk=obj.pk).update(
                    cantidad_disponible=F("cantidad_disponible") - cantidad
                )
            else:  # AJUSTE: la cantidad es delta (+/-)
                Insumo.objects.filter(pk=obj.pk).update(
                    cantidad_disponible=F("cantidad_disponible") + cantidad
                )

            Kardex.objects.create(
                insumo=obj,
                fecha=fecha,
                tipo=tipo,
                motivo=motivo,
                cantidad=cantidad,
                observacion=observacion[:200] or None,
            )

        messages.success(request, "Movimiento registrado.")
        return redirect("kardex_list")

    return render(request, "accounts/movimiento_form.html", {"form": form})


@login_required
@requiere_permiso("INVENTARIO_READ")
def kardex_list(request):
    qs = Kardex.objects.select_related("insumo").order_by("-fecha", "-id")
    insumo_id = request.GET.get("insumo")
    if insumo_id:
        qs = qs.filter(insumo_id=insumo_id)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    insumos = Insumo.objects.all().order_by("nombre")
    return render(
        request, "accounts/kardex_list.html",
        {"page": page, "insumos": insumos, "insumo_id": insumo_id}
    )


@login_required
@requiere_permiso("INVENTARIO_READ")
def kardex_por_insumo(request, pk: int):
    insumo = get_object_or_404(Insumo, pk=pk)
    page = Paginator(
        Kardex.objects.filter(insumo=insumo).order_by("-fecha", "-id"),
        20
    ).get_page(request.GET.get("page"))
    return render(
        request, "accounts/kardex_por_insumo.html",
        {"insumo": insumo, "page": page}
    )
