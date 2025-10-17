# core/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("", include("accounts.urls")),  # root apunta a accounts
    path("admin/", admin.site.urls),
]
