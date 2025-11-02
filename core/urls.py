# core/urls.py
from django.contrib import admin
from django.urls import path, include
from core.urls_debug import urls_debug_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # 👉 Incluye todo lo de la app principal
    path('', include('accounts.urls')),

    # 👉 Página de debug opcional (si existe)
    path("debug/urls/", urls_debug_view, name="urls_debug"),
]
