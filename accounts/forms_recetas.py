# accounts/forms_recetas.py
from django import forms
from .models_recetas import Receta
from .models_db import Insumo  # importar desde models_db, no redefinir

class RecipeItemForm(forms.ModelForm):
    class Meta:
        model = Receta
        fields = ['cantidad']
        labels = {'cantidad': 'Cantidad por unidad'}
        widgets = {
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0.001',
                'step': '0.001',
                'placeholder': '0.000',
            })
        }

class AddRecipeItemForm(forms.Form):
    insumo_id = forms.ModelChoiceField(
        queryset=Insumo.objects.none(),  # se setea en la vista
        label='Insumo',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    cantidad = forms.DecimalField(
        min_value=0.001, max_digits=12, decimal_places=3,
        label='Cantidad por unidad',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
