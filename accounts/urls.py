# accounts/urls.py  (REEMPLAZA TODO ESTE ARCHIVO)

from django.urls import path
from django.contrib.auth.views import LogoutView
from rest_framework.routers import DefaultRouter

# Vistas base
from .views import (
    cancelar_pedido, bitacora_view, confirmar_pedido,
    perfil_editar, cambiar_password, catalogo_view, crear_pedido,
    register_view, CustomLoginView, home_view, perfil_view,
    proveedores_list, proveedor_create, proveedor_update, proveedor_delete,
    insumos_list, insumo_create, insumo_update, insumo_delete,
)

# Módulos por feature
from . import views_inventario
from . import views_compras
from . import views_pedidos
from . import views_facturas
from . import views_envios
from . import views_pagos          # Stripe

# ---------- Web ----------
urlpatterns = [
    # Home / auth
    path("", home_view, name="home"),
    path("register/", register_view, name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),

    # Perfil
    path("perfil/", perfil_view, name="perfil"),
    path("perfil/editar/", perfil_editar, name="perfil_editar"),
    path("perfil/cambiar-password/", cambiar_password, name="cambiar_password"),

    # Catálogo y pedido
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

    # Inventario
    path("inventario/movimiento/", views_inventario.movimiento_crear, name="movimiento_crear"),
    path("inventario/kardex/", views_inventario.kardex_list, name="kardex_list"),
    path("inventario/kardex/<int:pk>/", views_inventario.kardex_por_insumo, name="kardex_por_insumo"),

    # Compras (CU14)
    path("compras/", views_compras.compras_list, name="compras_list"),
    path("compras/nueva/", views_compras.compra_crear, name="compra_crear"),
    path("compras/<int:compra_id>/", views_compras.compra_detalle, name="compra_detalle"),
    path("compras/<int:compra_id>/recepcionar/", views_compras.compra_recepcionar, name="compra_recepcionar"),

    # Pedidos
    path("pedidos/", views_pedidos.pedidos_pendientes, name="pedidos_pendientes"),
    path("pedidos/<int:pedido_id>/", views_pedidos.pedido_detalle, name="pedido_detalle"),
    path("pedidos/<int:pedido_id>/editar/", views_pedidos.pedido_editar, name="pedido_editar"),
    path("pedidos/confirmados/", views_pedidos.pedidos_confirmados, name="pedidos_confirmados"),

    # Registrar pago manual (tu CU16 existente)
    path("pedidos/<int:pedido_id>/pago/", views_pedidos.pago_registrar, name="pago_registrar"),

    # Facturas (CU17)
    path("facturas/", views_facturas.factura_list, name="factura_list"),
    path("pedidos/<int:pedido_id>/factura/emitir/", views_facturas.factura_emitir, name="factura_emitir"),
    path("pedidos/<int:pedido_id>/factura/", views_facturas.factura_detalle, name="factura_detalle"),

    # Envíos (CU24)
    path("envios/", views_envios.envio_list, name="envio_list"),
    path("envios/<int:pedido_id>/", views_envios.envio_crear_editar, name="envio_crear_editar"),
    path("envios/<int:pedido_id>/entregado/", views_envios.envio_marcar_entregado, name="envio_marcar_entregado"),

    # Stripe Checkout (CU16 – pasarela)
    path("pago/<int:pedido_id>/", views_pagos.crear_checkout_session, name="crear_checkout"),
    path("pagos/success/<int:pedido_id>/", views_pagos.pago_exitoso, name="pago_exitoso"),
    path("pagos/cancel/<int:pedido_id>/", views_pagos.pago_cancelado, name="pago_cancelado"),
]

# ---------- API (CU04) ----------
import accounts.api as accounts_api

router = DefaultRouter()
router.register(r"api/permisos", accounts_api.PermisoViewSet)
router.register(r"api/roles",    accounts_api.RolViewSet)
router.register(r"api/usuarios", accounts_api.UsuarioViewSet)

urlpatterns += router.urls
