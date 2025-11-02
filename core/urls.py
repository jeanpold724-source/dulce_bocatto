# core/urls.py
from django.contrib import admin
from django.urls import path, include
from core.urls_debug import urls_debug_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # 👉 incluye TODO lo de accounts (ahí ya tienes path("", views_auth.home_view, name="home"))
    path('', include('accounts.urls')),

    path("debug/urls/", urls_debug_view, name="urls_debug"),
]
