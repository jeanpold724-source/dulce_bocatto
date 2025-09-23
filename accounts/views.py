from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from .forms import RegistroForm, LoginForm

from accounts.models import User
from accounts.models_db import Usuario, Cliente

def register_view(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

            # Crear Usuario en la base original
            usuario_base = Usuario.objects.create(
                nombre=user.first_name,
                email=user.email,
                hash_password=user.password,  # opcional: encriptar si querés
                telefono=user.phone,
                activo=True
            )

            # Crear Cliente vinculado al nuevo Usuario
            Cliente.objects.create(
                usuario=usuario_base,
                nombre=usuario_base.nombre,
                telefono=usuario_base.telefono,
                direccion='Dirección por defecto'
            )

            return redirect('/')
    else:
        form = RegistroForm()
    return render(request, 'accounts/register.html', {'form': form})

class CustomLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'accounts/login.html'

def home_view(request):
    return HttpResponse("<h1>Bienvenido a Dulce Bocatto</h1><p>Estás en la página principal.</p>")