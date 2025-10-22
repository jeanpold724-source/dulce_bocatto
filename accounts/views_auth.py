from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import RegistroForm, LoginForm
from .forms_profile import ProfileForm
from .models_db import Usuario, Cliente, Pedido, Bitacora
from .utils import log_event

from django.shortcuts import render  # ya lo tienes arriba

def home_view(request):
    return render(request, "accounts/home.html")



# ---------- Helpers ----------
def ip_from_request(request):
    return request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))


def get_cliente_actual(request):
    """Obtiene o crea el cliente vinculado al usuario autenticado."""
    if not request.user.is_authenticated:
        raise Http404("No autenticado")

    email = (request.user.email or "").strip().lower()
    if not email:
        raise Http404("El usuario no tiene email asignado")

    nombre = (request.user.first_name or request.user.username or email).strip()
    telefono = getattr(request.user, "phone", "")

    with transaction.atomic():
        usuario_base, _ = Usuario.objects.get_or_create(
            email=email,
            defaults={
                "nombre": nombre,
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


# ---------- Login ----------
class CustomLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "accounts/login.html"


# ---------- Registro ----------
def register_view(request):
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if not form.is_valid():
            return render(request, "accounts/register.html", {"form": form})

        user = form.save()
        login(request, user)

        email = (user.email or "").strip().lower()
        nombre = (user.first_name or user.username or email)
        telefono = getattr(user, "phone", "")

        try:
            with transaction.atomic():
                usuario_base, _ = Usuario.objects.get_or_create(
                    email=email,
                    defaults={
                        "nombre": nombre,
                        "hash_password": user.password,
                        "telefono": telefono,
                        "activo": True,
                    },
                )

                Cliente.objects.get_or_create(
                    usuario=usuario_base,
                    defaults={
                        "nombre": usuario_base.nombre,
                        "telefono": usuario_base.telefono,
                        "direccion": "Dirección por defecto",
                    },
                )
        except IntegrityError:
            messages.error(request, "Este correo ya está registrado. Intenta iniciar sesión.")
            return redirect("login")

        try:
            Bitacora.objects.create(
                usuario=usuario_base,
                entidad="Usuario",
                entidad_id=usuario_base.id,
                accion="CREAR",
                ip=ip_from_request(request),
                fecha=timezone.now(),
            )
        except Exception:
            pass

        try:
            log_event(request, "Usuario", usuario_base.id, "CREAR", "Registro")
        except Exception:
            pass

        messages.success(request, "¡Registro completado! Bienvenido a Dulce Bocatto.")
        return redirect("perfil")

    form = RegistroForm()
    return render(request, "accounts/register.html", {"form": form})


# ---------- Perfil ----------
@login_required
def perfil_view(request):
    cliente = get_cliente_actual(request)
    pedidos = Pedido.objects.filter(cliente=cliente).order_by("-created_at")
    gran_total = pedidos.filter(estado="PENDIENTE").aggregate(
        total=Sum("total")
    )["total"] or Decimal("0.00")

    return render(
        request,
        "accounts/perfil.html",
        {"cliente": cliente, "pedidos": pedidos, "gran_total": gran_total},
    )


# ---------- Perfil editar ----------
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
            try:
                log_event(request, "Perfil", user.id, "ACTUALIZAR", "Editar perfil")
            except Exception:
                pass
            messages.success(request, "Perfil actualizado.")
            return redirect("perfil")
    else:
        form = ProfileForm(instance=user)
    return render(request, "accounts/perfil_editar.html", {"form": form})


# ---------- Cambiar contraseña ----------
@login_required
def cambiar_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            try:
                log_event(request, "Perfil", user.id, "ACTUALIZAR", "Cambiar contraseña")
            except Exception:
                pass
            messages.success(request, "Contraseña actualizada correctamente.")
            return redirect("perfil")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "accounts/cambiar_password.html", {"form": form})
