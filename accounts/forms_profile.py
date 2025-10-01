# accounts/forms_profile.py
from django import forms
from django.contrib.auth import get_user_model
User = get_user_model()

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]  # añade "phone" si tu User lo tiene
        labels = {"first_name": "Nombre", "last_name": "Apellido"}
