# Retirement Audit

Streamlit app for a free retirement audit: score, dollar projections, and charts. A one-time **$5** unlock adds a written action plan, a PDF, 50 AI questions, and saved plans. There is no subscription for new purchases. People who already have an active Stripe subscription stay unlocked.

The audit, the score, the metrics, and the charts stay free. Free AI questions: 3. Paid AI questions: 50. The count is stored on the profile for a logged-in user so a refresh does not reset it.

## What you do by hand before this works in production

1. In Stripe, create a **$5 one-time Price** (one-time payment, not a recurring price). Copy the Price ID (`price_...`).
2. In Streamlit Community Cloud secrets, add `STRIPE_PRICE_ID_ONETIME` with that Price ID. Leave the existing secrets in place, including `STRIPE_PRICE_ID` and `STRIPE_SECRET_KEY`.
3. In the Supabase SQL editor, run [`supabase/migrations/20261126_one_time_unlock.sql`](supabase/migrations/20261126_one_time_unlock.sql).

Do not commit secret values. This repo does not contain any.

If a paid visitor returns from Checkout and the app says the profile did not change, the signed-in user cannot update their own `user_profiles` row. The migration file has a commented policy for that case. Read it against the policies you already have before enabling it.

## Secrets the app reads

| Name | Required to boot | Used for |
| --- | --- | --- |
| `SUPABASE_URL` | yes | Login and profiles |
| `SUPABASE_KEY` | yes | Login and profiles |
| `STRIPE_SECRET_KEY` | yes | Checkout and confirming a returned payment |
| `STRIPE_PRICE_ID` | yes | Kept so the current deploy still boots. New checkouts do not use it. |
| `APP_URL` | yes | Checkout success and cancel URLs |
| `STRIPE_PRICE_ID_ONETIME` | no | The $5 Price. Checkout will not start until this is set. The free audit still runs. |
| `OPENAI_API_KEY` | no | AI questions and the model-written action plan |

`APP_URL` should be the public app URL with no trailing path, for example `https://retirementaudit.streamlit.app`.

## How a $5 payment is recorded

Checkout is `mode="payment"` with the one-time price. The success URL includes the literal `{CHECKOUT_SESSION_ID}` placeholder. When the buyer comes back, the app retrieves that Checkout Session, requires `payment_status == "paid"`, and requires the session to match the logged-in user (`client_reference_id`, or email if the reference id is absent). It then sets `is_paid_user`, `paid_via = one_time`, and `stripe_checkout_session_id` on that profile. Opening the same success URL again does not write a second time.

An active or trialing `subscription_status` still counts as paid, including existing $1.99/month subscribers. A one-time unlock does not clear an active subscription status.

The Supabase auth session is kept in the Streamlit session so the return from Stripe can update the profile as that user.

## New `user_profiles` columns

Documented in the SQL migration:

- `paid_via` — `one_time` or `subscription`
- `stripe_checkout_session_id` — session already applied
- `stripe_customer_id` — Stripe customer, when Checkout created one
- `paid_at` — when the one-time unlock was first saved
- `ai_questions_used` — questions answered (free cap 3, paid cap 50)

The migration also marks current `active` and `trialing` rows as paid and sets `paid_via` to `subscription` when it is empty.

## Action plan and PDF

Paid results include a short plan with three parts: what to change first, how much to save, and a Social Security claiming note. The model call uses `gpt-4.1-mini` with temperature 0 and a fixed prompt. If that call is unavailable, the same three parts are filled from the audit math. Both versions say they are educational and do not guarantee returns. The PDF (fpdf2) contains the score, the main dollar results, the charts, and the plan.

## Optional webhook

[`supabase/functions/stripe-checkout-webhook/`](supabase/functions/stripe-checkout-webhook/) is a sample for `checkout.session.completed`. **The app does not need it.** Unlock works from the success URL. Deploy the function later only if you want a backup for buyers who never return to the app.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Put secrets in `.streamlit/secrets.toml`. That file is gitignored.

Screenshots and the automated tests can run with no secrets and no Stripe calls:

```bash
RETIREMENT_AUDIT_LOCAL_DEMO=1 streamlit run app.py
```

Do not set `RETIREMENT_AUDIT_LOCAL_DEMO` on Streamlit Cloud. It is ignored when the Stripe secret is a live key, and the demo login and stubbed Checkout run only when the app is also using the in-memory stand-in (no real Supabase URL). Useful local URLs:

- `/?demo_sample=1` — free results, score visible, unlock box after the charts
- `/?demo_sample=1&demo_ai_used=3` — same paywall again because the 3 free questions are used
- `/?demo_user=paid&demo_sample=1` — action plan and PDF download
- `/?demo_subscriber=1&demo_sample=1` — existing subscriber treated as unlocked
- `/?checkout=success&session_id=cs_demo_paid&demo_sample=1` — return-from-checkout path, no Stripe call

```bash
RETIREMENT_AUDIT_LOCAL_DEMO=1 python -m pytest tests
```
