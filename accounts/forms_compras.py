# accounts/forms_compras.py
from django import forms
from django.forms import inlineformset_factory
from .models_db import Compra, CompraDetalle  # importa tus modelos "reales" (managed=False)

class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = ["proveedor", "fecha"]  # 'total' lo calculamos, no va en el form
        widgets = {
            "fecha": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Para que parsee bien el datetime-local
        self.fields["fecha"].input_formats = ["%Y-%m-%dT%H:%M"]
        if not self.instance.pk:
            self.initial.setdefault("fecha", None)

class CompraDetalleForm(forms.ModelForm):
    class Meta:
        model = CompraDetalle
        fields = ["insumo", "cantidad", "costo_unitario"]
        widgets = {
            "cantidad": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
            "costo_unitario": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

CompraDetalleFormSet = inlineformset_factory(
    Compra, CompraDetalle,
    form=CompraDetalleForm,
    fields=["insumo", "cantidad", "costo_unitario"],
    extra=3, can_delete=True, validate_min=True
)
