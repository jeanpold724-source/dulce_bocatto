# accounts/forms_inventario.py
from django import forms
from django.utils import timezone
from .models_db import Insumo

TIPOS = (("ENTRADA", "Entrada"), ("SALIDA", "Salida"), ("AJUSTE", "Ajuste"))
MOTIVOS = (
    ("COMPRA", "Compra"),
    ("CONSUMO", "Consumo"),
    ("AJUSTE", "Ajuste"),
)

class MovimientoInventarioForm(forms.Form):
    insumo = forms.ModelChoiceField(queryset=Insumo.objects.all())
    tipo = forms.ChoiceField(choices=TIPOS)
    motivo = forms.ChoiceField(choices=MOTIVOS)
    cantidad = forms.DecimalField(min_value=0.001, max_digits=12, decimal_places=3)
    observacion = forms.CharField(required=False, max_length=200)
    fecha = forms.DateTimeField(required=False, help_text="Si no envías, uso la fecha/hora actual.")

    def clean(self):
        data = super().clean()
        insumo = data.get("insumo")
        tipo = data.get("tipo")
        cant = data.get("cantidad")
        if tipo == "SALIDA" and insumo and cant:
            # Si NO quieres stock negativo, valida:
            if insumo.cantidad_disponible - cant < 0:
                raise forms.ValidationError("Stock insuficiente para realizar la salida.")
        return data

    def get_fecha(self):
        return self.cleaned_data["fecha"] or timezone.now()
