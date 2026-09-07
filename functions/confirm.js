// GET /confirm?t=TOKEN
export async function onRequestGet({ request, env }) {
  const t = new URL(request.url).searchParams.get("t") || "";
  let msg = "That link is not valid.";
  if (t) {
    const r = await env.DB.prepare(
      `UPDATE subscribers SET status='confirmed', confirmed_at=datetime('now')
       WHERE token=?1 AND status='pending'`
    ).bind(t).run();
    if (r.meta && r.meta.changes > 0) msg = "You are subscribed. Thank you.";
    else msg = "This link has already been used, or it has expired.";
  }
  return new Response(page(msg), { headers: { "Content-Type": "text/html; charset=utf-8" } });
}
function page(msg) {
  return `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>safeagi.ca</title><style>body{font-family:system-ui,sans-serif;background:#e6e9eb;color:#12161a;
display:grid;place-items:center;min-height:100vh;margin:0;padding:24px}main{max-width:44ch;text-align:center}
a{color:#2233cc}</style><main><h1>${msg}</h1><p><a href="/">Back to the guide</a></p></main>`;
}
