// OPTIONAL. Not used by the Streamlit app.
// The app unlocks a $5 payment from the Checkout success URL.
// Deploy this later only if you want a backup for buyers who never return.
//
// Secrets come from the function environment. This file has no secret values.

import Stripe from "https://esm.sh/stripe@14.25.0?target=denonext";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY") ?? "", {
  apiVersion: "2024-06-20",
});

Deno.serve(async (req) => {
  const signature = req.headers.get("stripe-signature") ?? "";
  const body = await req.text();
  let event;
  try {
    event = await stripe.webhooks.constructEventAsync(
      body,
      signature,
      Deno.env.get("STRIPE_WEBHOOK_SECRET") ?? "",
    );
  } catch (_error) {
    return new Response("Invalid signature", { status: 400 });
  }

  if (event.type !== "checkout.session.completed") {
    return new Response(JSON.stringify({ received: true, ignored: event.type }), { status: 200 });
  }

  const session = event.data.object;
  if (session.mode !== "payment" || session.payment_status !== "paid") {
    return new Response(JSON.stringify({ received: true, ignored: "not a paid one-time session" }), { status: 200 });
  }

  const userId = session.client_reference_id || session.metadata?.user_id;
  if (!userId) {
    return new Response(JSON.stringify({ received: true, ignored: "missing user" }), { status: 200 });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const existing = await fetch(
    `${supabaseUrl}/rest/v1/user_profiles?user_id=eq.${encodeURIComponent(userId)}&select=subscription_status,stripe_checkout_session_id,is_paid_user`,
    { headers: { apikey: serviceKey, Authorization: `Bearer ${serviceKey}` } },
  );
  const rows = await existing.json();
  const profile = Array.isArray(rows) && rows.length > 0 ? rows[0] : null;
  if (profile && profile.stripe_checkout_session_id === session.id && profile.is_paid_user) {
    return new Response(JSON.stringify({ received: true, already_unlocked: true }), { status: 200 });
  }

  const status = String(profile?.subscription_status || "").toLowerCase();
  const patch: Record<string, unknown> = {
    is_paid_user: true,
    paid_via: "one_time",
    stripe_checkout_session_id: session.id,
  };
  if (status !== "active" && status !== "trialing") {
    patch.subscription_status = "one_time";
  }
  if (typeof session.customer === "string" && session.customer) {
    patch.stripe_customer_id = session.customer;
  }

  const saved = await fetch(
    `${supabaseUrl}/rest/v1/user_profiles?user_id=eq.${encodeURIComponent(userId)}`,
    {
      method: "PATCH",
      headers: {
        apikey: serviceKey,
        Authorization: `Bearer ${serviceKey}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify(patch),
    },
  );
  if (!saved.ok) {
    return new Response("Profile update failed", { status: 500 });
  }
  return new Response(JSON.stringify({ received: true, unlocked: true }), { status: 200 });
});
