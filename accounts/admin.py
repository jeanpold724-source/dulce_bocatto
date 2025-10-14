from django.contrib import admin
from .models_db import Bitacora, Sabor, Producto, Usuario, Rol, Permiso, UsuarioRol, RolPermiso

# ====== ya tenías estos ======
@admin.register(Sabor)
class SaborAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "activo", "imagen")
    search_fields = ("nombre",)
    list_filter = ("activo",)

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "precio_unitario", "activo", "creado_en")
    search_fields = ("nombre",)
    list_filter = ("activo",)

@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ("fecha_local", "usuario", "accion", "entidad", "entidad_id", "ip")
    search_fields = ("usuario__email", "usuario__nombre", "accion", "entidad", "ip")
    list_filter = ("accion", "entidad")
    def fecha_local(self, obj):
        from django.utils import timezone
        if not obj.fecha:
            return "-"
        return timezone.localtime(obj.fecha)
    fecha_local.short_description = "Fecha"

# ====== CU04 ======
@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "email", "activo", "created_at")
    search_fields = ("nombre", "email", "telefono")
    list_filter = ("activo",)

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)

@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ("id", "codigo", "descripcion")
    search_fields = ("codigo", "descripcion")

@admin.register(UsuarioRol)
class UsuarioRolAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "rol")
    search_fields = ("usuario__email", "usuario__nombre", "rol__nombre")
    list_select_related = ("usuario", "rol")

@admin.register(RolPermiso)
class RolPermisoAdmin(admin.ModelAdmin):
    list_display = ("id", "rol", "permiso")
    search_fields = ("rol__nombre", "permiso__codigo")
    list_select_related = ("rol", "permiso")
