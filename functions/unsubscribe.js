// GET /unsubscribe?t=TOKEN
export async function onRequestGet({ request, env }) {
  const t = new URL(request.url).searchParams.get("t") || "";
  let msg = "That link is not valid.";
  if (t) {
    const r = await env.DB.prepare(
      `UPDATE subscribers SET status='unsubscribed' WHERE token=?1`
    ).bind(t).run();
    if (r.meta && r.meta.changes > 0) msg = "You are unsubscribed.";
  }
  return new Response(`<!doctype html><meta charset="utf-8"><title>safeagi.ca</title>
<style>body{font-family:system-ui,sans-serif;background:#e6e9eb;display:grid;place-items:center;min-height:100vh;margin:0}
</style><main><h1>${msg}</h1><p><a href="/">Back to the guide</a></p></main>`,
  { headers: { "Content-Type": "text/html; charset=utf-8" } });
}
