from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from .forms import RegistroForm, LoginForm

def register_view(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('/')
    else:
        form = RegistroForm()
    return render(request, 'accounts/register.html', {'form': form})

class CustomLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'accounts/login.html'


from django.http import HttpResponse

def home_view(request):
    return HttpResponse("<h1>Bienvenido a Dulce Bocatto</h1><p>Estás en la página principal.</p>")