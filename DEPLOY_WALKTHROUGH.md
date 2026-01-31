# RinkRent: GitHub + first Render deploy

Follow these steps in order.

---

## Part 1: Put the project on GitHub

### Step 1.1 – Create the repo on GitHub (in your browser)

1. Go to **https://github.com/new**
2. **Repository name:** `RinkRent` (or whatever you prefer)
3. **Description (optional):** e.g. "Ice rink booking for hockey, ringette, etc."
4. Choose **Public**
5. **Do not** check "Add a README" or ".gitignore" (this project already has them)
6. Click **Create repository**

### Step 1.2 – Connect and push from your machine

Git is already initialized and the first commit is made. In your project folder, run (replace `YOUR_USERNAME` with your GitHub username):

```bash
cd "/Users/jeff/Documents/Personal Projects/RinkRent"
git remote add origin https://github.com/YOUR_USERNAME/RinkRent.git
git branch -M main
git push -u origin main
```

If GitHub prompts for login, use your GitHub account (or a [Personal Access Token](https://github.com/settings/tokens) if you use 2FA).

---

## Part 2: First deployment on Render

### Step 2.1 – Create the app from the Blueprint

1. Go to **https://dashboard.render.com**
2. Sign up or log in (e.g. "Sign up with GitHub" so Render can see your repos)
3. In the left sidebar, open **Blueprints**
4. Click **New Blueprint Instance**
5. Connect your GitHub account if asked, then select the **RinkRent** repo
6. Click **Connect**
7. Render will read `render.yaml` and show:
   - 1 PostgreSQL database (`rinkrent-db`)
   - 1 Web Service (`rinkrent`)
8. **Blueprint name** can stay as-is (e.g. "RinkRent")
9. Click **Apply**

Render will create the database and web service and start the first build. This can take a few minutes.

### Step 2.2 – Add Stripe and finish env (after first deploy)

1. In the Render dashboard, open your **rinkrent** web service (not the database)
2. Go to **Environment**
3. Add these (get values from [Stripe Dashboard](https://dashboard.stripe.com) → Developers → API keys / Webhooks):
   - `STRIPE_SECRET_KEY` = sk_live_... or sk_test_...
   - `STRIPE_PUBLISHABLE_KEY` = pk_live_... or pk_test_...
   - `STRIPE_WEBHOOK_SECRET` = whsec_... (create a webhook first; see below)
4. Click **Save Changes** (Render will redeploy once)

**Webhook for payments:**

1. In Stripe Dashboard → **Developers → Webhooks** → **Add endpoint**
2. **Endpoint URL:** `https://<your-app-name>.onrender.com/bookings/stripe/webhook/`  
   (Replace `<your-app-name>` with your Render service name, e.g. `rinkrent-xxxx`.)
3. **Events to send:** `payment_intent.succeeded`
4. Create the endpoint, then copy the **Signing secret** (whsec_...) into `STRIPE_WEBHOOK_SECRET` on Render.

### Step 2.3 – Create admin user and generate slots

1. In Render, open your **rinkrent** web service
2. Open the **Shell** tab (top right)
3. In the shell, run:

```bash
python manage.py createsuperuser
```

Enter username, email, and password when prompted.

4. Then run:

```bash
python manage.py generate_slots --days 28
```

5. Close the shell when done.

### Step 2.4 – Open the app

- Your app URL is: **https://&lt;your-service-name&gt;.onrender.com**
- Homepage: same URL
- Admin: **https://&lt;your-service-name&gt;.onrender.com/admin/** (log in with the superuser you just created)
- Facility dashboard: same URL + **/facility/** (log in as a user who is a facility manager)

---

## Part 3: Optional – cron for slot generation

To keep generating new slots (e.g. daily):

1. In Render dashboard, open your **rinkrent** web service
2. Go to **Cron Jobs** (or **Background Workers** depending on plan)
3. Add a cron job:
   - **Command:** `python manage.py generate_slots --days 28`
   - **Schedule:** e.g. daily at 2am (`0 2 * * *`)

(Exact UI may vary; free tier may have limits on cron.)

---

## Troubleshooting

- **Build fails:** Check the **Logs** tab for the web service. Common issues: missing env var, `DATABASE_URL` not set (it should be set automatically by the Blueprint).
- **502 / app won’t start:** Ensure **Start Command** is `gunicorn config.wsgi:application` and that the build (including `build.sh`) finished successfully.
- **Static files missing:** The build runs `collectstatic`; if something’s wrong, check the build logs for errors during that step.
- **Cold starts:** On the free tier the app sleeps after ~15 minutes of no traffic; the first request after that can take ~1 minute.
