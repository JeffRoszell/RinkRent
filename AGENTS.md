# RinkRent – AI Agent Context

Instructions for AI agents working on this codebase.

## Project

RinkRent is a web app for finding and booking ice time (hockey, ringette, figure skating, curling, public skate, and other ice sports). Two sides:

- **Facility managers**: register rinks, add surfaces and hours, connect Stripe, manage bookings.
- **Customers**: search facilities, view availability, book and pay.

## Tech Stack

- **Backend**: Django (Python 3.x), `django-environ` for config.
- **Frontend**: **HTMX first** + DaisyUI; templates in `templates/` with `base.html`.
- **Payments**: Stripe (Connect for facilities, PaymentIntent for customer bookings).
- **DB**: SQLite by default; PostgreSQL via `DATABASE_URL`.

## Bias: HTMX

Prefer HTMX over custom JavaScript. Use HTMX for:

- Dynamic content (lists, filters, search results, availability, forms).
- Partial page updates (`hx-get`, `hx-post`, `hx-swap`); return HTML fragments, not JSON APIs for UI.
- Inline validation, dependent dropdowns, infinite scroll, modals, and “click to load more” patterns.

Avoid adding React, Vue, or heavy client-side frameworks unless there is a clear requirement. Keep JS minimal; let the server render and HTMX swap. Use `hx-headers` for CSRF and `HX-Request` checks in views when you need to return partials only.

## Bias: Ice sports and rink context

The product is for **ice sports**: hockey, ringette, figure skating, curling, public skate, learn-to-skate, etc. Reflect that in:

- **Wording**: Use “ice time”, “rink”, “surface”, “slot”, “ice slot”, “book ice”, “drop-in”, “stick-and-puck”, “figure session”, “public skate” where appropriate. Avoid generic “venue” or “resource” in user-facing copy when “rink” or “ice” fits.
- **Use cases and examples**: In docs, placeholder text, and tests, use realistic scenarios (e.g. “Tuesday night hockey”, “Saturday public skate”, “figure skating practice”, “ringette tournament”).
- **Styling and tone**: Cool/ice-inspired accents are fine (e.g. blues, clean whites, subtle frost); keep it professional and sporty, not childish. Imagery and microcopy should feel at home in a rink/facility context.

**Tone reference — Spittin’ Chiclets–style context:** Align with the kind of hockey/rink culture that shows like *Spittin’ Chiclets* (Barstool’s hockey podcast) reflect: **hockey-first**, **casual and candid**, insider rink life rather than corporate-speak. Think rink rats, beer league, early-morning ice, tournament weekends, Zamboni, dressing rooms, “chiclets” (teeth) and the unfiltered, relatable vibe of people who live in rinks. Copy and use cases should feel authentic to that world—conversational, a bit irreverent where it fits, and grounded in real ice-sports scenarios (NHL, minor hockey, ringette, figure skating, curling, shinny, drop-in). Don’t mimic Barstool’s brand; do bias wording and examples toward that hockey/rink-insider feel so the product resonates with players, parents, and facility staff.

## App Layout

| App | Purpose |
|-----|--------|
| `core` | Home, auth (login/register), shared views/decorators/forms. |
| `bookings` | Core booking models (`Facility`, `Surface`, `Slot`, `Booking`, `BookingEvent`), slot generation, Stripe webhooks, notifications. |
| `facilities` | Facility manager UI: dashboard, register/edit facility, surfaces, hours, manual reserve, Stripe Connect. |
| `customers` | Customer UI: search, facility detail, availability, book flow, payment, my bookings. |

Models for facilities and bookings live in **`bookings`** (not `facilities`). `facilities` is the manager-facing app that uses those models.

## Conventions

- **Python**: Prefer type hints where helpful. Use `path` from `django.urls` (no `url()`). Follow existing patterns in each app.
- **Templates**: Extend `base.html`. Use DaisyUI classes; keep custom CSS minimal. **Use HTMX for dynamic behavior** (e.g. address autocomplete in `templates/components/`); avoid adding JS frameworks.
- **Forms**: Django forms in each app (`forms.py`). Use them in views and templates; avoid raw `request.POST` for validation.
- **Stripe**: Secrets and keys from `.env`; never commit. Facilities use Stripe Connect (Express); customers pay via PaymentIntent. Webhook: `bookings/stripe/webhook/`, event `payment_intent.succeeded`.
- **Env**: Copy `.env.example` to `.env`; required: `SECRET_KEY`, `DEBUG`, optional: `DATABASE_URL`, `STRIPE_*`, `EMAIL_BACKEND`, `ALLOWED_HOSTS`.

## Testing

- **Write tests when adding or changing behavior.** New features, views, forms, and model logic should have tests that verify they work.
- Use Django’s `TestCase` (and `RequestFactory` / `Client` for views). Put tests in each app’s `tests.py` (or `tests/` package if it grows).
- Run the full suite before considering a change done: `python manage.py test core bookings facilities customers`
- Prefer realistic ice-sports scenarios in test data (e.g. facilities named like “Maple Leaf Arena”, bookings for “hockey practice”, “public skate”).

## Useful Commands

- Run server: `python manage.py runserver`
- Migrations: `python manage.py migrate`
- Generate bookable slots: `python manage.py generate_slots --days 28`
- Tests: `python manage.py test core bookings facilities customers`

## Adding Features

- New models or fields → migrations in the app that owns the model (usually `bookings` for facility/booking/slot).
- New pages/views → appropriate app (`core`, `facilities`, `customers`), add URL, template, and view; use existing auth decorators and patterns. Prefer HTMX for any dynamic UI.
- Stripe changes → keep webhook idempotent and use existing helpers in `bookings` and `customers.stripe_payment` / `facilities.stripe_connect`.
- **Add or update tests** so the new or changed behavior is covered and the suite passes.
