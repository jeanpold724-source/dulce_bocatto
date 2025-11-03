# accounts/urls.py  (REEMPLAZA TODO ESTE ARCHIVO)
from django.urls import path
from django.contrib.auth.views import LogoutView
from rest_framework.routers import DefaultRouter

# Import modular (áreas principales)
from . import (
    views,               # catálogo, bitácora, proveedores, insumos, etc.
    views_auth,          # login, register, perfil, editar perfil, cambiar password
    views_inventario,
    views_compras,
    views_pedidos,
    views_facturas,
    views_envios,
    views_pagos,         # Stripe
)

# ---------- Reportes (funciones específicas) ----------
# CU18 – Historial de compras de clientes
from .views_reportes import (
    historial_clientes,
    historial_clientes_csv,
    historial_clientes_pdf,
    historial_clientes_html,
)

# CU23 – Ventas diarias
from .views_reportes import (
    ventas_diarias,
    ventas_diarias_csv,
    ventas_diarias_html,
    ventas_diarias_pdf,
)

# CU25 – Historial de compras a proveedores
from .views_reportes import (
    historial_proveedores,
    historial_proveedores_csv,
    historial_proveedores_html,
    historial_proveedores_pdf,
)

# CU26 – Historial de entregas
from .views_reportes import (
    historial_entregas,
    historial_entregas_csv,
    historial_entregas_html,
    historial_entregas_pdf,
)

# CU27 – Generar reportes de ventas
from .views_reportes import reporte_ventas


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

    # Catálogo y pedido
    path("catalogo/", views.catalogo_view, name="catalogo"),
    path("pedido/<int:sabor_id>/", views.crear_pedido, name="crear_pedido"),
    path("cancelar-pedido/<int:pedido_id>/", views.cancelar_pedido, name="cancelar_pedido"),
    path("confirmar-pedido/<int:pedido_id>/", views.confirmar_pedido, name="confirmar_pedido"),
    path("bitacora/", views.bitacora_view, name="bitacora"),

    # Proveedores
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

    # Compras
    path("compras/", views_compras.compras_list, name="compras_list"),
    path("compras/nueva/", views_compras.compra_crear, name="compra_crear"),
    path("compras/<int:compra_id>/", views_compras.compra_detalle, name="compra_detalle"),
    path("compras/<int:compra_id>/recepcionar/", views_compras.compra_recepcionar, name="compra_recepcionar"),

    # Pedidos
    path("pedidos/", views_pedidos.pedidos_pendientes, name="pedidos_pendientes"),
    path("pedidos/confirmados/", views_pedidos.pedidos_confirmados, name="pedidos_confirmados"),
    path("pedidos/<int:pedido_id>/", views_pedidos.pedido_detalle, name="pedido_detalle"),
    path("pedidos/<int:pedido_id>/editar/", views_pedidos.pedido_editar, name="pedido_editar"),

    # Pagos (manual CU16 + Stripe)
    path("pedidos/<int:pedido_id>/pago/", views_pedidos.pago_registrar, name="pago_registrar"),
    path("pago/<int:pedido_id>/", views_pagos.crear_checkout_session, name="crear_checkout"),
    path("pagos/success/<int:pedido_id>/", views_pagos.pago_exitoso, name="pago_exitoso"),
    path("pagos/cancel/<int:pedido_id>/", views_pagos.pago_cancelado, name="pago_cancelado"),

    # Facturas (CU17)
    path("facturas/", views_facturas.factura_list, name="factura_list"),
    path("pedidos/<int:pedido_id>/factura/emitir/", views_facturas.factura_emitir, name="factura_emitir"),
    path("pedidos/<int:pedido_id>/factura/", views_facturas.factura_detalle, name="factura_detalle"),
]

# ---------- Reportes ----------
# CU18 – Historial de compras de clientes + exportaciones
urlpatterns += [
    path("clientes/historial/", historial_clientes, name="historial_clientes"),
    path("clientes/historial/export.csv",  historial_clientes_csv,  name="historial_clientes_csv"),
    path("clientes/historial/export.pdf",  historial_clientes_pdf,  name="historial_clientes_pdf"),
    path("clientes/historial/export.html", historial_clientes_html, name="historial_clientes_html"),
]

# CU23 – Ventas diarias + exportaciones
urlpatterns += [
    path("reportes/ventas-diarias/", ventas_diarias, name="ventas_diarias"),
    path("reportes/ventas-diarias/export.csv",  ventas_diarias_csv,  name="ventas_diarias_csv"),
    path("reportes/ventas-diarias/export.html", ventas_diarias_html, name="ventas_diarias_html"),
    path("reportes/ventas-diarias/export.pdf",  ventas_diarias_pdf,  name="ventas_diarias_pdf"),
]

# CU25 – Compras a proveedores + exportaciones
urlpatterns += [
    path("reportes/proveedores/", historial_proveedores, name="historial_proveedores"),
    path("reportes/proveedores/export.csv",  historial_proveedores_csv,  name="historial_proveedores_csv"),
    path("reportes/proveedores/export.html", historial_proveedores_html, name="historial_proveedores_html"),
    path("reportes/proveedores/export.pdf",  historial_proveedores_pdf,  name="historial_proveedores_pdf"),
]

# CU26 – Historial de entregas + exportaciones
urlpatterns += [
    path("reportes/entregas/", historial_entregas, name="historial_entregas"),
    path("reportes/entregas/export.csv",  historial_entregas_csv,  name="historial_entregas_csv"),
    path("reportes/entregas/export.html", historial_entregas_html, name="historial_entregas_html"),
    path("reportes/entregas/export.pdf",  historial_entregas_pdf,  name="historial_entregas_pdf"),
]

# ---- CU27 – Generar reportes de ventas ----
from .views_reportes import (
    ventas_reportes,
    ventas_reportes_csv,
    ventas_reportes_html,
    ventas_reportes_pdf,
)

urlpatterns += [
    path("reportes/ventas/", ventas_reportes, name="ventas_reportes"),
    path("reportes/ventas/export.csv",  ventas_reportes_csv,  name="ventas_reportes_csv"),
    path("reportes/ventas/export.html", ventas_reportes_html, name="ventas_reportes_html"),
    path("reportes/ventas/export.pdf",  ventas_reportes_pdf,  name="ventas_reportes_pdf"),
]


# ---------- API (CU04) ----------
import accounts.api as accounts_api

router = DefaultRouter()
router.register(r"api/permisos", accounts_api.PermisoViewSet)
router.register(r"api/roles",    accounts_api.RolViewSet)
router.register(r"api/usuarios", accounts_api.UsuarioViewSet)

urlpatterns += router.urls
