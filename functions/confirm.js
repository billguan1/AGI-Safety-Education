// GET /confirm?t=TOKEN
const JSON_HEADERS = { "Content-Type": "application/json" };
export async function onRequestGet({ request, env }) {
  const t = new URL(request.url).searchParams.get("t") || "";
  let msg = "That link is not valid.";
  if (t) {
    const r = await env.DB.prepare(
      `UPDATE subscribers SET status='confirmed', confirmed_at=datetime('now')
       WHERE token=?1 AND status='pending'`
    ).bind(t).run();
    if (r.meta && r.meta.changes > 0) {
      msg = "You are subscribed. Thank you.";
      // notify the owner
      if (env.RESEND_API_KEY) {
      const notifyTo = env.OWNER_EMAIL || "billguan1@gmail.com";
      const res = await fetch("https://api.resend.com/emails", {
        method: "POST",
        headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, ...JSON_HEADERS },
        body: JSON.stringify({
          from: "AGI & ASI Safety <hello@safeagi.ca>",
          to: [notifyTo],
          subject: "New safeagi.ca newsletter subscriber",
          text: `Someone just confirmed a subscription on safeagi.ca.\n\nToken: ${t}`
        })
      }).catch(e => { console.error("confirm-notify error:", e); });
      if (res && !res.ok) console.error("confirm-notify status:", res.status, await res.text());
      }
    } else msg = "This link has already been used, or it has expired.";
  }
  return new Response(page(msg), { headers: { "Content-Type": "text/html; charset=utf-8" } });
}
function page(msg) {
  return `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>safeagi.ca</title><style>body{font-family:system-ui,sans-serif;background:#e6e9eb;color:#12161a;
display:grid;place-items:center;min-height:100vh;margin:0;padding:24px}main{max-width:44ch;text-align:center}
a{color:#2233cc}</style><main><h1>${msg}</h1><p><a href="/">Back to the guide</a></p></main>`;
}
