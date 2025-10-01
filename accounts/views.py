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

from django.db import transaction
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

from .forms import RegistroForm, LoginForm
from .forms_profile import ProfileForm
from .models_db import Usuario, Cliente, Sabor, Pedido, Bitacora
from .utils import log_event


def get_cliente_actual(request):
    """
    Obtiene (o crea si no existe) el Cliente ligado al usuario autenticado.
    Evita 404 cuando el User de Django no tiene su espejo en tablas legadas.
    """
    if not request.user.is_authenticated:
        raise Http404("No autenticado")

    email = (request.user.email or "").strip().lower()
    if not email:
        raise Http404("El usuario no tiene email asignado")

    nombre = (request.user.first_name or request.user.username or "").strip()
    telefono = getattr(request.user, "phone", "")

    with transaction.atomic():
        usuario_base, _ = Usuario.objects.get_or_create(
            email=email,
            defaults={
                "nombre": nombre or email,
                "hash_password": request.user.password,
                "telefono": telefono,
                "activo": 1,
            },
        )

        cliente, _ = Cliente.objects.get_or_create(
            usuario=usuario_base,
            defaults={
                "nombre": usuario_base.nombre,
                "telefono": usuario_base.telefono,
                "direccion": "Dirección por defecto",
            },
        )

    return cliente


def ip_from_request(request):
    return request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))


class CustomLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "accounts/login.html"


def home_view(request):
    return render(request, "accounts/home.html")


def catalogo_view(request):
    sabores = Sabor.objects.filter(activo=1).order_by("nombre")
    return render(request, "accounts/catalogo.html", {"sabores": sabores})


def register_view(request):
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

            usuario_base = Usuario.objects.create(
                nombre=user.first_name,
                email=user.email,
                hash_password=user.password,
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
            log_event(request, "Usuario", usuario_base.id, "Registro")
            return redirect("perfil")
    else:
        form = RegistroForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def perfil_view(request):
    cliente = get_cliente_actual(request)
    pedidos = Pedido.objects.filter(cliente=cliente).order_by("-created_at")
    return render(request, "accounts/perfil.html", {"cliente": cliente, "pedidos": pedidos})


@login_required
def crear_pedido(request, sabor_id):
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
                pass

        precio_base = Decimal("10.00")
        costo_envio = Decimal("5.00") if metodo == "delivery" else Decimal("0.00")
        total = precio_base + costo_envio

        pedido = Pedido.objects.create(
            cliente=cliente,
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
        log_event(request, "Pedido", pedido.id, "Crear Pedido")

        messages.success(request, "Pedido creado con éxito. Por favor, confírmalo en tu perfil.")
        return redirect("perfil")

    return render(request, "accounts/crear_pedido.html", {"sabor": sabor})


@login_required
@require_POST
def confirmar_pedido(request, pedido_id):
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
    log_event(request, "Pedido", pedido.id, "Confirmar Pedido")

    messages.success(request, "Tu pedido ha sido confirmado.")
    return redirect("perfil")


@login_required
@require_POST
def cancelar_pedido(request, pedido_id):
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
    log_event(request, "Pedido", pedido.id, "Cancelar Pedido")

    messages.info(request, "Tu pedido ha sido cancelado.")
    return redirect("perfil")


@login_required
def bitacora_view(request):
    logs = Bitacora.objects.all().order_by("-fecha")
    return render(request, "accounts/bitacora.html", {"logs": logs})


@login_required
def perfil_editar(request):
    user = request.user
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            try:
                u = Usuario.objects.filter(email=user.email).first()
                if u:
                    u.nombre = user.first_name or u.nombre
                    u.telefono = getattr(user, "phone", u.telefono)
                    u.save()
                c = Cliente.objects.filter(usuario=u).first() if u else None
                if c:
                    c.nombre = u.nombre
                    c.telefono = u.telefono
                    c.save()
            except Exception:
                pass
            log_event(request, "Perfil", user.id, "Actualizar Perfil")
            messages.success(request, "Perfil actualizado.")
            return redirect("perfil")
    else:
        form = ProfileForm(instance=user)
    return render(request, "accounts/perfil_editar.html", {"form": form})


@login_required
def cambiar_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            log_event(request, "Perfil", user.id, "Cambiar Password")
            messages.success(request, "Contraseña actualizada correctamente.")
            return redirect("perfil")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "accounts/cambiar_password.html", {"form": form})
