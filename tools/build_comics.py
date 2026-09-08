#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the comic.safeagi.ca static site from comics_generated/.

Adding a comic is: drop a folder into comics_generated/ with the page images
and a story.json beside them, then run this. Nothing central needs editing.

    comics_generated/
      comic1/
        story.json          title, slug, concept, per-page alt text
        comic1_P1.jpeg
        comic1_P2.jpeg

Output goes to comic-site/, which is generated and never edited by hand.
"""
import datetime, json, os, re, shutil, subprocess, sys, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, 'comics_generated')
OUT  = os.path.join(ROOT, 'comic-site')
ORIGIN = 'https://comic.safeagi.ca'
SITE   = 'https://safeagi.ca'

FONTS = ('https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800;900'
         '&family=Newsreader:opsz,wght@6..72,300;6..72,400;6..72,500'
         '&family=IBM+Plex+Mono:wght@400;500;600&display=swap')

# Capy's hexagonal collar tag, the series continuity anchor, reused as the mark.
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
           "%3Crect width='32' height='32' fill='%23efe6d4'/%3E"
           "%3Cpath d='M16 5l9 5.5v11L16 27l-9-5.5v-11z' fill='none' stroke='%231a1714' stroke-width='2.6'/%3E"
           "%3C/svg%3E")

CSS = """
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
:root{
  --paper:#efe6d4; --card:#f8f3e7; --ink:#1a1714; --ink-2:#4a423a; --ink-3:#7d7266;
  --rule:#d8cbb2; --rule-2:#c2b295; --red:#c4462c; --gold:#d9a026; --blue:#316f96;
  --display:"Archivo",system-ui,sans-serif;
  --body:"Newsreader",Georgia,serif;
  --mono:"IBM Plex Mono",ui-monospace,monospace;
  --gut:clamp(18px,5vw,48px); --maxw:1080px;
}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);font-weight:300;
  font-size:17px;line-height:1.6;-webkit-font-smoothing:antialiased;
  background-image:radial-gradient(rgba(120,100,70,.055) 1px,transparent 1px);background-size:3px 3px}
img{display:block;max-width:100%;height:auto}
a{color:var(--blue);text-underline-offset:.18em}
a:hover{color:var(--ink)}
:focus-visible{outline:2.5px solid var(--red);outline-offset:3px}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 var(--gut)}
.skip{position:absolute;left:-9999px;background:var(--ink);color:var(--paper);padding:12px 18px;z-index:99;font-family:var(--mono);font-size:13px}
.skip:focus{left:8px;top:8px}
h1,h2,h3{font-family:var(--display);font-weight:800;letter-spacing:-.028em;line-height:1.04;margin:0}
.kick{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.17em;text-transform:uppercase;color:var(--ink-3);margin:0 0 14px}

/* ---------- masthead ---------- */
.top{border-bottom:2px solid var(--ink);background:var(--card)}
.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;padding-top:14px;padding-bottom:14px}
.mark{display:inline-flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink)}
.mark svg{width:22px;height:22px;flex:0 0 22px}
.mark b{font-family:var(--display);font-weight:900;letter-spacing:.02em;font-size:19px}
.mark span{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.top nav{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase}
.top nav a{color:var(--ink-2);text-decoration:none;border-bottom:1.5px solid var(--rule-2);padding-bottom:2px}
.top nav a:hover{color:var(--ink);border-color:var(--ink)}

/* ---------- hero ---------- */
.hero{padding:clamp(38px,7vw,74px) 0 clamp(28px,4vw,44px)}
.hero h1{font-size:clamp(38px,9vw,78px)}
.hero .sub{font-size:clamp(18px,2.4vw,23px);line-height:1.45;color:var(--ink-2);max-width:44ch;margin:18px 0 0}
.hero .meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}
.tag{font-family:var(--mono);font-size:10.5px;font-weight:600;letter-spacing:.11em;text-transform:uppercase;
  border:1.5px solid var(--rule-2);border-radius:999px;padding:6px 13px;color:var(--ink-2);background:var(--card)}

/* ---------- gallery ---------- */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:clamp(18px,3vw,30px);align-items:start;
  padding:clamp(10px,2vw,18px) 0 clamp(50px,8vw,90px)}
.card{display:flex;flex-direction:column;text-decoration:none;color:inherit;background:var(--card);
  border:2px solid var(--ink);box-shadow:5px 5px 0 rgba(26,23,20,.16);transition:transform .16s,box-shadow .16s}
.card:hover{transform:translate(-2px,-2px);box-shadow:8px 8px 0 rgba(26,23,20,.22);color:inherit}
.card .cover{position:relative;border-bottom:2px solid var(--ink);background:var(--paper);aspect-ratio:864/1248;overflow:hidden}
.card .cover img{width:100%;height:100%;object-fit:cover;object-position:top center}
.card .no{position:absolute;top:0;left:0;font-family:var(--display);font-weight:900;font-size:13px;letter-spacing:.06em;
  background:var(--ink);color:var(--paper);padding:6px 11px}
.card .body{padding:15px 16px 18px}
.card h3{font-size:22px;margin:0 0 7px}
.card .concept{font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--red);margin:0 0 9px}
.card .tl{font-size:14.5px;line-height:1.5;color:var(--ink-2);margin:0}
.card .go{margin-top:13px;font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--blue)}
.card .go::after{content:" \\2192"}
.soon{display:flex;align-items:center;justify-content:center;text-align:center;border:2px dashed var(--rule-2);
  background:transparent;box-shadow:none;padding:44px 24px}
.soon:hover{transform:none;box-shadow:none}
.soon p{font-family:var(--mono);font-size:11.5px;line-height:1.7;letter-spacing:.04em;color:var(--ink-3);margin:0}

/* ---------- reader ---------- */
.read{padding:clamp(26px,5vw,52px) 0 0}
.read .no{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-3);margin:0 0 10px}
.read h1{font-size:clamp(32px,6.5vw,58px)}
.read .tl{font-size:clamp(17px,2vw,20px);line-height:1.5;color:var(--ink-2);max-width:48ch;margin:14px 0 0}
.pages{padding:clamp(26px,4.5vw,44px) 0}
.pg img{width:100%}
.pg{margin:0 auto clamp(22px,3.5vw,36px);max-width:900px;border:2px solid var(--ink);box-shadow:6px 6px 0 rgba(26,23,20,.16);background:var(--card)}
.pg:last-child{margin-bottom:0}
.pgn{font-family:var(--mono);font-size:10.5px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;
  color:var(--ink-3);max-width:900px;margin:0 auto 8px;padding-top:4px}
.about{max-width:900px;margin:clamp(30px,5vw,54px) auto 0;background:var(--card);border:2px solid var(--ink);padding:clamp(20px,3.4vw,30px)}
.about h2{font-size:clamp(20px,2.8vw,26px);margin:0 0 12px}
.about p{margin:0 0 14px;color:var(--ink-2);max-width:66ch}
.about p:last-child{margin-bottom:0}
.about .chip{display:inline-block;font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.1em;
  text-transform:uppercase;color:var(--red);border:1.5px solid var(--red);border-radius:999px;padding:4px 11px;margin-bottom:13px}
.ends{display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;align-items:center;
  max-width:900px;margin:clamp(24px,4vw,40px) auto 0;padding-bottom:clamp(46px,7vw,80px)}
.btn{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:.11em;text-transform:uppercase;
  text-decoration:none;border:2px solid var(--ink);background:var(--card);color:var(--ink);padding:11px 17px;
  box-shadow:3px 3px 0 rgba(26,23,20,.18);transition:transform .14s,box-shadow .14s}
.btn:hover{color:var(--ink);transform:translate(-1px,-1px);box-shadow:5px 5px 0 rgba(26,23,20,.24)}
.btn.q{border-style:dashed;box-shadow:none;color:var(--ink-3);cursor:default}
.btn.q:hover{transform:none;box-shadow:none}

/* ---------- footer ---------- */
footer{border-top:2px solid var(--ink);background:var(--card);padding:26px 0 34px}
footer p{font-family:var(--mono);font-size:11.5px;line-height:1.75;color:var(--ink-3);margin:0 0 8px;max-width:70ch}
footer p:last-child{margin-bottom:0}
@media(max-width:560px){
  .top .wrap{flex-direction:column;align-items:flex-start;gap:9px}
  .pg,.ends,.about,.pgn{max-width:100%}
}
"""

HEX = ('<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
       '<path d="M16 4l10.4 6v12L16 28 5.6 22V10z" fill="none" stroke="currentColor" stroke-width="2.6"/></svg>')


def esc(s):
    return html.escape(s, quote=True)


def shell(title, desc, canonical, og_image, body, extra_head=''):
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(canon)s">
<link rel="icon" href="%(fav)s">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Capy">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(canon)s">
<meta property="og:image" content="%(og)s">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="%(fonts)s">
<style>%(css)s</style>
%(extra)s
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top">
  <div class="wrap">
    <a class="mark" href="/"><span class="hx">%(hex)s</span><b>CAPY</b><span>An AI safety comic</span></a>
    <nav><a href="%(site)s">safeagi.ca</a></nav>
  </div>
</header>
<main id="main">
%(body)s
</main>
<footer>
  <div class="wrap">
    <p>Capy is a comic series about how machine systems fail. The ideas come from safeagi.ca, where every
       claim is linked to a primary source. The stories are made up. The failure modes are not.</p>
    <p>Built and maintained by Bill Guan. <a href="%(site)s">Read the full argument</a></p>
  </div>
</footer>
</body>
</html>
""" % dict(title=esc(title), desc=esc(desc), canon=canonical, og=og_image, fonts=FONTS,
           css=CSS, hex=HEX, body=body, site=SITE, fav=FAVICON, extra=extra_head)


def _pillow():
    try:
        from PIL import Image
        return Image
    except Exception:
        return None


def compress(src_path, dst_path):
    """Re-encode. The generator output runs about 1 MB a page, which is a lot to
    push at a phone for something the reader scrolls straight past.

    Pillow first so this behaves identically on the Linux runner and on a Mac.
    sips is the local fallback when Pillow is not installed."""
    before = os.path.getsize(src_path)
    Image = _pillow()
    done = False
    if Image:
        try:
            im = Image.open(src_path)
            im.convert('RGB').save(dst_path, 'JPEG', quality=72, optimize=True, progressive=True)
            done = True
        except Exception:
            done = False
    if not done:
        try:
            subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '68',
                            src_path, '--out', dst_path], check=True, capture_output=True)
            done = True
        except Exception:
            done = False
    if not done:
        shutil.copy2(src_path, dst_path)
    after = os.path.getsize(dst_path)
    if after >= before:                       # never ship a bigger file than we were handed
        shutil.copy2(src_path, dst_path)
        after = before
    return before, after


def dimensions(path):
    Image = _pillow()
    if Image:
        try:
            with Image.open(path) as im:
                return im.size
        except Exception:
            pass
    try:
        out = subprocess.run(['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', path],
                             check=True, capture_output=True, text=True).stdout
        return (int(re.search(r'pixelWidth:\s*(\d+)', out).group(1)),
                int(re.search(r'pixelHeight:\s*(\d+)', out).group(1)))
    except Exception:
        return None, None


def load_stories():
    stories, skipped = [], []
    for name in sorted(os.listdir(SRC)):
        d = os.path.join(SRC, name)
        if not os.path.isdir(d):
            continue
        meta = os.path.join(d, 'story.json')
        if not os.path.isfile(meta):
            skipped.append(name)
            continue
        s = json.load(open(meta, encoding='utf-8'))
        s['dir'] = d
        s.setdefault('slug', name)
        s.setdefault('number', 0)
        missing = [p['file'] for p in s['pages'] if not os.path.isfile(os.path.join(d, p['file']))]
        if missing:
            sys.exit('%s/story.json lists pages that are not in the folder: %s' % (name, ', '.join(missing)))
        stories.append(s)
    stories.sort(key=lambda s: s['number'])
    return stories, skipped


def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    stories, skipped = load_stories()
    if not stories:
        sys.exit('No stories found in comics_generated/. Each comic needs a story.json.')

    saved = 0
    for i, s in enumerate(stories):
        sd = os.path.join(OUT, s['slug'])
        os.makedirs(sd)
        for n, pg in enumerate(s['pages'], 1):
            out_name = 'page-%d.jpeg' % n
            b, a = compress(os.path.join(s['dir'], pg['file']), os.path.join(sd, out_name))
            saved += b - a
            pg['out'] = out_name
            pg['w'], pg['h'] = dimensions(os.path.join(sd, out_name))
        write_story(s, stories, i)

    write_gallery(stories)
    write_404()
    write_extras(stories)
    print('Built %d %s into comic-site/' % (len(stories), 'story' if len(stories) == 1 else 'stories'))
    for s in stories:
        print('  %02d  %-16s %d page(s)  ->  /%s/' % (s['number'], s['title'], len(s['pages']), s['slug']))
    print('  images shrunk by %.1f MB' % (saved / 1048576.0))
    if skipped:
        print('  skipped (no story.json): %s' % ', '.join(skipped))


def write_story(s, stories, i):
    pages = []
    for n, pg in enumerate(s['pages'], 1):
        dim = (' width="%d" height="%d"' % (pg['w'], pg['h'])) if pg['w'] else ''
        lazy = '' if n == 1 else ' loading="lazy"'
        pages.append(
            '  <p class="pgn">Page %d of %d</p>\n'
            '  <div class="pg"><img src="%s" alt="%s"%s%s decoding="async"></div>'
            % (n, len(s['pages']), pg['out'], esc(pg['alt']), dim, lazy))

    link = s.get('siteLink')
    more = ('<p><a href="%s">%s</a> on safeagi.ca goes into it properly.</p>'
            % (link['url'], esc(link['label']))) if link else ''

    nxt = stories[i + 1] if i + 1 < len(stories) else None
    nav = ('<a class="btn" href="/%s/">Next: %s</a>' % (nxt['slug'], esc(nxt['title']))
           if nxt else '<span class="btn q">Next one is being drawn</span>')

    og = '%s/%s/%s' % (ORIGIN, s['slug'], s['pages'][0]['out'])
    schema = json.dumps({
        "@context": "https://schema.org", "@type": "ComicStory",
        "name": s['title'], "position": s['number'],
        "description": s['tagline'],
        "url": '%s/%s/' % (ORIGIN, s['slug']),
        "image": og,
        "author": {"@type": "Person", "name": "Bill Guan"},
        "isPartOf": {"@type": "CreativeWorkSeries", "name": "Capy", "url": ORIGIN + '/'},
        "numberOfPages": len(s['pages']),
    }, ensure_ascii=False)

    body = """<section class="read"><div class="wrap">
  <p class="no">Number %02d</p>
  <h1>%s</h1>
  <p class="tl">%s</p>
</div></section>

<section class="pages"><div class="wrap">
%s

  <div class="about">
    <span class="chip">%s</span>
    <h2>What went wrong</h2>
    <p>%s</p>
    %s
  </div>

  <div class="ends">
    <a class="btn" href="/">All stories</a>
    %s
  </div>
</div></section>""" % (s['number'], esc(s['title']), esc(s['tagline']), '\n'.join(pages),
                       esc(s['concept']), esc(s['about']), more, nav)

    html_out = shell('%s: Capy number %02d' % (s['title'], s['number']),
                     s['tagline'], '%s/%s/' % (ORIGIN, s['slug']), og, body,
                     '<script type="application/ld+json">%s</script>' % schema)
    open(os.path.join(OUT, s['slug'], 'index.html'), 'w', encoding='utf-8').write(html_out)


def write_gallery(stories):
    cards = []
    for s in stories:
        cards.append(
            '    <a class="card" href="/%s/">\n'
            '      <div class="cover"><span class="no">%02d</span>'
            '<img src="/%s/%s" alt="Cover of %s" loading="lazy" decoding="async"></div>\n'
            '      <div class="body">\n'
            '        <p class="concept">%s</p>\n'
            '        <h3>%s</h3>\n'
            '        <p class="tl">%s</p>\n'
            '        <p class="go">Read it</p>\n'
            '      </div>\n    </a>'
            % (s['slug'], s['number'], s['slug'], s['pages'][0]['out'], esc(s['title']),
               esc(s['concept']), esc(s['title']), esc(s['tagline'])))
    cards.append('    <div class="card soon"><p>More on the way.<br>One idea, two pages,<br>nobody explains the moral.</p></div>')

    body = """<section class="hero"><div class="wrap">
  <p class="kick">A comic about machines doing exactly what they were told</p>
  <h1>Capy grants<br>your wish.</h1>
  <p class="sub">Kenji asks for something reasonable. Capy the capybara carries it out precisely.
     That is where the trouble starts, every time.</p>
  <div class="meta"><span class="tag">%d %s</span><span class="tag">Two pages each</span><span class="tag">No moral in a caption</span></div>
</div></section>

<div class="wrap">
  <div class="grid">
%s
  </div>
</div>""" % (len(stories), 'story' if len(stories) == 1 else 'stories', '\n'.join(cards))

    og = '%s/%s/%s' % (ORIGIN, stories[0]['slug'], stories[0]['pages'][0]['out'])
    schema = json.dumps({
        "@context": "https://schema.org", "@type": "CreativeWorkSeries",
        "name": "Capy", "url": ORIGIN + '/',
        "description": "A comic series about AI systems that do exactly what they were asked.",
        "author": {"@type": "Person", "name": "Bill Guan"},
    }, ensure_ascii=False)
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(
        shell('Capy: an AI safety comic',
              'Kenji asks for something reasonable. Capy carries it out precisely. That is where the trouble starts.',
              ORIGIN + '/', og, body,
              '<script type="application/ld+json">%s</script>' % schema))


def write_404():
    """Without a 404.html, Pages falls back to serving index.html with a 200,
    so every mistyped URL becomes a duplicate of the homepage."""
    body = """<section class="hero"><div class="wrap">
  <p class="kick">Error 404</p>
  <h1>Removed.</h1>
  <p class="sub">Objects reduce tidiness. Nothing lives at this address, which is either a broken link
     or a page that was never here.</p>
  <div class="meta" style="margin-top:26px"><a class="btn" href="/">Back to the stories</a></div>
</div></section>"""
    open(os.path.join(OUT, '404.html'), 'w', encoding='utf-8').write(
        shell('Not found', 'Nothing lives at this address.', ORIGIN + '/404', ORIGIN + '/', body,
              '<meta name="robots" content="noindex">'))


def write_extras(stories):
    open(os.path.join(OUT, 'robots.txt'), 'w').write(
        'User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n' % ORIGIN)
    today = datetime.date.today().isoformat()
    urls = ['%s/' % ORIGIN] + ['%s/%s/' % (ORIGIN, s['slug']) for s in stories]
    body = '\n'.join('  <url><loc>%s</loc><lastmod>%s</lastmod></url>' % (u, today) for u in urls)
    open(os.path.join(OUT, 'sitemap.xml'), 'w').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % body)


if __name__ == '__main__':
    build()
