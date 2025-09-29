from django.urls import path
from .views import cancelar_pedido
from .views import bitacora_view

from .views import (
    register_view,
    CustomLoginView,
    home_view,
    perfil_view,
    catalogo_view,
    crear_pedido,
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
]