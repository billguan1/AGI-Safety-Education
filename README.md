# AGI & ASI Safety

A free, independently maintained field guide to why aligning advanced AI is an
unsolved technical and coordination problem, and what to do about it. Argued from
first principles, sourced throughout, in English and Simplified Chinese.

Live at **[safeagi.ca](https://safeagi.ca)**. Built and maintained by Bill Guan.

## What's here

| File | Purpose |
| --- | --- |
| `index.html` | English site. Self-contained: HTML, CSS, JS and all SVG in one file. |
| `index-zh.html` | Simplified Chinese site. Same structure and figures. |
| `functions/subscribe.js` | Pages Function. Validates an email, stores it as pending, sends a confirmation. |
| `functions/confirm.js` | `GET /confirm?t=TOKEN`. Completes double opt-in. |
| `functions/unsubscribe.js` | `GET /unsubscribe?t=TOKEN`. |
| `schema.sql` | D1 table for the mailing list. |
| `og-image.png` | Social share image, 1200×630. |
| `robots.txt` | Crawl directives and sitemap pointer. |
| `sitemap.xml` | Both languages with reciprocal `hreflang`. |
| `CONTEXT.md` | Handoff notes: architecture, conventions, fixed bugs, open work. |

Roughly 11,600 words across 14 sections, 25 figures and 55 numbered sources.
No build step, no dependencies, no framework.

## Deploying

Push to GitHub, then create a Cloudflare Pages project from the repo. Leave the
build command empty and set the output directory to `/`. Pages picks up
`functions/` automatically.

## Mailing list setup

The signup form posts to `/subscribe` on your own origin. To make it work:

1. **D1** → create a database named `safeagi`, open the console, run `schema.sql`.
2. **Bindings** → add the D1 database with variable name `DB`, for Production and
   Preview.
3. **Resend** → add `safeagi.ca` as a domain, add the SPF, DKIM and return-path
   records to Cloudflare DNS with the proxy off, then create an API key.
4. **Secrets** → add `RESEND_API_KEY` as an encrypted variable.
5. **Turnstile** (optional) → add `TURNSTILE_SECRET`. Without it the code skips
   the check and relies on the honeypot field.

Free tiers cover this comfortably: D1 gives 5GB, Pages Functions 100,000 requests
a day, Resend 3,000 emails a month.

Sending broadcasts is not built. Export confirmed subscribers from D1 and send
through Resend, or add a `functions/send.js` behind a secret header.

**Note:** Listmonk cannot run on Cloudflare. It needs a persistent process and
PostgreSQL, and Workers provide neither. The setup above replaces it.

If you email from Canada, CASL requires a physical mailing address in every
message. Double opt-in and unsubscribe are already handled.

## Editing notes

**Sources.** Citations live in one `<ol>` per page, auto-numbered by the browser.
Entries must stay in ascending `id` order or the rendered numbers stop matching
the `<a href="#s12">12</a>` references in the body. Append new sources and use the
next number.

**Figures.** All 25 are inline SVG with an `aria-label` and a caption. Charts
making quantitative claims also carry a `.fig-src` line linking to the primary
source. Keep that pattern: the page's credibility rests on every number being
checkable in one click.

**Technique cards.** Each shows a short summary with a toggle that swaps in the
full version in place. Beginners get the overview, experts get the depth.

**Reading routes.** The selector folds off-route chapters with a class toggle.
Nothing is removed from the DOM, so all content stays crawlable.

**Translations.** The two files are structurally identical. Change one, change the
other, or the language toggle will strand readers.

## Style conventions

- No em dashes, in either language. Chinese uses `，` `；` `。` rather than `——`.
- Avoid "X, not Y" constructions. Use "X rather than Y".
- Claims that can be checked carry a numbered source.
- Positions are framed as where the evidence points, never as verdicts.
- Prose measure 74ch, section heads 72ch, figures capped at 1040px.

## Before you change anything

Read `CONTEXT.md`. It lists seven bugs already found and fixed, with causes, and
the validation checks to run after any edit. Several were invisible to static
checks and only appeared when the page was executed in a real DOM.

## License

Site copy and figures © Bill Guan. Linked material belongs to its authors; this
page summarises and points rather than reproducing.

Corrections and additions welcome via issue or pull request.
