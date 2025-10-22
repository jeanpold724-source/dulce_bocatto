from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, connection, IntegrityError
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models_db import (
    Usuario, Cliente, Sabor, Pedido, Bitacora,
    Producto, Proveedor, Insumo, Rol, Permiso,
    UsuarioRol, RolPermiso, Pago
)
from .utils import log_event
from .permissions import requiere_permiso
from .forms_proveedor import ProveedorForm
from .forms import InsumoForm

# ---------- Catálogo ----------
def catalogo_view(request):
    sabores = Sabor.objects.filter(activo=1).order_by("nombre")
    precio = Decimal(str(getattr(settings, "COOKIE_UNIT_PRICE_BS", 10)))
    return render(
        request,
        "accounts/catalogo.html",
        {"sabores": sabores, "precio": precio},
    )


# ---------- Crear pedido ----------
@login_required
def crear_pedido(request, sabor_id):
    sabor = get_object_or_404(Sabor, id=sabor_id, activo=1)
    from .views_auth import get_cliente_actual
    cliente = get_cliente_actual(request)

    if request.method == "GET":
        cantidad = int(request.GET.get("cantidad", "1") or 1)
        return render(
            request,
            "accounts/crear_pedido.html",
            {"sabor": sabor, "cantidad": cantidad, "precio_unit": Decimal("10.00")},
        )

    cantidad = int(request.POST.get("cantidad", "1") or 1)
    metodo = (request.POST.get("metodo_envio") or "").strip().upper()
    if metodo not in ("RETIRO", "DELIVERY"):
        metodo = "RETIRO"

    direccion = (request.POST.get("direccion_entrega") or "").strip()
    if metodo == "RETIRO":
        direccion = None

    fecha_str = request.POST.get("fecha_entrega_programada", "")
    fecha_entrega = None
    if fecha_str:
        try:
            fecha_entrega = timezone.make_aware(datetime.strptime(fecha_str, "%Y-%m-%dT%H:%M"))
        except Exception:
            pass

    costo_envio = Decimal("5.00") if metodo == "DELIVERY" else Decimal("0.00")
    pedido = Pedido.objects.create(
        cliente=cliente,
        estado="PENDIENTE",
        metodo_envio=metodo,
        costo_envio=costo_envio,
        direccion_entrega=direccion,
        total=Decimal("0.00"),
        created_at=timezone.now(),
        fecha_entrega_programada=fecha_entrega,
    )

    producto = Producto.objects.filter(nombre__iexact="Galleta").first() or Producto.objects.first()
    if not producto:
        messages.error(request, "No hay productos definidos.")
        return redirect("catalogo")

    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO detalle_pedido (pedido_id, producto_id, sabor_id, cantidad, precio_unitario)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [pedido.id, producto.id, sabor.id, cantidad, Decimal("10.00")],
        )

    with connection.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(SUM(sub_total), 0) FROM detalle_pedido WHERE pedido_id=%s",
            [pedido.id],
        )
        subtotal = Decimal(cur.fetchone()[0] or 0)

    pedido.total = subtotal + costo_envio
    pedido.save(update_fields=["total"])

    messages.success(request, "Pedido creado correctamente.")
    return redirect("perfil")


# ---------- Confirmar / Cancelar ----------
@login_required
@require_POST
def confirmar_pedido(request, pedido_id):
    from .views_auth import get_cliente_actual
    cliente = get_cliente_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente, estado="PENDIENTE")
    pedido.estado = "CONFIRMADO"
    pedido.save(update_fields=["estado"])
    messages.success(request, "Tu pedido ha sido confirmado.")
    return redirect("perfil")


@login_required
@require_POST
def cancelar_pedido(request, pedido_id):
    from .views_auth import get_cliente_actual
    cliente = get_cliente_actual(request)
    pedido = get_object_or_404(Pedido, id=pedido_id, cliente=cliente, estado="PENDIENTE")
    pedido.estado = "CANCELADO"
    pedido.save(update_fields=["estado"])
    messages.info(request, "Tu pedido ha sido cancelado.")
    return redirect("perfil")


# ---------- Bitácora ----------
@login_required
@requiere_permiso("permisos.ver")
def bitacora_view(request):
    logs = Bitacora.objects.all().order_by("-fecha")
    return render(request, "accounts/bitacora.html", {"logs": logs})


# ---------- CRUD Proveedores ----------
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
            log_event(request, "Proveedor", prov.id, "CREAR", prov.nombre)
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
            form.save()
            log_event(request, "Proveedor", prov.id, "ACTUALIZAR", prov.nombre)
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
        log_event(request, "Proveedor", pk, "BORRAR", nombre)
        messages.info(request, "Proveedor eliminado.")
        return redirect("proveedores_list")
    return render(request, "accounts/proveedor_confirm_delete.html", {"prov": prov})


# ---------- CRUD Insumos ----------
@login_required
@requiere_permiso("INSUMO_READ")
def insumos_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Insumo.objects.all()
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(unidad_medida__icontains=q))
    page = Paginator(qs, 10).get_page(request.GET.get("page"))
    return render(request, "accounts/insumos_list.html", {"page": page, "q": q})


@login_required
@requiere_permiso("INSUMO_WRITE")
def insumo_create(request):
    form = InsumoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Insumo creado.")
        return redirect("insumos_list")
    return render(request, "accounts/insumo_form.html", {"form": form, "title": "Nuevo insumo"})


@login_required
@requiere_permiso("INSUMO_WRITE")
def insumo_update(request, pk):
    obj = get_object_or_404(Insumo, pk=pk)
    form = InsumoForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Insumo actualizado.")
        return redirect("insumos_list")
    return render(request, "accounts/insumo_form.html", {"form": form, "title": f"Editar: {obj.nombre}"})


@login_required
@requiere_permiso("INSUMO_WRITE")
def insumo_delete(request, pk):
    obj = get_object_or_404(Insumo, pk=pk)
    if request.method == "POST":
        try:
            obj.delete()
            messages.success(request, "Insumo eliminado.")
        except IntegrityError:
            messages.error(request, "No se puede eliminar: está referenciado en recetas/compras/kardex.")
        return redirect("insumos_list")
    return render(request, "accounts/insumo_confirm_delete.html", {"obj": obj})
