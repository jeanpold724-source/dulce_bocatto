# accounts/views_compras.py
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, ExpressionWrapper, DecimalField, Sum
from django.shortcuts import get_object_or_404, redirect, render

from .permissions import requiere_permiso
from .models_db import Compra, CompraDetalle
from .forms_compras import CompraForm, CompraDetalleFormSet
from .services_compras import recepcionar_compra


@login_required
@requiere_permiso("COMPRA_READ")
def compras_list(request):
    qs = Compra.objects.select_related("proveedor").order_by("-fecha", "-id")
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "accounts/compras_list.html", {"page": page})


@login_required
@requiere_permiso("COMPRA_WRITE")
def compra_crear(request):
    if request.method == "POST":
        form = CompraForm(request.POST)
        formset = CompraDetalleFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                compra = form.save(commit=False)
                compra.total = Decimal("0.00")
                compra.save()

                detalles = formset.save(commit=False)
                for d in detalles:
                    d.compra = compra
                    d.save()

                for d in formset.deleted_objects:
                    d.delete()

                total_calc = (CompraDetalle.objects
                              .filter(compra=compra)
                              .annotate(sub=ExpressionWrapper(
                                  F("cantidad") * F("costo_unitario"),
                                  output_field=DecimalField(max_digits=12, decimal_places=2)))
                              .aggregate(t=Sum("sub"))["t"] or Decimal("0.00"))

                compra.total = total_calc
                compra.save(update_fields=["total"])

            messages.success(request, "Compra creada.")
            return redirect("compra_detalle", compra.id)
    else:
        form = CompraForm()
        formset = CompraDetalleFormSet()

    return render(request, "accounts/compra_form.html", {"form": form, "formset": formset})


@login_required
@requiere_permiso("COMPRA_READ")
def compra_detalle(request, compra_id):
    compra = get_object_or_404(Compra, pk=compra_id)
    detalles = (CompraDetalle.objects
                .filter(compra=compra)
                .annotate(subtotal_calc=ExpressionWrapper(
                    F("cantidad") * F("costo_unitario"),
                    output_field=DecimalField(max_digits=12, decimal_places=2))))
    return render(request, "accounts/compra_detalle.html",
                  {"compra": compra, "detalles": detalles})


@login_required
@requiere_permiso("COMPRA_WRITE")
def compra_recepcionar(request, compra_id):
    movs = recepcionar_compra(compra_id)
    if movs > 0:
        messages.success(request, f"Compra recepcionada. Entradas al Kardex: {movs}.")
    else:
        messages.info(request, "La compra ya estaba recepcionada o no tiene detalles.")
    return redirect("compra_detalle", compra_id=compra_id)


# --- Placeholder CU25 ---
from django.shortcuts import redirect
from django.contrib import messages

def historial_proveedores_placeholder(request):
    messages.info(
        request,
        "CU25 (Historial de compras a proveedores) aún no está implementado. Te llevé a Compras."
    )
    return redirect("compras_list")
