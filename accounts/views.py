from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from .forms import RegistroForm, LoginForm
from accounts.models import User
from accounts.models_db import Usuario, Cliente
from django.contrib.auth.decorators import login_required
from accounts.models_db import Sabor
from django.shortcuts import render, redirect, get_object_or_404
from accounts.models_db import Sabor, Pedido, Cliente
from django.utils import timezone
from decimal import Decimal
from django.utils.timezone import make_aware
from datetime import datetime

from accounts.models_db import Cliente, Pedido


from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from accounts.models_db import Pedido

from accounts.models_db import Bitacora
from django.utils import timezone










@login_required
def perfil_view(request):
    try:
        cliente = Cliente.objects.get(nombre=request.user.first_name)
    except Cliente.DoesNotExist:
        return render(request, 'accounts/error.html', {'mensaje': 'Cliente no encontrado'})

    pedidos = Pedido.objects.filter(cliente=cliente).order_by('-created_at')

    return render(request, 'accounts/perfil.html', {
        'cliente': cliente,
        'pedidos': pedidos,
        'confirmado': request.GET.get('confirmado') == '1'
    })


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

def catalogo_view(request):
    sabores = Sabor.objects.filter(activo=True)
    return render(request, 'accounts/catalogo.html', {'sabores': sabores})

@login_required
def crear_pedido(request, sabor_id):
    sabor = get_object_or_404(Sabor, id=sabor_id)

    try:
        cliente = Cliente.objects.get(nombre=request.user.first_name)
    except Cliente.DoesNotExist:
        return render(request, 'accounts/error.html', {'mensaje': 'Cliente no encontrado'})

    if request.method == 'POST':
        metodo = request.POST.get('metodo_envio')
        direccion = request.POST.get('direccion_entrega')
        fecha_str = request.POST.get('fecha_entrega_programada')
        observaciones = request.POST.get('observaciones')

        # Convertir fecha con zona horaria
        fecha = make_aware(datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M'))

        precio_base = Decimal('10.00')
        costo_envio = Decimal('5.00') if metodo == 'delivery' else Decimal('0.00')
        total = precio_base + costo_envio

        Pedido.objects.create(
            cliente=cliente,
            estado='PENDIENTE',
            metodo_envio=metodo,
            costo_envio=costo_envio,
            direccion_entrega=direccion,
            total=total,
            observaciones=observaciones,
            created_at=timezone.now(),
            fecha_entrega_programada=fecha
        )
        return redirect('perfil')

    return render(request, 'accounts/crear_pedido.html', {'sabor': sabor})



@require_POST
@login_required
def cancelar_pedido(request, pedido_id):
    try:
        pedido = Pedido.objects.get(id=pedido_id)
        if pedido.estado == 'PENDIENTE':
            pedido.estado = 'CANCELADO'
            pedido.save()
            cliente = Cliente.objects.get(nombre=request.user.first_name)
            usuario = cliente.usuario
            Bitacora.objects.create(
                usuario=usuario,
                entidad='Pedido',
                entidad_id=pedido.id,
                accion='Cancelar',
                ip=request.META.get('REMOTE_ADDR'),
                fecha=timezone.now()
           )

    except Pedido.DoesNotExist:
        pass
    return redirect('perfil')



@login_required
def bitacora_view(request):
    logs = Bitacora.objects.all().order_by('-fecha')
    return render(request, 'accounts/bitacora.html', {'logs': logs})