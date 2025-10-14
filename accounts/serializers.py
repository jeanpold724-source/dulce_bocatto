from rest_framework import serializers
from .models_db import Usuario, Rol, Permiso, UsuarioRol, RolPermiso

class PermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permiso
        fields = ("id", "codigo", "descripcion")

class RolListSerializer(serializers.ModelSerializer):
    permisos = serializers.SerializerMethodField()

    class Meta:
        model = Rol
        fields = ("id", "nombre", "permisos")

    def get_permisos(self, obj):
        qs = Permiso.objects.filter(rolpermiso__rol=obj).order_by("codigo")
        return PermisoSerializer(qs, many=True).data

class RolWriteSerializer(serializers.ModelSerializer):
    permisos = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False
    )

    class Meta:
        model = Rol
        fields = ("id", "nombre", "permisos")

    def create(self, validated_data):
        permisos_ids = validated_data.pop("permisos", [])
        rol = Rol.objects.create(**validated_data)
        if permisos_ids:
            RolPermiso.objects.bulk_create(
                [RolPermiso(rol=rol, permiso_id=p) for p in permisos_ids],
                ignore_conflicts=True,
            )
        return rol

    def update(self, instance, validated_data):
        permisos_ids = validated_data.pop("permisos", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if permisos_ids is not None:
            RolPermiso.objects.filter(rol=instance).delete()
            RolPermiso.objects.bulk_create(
                [RolPermiso(rol=instance, permiso_id=p) for p in permisos_ids],
                ignore_conflicts=True,
            )
        return instance

class UsuarioListSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ("id", "nombre", "email", "activo", "roles")

    def get_roles(self, obj):
        return list(
            UsuarioRol.objects.filter(usuario=obj).values_list("rol_id", flat=True)
        )

class UsuarioRolesWriteSerializer(serializers.Serializer):
    roles = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True
    )
