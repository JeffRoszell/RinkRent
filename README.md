# RinkRent

A web app for finding and booking ice time for hockey, ringette, and other ice sports. Two sides: **facility managers** (rinks) and **customers** (teams/organizations).

## Tech stack

- Django (backend)
- HTMX + DaisyUI (frontend)
- Stripe (Connect for facilities, PaymentIntent for bookings)
- SQLite (default) or PostgreSQL

## Setup

1. Clone and create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. Copy environment template and set values:

   ```bash
   cp .env.example .env
   # Edit .env: SECRET_KEY, DEBUG=True, optional DATABASE_URL, STRIPE_* for payments
   ```

3. Run migrations and create a superuser:

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. (Optional) Create a facility and add yourself as manager via Django admin: `/admin/` → Facilities → add facility → add your user to "Managers". Add ice surfaces and hours of operation.

5. Generate slots (required for booking):

   ```bash
   python manage.py generate_slots --days 28
   ```

6. Run the server:

   ```bash
   python manage.py runserver
   ```

- **Customer side**: http://127.0.0.1:8000/ — search, book, my bookings.
- **Facility side**: http://127.0.0.1:8000/facility/ — dashboard (login as a facility manager).
- **Admin**: http://127.0.0.1:8000/admin/

## Stripe

- Set `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, and `STRIPE_WEBHOOK_SECRET` in `.env`.
- Facility managers connect Stripe via **Facility → Edit → Connect Stripe** (Stripe Connect Express).
- Configure webhook in Stripe Dashboard: URL `https://your-domain/bookings/stripe/webhook/`, event `payment_intent.succeeded`.

## Development

Install dev dependencies (linting):

```bash
pip install -r requirements-dev.txt
```

- **Lint:** `ruff check .`
- **Format:** `ruff format .` (or `ruff format --check .` in CI)
- **Tests:** `python manage.py test`

## CI

GitHub Actions runs on push/PR to `main` (or `master`): Ruff lint + format check, then Django tests with SQLite. See [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Deploy (free & easy): Render

RinkRent is set up to deploy on **[Render](https://render.com)** (free tier: web service + PostgreSQL). Free instances spin down after 15 minutes of inactivity (wake-up can take ~1 minute).

### One-click deploy

1. Push this repo to GitHub (or GitLab/Bitbucket).
2. Go to [Render Dashboard → Blueprints](https://dashboard.render.com/blueprints) and click **New Blueprint Instance**.
3. Connect the repo; Render will read `render.yaml` and create a **web service** and **PostgreSQL** database.
4. After the first deploy, in the web service → **Environment**, add:
   - `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` (from [Stripe Dashboard](https://dashboard.stripe.com)).
5. In the **Shell** tab for the web service, run:
   - `python manage.py createsuperuser` (admin account)
   - `python manage.py generate_slots --days 28` (then set up a [cron job](https://render.com/docs/cronjobs) to run this daily if you want ongoing slots).

Your app will be at `https://<service-name>.onrender.com`. Add that URL (and any custom domain) to Stripe webhooks: `https://<service-name>.onrender.com/bookings/stripe/webhook/`, event `payment_intent.succeeded`.

### Manual deploy

Create a **PostgreSQL** database and a **Web Service** (Python), set **Build Command** to `./build.sh`, **Start Command** to `gunicorn config.wsgi:application`, and add env vars: `DATABASE_URL` (from the DB), `SECRET_KEY` (generate), plus Stripe keys.
