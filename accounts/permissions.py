# accounts/permissions.py
from django.core.exceptions import PermissionDenied
from .models_db import Usuario, UsuarioRol, RolPermiso

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
