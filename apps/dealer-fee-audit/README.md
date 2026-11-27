# Dealer Fee Audit

Streamlit entrypoint: `apps/dealer-fee-audit/app.py`. **Not deployed.** Nothing here is live until Jacob approves.

Type the line items from a dealer's out-the-door quote. Each line is sorted (taxes and government fees, doc fee,
destination, market adjustment, dealer add-ons, finance-office products, discounts, unclear) and given a neutral
verdict. Doc fees are compared to the 2026 limits published in 17 states plus the presumed-reasonable amount in
Texas and South Carolina (`fees.py`, dated `RULES_DATE`).

- **Free:** out-the-door total, number of items to question, dollars that are optional or above a state limit,
  a chart by category, and the top flagged line explained.
- **Paid, one-time $7:** every line explained with its state source, doc-fee check, monthly payment with and without
  the optional items, an editable message asking the dealer for a revised quote, questions to ask, PDF download.

The app never contacts a dealer, never says a fee is "illegal", and never asks for a name, VIN, SSN or account number.

## Secrets

| Name | Required to boot | Used for |
| --- | --- | --- |
| `SUPABASE_URL` | yes | Login, `dealer_fee_quotes`, `unlocks` |
| `SUPABASE_KEY` | yes | Anon key, used with the signed-in user's session |
| `STRIPE_SECRET_KEY` | yes | Creating the Checkout Session and confirming the return |
| `APP_URL` | yes | Checkout success and cancel URLs |
| `STRIPE_PRICE_ID_DEALERFEE` | no | The $7 one-time Price ID for this app. Checkout stays closed until set. |
| `DEALERFEE_UNLOCK_RECORD_TOKEN` | no | Matches the SHA-256 digest in `private.dealer_fee_unlock_gate`. Without it a paid return can't be recorded. |

It does not read `STRIPE_PRICE_ID_LOANAUDIT`, `STRIPE_PRICE_ID_ONETIME` or `UNLOCK_RECORD_TOKEN`. No ad pixels.

## Database

`supabase/migrations/20261129_dealer_fee_audit.sql` (not applied) adds `public.dealer_fee_quotes` with row-level security,
`private.dealer_fee_unlock_gate`, `public.record_dealer_fee_unlock(p_session_id, p_token)` and
`public.delete_my_dealer_fee_unlock()`. It reuses the existing `public.unlocks` table with product `dealer_fee_audit`.
Users can't write `unlocks` directly (that was locked down in `20261128_loan_unlock_server_write.sql`).

## Tests and local demo

```bash
python3 -m pytest tests
DEALER_FEE_AUDIT_LOCAL_DEMO=1 streamlit run app.py
```

Don't set `DEALER_FEE_AUDIT_LOCAL_DEMO` on Streamlit Cloud; it is ignored with a live Stripe key.

- `/?demo_sample=1` — free result for a sample Texas quote
- `/?demo_sample=1&demo_login=1&demo_terms=1` — paywall with the checkout button (does not contact Stripe)
- `/?demo_sample=1&demo_user=paid` — full report (`&demo_state=CA` for the California CARS Act notes)
- `/?demo_sample=1&demo_missing_price=1` — setup error for the missing price id
- `/?view=method`, `/?view=disclaimer`, `/?view=terms`, `/?view=privacy`
