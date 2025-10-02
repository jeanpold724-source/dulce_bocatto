# accounts/forms_profile.py
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Nombre", max_length=150, required=False)
    last_name = forms.CharField(label="Apellido", max_length=150, required=False)
    # Si tu modelo User tiene un campo extra (ej. phone), aquí lo agregas:
    # phone = forms.CharField(label="Teléfono", max_length=20, required=False)

    class Meta:
        model = User
        fields = ["first_name", "last_name"]  # añade "phone" si tu User lo tiene
