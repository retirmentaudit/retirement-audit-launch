# Optional later step: `checkout.session.completed` webhook

This function is **not required** for Retirement Audit to run or to unlock a $5 payment.

The Streamlit app unlocks the audit itself. On the success URL it retrieves the Checkout Session, checks `payment_status == "paid"`, checks that the session matches the logged-in user, and sets `is_paid_user` on that profile. Doing that twice is safe.

Add this function later if you also want the profile updated when a buyer pays but never lands back on the app. Until then, leave it undeployed.

## What it expects

Environment variables on the function (names only; do not commit the values):

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET` (the signing secret from the Stripe webhook endpoint)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Point the Stripe endpoint at `checkout.session.completed` only. The sample ignores every other event, and it ignores sessions that are not `mode=payment` with `payment_status=paid`.

The sample updates `user_profiles` by `user_id` (`client_reference_id`, then `metadata.user_id`). It sets `is_paid_user`, `paid_via = one_time`, and `stripe_checkout_session_id`. Run `supabase/migrations/20261126_one_time_unlock.sql` first.
