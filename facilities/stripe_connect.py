"""Stripe Connect: create account link for facility onboarding."""

import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def get_or_create_connect_account(facility):
    """Create Stripe Express account for facility if none; return account id."""
    if facility.stripe_account_id:
        return facility.stripe_account_id
    account = stripe.Account.create(
        type="express",
        country="CA",
        email=facility.managers.first().email if facility.managers.exists() else None,
    )
    facility.stripe_account_id = account.id
    facility.save(update_fields=["stripe_account_id"])
    return account.id


def create_account_link(account_id, request):
    """Create AccountLink for onboarding; redirect URL uses request.build_absolute_uri."""
    return_url = request.build_absolute_uri("/facility/")
    refresh_url = request.build_absolute_uri("/facility/")
    return stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
