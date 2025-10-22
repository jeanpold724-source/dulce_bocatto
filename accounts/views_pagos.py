# accounts/views_pagos.py
from decimal import Decimal, ROUND_HALF_UP
import stripe

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.shortcuts import get_object_or_404, redirect, render

from .models_db import Pedido  # igual que en tus otras vistas

def _total_pagado(pedido_id: int) -> Decimal:
    with connection.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(monto),0) FROM pago WHERE pedido_id=%s", [pedido_id])
        (s,) = cur.fetchone()
        return Decimal(str(s or 0))

def _existe_referencia(ref: str) -> bool:
    """Evita duplicados por session_id."""
    if not ref:
        return False
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM pago WHERE referencia=%s LIMIT 1", [ref])
        return cur.fetchone() is not None

@login_required
def crear_checkout_session(request, pedido_id: int):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # 🔧 Si tu Pedido tiene user_id, protege así:
    try:
        # Si tu modelo NO tiene user, usa el get_object_or_404(Pedido, pk=pedido_id) de antes.
        pedido = Pedido.objects.get(pk=pedido_id, user_id=request.user.id)  # 🔧 AJUSTA SI NO EXISTE user_id
    except Exception:
        # fallback
        pedido = get_object_or_404(Pedido, pk=pedido_id)

    pagado = _total_pagado(pedido.id)
    saldo = (Decimal(pedido.total or 0) - pagado)
    if saldo <= 0:
        messages.info(request, "Este pedido ya no tiene saldo pendiente.")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    # Centavos seguros (ROUND_HALF_UP)
    cents = int((saldo * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))
    currency = (getattr(settings, "CURRENCY", "USD") or "USD").lower()
    domain = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": f"Pedido #{pedido.id}"},
                    "unit_amount": cents,
                },
                "quantity": 1,
            }],
            success_url=f"{domain}/pagos/success/{pedido.id}/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{domain}/pagos/cancel/{pedido.id}/",
            metadata={
                "pedido_id": str(pedido.id),
                "saldo": str(saldo),
                "user_id": str(getattr(request.user, 'id', '')),
            }
        )
    except stripe.error.StripeError as e:
        messages.error(request, f"Error creando sesión de Stripe: {getattr(e, 'user_message', str(e))}")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    return redirect(session.url, code=303)

@login_required
def pago_exitoso(request, pedido_id: int):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    session_id = request.GET.get("session_id")
    if not session_id:
        messages.warning(request, "No se encontró la sesión de pago.")
        return redirect("pedido_detalle", pedido_id=pedido_id)

    # Idempotencia: si ya lo guardamos, no repetir
    if _existe_referencia(session_id):
        messages.success(request, "Pago ya registrado anteriormente.")
        return redirect("pedido_detalle", pedido_id=pedido_id)

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError as e:
        messages.warning(request, f"No se pudo validar la sesión de pago: {getattr(e, 'user_message', str(e))}")
        return redirect("pedido_detalle", pedido_id=pedido_id)

    if session.get("payment_status") == "paid":
        amount_paid = Decimal(session.get("amount_total", 0)) / Decimal("100")

        # Opcional: validar contra saldo pendiente del momento (defensivo)
        pagado = _total_pagado(pedido_id)
        with connection.cursor() as cur:
            cur.execute("SELECT total FROM pedido WHERE id=%s", [pedido_id])  # 🔧 si tu tabla se llama distinto, ajusta
            (total_db,) = cur.fetchone() or (0,)
        saldo_actual = Decimal(str(total_db or 0)) - pagado
        if amount_paid > saldo_actual + Decimal("0.01"):
            messages.warning(request, "El monto cobrado supera el saldo pendiente. Revisa el pedido.")
            # Aun así registramos para no perder trazabilidad

        try:
            with connection.cursor() as cur:
                cur.execute("""
                    INSERT INTO pago (pedido_id, metodo, monto, referencia, registrado_por_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, [pedido_id, "STRIPE", float(amount_paid), session_id, request.user.id])
            messages.success(request, "Pago registrado correctamente (Stripe).")
        except Exception:
            messages.success(
                request,
                "Pago aprobado en Stripe, pero no se pudo insertar el registro. "
                "Si no aparece en la lista, regístralo manualmente con la referencia."
            )
    else:
        messages.warning(request, "El pago no aparece como 'paid'.")

    return redirect("pedido_detalle", pedido_id=pedido_id)

@login_required
def pago_cancelado(request, pedido_id: int):
    return render(request, "accounts/pago_cancelado.html", {"pedido_id": pedido_id})
