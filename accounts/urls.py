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

# --- Inventario ---
from . import views_inventario

urlpatterns += [
    path("inventario/movimiento/", views_inventario.movimiento_crear, name="movimiento_crear"),
    path("inventario/kardex/", views_inventario.kardex_list, name="kardex_list"),
    path("inventario/kardex/<int:pk>/", views_inventario.kardex_por_insumo, name="kardex_por_insumo"),
]

# --- Compras ---
from . import views_compras

urlpatterns += [
    # CU14
    path("compras/", views_compras.compras_list, name="compras_list"),
    path("compras/nueva/", views_compras.compra_crear, name="compra_crear"),
    path("compras/<int:compra_id>/", views_compras.compra_detalle, name="compra_detalle"),
    path("compras/<int:compra_id>/recepcionar/", views_compras.compra_recepcionar, name="compra_recepcionar"),
]

# --- Pedidos ---
from . import views_pedidos

urlpatterns += [
    path("pedidos/", views_pedidos.pedidos_pendientes, name="pedidos_pendientes"),
    path("pedidos/<int:pedido_id>/", views_pedidos.pedido_detalle, name="pedido_detalle"),
    path("pedidos/<int:pedido_id>/editar/", views_pedidos.pedido_editar, name="pedido_editar"),

    # ✅ CU15: Pedidos confirmados
    path("pedidos/confirmados/", views_pedidos.pedidos_confirmados, name="pedidos_confirmados"),
]



from . import views_pedidos

urlpatterns += [
    # ...
    path("pedidos/<int:pedido_id>/pago/", views_pedidos.pago_registrar, name="pago_registrar"),
]


from . import views_facturas

urlpatterns += [
    # CU17: facturación
    path("pedidos/<int:pedido_id>/factura/emitir/", views_facturas.factura_emitir, name="factura_emitir"),
    path("pedidos/<int:pedido_id>/factura/", views_facturas.factura_detalle, name="factura_detalle"),
]


from . import views_facturas

urlpatterns += [
    path("facturas/", views_facturas.factura_list, name="factura_list"),
    # … (las 2 rutas que ya tienes de emitir y detalle)
]


from . import views_envios

urlpatterns += [
    path("envios/", views_envios.envio_list, name="envio_list"),
    path("envios/<int:pedido_id>/", views_envios.envio_crear_editar, name="envio_crear_editar"),
    path("envios/<int:pedido_id>/entregado/", views_envios.envio_marcar_entregado, name="envio_marcar_entregado"),
]
