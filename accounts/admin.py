# accounts/admin.py
from django.contrib import admin
from .models_db import Bitacora, Sabor, Producto


@admin.register(Sabor)
class SaborAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "activo", "imagen")   # usamos imagen, no created_at
    search_fields = ("nombre",)
    list_filter = ("activo",)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "precio_unitario", "activo", "creado_en")
    search_fields = ("nombre",)
    list_filter = ("activo",)


@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    # NO usamos date_hierarchy ni list_filter con 'fecha' para evitar CONVERT_TZ
    list_display = ("fecha_local", "usuario", "accion", "entidad", "entidad_id", "ip")
    search_fields = ("usuario__email", "usuario__nombre", "accion", "entidad", "ip")
    list_filter = ("accion", "entidad")  # dejamos fuera 'fecha'

    def fecha_local(self, obj):
        from django.utils import timezone
        if not obj.fecha:
            return "-"
        # mostrar en tz local sin forzar conversiones en SQL
        return timezone.localtime(obj.fecha)
    fecha_local.short_description = "Fecha"
