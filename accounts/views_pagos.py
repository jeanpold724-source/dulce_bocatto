# accounts/views_pagos.py
from decimal import Decimal, ROUND_HALF_UP
import stripe

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models_db import Pedido


# -----------------------
# Helpers SQL
# -----------------------
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


def _usuario_id_por_email(email: str) -> int | None:
    """Retorna id en tabla 'usuario' a partir del email."""
    if not email:
        return None
    with connection.cursor() as cur:
        cur.execute("SELECT id FROM usuario WHERE email=%s LIMIT 1", [email])
        row = cur.fetchone()
        return row[0] if row else None


def _usuario_id_dueno_pedido(pedido_id: int) -> int | None:
    """Devuelve el id del usuario dueño del pedido."""
    with connection.cursor() as cur:
        cur.execute("""
            SELECT u.id
            FROM pedido p
            JOIN cliente c ON c.id = p.cliente_id
            JOIN usuario u ON u.id = c.usuario_id
            WHERE p.id = %s
            LIMIT 1
        """, [pedido_id])
        row = cur.fetchone()
        return row[0] if row else None


def _es_duenio_del_pedido(request, pedido: Pedido) -> bool:
    """Compara email del cliente con el del usuario logueado."""
    try:
        email_pedido = (pedido.cliente.usuario.email or "").lower()
    except Exception:
        return False
    email_req = (getattr(request.user, "email", "") or "").lower()
    return email_pedido and email_req and (email_pedido == email_req)


# -----------------------
# Vistas
# -----------------------
@login_required
def crear_checkout_session(request, pedido_id: int):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Trae el pedido y valida propiedad por email
    pedido = get_object_or_404(
        Pedido.objects.select_related("cliente__usuario"),
        pk=pedido_id
    )
    if not _es_duenio_del_pedido(request, pedido) and not request.user.is_staff:
        messages.error(request, "No puedes pagar un pedido que no te pertenece.")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    # Calcula saldo
    pagado = _total_pagado(pedido.id)
    saldo = (Decimal(pedido.total or 0) - pagado)
    if saldo <= 0:
        messages.info(request, "Este pedido ya no tiene saldo pendiente.")
        return redirect("pedido_detalle", pedido_id=pedido.id)

    # Monto (centavos) con redondeo seguro
    cents = int((saldo * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))
    currency = (getattr(settings, "CURRENCY", "BOB") or "BOB").lower()
    domain = (getattr(settings, "SITE_URL", "http://127.0.0.1:8000") or "").rstrip("/")

    success_url = f"{domain}{reverse('pago_exitoso', args=[pedido.id])}?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = f"{domain}{reverse('pago_cancelado', args=[pedido.id])}"

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
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "pedido_id": str(pedido.id),
                "user_email": getattr(request.user, "email", "") or "",
                "saldo": str(saldo),
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

    # Idempotencia
    if _existe_referencia(session_id):
        messages.success(request, "Pago ya registrado anteriormente.")
        return redirect("pedido_detalle", pedido_id=pedido_id)

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError as e:
        messages.warning(request, f"No se pudo validar la sesión de pago: {getattr(e, 'user_message', str(e))}")
        return redirect("pedido_detalle", pedido_id=pedido_id)

    if session.get("payment_status") != "paid":
        messages.warning(request, "El pago no aparece como 'paid'.")
        return redirect("pedido_detalle", pedido_id=pedido_id)

    amount_paid = Decimal(session.get("amount_total", 0)) / Decimal("100")

    # Validación contra saldo actual
    pagado = _total_pagado(pedido_id)
    with connection.cursor() as cur:
        cur.execute("SELECT total FROM pedido WHERE id=%s", [pedido_id])
        (total_db,) = cur.fetchone() or (0,)
    saldo_actual = Decimal(str(total_db or 0)) - pagado
    if amount_paid > saldo_actual + Decimal("0.01"):
        messages.warning(request, "El monto cobrado supera el saldo pendiente. Revisa el pedido.")

    # Resolver registrado_por_id:
    registrador_id = _usuario_id_por_email(getattr(request.user, "email", ""))
    if registrador_id is None:
        registrador_id = _usuario_id_dueno_pedido(pedido_id)

    try:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO pago (pedido_id, metodo, monto, referencia, registrado_por_id, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, [pedido_id, "TRANSFERENCIA", float(amount_paid), session_id, registrador_id])
        messages.success(request, "Pago registrado correctamente (Stripe).")
    except Exception as e:
        print("Error insertando pago:", e)
        import traceback
        traceback.print_exc()
        messages.success(
            request,
            "Pago aprobado en Stripe, pero no se pudo insertar el registro. "
            "Si no aparece en la lista, regístralo manualmente con la referencia."
        )

    return redirect("pedido_detalle", pedido_id=pedido_id)


@login_required
def pago_cancelado(request, pedido_id: int):
    return render(request, "accounts/pago_cancelado.html", {"pedido_id": pedido_id})
