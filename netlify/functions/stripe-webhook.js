const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

exports.handler = async (event) => {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }

  let stripeEvent;
  try {
    stripeEvent = stripe.webhooks.constructEvent(
      event.body,
      event.headers['stripe-signature'],
      process.env.STRIPE_WEBHOOK_SECRET
    );
  } catch (err) {
    console.error('Webhook signature verification failed:', err.message);
    return { statusCode: 400, body: `Webhook Error: ${err.message}` };
  }

  const session = stripeEvent.data.object;

  try {
    switch (stripeEvent.type) {

      case 'customer.subscription.created': {
        const customer = await stripe.customers.retrieve(session.customer);
        const priceId = session.items.data[0].price.id;

        // Determine tier from price amount
        const amount = session.items.data[0].price.unit_amount;
        const tier = amount >= 79900 ? 'elite' : 'featured';

        // Upsert vendor record
        const { error } = await supabase
          .from('vendors')
          .upsert({
            stripe_customer_id: session.customer,
            stripe_subscription_id: session.id,
            email: customer.email,
            vendor_name: customer.name || customer.email,
            tier,
            status: 'active',
            featured_since: new Date().toISOString(),
          }, { onConflict: 'stripe_customer_id' });

        if (error) throw error;
        console.log(`✅ Vendor activated: ${customer.email} — ${tier}`);
        break;
      }

      case 'customer.subscription.updated': {
        const amount = session.items.data[0].price.unit_amount;
        const tier = amount >= 79900 ? 'elite' : 'featured';
        const status = session.status === 'active' ? 'active' : 'cancelled';

        const { error } = await supabase
          .from('vendors')
          .update({ tier, status })
          .eq('stripe_subscription_id', session.id);

        if (error) throw error;
        console.log(`✅ Subscription updated: ${session.id} → ${status}`);
        break;
      }

      case 'customer.subscription.deleted': {
        const { error } = await supabase
          .from('vendors')
          .update({ status: 'cancelled' })
          .eq('stripe_subscription_id', session.id);

        if (error) throw error;
        console.log(`✅ Subscription cancelled: ${session.id}`);
        break;
      }

      default:
        console.log(`Unhandled event type: ${stripeEvent.type}`);
    }
  } catch (err) {
    console.error('Error processing webhook:', err);
    return { statusCode: 500, body: 'Internal Server Error' };
  }

  return { statusCode: 200, body: JSON.stringify({ received: true }) };
};
