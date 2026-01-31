"""Stripe webhook handler: mark bookings paid on payment_intent.succeeded."""

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bookings.models import Booking


@require_POST
@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhooks. Verify signature and update Booking payment status."""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    if not webhook_secret:
        return HttpResponse("Webhook secret not configured", status=500)
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return HttpResponse("Invalid payload", status=400)
    except stripe.SignatureVerificationError:
        return HttpResponse("Invalid signature", status=400)

    if event["type"] == "payment_intent.succeeded":
        pi = event["data"]["object"]
        pi_id = pi.get("id")
        if pi_id:
            Booking.objects.filter(stripe_payment_intent_id=pi_id).update(payment_status="paid")

    return HttpResponse(status=200)
