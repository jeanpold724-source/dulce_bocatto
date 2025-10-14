from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.db import transaction, connection
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.timezone import make_aware
from django.views.decorators.http import require_POST

from .forms import RegistroForm, LoginForm
from .forms_profile import ProfileForm
from .models_db import Usuario, Cliente, Sabor, Pedido, Bitacora, Producto
from .utils import log_event

from .permissions import requiere_permiso


# ---------- Helpers ----------
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


def get_precio_unit():
    """Precio único por galleta, configurable por env; default 10 Bs."""
    return Decimal(str(getattr(settings, "COOKIE_UNIT_PRICE_BS", 10)))


# ---------- Auth / páginas simples ----------
class CustomLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "accounts/login.html"


def home_view(request):
    return render(request, "accounts/home.html")


# ---------- Catálogo ----------
def catalogo_view(request):
    sabores = Sabor.objects.filter(activo=1).order_by("nombre")
    return render(
        request,
        "accounts/catalogo.html",
        {"sabores": sabores, "precio": get_precio_unit()},
    )


# ---------- Registro ----------
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
            # Bitácora/log_event en clave segura
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
            return redirect("perfil")
    else:
        form = RegistroForm()
    return render(request, "accounts/register.html", {"form": form})


# ---------- Perfil ----------
@login_required
def perfil_view(request):
    cliente = get_cliente_actual(request)
    pedidos = Pedido.objects.filter(cliente=cliente).order_by("-created_at")

    # Gran total de pedidos PENDIENTES (ajusta si quieres incluir CONFIRMADO)
    gran_total = pedidos.filter(estado="PENDIENTE").aggregate(
        total=Sum("total")
    )["total"] or Decimal("0.00")

    return render(
        request,
        "accounts/perfil.html",
        {"cliente": cliente, "pedidos": pedidos, "gran_total": gran_total},
    )


# ---------- Crear pedido (con cantidad y detalle) ----------
@login_required
def crear_pedido(request, sabor_id):
    sabor = get_object_or_404(Sabor, id=sabor_id, activo=1)
    cliente = get_cliente_actual(request)

    # --- GET: mostrar la pantalla intermedia con cantidad y precio ---
    if request.method == "GET":
        # viene del catálogo como ?cantidad=N (si no, 1)
        qty_str = request.GET.get("cantidad", "1")
        try:
            cantidad = max(1, min(int(qty_str), 99))
        except ValueError:
            cantidad = 1

        return render(
            request,
            "accounts/crear_pedido.html",
            {
                "sabor": sabor,
                "cantidad": cantidad,
                "precio_unit": get_precio_unit(),  # <-- importante
            },
        )

    # --- POST: crear el pedido y el detalle ---
    # cantidad desde el formulario intermedio
    qty_str = request.POST.get("cantidad", "1")
    try:
        cantidad = max(1, min(int(qty_str), 99))
    except ValueError:
        cantidad = 1

    metodo = request.POST.get("metodo_envio", "local")  # "local" / "delivery"
    direccion = request.POST.get("direccion_entrega", "")
    fecha_str = request.POST.get("fecha_entrega_programada", "")
    observaciones = request.POST.get("observaciones", "")

    fecha_entrega = None
    if fecha_str:
        try:
            fecha_entrega = make_aware(datetime.strptime(fecha_str, "%Y-%m-%dT%H:%M"))
        except (ValueError, TypeError):
            fecha_entrega = None

    precio_unit = get_precio_unit()
    costo_envio = Decimal("5.00") if metodo.lower() == "delivery" else Decimal("0.00")

    # 1) Pedido
    pedido = Pedido.objects.create(
        cliente=cliente,
        estado="PENDIENTE",
        metodo_envio=metodo,
        costo_envio=costo_envio,
        direccion_entrega=direccion,
        total=Decimal("0.00"),
        observaciones=observaciones,
        created_at=timezone.now(),
        fecha_entrega_programada=fecha_entrega,
    )

    # 2) Producto base
    producto = Producto.objects.filter(nombre__iexact="Galleta").first() or Producto.objects.first()
    if not producto:
        messages.error(request, "No hay productos definidos. Crea 'Galleta' en la base.")
        return redirect("catalogo")

    # 3) Detalle (por SQL porque la tabla usa clave compuesta)
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO detalle_pedido (pedido_id, producto_id, sabor_id, cantidad, precio_unitario)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [pedido.id, producto.id, sabor.id, cantidad, precio_unit],
        )

    # 4) Total = suma subtotales + envío
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(sub_total), 0)
            FROM detalle_pedido
            WHERE pedido_id = %s
            """,
            [pedido.id],
        )
        subtotal = Decimal(cur.fetchone()[0] or 0)

    pedido.total = subtotal + costo_envio
    pedido.save(update_fields=["total"])

    # Bitácora (a prueba de fallos)
    try:
        Bitacora.objects.create(
            usuario=cliente.usuario,
            entidad="Pedido",
            entidad_id=pedido.id,
            accion="CREAR",
            ip=ip_from_request(request),
            fecha=timezone.now(),
        )
    except Exception:
        pass
    try:
        log_event(request, "Pedido", pedido.id, "CREAR", f"{cantidad} x {sabor.nombre}")
    except Exception:
        pass

    messages.success(
        request,
        f"Añadido: {cantidad} × {sabor.nombre}. "
        f"Subtotal Bs {subtotal:.2f} | Envío Bs {costo_envio:.2f} | Total Bs {(subtotal + costo_envio):.2f}"
    )
    return redirect("perfil")


# ---------- Confirmar / Cancelar ----------
@login_required
@require_POST
def confirmar_pedido(request, pedido_id):
    cliente = get_cliente_actual(request)
    pedido = get_object_or_404(
        Pedido, id=pedido_id, cliente=cliente, estado="PENDIENTE"
    )
    pedido.estado = "CONFIRMADO"
    pedido.save(update_fields=["estado"])

    try:
        Bitacora.objects.create(
            usuario=cliente.usuario,
            entidad="Pedido",
            entidad_id=pedido.id,
            accion="ACTUALIZAR",
            ip=ip_from_request(request),
            fecha=timezone.now(),
        )
    except Exception:
        pass
    try:
        log_event(request, "Pedido", pedido.id, "ACTUALIZAR", "Confirmado")
    except Exception:
        pass

    messages.success(request, "Tu pedido ha sido confirmado.")
    return redirect("perfil")


@login_required
@require_POST
def cancelar_pedido(request, pedido_id):
    cliente = get_cliente_actual(request)
    pedido = get_object_or_404(
        Pedido, id=pedido_id, cliente=cliente, estado="PENDIENTE"
    )
    pedido.estado = "CANCELADO"
    pedido.save(update_fields=["estado"])

    try:
        Bitacora.objects.create(
            usuario=cliente.usuario,
            entidad="Pedido",
            entidad_id=pedido.id,
            accion="ACTUALIZAR",  # o "BORRAR" si tratas cancelación como baja
            ip=ip_from_request(request),
            fecha=timezone.now(),
        )
    except Exception:
        pass
    try:
        log_event(request, "Pedido", pedido.id, "ACTUALIZAR", "Cancelado")
    except Exception:
        pass

    messages.info(request, "Tu pedido ha sido cancelado.")
    return redirect("perfil")


# ---------- Bitácora ----------
@login_required
@requiere_permiso("permisos.ver")   # <--- ESTA LÍNEA ES LA CLAVE
def bitacora_view(request):
    logs = Bitacora.objects.all().order_by("-fecha")
    return render(request, "accounts/bitacora.html", {"logs": logs})



# ---------- Perfil: editar / password ----------
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


# ============================================
# CU04 — API: gestionar roles y permisos
# ============================================

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models_db import Usuario, Rol, Permiso, UsuarioRol, RolPermiso
from .serializers import (
    PermisoSerializer,
    RolListSerializer, RolWriteSerializer,
    UsuarioListSerializer, UsuarioRolesWriteSerializer,
)

# --- Permisos (solo lectura)
class PermisoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Permiso.objects.all().order_by("codigo")
    serializer_class = PermisoSerializer

# --- Roles (CRUD + no borrar si está en uso)
class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.all().order_by("nombre")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RolWriteSerializer
        return RolListSerializer

    def destroy(self, request, *args, **kwargs):
        rol = self.get_object()
        if UsuarioRol.objects.filter(rol=rol).exists():
            return Response(
                {"detail": "No se puede eliminar el rol porque está asignado a usuarios."},
                status=status.HTTP_409_CONFLICT,
            )
        RolPermiso.objects.filter(rol=rol).delete()
        return super().destroy(request, *args, **kwargs)

# --- Usuarios (listado + asignar roles)
class UsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Usuario.objects.all().order_by("nombre")
    serializer_class = UsuarioListSerializer

    @action(detail=True, methods=["post"])
    def asignar_roles(self, request, pk=None):
        usuario = self.get_object()
        ser = UsuarioRolesWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        roles_ids = ser.validated_data["roles"]

        UsuarioRol.objects.filter(usuario=usuario).delete()
        UsuarioRol.objects.bulk_create(
            [UsuarioRol(usuario=usuario, rol_id=r) for r in roles_ids],
            ignore_conflicts=True,
        )
        return Response({"ok": True, "roles": roles_ids})




from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from .permissions import requiere_permiso
from .forms_proveedor import ProveedorForm
from .models_db import Proveedor

@login_required
@requiere_permiso("PROVEEDOR_READ")
def proveedores_list(request):
    q = request.GET.get("q", "").strip()
    qs = Proveedor.objects.all().order_by("nombre")
    if q:
        qs = qs.filter(nombre__icontains=q)
    page = Paginator(qs, 10).get_page(request.GET.get("page"))
    return render(request, "accounts/proveedores_list.html", {"page": page, "q": q})

@login_required
@requiere_permiso("PROVEEDOR_WRITE")
def proveedor_create(request):
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            prov = form.save()
            try:
                log_event(request, "Proveedor", prov.id, "CREAR", prov.nombre)
            except Exception:
                pass
            messages.success(request, "Proveedor creado.")
            return redirect("proveedores_list")
    else:
        form = ProveedorForm()
    return render(request, "accounts/proveedor_form.html", {"form": form, "modo": "Crear"})

@login_required
@requiere_permiso("PROVEEDOR_WRITE")
def proveedor_update(request, pk):
    prov = get_object_or_404(Proveedor, pk=pk)
    if request.method == "POST":
        form = ProveedorForm(request.POST, instance=prov)
        if form.is_valid():
            prov = form.save()
            try:
                log_event(request, "Proveedor", prov.id, "ACTUALIZAR", prov.nombre)
            except Exception:
                pass
            messages.success(request, "Proveedor actualizado.")
            return redirect("proveedores_list")
    else:
        form = ProveedorForm(instance=prov)
    return render(request, "accounts/proveedor_form.html", {"form": form, "modo": "Editar"})

@login_required
@requiere_permiso("PROVEEDOR_WRITE")
def proveedor_delete(request, pk):
    prov = get_object_or_404(Proveedor, pk=pk)
    if request.method == "POST":
        nombre = prov.nombre
        prov.delete()
        try:
            log_event(request, "Proveedor", pk, "BORRAR", nombre)
        except Exception:
            pass
        messages.info(request, "Proveedor eliminado.")
        return redirect("proveedores_list")
    return render(request, "accounts/proveedor_confirm_delete.html", {"prov": prov})
