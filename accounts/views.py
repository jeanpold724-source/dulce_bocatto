from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.timezone import make_aware
from django.views.decorators.http import require_POST

from .forms import RegistroForm, LoginForm
from .models_db import Usuario, Cliente, Sabor, Pedido, Bitacora


def get_cliente_actual(request):
    """Obtiene el cliente actual a partir del usuario autenticado."""
    usuario_base = get_object_or_404(Usuario, email=request.user.email)
    return get_object_or_404(Cliente, usuario=usuario_base)

def ip_from_request(request):
    """Obtiene la dirección IP del cliente a partir del request."""
    return request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))

class CustomLoginView(LoginView):
    """Vista de inicio de sesión personalizada."""
    authentication_form = LoginForm
    template_name = "accounts/login.html"

def home_view(request):
    """Muestra la página de inicio."""
    return render(request, "accounts/home.html")

def catalogo_view(request):
    """Muestra el catálogo de sabores de galletas."""
    sabores = Sabor.objects.filter(activo=1).order_by("nombre")
    return render(request, "accounts/catalogo.html", {"sabores": sabores})

def register_view(request):
    """Gestiona el registro de nuevos usuarios."""
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

            # Crear Usuario y Cliente en la base de datos original
            usuario_base = Usuario.objects.create(
                nombre=user.first_name,
                email=user.email,
                hash_password=user.password,  # Considerar un mejor manejo de contraseñas
                telefono=getattr(user, "phone", ""),
                activo=True,
            )
            Cliente.objects.create(
                usuario=usuario_base,
                nombre=usuario_base.nombre,
                telefono=usuario_base.telefono,
                direccion="Dirección por defecto",
            )

            messages.success(request, "¡Registro completado! Bienvenido a Dulce Bocatto.")
            return redirect("perfil")
    else:
        form = RegistroForm()
    return render(request, "accounts/register.html", {"form": form})

@login_required
def perfil_view(request):
    """Muestra el perfil del usuario, incluyendo sus pedidos."""
    cliente = get_cliente_actual(request)
    pedidos = Pedido.objects.filter(cliente=cliente).order_by("-created_at")
    return render(request, "accounts/perfil.html", {"cliente": cliente, "pedidos": pedidos})

@login_required
def crear_pedido(request, sabor_id):
    """Muestra el formulario para crear un pedido y procesa su envío."""
    sabor = get_object_or_404(Sabor, id=sabor_id, activo=1)
    cliente = get_cliente_actual(request)

    if request.method == "POST":
        metodo = request.POST.get("metodo_envio", "local")
        direccion = request.POST.get("direccion_entrega", "")
        fecha_str = request.POST.get("fecha_entrega_programada", "")
        observaciones = request.POST.get("observaciones", "")

        fecha_entrega = None
        if fecha_str:
            try:
                fecha_entrega = make_aware(datetime.strptime(fecha_str, "%Y-%m-%dT%H:%M"))
            except (ValueError, TypeError):
                pass  # Mantener como None si hay error

        # Lógica de costos
        precio_base = Decimal("10.00")
        costo_envio = Decimal("5.00") if metodo == "delivery" else Decimal("0.00")
        total = precio_base + costo_envio

        pedido = Pedido.objects.create(
            cliente=cliente,
            sabor=sabor,
            estado="PENDIENTE",
            metodo_envio=metodo,
            costo_envio=costo_envio,
            direccion_entrega=direccion,
            total=total,
            observaciones=observaciones,
            created_at=timezone.now(),
            fecha_entrega_programada=fecha_entrega,
        )

        Bitacora.objects.create(
            usuario=cliente.usuario,
            entidad="Pedido",
            entidad_id=pedido.id,
            accion="Crear Pedido",
            ip=ip_from_request(request),
            fecha=timezone.now(),
        )

        messages.success(request, "Pedido creado con éxito. Por favor, confírmalo en tu perfil.")
        return redirect("perfil")

    return render(request, "accounts/crear_pedido.html", {"sabor": sabor})

@login_required
@require_POST
def confirmar_pedido(request, pedido_id):
    """Confirma un pedido pendiente."""
    cliente = get_cliente_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente, estado="PENDIENTE")

    pedido.estado = "CONFIRMADO"
    pedido.save()

    Bitacora.objects.create(
        usuario=cliente.usuario,
        entidad="Pedido",
        entidad_id=pedido.id,
        accion="Confirmar Pedido",
        ip=ip_from_request(request),
        fecha=timezone.now(),
    )

    messages.success(request, "Tu pedido ha sido confirmado.")
    return redirect("perfil")

@login_required
@require_POST
def cancelar_pedido(request, pedido_id):
    """Cancela un pedido pendiente."""
    cliente = get_cliente_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente, estado="PENDIENTE")

    pedido.estado = "CANCELADO"
    pedido.save()

    Bitacora.objects.create(
        usuario=cliente.usuario,
        entidad="Pedido",
        entidad_id=pedido.id,
        accion="Cancelar Pedido",
        ip=ip_from_request(request),
        fecha=timezone.now(),
    )

    messages.info(request, "Tu pedido ha sido cancelado.")
    return redirect("perfil")

@login_required
def bitacora_view(request):
    """Muestra la bitácora de eventos del sistema."""
    logs = Bitacora.objects.all().order_by("-fecha")
    return render(request, "accounts/bitacora.html", {"logs": logs})
