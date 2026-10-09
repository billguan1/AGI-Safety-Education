"""Share-preview (Open Graph) images for safeagi.ca, built from the deck's own cover.

    python3 tools/build_og.py

Renders the cover title and the cover drawing at 1200x630 in headless Chrome, once per
language, and names each file by its content hash (og-en-<hash>.png) so social sites
fetch the new image instead of a cached one. Then points index.html, index-zh.html,
the reference pages and 404.html at the new files, and adds them to the deploy
allowlist. Rebuild the deck afterwards (tools/build_deck.py) so it picks up the tags.
Run on a Mac with Google Chrome installed; CI does not run this.
"""
import hashlib, json, os, re, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
FONTS = {'en': 'https://fonts.googleapis.com/css2?family=Bangers&family=Comic+Neue:wght@700&display=swap',
         'zh': 'https://fonts.googleapis.com/css2?family=Bangers&family=Comic+Neue:wght@700&family=ZCOOL+KuaiLe&display=swap'}
USES = {'en': ['deck.html', 'index.html', 'reference.html', '404.html'], 'zh': ['deck-zh.html', 'index-zh.html', 'reference-zh.html']}

PAGE = '''<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="%(fonts)s"><style>
html,body{margin:0;width:1200px;height:630px;overflow:hidden;background:#f4ecd8}
.card{position:relative;width:1200px;height:630px;box-sizing:border-box;padding:30px 48px}
h1{margin:0;max-width:1104px;font-family:Bangers,"ZCOOL KuaiLe",sans-serif;font-weight:400;font-size:%(size)dpx;line-height:1.04;letter-spacing:.02em;color:#1b1b1b;text-shadow:4px 4px 0 rgba(27,27,27,.17)}
h1 .mh-hl{color:#d2553f}
.fig{position:absolute;left:160px;top:150px;width:880px}
.fig svg{display:block;width:880px;height:auto}
.url{position:absolute;left:48px;bottom:24px;font-family:"Comic Neue",sans-serif;font-weight:700;font-size:22px;color:#5c574e}
</style></head><body><div class="card"><h1>%(title)s</h1><div class="fig">%(svg)s</div><div class="url">safeagi.ca</div></div>
<script>document.fonts.ready.then(function(){setTimeout(function(){
  var r = function(e){ var b = e.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
  var h = document.querySelector("h1"), f = document.querySelector(".fig svg"), u = document.querySelector(".url");
  var out = {h1: r(h), fig: r(f), url: r(u), fonts: document.fonts.check("40px Bangers")};
  var p = document.createElement("pre"); p.id = "probe"; p.textContent = JSON.stringify(out); p.style.display = "none"; document.body.appendChild(p);
}, 300); });</script></body></html>'''

def cover(lang):
    s = open(os.path.join(ROOT, 'deck.html' if lang == 'en' else 'deck-zh.html'), encoding='utf-8').read()
    seg = s[s.index('data-key="cover"'):s.index('data-key="care"')]
    title = re.search(r'<h1 class="mh-title">(.*?)</h1>', seg, re.S).group(1)
    svg = re.search(r'<svg\b[^>]*viewBox="0 0 800 430".*?</svg>', seg, re.S).group(0)
    return title, svg

def chrome(url, *args):
    return subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1200,630',
                           '--virtual-time-budget=10000'] + list(args) + [url], capture_output=True, text=True).stdout

def build(lang):
    title, svg = cover(lang)
    html = PAGE % dict(fonts=FONTS[lang], title=title, svg=svg, size=52 if lang == 'en' else 56)
    tmp = tempfile.mkdtemp()
    page = os.path.join(tmp, 'og.html'); open(page, 'w', encoding='utf-8').write(html)
    probe = re.search(r'<pre id="probe"[^>]*>(.*?)</pre>', chrome('file://' + page, '--dump-dom'), re.S)
    assert probe, 'layout probe did not run'
    m = json.loads(probe.group(1))
    assert m['fonts'], 'display font did not load'
    assert m['h1'][2] <= 1160 and m['fig'][3] <= 630 and m['fig'][2] <= 1200, ('outside the frame', m)
    assert m['h1'][3] <= m['fig'][1] + 4, ('title runs into the drawing', m)
    assert m['url'][2] <= m['fig'][0] or m['url'][1] >= m['fig'][3] - 40, ('url label under the drawing', m)
    png = os.path.join(tmp, 'og.png'); chrome('file://' + page, '--screenshot=' + png)
    data = open(png, 'rb').read()
    assert data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) > 20000, 'screenshot failed'
    name = 'og-%s-%s.png' % (lang, hashlib.md5(data).hexdigest()[:8])
    open(os.path.join(ROOT, name), 'wb').write(data)
    return name, m

def point_at(lang, name):
    for f in USES[lang]:
        p = os.path.join(ROOT, f); s = open(p, encoding='utf-8').read()
        old = set(re.findall(r'og-%s-[0-9a-f]{8}\.png' % lang, s))
        assert old, (f, 'no share image found')
        for o in old: s = s.replace(o, name)
        open(p, 'w', encoding='utf-8').write(s)
    wf = os.path.join(ROOT, '.github', 'workflows', 'deploy.yml'); s = open(wf, encoding='utf-8').read()
    if name not in s:
        anchor = ' robots.txt sitemap.xml'
        assert s.count(anchor) == 1
        s = s.replace(anchor, ' ' + name + anchor, 1)
        open(wf, 'w', encoding='utf-8').write(s)

if __name__ == '__main__':
    for lang in ('en', 'zh'):
        name, m = build(lang)
        point_at(lang, name)
        print('wrote %s  title box %s  drawing box %s' % (name, [round(x) for x in m['h1']], [round(x) for x in m['fig']]))
