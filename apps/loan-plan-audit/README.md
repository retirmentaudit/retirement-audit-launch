# Loan Plan Audit

An independent calculator that compares estimated payments under RAP, IBR, and Standard. It does not enroll anyone in a plan, contact a servicer, or recommend a plan.

The free page shows the first-year monthly estimate. The full report is a **one-time $9** software purchase: lifetime comparison, payoff timeline, what-if sliders, a PDF, a share card, and saved scenarios. There is no subscription.

California and Illinois residents can use the free comparison. The paid report and Checkout are not offered for those states.

## Streamlit app entry

On Streamlit Community Cloud, set the main file to:

```text
apps/loan-plan-audit/app.py
```

Run it locally from this folder so the light theme in `.streamlit/config.toml` loads:

```bash
pip install -r requirements.txt
streamlit run app.py
```

From the repo root:

```bash
streamlit run apps/loan-plan-audit/app.py
```

## What Jacob configures

Do not commit secret values. This app does **not** create Stripe products or prices. Create them in the Stripe Dashboard, then paste the Price ID.

1. In Stripe, create a one-time Price for **$9** (not a recurring price) on a product such as "Loan Plan Audit — Full Report". Copy the Price ID (`price_...`).
2. In the Streamlit app's secrets, set `STRIPE_PRICE_ID_LOANAUDIT` to that Price ID. If it is missing, the free calculator still runs and Checkout shows a setup error. The app will not call Stripe to create a product or a price.
3. In the Supabase SQL editor, run [`supabase/migrations/20261127_loan_plan_audit.sql`](../../supabase/migrations/20261127_loan_plan_audit.sql). That creates `loan_scenarios` and `unlocks`, both with owner-only row level security. It does not change Retirement Audit's `user_profiles` or `scenarios` tables.
4. Set `APP_URL` to this app's public URL with no trailing path, for example `https://loanplanaudit.streamlit.app`.

The optional webhook sample at `supabase/functions/stripe-checkout-webhook/` now sends `metadata.product = loan_plan_audit` to `public.unlocks` and leaves Retirement Audit profiles alone. The app does not need the webhook. Unlock works from the Checkout success URL. Deploy the function only as a backup, after the migration.

## Secrets

| Name | Required to boot | Used for |
| --- | --- | --- |
| `SUPABASE_URL` | yes | Login, `loan_scenarios`, `unlocks` |
| `SUPABASE_KEY` | yes | Login and those tables (anon key, with the user's session) |
| `STRIPE_SECRET_KEY` | yes | Creating the Checkout Session and confirming the return |
| `APP_URL` | yes | Checkout success and cancel URLs |
| `STRIPE_PRICE_ID_LOANAUDIT` | no | The $9 Price ID. Checkout will not start until this is set. |
| `OPENAI_API_KEY` | no | The question box. Without it, the box says it is not configured. |

`STRIPE_PRICE_ID_ONETIME` is the Retirement Audit price. This app does not read it.

There are no ad pixels. The app never asks for an SSN, an FSA ID, or a servicer login.

## Tests and screenshots

```bash
python3 -m pytest tests
```

Screenshots without live Stripe or Supabase:

```bash
LOAN_PLAN_AUDIT_LOCAL_DEMO=1 streamlit run app.py
```

Do not set `LOAN_PLAN_AUDIT_LOCAL_DEMO` on Streamlit Cloud. It is ignored when the Stripe secret is a live key.

- `/?demo_sample=1` — free results for a $40,000 loan and $53,000 AGI (RAP shows $221)
- `/?demo_sample=1&demo_user=paid` — full report
- `/?demo_sample=1&demo_state=CA` — free results and the state note, no Checkout
- `/?demo_sample=1&demo_missing_price=1` — setup error for the missing price id
- `/?view=terms` and `/?view=privacy` — drafts with `[placeholders]` still visible
