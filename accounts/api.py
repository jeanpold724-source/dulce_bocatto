# accounts/api.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models_db import Usuario, Rol, Permiso, UsuarioRol, RolPermiso
from .serializers import (
    PermisoSerializer,
    RolListSerializer, RolWriteSerializer,
    UsuarioListSerializer, UsuarioRolesWriteSerializer,
)

class PermisoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Permiso.objects.all().order_by("codigo")
    serializer_class = PermisoSerializer

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
