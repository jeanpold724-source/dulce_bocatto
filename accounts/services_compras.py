# accounts/services_compras.py
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models_db import Compra, CompraDetalle, Insumo, Kardex

@transaction.atomic
def recepcionar_compra(compra_id: int) -> int:
    """
    Marca la compra como recepcionada, suma stock por cada detalle,
    y escribe movimientos ENTRADA/COMPRA en kardex.
    Devuelve la cantidad de líneas procesadas.
    """
    compra = Compra.objects.select_for_update().get(pk=compra_id)
    if getattr(compra, "recepcionada", 0):
        return 0

    detalles = list(CompraDetalle.objects.filter(compra_id=compra.id))
    if not detalles:
        return 0

    # Recalcular total si es necesario
    if getattr(compra, "total", None) in (None, 0):
        total = sum((d.cantidad or 0) * (d.costo_unitario or 0) for d in detalles)
        Compra.objects.filter(pk=compra.id).update(total=total)

    movs = 0
    for d in detalles:
        ins = Insumo.objects.select_for_update().get(pk=d.insumo_id)
        # Sumar stock
        Insumo.objects.filter(pk=ins.pk).update(
            cantidad_disponible=F("cantidad_disponible") + d.cantidad
        )
        # Kardex
        Kardex.objects.create(
            insumo=ins,
            fecha=timezone.now(),
            tipo="ENTRADA",
            motivo="COMPRA",
            cantidad=d.cantidad,
            observacion=f"Compra #{compra.id}"
        )
        movs += 1

    Compra.objects.filter(pk=compra.id).update(
        recepcionada=1, fecha_recepcion=timezone.now()
    )
    return movs
