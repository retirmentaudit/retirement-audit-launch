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
3. In the Supabase SQL editor, run [`supabase/migrations/20261127_loan_plan_audit.sql`](../../supabase/migrations/20261127_loan_plan_audit.sql) if it is not already applied. Then run [`supabase/migrations/20261128_loan_unlock_server_write.sql`](../../supabase/migrations/20261128_loan_unlock_server_write.sql). The second file drops user writes on `unlocks`. A signed-in user can still read their own row. Inserts go through `record_loan_unlock`, which writes only for `auth.uid()` and only when the recording token matches. It does not change Retirement Audit's `user_profiles` or `scenarios` tables.
4. Choose a long random string (at least 16 characters). Put that exact string in the Streamlit secret `UNLOCK_RECORD_TOKEN`. In the Supabase SQL editor, store only its SHA-256 digest. Do not commit the string:

```sql
insert into private.loan_unlock_gate (id, token_sha256)
values (
  1,
  encode(extensions.digest(convert_to('PASTE_UNLOCK_RECORD_TOKEN', 'utf8'), 'sha256'), 'hex')
)
on conflict (id) do update set token_sha256 = excluded.token_sha256;
```

5. Set `APP_URL` to this app's public URL with no trailing path, for example `https://loanplanaudit.streamlit.app`.

The optional webhook sample at `supabase/functions/stripe-checkout-webhook/` can still insert a `loan_plan_audit` unlock with the Supabase service-role key after it checks the Stripe signature. It does not use `UNLOCK_RECORD_TOKEN`. Leave it undeployed unless you want a backup for buyers who never return. It does not change Retirement Audit profiles.

No service-role key is required in this Streamlit app. The anon key plus the signed-in user's session calls `record_loan_unlock`. A wrong token does not write a row.

### Residual risk

`record_loan_unlock` does not call Stripe. The Streamlit server retrieves the Checkout Session with `STRIPE_SECRET_KEY`, requires `payment_status = paid`, requires the Price ID to match `STRIPE_PRICE_ID_LOANAUDIT`, and requires the session to belong to the signed-in user. Only then does it pass `UNLOCK_RECORD_TOKEN`.

Someone who learns that token can call the function while logged in and store an unused `cs_...` session id. They can unlock only the account they are logged into. The token cannot read or write other tables. A leaked service-role key could, which is why this app does not use one.

The same Checkout Session cannot be applied to a second account. The database raises `session already used`, and the session id is unique. California and Illinois still do not get the paid report in the app, even if a row exists.

If the gate row is missing, or the token does not match its digest, recording fails and no row is written.

## Secrets

| Name | Required to boot | Used for |
| --- | --- | --- |
| `SUPABASE_URL` | yes | Login, `loan_scenarios`, `unlocks` |
| `SUPABASE_KEY` | yes | Login and those tables (anon key, with the user's session) |
| `STRIPE_SECRET_KEY` | yes | Creating the Checkout Session and confirming the return |
| `APP_URL` | yes | Checkout success and cancel URLs |
| `STRIPE_PRICE_ID_LOANAUDIT` | no | The $9 Price ID. Checkout will not start until this is set. The return URL also requires this price on the Checkout Session. |
| `UNLOCK_RECORD_TOKEN` | no | Shared with `private.loan_unlock_gate` as a SHA-256 digest. Without it, a paid return cannot be recorded. Not the service-role key. |
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
