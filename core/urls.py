# core/urls.py
from django.contrib import admin
from django.urls import path, include

# importa tus vistas de pago
from accounts.views_pagos import crear_checkout_session, pago_exitoso, pago_cancelado
# (si agregás el webhook, también)
# from accounts.views_webhooks import stripe_webhook

urlpatterns = [
    path('admin/', admin.site.urls),

    # rutas principales de tu app
    path('', include('accounts.urls')),

    # Stripe Checkout y resultados
    path('pago/<int:pedido_id>/', crear_checkout_session, name='crear_checkout'),
    path('pagos/success/<int:pedido_id>/', pago_exitoso, name='pago_exitoso'),
    path('pagos/cancel/<int:pedido_id>/', pago_cancelado, name='pago_cancelado'),

    # si decides activar el webhook más adelante:
    # path('webhooks/stripe/', stripe_webhook, name='stripe_webhook'),
]
