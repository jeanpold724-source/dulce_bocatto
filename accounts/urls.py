# accounts/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    cancelar_pedido, bitacora_view, confirmar_pedido,
    perfil_editar, cambiar_password, catalogo_view, crear_pedido,
    register_view, CustomLoginView, home_view, perfil_view,
    proveedores_list, proveedor_create, proveedor_update, proveedor_delete
)

urlpatterns = [
    path('', home_view, name='home'),
    path('register/', register_view, name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('perfil/', perfil_view, name='perfil'),
    path('catalogo/', catalogo_view, name='catalogo'),
    path('pedido/<int:sabor_id>/', crear_pedido, name='crear_pedido'),
    path('cancelar-pedido/<int:pedido_id>/', cancelar_pedido, name='cancelar_pedido'),
    path('bitacora/', bitacora_view, name='bitacora'),
    path('confirmar-pedido/<int:pedido_id>/', confirmar_pedido, name='confirmar_pedido'),
    path('perfil/editar/', perfil_editar, name='perfil_editar'),
    path('perfil/cambiar-password/', cambiar_password, name='cambiar_password'),
]

# --- API (CU04) ---
# Importa el módulo completo para evitar problemas de timing/circularidad
import accounts.api as accounts_api

router = DefaultRouter()
router.register(r'api/permisos', accounts_api.PermisoViewSet)
router.register(r'api/roles',    accounts_api.RolViewSet)
router.register(r'api/usuarios', accounts_api.UsuarioViewSet)

urlpatterns += router.urls


urlpatterns += [
    path("proveedores/", proveedores_list, name="proveedores_list"),
    path("proveedores/nuevo/", proveedor_create, name="proveedor_create"),
    path("proveedores/<int:pk>/editar/", proveedor_update, name="proveedor_update"),
    path("proveedores/<int:pk>/eliminar/", proveedor_delete, name="proveedor_delete"),
]