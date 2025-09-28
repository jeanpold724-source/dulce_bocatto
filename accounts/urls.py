from django.urls import path
from .views import register_view, CustomLoginView, home_view
from .views import perfil_view
from .views import register_view, CustomLoginView, home_view, perfil_view, catalogo_view


urlpatterns = [
    path('', home_view, name='home'),
    path('register/', register_view, name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('perfil/', perfil_view, name='perfil'),
    path('catalogo/', catalogo_view, name='catalogo'),

]