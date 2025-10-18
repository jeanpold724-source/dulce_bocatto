# accounts/urls.py
from django.urls import path
from django.contrib.auth.views import LogoutView
from rest_framework.routers import DefaultRouter

from .views import (
    cancelar_pedido, bitacora_view, confirmar_pedido,
    perfil_editar, cambiar_password, catalogo_view, crear_pedido,
    register_view, CustomLoginView, home_view, perfil_view,
    proveedores_list, proveedor_create, proveedor_update, proveedor_delete,
    insumos_list, insumo_create, insumo_update, insumo_delete,
)

# --- Web ---
urlpatterns = [
    path("", home_view, name="home"),
    path("register/", register_view, name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),

    path("perfil/", perfil_view, name="perfil"),
    path("perfil/editar/", perfil_editar, name="perfil_editar"),
    path("perfil/cambiar-password/", cambiar_password, name="cambiar_password"),

    path("catalogo/", catalogo_view, name="catalogo"),
    path("pedido/<int:sabor_id>/", crear_pedido, name="crear_pedido"),
    path("cancelar-pedido/<int:pedido_id>/", cancelar_pedido, name="cancelar_pedido"),
    path("confirmar-pedido/<int:pedido_id>/", confirmar_pedido, name="confirmar_pedido"),
    path("bitacora/", bitacora_view, name="bitacora"),

    # Proveedores (CU06)
    path("proveedores/", proveedores_list, name="proveedores_list"),
    path("proveedores/nuevo/", proveedor_create, name="proveedor_create"),
    path("proveedores/<int:pk>/editar/", proveedor_update, name="proveedor_update"),
    path("proveedores/<int:pk>/eliminar/", proveedor_delete, name="proveedor_delete"),

    # Insumos
    path("insumos/", insumos_list, name="insumos_list"),
    path("insumos/nuevo/", insumo_create, name="insumo_create"),
    path("insumos/<int:pk>/editar/", insumo_update, name="insumo_update"),
    path("insumos/<int:pk>/eliminar/", insumo_delete, name="insumo_delete"),
]

# --- API (CU04) ---
import accounts.api as accounts_api

router = DefaultRouter()
router.register(r"api/permisos", accounts_api.PermisoViewSet)
router.register(r"api/roles",    accounts_api.RolViewSet)
router.register(r"api/usuarios", accounts_api.UsuarioViewSet)

urlpatterns += router.urls


from . import views_inventario

urlpatterns += [
    path("inventario/movimiento/", views_inventario.movimiento_crear, name="movimiento_crear"),
    path("inventario/kardex/", views_inventario.kardex_list, name="kardex_list"),
    path("inventario/kardex/<int:pk>/", views_inventario.kardex_por_insumo, name="kardex_por_insumo"),
]
