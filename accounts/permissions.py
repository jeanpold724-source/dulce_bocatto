# accounts/permissions.py
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.db import connection
from decimal import Decimal

from .models_db import Usuario, UsuarioRol, RolPermiso, Pedido



# -------------------------------------------------
# Permisos por código (lo que ya tenías)
# -------------------------------------------------
def requiere_permiso(codigo_permiso):
    def wrapper(view):
        def inner(request, *args, **kwargs):
            # Si no está logueado, a login
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())

            email = (request.user.email or "").lower()
            try:
                u = Usuario.objects.get(email=email)
                tiene = RolPermiso.objects.filter(
                    rol__in=UsuarioRol.objects.filter(usuario=u).values("rol"),
                    permiso__codigo=codigo_permiso,
                ).exists()
            except Usuario.DoesNotExist:
                tiene = False

            if not tiene:
                raise PermissionDenied("No tienes permiso.")
            return view(request, *args, **kwargs)
        return inner
    return wrapper


# -------------------------------------------------
# Nuevo decorador: permite acceso si tiene alguno de varios permisos
# -------------------------------------------------
def permission_required_any(*perms):
    """
    Permite acceso si el usuario es staff/superuser o tiene al menos uno de los permisos dados.
    Uso:
        @permission_required_any("accounts.view_pedido", "accounts.view_pago")
        def mi_vista(...):
            ...
    """
    def decorator(view_func):
        @login_required
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or user.is_staff:
                return view_func(request, *args, **kwargs)
            if any(user.has_perm(p) for p in perms):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("No tienes permiso para acceder a esta vista.")
        return _wrapped
    return decorator



# -------------------------------------------------
# Nuevo: permitir editar pedido si es dueño o staff,
# el pedido no está finalizado y no tiene pagos.
# -------------------------------------------------
def _pedido_tiene_pagos(pedido_id: int) -> bool:
    with connection.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(monto),0) FROM pago WHERE pedido_id=%s", [pedido_id])
        (s,) = cur.fetchone()
        return Decimal(str(s or 0)) > 0

def owner_or_staff_pedido(view_func):
    """
    Deja pasar si:
      - es staff, o
      - es el dueño (email cliente == email del request) y
        el pedido NO está ENTREGADO/CANCELADO y NO tiene pagos.

    Si no cumple, muestra mensaje y redirige al detalle del pedido.
    """
    @login_required
    def _wrapped(request, *args, **kwargs):
        # staff siempre puede
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        pedido_id = kwargs.get("pedido_id") or kwargs.get("pk") or kwargs.get("id")
        p = Pedido.objects.select_related("cliente__usuario").filter(pk=pedido_id).first()
        if not p:
            messages.warning(request, "El pedido no existe.")
            return redirect("pedidos_confirmados")

        email_req = (getattr(request.user, "email", "") or "").lower()
        email_cli = (getattr(getattr(p.cliente, "usuario", None), "email", "") or "").lower()

        if email_cli != email_req:
            messages.warning(request, "No puedes editar un pedido que no te pertenece.")
            return redirect("pedido_detalle", pedido_id=p.id)

        if p.estado in ("ENTREGADO", "CANCELADO"):
            messages.info(request, "Este pedido ya está finalizado y no se puede editar.")
            return redirect("pedido_detalle", pedido_id=p.id)

        if _pedido_tiene_pagos(p.id):
            messages.info(request, "Este pedido ya tiene pagos registrados y no se puede editar.")
            return redirect("pedido_detalle", pedido_id=p.id)

        return view_func(request, *args, **kwargs)

    return _wrapped
