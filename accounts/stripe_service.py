from django.conf import settings
import stripe

def init_stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe

def create_checkout_session(pedido, success_url, cancel_url):
    stripe = init_stripe()

    # Obtiene detalles (ajusta si tus related_name cambian)
    detalles = getattr(pedido, "detalles", None) or getattr(pedido, "detallepedido_set", None)
    if callable(detalles):
        detalles = detalles.all()

    line_items = []
    for d in detalles:
        nombre = getattr(d, "producto_nombre", None) or str(d)
        cantidad = int(getattr(d, "cantidad", 1))
        precio_unitario = float(getattr(d, "precio_unitario", 0))
        unit_amount = int(round(precio_unitario * 100))  # centavos

        line_items.append({
            "price_data": {
                "currency": settings.CURRENCY.lower(),
                "product_data": {"name": nombre},
                "unit_amount": unit_amount,
            },
            "quantity": cantidad,
        })

    metadata = {
        "pedido_id": str(pedido.id),
        "monto_esperado": str(getattr(pedido, "total", 0)),
        "user_id": str(getattr(pedido, "user_id", "")),
    }

    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=line_items,
        metadata=metadata,
    )
    return session
