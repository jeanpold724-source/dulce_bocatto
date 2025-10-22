# accounts/urls.py  (PEGA Y REEMPLAZA TODO)

from django.urls import path
from django.contrib.auth.views import LogoutView
from rest_framework.routers import DefaultRouter

# Import modular: auth separado del resto
from . import (
    views,               # catálogo, pedidos básicos, bitácora, proveedores, insumos, etc.
    views_auth,          # login, register, perfil, editar perfil, cambiar password
    views_inventario,
    views_compras,
    views_pedidos,
    views_facturas,
    views_envios,
    views_pagos,         # Stripe
)

# ---------- Web ----------
urlpatterns = [
    # Home / auth
    path("", views_auth.home_view, name="home"),
    path("register/", views_auth.register_view, name="register"),
    path("login/", views_auth.CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),

    # Perfil
    path("perfil/", views_auth.perfil_view, name="perfil"),
    path("perfil/editar/", views_auth.perfil_editar, name="perfil_editar"),
    path("perfil/cambiar-password/", views_auth.cambiar_password, name="cambiar_password"),

    # Catálogo y pedido (estas viven en views.py)
    path("catalogo/", views.catalogo_view, name="catalogo"),
    path("pedido/<int:sabor_id>/", views.crear_pedido, name="crear_pedido"),
    path("cancelar-pedido/<int:pedido_id>/", views.cancelar_pedido, name="cancelar_pedido"),
    path("confirmar-pedido/<int:pedido_id>/", views.confirmar_pedido, name="confirmar_pedido"),
    path("bitacora/", views.bitacora_view, name="bitacora"),

    # Proveedores (CU06)
    path("proveedores/", views.proveedores_list, name="proveedores_list"),
    path("proveedores/nuevo/", views.proveedor_create, name="proveedor_create"),
    path("proveedores/<int:pk>/editar/", views.proveedor_update, name="proveedor_update"),
    path("proveedores/<int:pk>/eliminar/", views.proveedor_delete, name="proveedor_delete"),

    # Insumos
    path("insumos/", views.insumos_list, name="insumos_list"),
    path("insumos/nuevo/", views.insumo_create, name="insumo_create"),
    path("insumos/<int:pk>/editar/", views.insumo_update, name="insumo_update"),
    path("insumos/<int:pk>/eliminar/", views.insumo_delete, name="insumo_delete"),

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

    # Registrar pago manual (CU16 existente)
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
    # OJO: usa la función que realmente tengas en views_pagos (crear_checkout_session o crear_checkout)
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
