# AGI & ASI Safety

A free, independently maintained field guide to AI safety, argued from first principles and sourced throughout. Available in English and Simplified Chinese.

Built and maintained by Bill Guan.

## What's here

| File | Purpose |
| --- | --- |
| `index.html` | English site. Self-contained: HTML, CSS, JS, and all SVG figures in one file. |
| `index-zh.html` | Simplified Chinese site. Same structure and figures. |
| `og-image.png` | Social share image (1200×630). |
| `robots.txt` | Crawl directives and sitemap pointer. |
| `sitemap.xml` | Both language versions with reciprocal `hreflang`. |

No build step, no dependencies, no framework. Edit the HTML and it ships.

## Deploying to Cloudflare Pages

1. Push this repo to GitHub.
2. In Cloudflare Pages, create a project from the repo.
3. Leave the build command empty and set the output directory to `/`.

Both pages go live immediately. The language toggle links `index.html` and `index-zh.html` relatively, so it works as long as they sit in the same directory.

## Before you go live

Search every file for `example.com` and replace it with your real domain: 13 occurrences in each HTML file (head tags plus the JSON-LD block), 2 in `robots.txt`, 9 in `sitemap.xml`. The head of each page carries an `EDIT ME` comment marking the spot. Until this is done, the canonical and `hreflang` tags point at the wrong place, which is worse for search engines than having none at all.

Also worth updating:

- The author line in the About section of each page (marked `EDIT ME`).
- `dateModified` in the JSON-LD block when you make substantive changes.
- The game URL, currently `https://ai-safety-game.billguan1-c4f.workers.dev/`.

## Editing notes

**Sources.** Citations live in one `<ol>` at the foot of each page. The list is auto-numbered by the browser, so entries must stay in ascending `id` order (`s1`, `s2`, …) or the rendered numbers stop matching the `<a href="#s12">12</a>` references in the body. If you add a source, append it and use the next number.

**Figures.** All 14 are inline SVG with an `aria-label` and a caption. Charts making quantitative claims also carry a `.fig-src` line linking to the primary source. Keep that pattern: the page's credibility rests on every number being checkable in one click.

**Reading routes.** The route chooser near the top collapses off-route chapters via a class toggle. Nothing is removed from the DOM, so all content stays crawlable and reachable regardless of the selected route.

**Translations.** The two files are structurally identical. When you change one, change the other, or the language toggle will drop readers somewhere that no longer matches.

## Style conventions

- No em dashes in English copy.
- Avoid "X, not Y" constructions.
- Claims that could be checked should carry a numbered source.
- Positions are framed as where the evidence points, never as settled verdicts.

## License

Site copy and figures © Bill Guan. Linked material belongs to its respective authors; this page summarises and points rather than reproducing.

Corrections and additions are welcome via issue or pull request.
