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
from .models import User  # si no lo usas, puedes quitar esta línea
from .models_db import Usuario, Cliente, Sabor, Pedido, Bitacora

from django.http import HttpResponse



# =======================
# Helpers
# =======================
def get_cliente_actual(request):
    """
    Resuelve el Cliente usando el email del usuario autenticado.
    Evita colisiones por nombre.
    """
    usuario_base = get_object_or_404(Usuario, email=request.user.email)
    return get_object_or_404(Cliente, usuario=usuario_base)


def ip_from_request(request):
    return request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))


# =======================
# Auth / públicas
# =======================
class CustomLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "accounts/login.html"


def home_view(request):
    return render(request, "accounts/home.html")



def catalogo_view(request):
    # Si "activo" es TINYINT(1) en MySQL, usar 1; si es boolean, True.
    sabores = Sabor.objects.filter(activo=1).order_by("nombre")
    return render(request, "accounts/catalogo.html", {"sabores": sabores})


def register_view(request):
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

            # Crear Usuario en la base original
            usuario_base = Usuario.objects.create(
                nombre=user.first_name,
                email=user.email,
                hash_password=user.password,  # si la otra BD requiere hashing propio, ajusta aquí
                telefono=getattr(user, "phone", ""),
                activo=True,
            )

            # Crear Cliente vinculado
            Cliente.objects.create(
                usuario=usuario_base,
                nombre=usuario_base.nombre,
                telefono=usuario_base.telefono,
                direccion="Dirección por defecto",
            )

            messages.success(request, "Registro completo. ¡Bienvenido!")
            return redirect("perfil")
    else:
        form = RegistroForm()
    return render(request, "accounts/register.html", {"form": form})


# =======================
# Perfil
# =======================
@login_required
def perfil_view(request):
    try:
        cliente = get_cliente_actual(request)
    except Exception:
        return render(
            request,
            "accounts/error.html",
            {"mensaje": "Cliente no encontrado"},
        )

    pedidos = Pedido.objects.filter(cliente=cliente).order_by("-created_at")
    return render(
        request,
        "accounts/perfil.html",
        {"cliente": cliente, "pedidos": pedidos},
    )


# =======================
# Pedidos
# =======================
@login_required
def crear_pedido(request, sabor_id):
    """
    GET: muestra formulario (si lo usas)
    POST: crea pedido y registra en bitácora
    """
    sabor = get_object_or_404(Sabor, id=sabor_id, activo=1)
    cliente = get_cliente_actual(request)

    if request.method == "POST":
        metodo = request.POST.get("metodo_envio", "local")
        direccion = request.POST.get("direccion_entrega", "")
        fecha_str = request.POST.get("fecha_entrega_programada", "")
        observaciones = request.POST.get("observaciones", "")

        # Fecha programada (opcional)
        fecha = None
        if fecha_str:
            try:
                fecha = make_aware(datetime.strptime(fecha_str, "%Y-%m-%dT%H:%M"))
            except Exception:
                fecha = None

        # Totales (demostrativo)
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
            fecha_entrega_programada=fecha,
        )

        Bitacora.objects.create(
            usuario=cliente.usuario,
            entidad="Pedido",
            entidad_id=pedido.id,
            accion="Crear Pedido",
            ip=ip_from_request(request),
            fecha=timezone.now(),
        )

        messages.success(request, "Pedido creado. Revisa tu perfil para confirmarlo.")
        return redirect("perfil")

    # Si usas un formulario explícito de creación:
    return render(request, "accounts/crear_pedido.html", {"sabor": sabor})


@login_required
@require_POST
def confirmar_pedido(request, pedido_id):
    cliente = get_cliente_actual(request)
    pedido = get_object_or_404(
        Pedido, id=pedido_id, cliente=cliente, estado="PENDIENTE"
    )

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

    messages.success(request, "Pedido confirmado.")
    return redirect("perfil")


@login_required
@require_POST
def cancelar_pedido(request, pedido_id):
    cliente = get_cliente_actual(request)
    pedido = get_object_or_404(
        Pedido, id=pedido_id, cliente=cliente, estado="PENDIENTE"
    )

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

    messages.info(request, "Pedido cancelado.")
    return redirect("perfil")


# =======================
# Bitácora
# =======================
@login_required
def bitacora_view(request):
    # Si quieres filtrar por el usuario actual, cambia a:
    # logs = Bitacora.objects.filter(usuario=get_cliente_actual(request).usuario).order_by('-fecha')
    logs = Bitacora.objects.all().order_by("-fecha")
    return render(request, "accounts/bitacora.html", {"logs": logs})
