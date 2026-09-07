// POST /subscribe  { email, lang }
// Stores a pending subscriber and sends a confirmation email (double opt-in).
const JSON_HEADERS = { "Content-Type": "application/json" };

function ok(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

export async function onRequestPost({ request, env }) {
  let data;
  try { data = await request.json(); } catch { return ok({ error: "bad json" }, 400); }

  const email = String(data.email || "").trim().toLowerCase();
  const lang  = data.lang === "zh" ? "zh" : "en";

  // basic validation
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) {
    return ok({ error: "invalid email" }, 400);
  }
  // honeypot: real users leave this empty
  if (data.company) return ok({ ok: true });

  // Turnstile (skip if not configured)
  if (env.TURNSTILE_SECRET && data.token) {
    const v = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST",
      body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: data.token })
    }).then(r => r.json()).catch(() => null);
    if (!v || !v.success) return ok({ error: "verification failed" }, 403);
  }

  const token = crypto.randomUUID();

  try {
    await env.DB.prepare(
      `INSERT INTO subscribers (email, token, lang) VALUES (?1, ?2, ?3)
       ON CONFLICT(email) DO UPDATE SET token = ?2, lang = ?3
       WHERE subscribers.status = 'unsubscribed'`
    ).bind(email, token, lang).run();
  } catch (e) {
    return ok({ error: "store failed" }, 500);
  }

  // send the confirmation email
  if (env.RESEND_API_KEY) {
    const url = `https://safeagi.ca/confirm?t=${token}`;
    const subject = lang === "zh" ? "确认订阅 safeagi.ca" : "Confirm your safeagi.ca subscription";
    const body = lang === "zh"
      ? `点击这里确认订阅：${url}\n\n如果你没有提交过这个邮箱，忽略这封信即可。`
      : `Confirm your subscription: ${url}\n\nIf you did not enter this address, ignore this email.`;
    await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { "Authorization": `Bearer ${env.RESEND_API_KEY}`, ...JSON_HEADERS },
      body: JSON.stringify({
        from: "AGI & ASI Safety <hello@safeagi.ca>",
        to: [email], subject, text: body
      })
    }).catch(() => {});
  }

  return ok({ ok: true });
}
