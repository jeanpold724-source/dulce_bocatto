from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

class RegistroForm(UserCreationForm):
    email = forms.EmailField(label='Correo electrónico')
    phone = forms.CharField(label='Teléfono', required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'password1', 'password2']

class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Correo electrónico')


from .models_db import Insumo

class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ["nombre", "unidad_medida", "cantidad_disponible"]
