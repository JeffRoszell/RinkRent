"""Stripe PaymentIntent for customer bookings."""

import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_booking_payment_intent(amount_cents, facility, booking_ids, metadata=None):
    """
    Create PaymentIntent for booking total. If facility has Connect account, use destination charge.
    Returns dict with client_secret and payment_intent_id.
    """
    params = {
        "amount": amount_cents,
        "currency": "usd",
        "automatic_payment_methods": {"enabled": True},
        "metadata": metadata or {},
    }
    if facility.stripe_account_id:
        params["transfer_data"] = {"destination": facility.stripe_account_id}
    pi = stripe.PaymentIntent.create(**params)
    return {"client_secret": pi.client_secret, "payment_intent_id": pi.id}


def refund_booking(booking):
    """Refund a paid booking. booking must have stripe_payment_intent_id and amount_paid."""
    if not booking.stripe_payment_intent_id or booking.payment_status != "paid":
        return None
    amount_cents = int(booking.amount_paid * 100) if booking.amount_paid else 0
    if amount_cents <= 0:
        return None
    try:
        refund = stripe.Refund.create(
            payment_intent=booking.stripe_payment_intent_id,
            amount=amount_cents,
        )
        return refund.id
    except Exception:
        return None
