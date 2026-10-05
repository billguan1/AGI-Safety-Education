#!/usr/bin/env python3
"""Build the comic slide deck from the long pages.

    python3 tools/build_deck.py            writes deck.html and deck-zh.html

index.html and index-zh.html stay the content source. This script cuts each
section into slides, adds Kenji's narration and the chapter navigation, redraws
the charts for cream paper, and keeps every site script so the quizzes, forms,
share buttons and card folding work as they do on the long page. Slide copy
that exists only in the deck (narration, part headings, buttons) lives in
tools/deck/text.py. Styles and deck behaviour live in tools/deck/deck.css and
tools/deck/deck.js.
"""
import re, os, sys, html, colorsys, json, ast
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'deck'))
import text as TXT                      # noqa: E402  (deck-only copy, both languages)

PAGES = {'en': ('index.html', 'deck.html'), 'zh': ('index-zh.html', 'deck-zh.html')}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}


# ---------------------------------------------------------------- html helpers
def children(frag):
    """(start, end) spans of the top-level elements of an HTML fragment."""
    lines = frag.split('\n'); offs = [0]
    for l in lines[:-1]: offs.append(offs[-1] + len(l) + 1)

    class P(HTMLParser):
        def __init__(p): super().__init__(convert_charrefs=False); p.d = 0; p.spans = []; p.cur = None
        def pos(p): ln, col = p.getpos(); return offs[ln - 1] + col
        def handle_starttag(p, t, a):
            if t in VOID:
                if p.d == 0: p.spans.append((p.pos(), frag.index('>', p.pos()) + 1))
                return
            if p.d == 0: p.cur = p.pos()
            p.d += 1
        def handle_startendtag(p, t, a):
            if p.d == 0: p.spans.append((p.pos(), frag.index('>', p.pos()) + 1))
        def handle_endtag(p, t):
            if t in VOID: return
            p.d -= 1
            if p.d == 0: p.spans.append((p.cur, frag.index('>', p.pos()) + 1))
    p = P(); p.feed(frag)
    assert p.d == 0, 'unbalanced fragment'
    return p.spans

def kids(el):
    inn = inner(el); return [inn[x:y] for x, y in children(inn)]

def inner(el): return el[el.index('>') + 1: el.rindex('<')]

def text(frag): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', frag))).strip()

def one(blocks, prefix, n=0):
    hits = [b for b in blocks if b.startswith(prefix)]
    assert len(hits) > n, ('missing block', prefix, len(hits))
    return hits[n]

def balanced(h):
    for t in ('div', 'section', 'figure', 'ul', 'ol', 'p', 'details', 'header', 'form', 'a', 'svg'):
        o = len(re.findall(r'<%s\b' % t, h)); c = h.count('</%s>' % t)
        assert o == c, ('unbalanced', t, o, c)
    return h


# ---------------------------------------------------------------- one language
class Page:
    def __init__(self, lang):
        self.lang = lang
        self.src, self.out = PAGES[lang]
        self.s = open(os.path.join(ROOT, self.src), encoding='utf-8').read()
        self.T = TXT.T[lang]
        self.refbase = '/reference' if lang == 'en' else '/reference-zh'
        self.nav()

    def nav(self):
        """Chapter labels, group names and accents, read from the page's own nav."""
        s = self.s; a = s.index('<nav class="chapters'); nav = s[a:s.index('</nav>', a)]
        self.label = {}; self.group = {}
        for li in re.finditer(r'<li( class="ng-grp" style="--ga:([^"]+)")?><a href="#([^"]+)">(.*?)</a>', nav):
            grp, acc, sid, lab = li.group(1), li.group(2), li.group(3), text(li.group(4))
            if grp:
                n = re.match(r'\D*(\d+)', lab).group(1)
                self.group[n] = (lab, acc)
            else:
                self.label[sid] = lab.split(' · ', 1)[-1]
        assert len(self.group) == 5 and len(self.label) >= 13, (self.group, self.label)
        self.old_intro = self.label['crossroads']; self.label['crossroads'] = self.T['intro_label']        # the deck is many slides, so no "in one page"

    def section(self, sid):
        s = self.s; a = s.index('<section id="%s"' % sid); b = s.index('</section>', a) + 10
        sec = s[a:b]; wrap = kids(sec)[0]
        assert wrap.startswith('<div class="wrap'), sid
        blocks = kids(wrap)
        if sid == 'do':      # the reference link sits outside the wrap
            blocks.append([x for x in kids(sec) if x.startswith('<a class="refjump"')][0])
        return blocks

    def chapter(self, sid):
        bl = self.section(sid)
        head = [b for b in bl if b.startswith('<div class="sec-head')][0]
        cn = re.search(r'<(?:span class="chapno"|p class="eyebrow")>(.*?)</(?:span|p)>\s*<h2', head, re.S).group(1)
        num = re.search(r'(\d\.\d)', cn).group(1)
        g = num.split('.')[0]
        return dict(id=sid, num=num, chapno=cn.strip(), h2=re.search(r'<h2>(.*?)</h2>', head, re.S).group(1),
                    stand=re.search(r'<p class="(?:stand|lede)[^"]*">(.*?)</p>', head, re.S).group(1),
                    label=self.label[sid], group=self.group[g][0], acc=self.group[g][1], blocks=bl)


# ---------------------------------------------------------------- slide pieces
# parts that sit under another part, by section: (first, last) indices of the children
SUBS = {'crossroads': [(2, 4)], 'why-one-try': [(1, 2)], 'why-translation': [(2, 3), (5, 5)], 'response': [(1, 4)]}
def is_sub(sid, k): return any(a <= k <= b for a, b in SUBS.get(sid, []))
def part_nums(sid, n):
    """Top-level parts count 1, 2, 3; a child reads 2.1, 2.2 under its parent."""
    out, top, child = [], 0, 0
    for k in range(n):
        if is_sub(sid, k): child += 1; out.append('%d.%d' % (top, child))
        else: top += 1; child = 0; out.append('%d' % top)
    return out

def part_head(kicker, title='', lead=''):
    return ('<div class="t-parthead"><span class="t-pk">%s</span>%s%s</div>'
            % (kicker, ('<h3 class="t-ph">%s</h3>' % title) if title else '', ('<p class="t-lead">%s</p>' % lead) if lead else ''))

def auto(block):
    """Cards that carry a chart, or are short, open by default."""
    return re.sub(r'<div class="(ddc|endc)', r'<div data-auto="1" class="\1', block)

def auto_first(block, n):
    """Only the first n cards open by default; the rest start folded under Read more."""
    k = [0]
    def rep(m):
        k[0] += 1
        return '<div data-auto="1" class="%s' % m.group(1) if k[0] <= n else m.group(0)
    out = re.sub(r'<div class="(ddc|endc)', rep, block)
    assert k[0] > n, (k[0], n)
    return out

def unp(p): return re.sub(r'^<p[^>]*>|</p>$', '', p.strip())

def into_card(block, n, fig):
    """Put a figure at the end of the block's nth card, found by tag balance."""
    starts = [m.start() for m in re.finditer(r'<div(?: [\w-]+="[^"]*")* class="ddc\b', block)]
    assert len(starts) > n, ('cards', len(starts))
    d = 0
    for m in re.finditer(r'<div\b|</div>', block[starts[n]:]):
        d += 1 if m.group(0) == '<div' else -1
        if d == 0:
            end = starts[n] + m.start(); break
    return block[:end] + fig + block[end:]

FEEL_ICONS = [   # abundance, health, education, science, work, energy
    '<circle cx="9" cy="20" r="1.5"/><circle cx="17" cy="20" r="1.5"/><path d="M3 4h2l2.4 11h10.2L20 8H6.3"/>',
    '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/><path d="M7.5 12h2.5l1.5-2.5 2 4.5 1.5-2h1.5"/>',
    '<path d="M4 19V5.5A2.5 2.5 0 0 1 6.5 3H20v14H6.5A2.5 2.5 0 0 0 4 19.5 2.5 2.5 0 0 0 6.5 22H20v-5"/>',
    '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3"/><path d="M7.5 15h9"/>',
    '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M3 13h18"/>',
    '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>']
def feel_icons(block, lang):
    """2.1 where people would feel it: a small icon in each card's label row."""
    labs = [m for m in re.finditer(r'<span class="k">([^<]*)</span>', block)]
    assert len(labs) == 6, len(labs)
    if lang == 'en': assert [m.group(1) for m in labs] == ['Abundance', 'Health', 'Education', 'Scientific progress', 'Work', 'Energy'], [m.group(1) for m in labs]
    for m, ic in reversed(list(zip(labs, FEEL_ICONS))):
        svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>' % ic
        block = block[:m.start()] + '<span class="fl-lab"><span class="sc-ic sc-sm">%s</span>%s</span>' % (svg, m.group(0)) + block[m.end():]
    return block

def worded_figs(block, T):
    """4.1 worded well, still wrong: what was asked beside what it did; and a climb with no finish."""
    L = T['worded']
    rows = ''.join('<div class="wl-row"><div class="wl-ask"><span>%s</span><b>%s</b></div><span class="wl-to" aria-hidden="true">\u2192</span>'
                   '<div class="wl-did"><span>%s</span><b>%s</b></div></div>' % (E(L['asked']), E(a), E(L['did']), E(d)) for a, d in L['rows'])
    lit = '<figure class="secfig wl-fig" aria-label="%s">%s</figure>' % (E(L['alt1']), rows)
    steps = ''.join('<rect x="%d" y="%d" width="46" height="%d" rx="4" fill="%s" stroke="#1b1b1b" stroke-width="2.5"/>'
                    '<text x="%d" y="%d" text-anchor="middle" font-family="Comic Neue,PingFang SC,sans-serif" font-size="12" font-weight="700" fill="#1b1b1b">%s</text>'
                    % (8 + i * 52, 126 - (26 + i * 20), 26 + i * 20, c, 31 + i * 52, 126 - (26 + i * 20) - 7, E(s))
                    for i, (s, c) in enumerate(zip(L['steps'], ['#fff6d8', '#f6e3a8', '#e8b53a', '#e9a07f', '#d9492c'])))
    # sized with the drawing (dk-chart keeps the page's label-fitting script away), so labels shrink with it on a phone
    svg = ('<svg class="dk-chart" viewBox="0 0 330 150" role="img" aria-label="%s">%s'
           '<path d="M268 24 L316 6" stroke="#1b1b1b" stroke-width="3" stroke-dasharray="5 4" marker-end="url(#wl-tip)"/>'
           '<defs><marker id="wl-tip" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill="#1b1b1b"/></marker></defs>'
           '<g transform="translate(290 88)"><path d="M0 40 V0" stroke="#1b1b1b" stroke-width="2.5"/><path d="M0 0 H26 L20 7 L26 14 H0 Z" fill="#cfe6c4" stroke="#1b1b1b" stroke-width="2"/>'
           '<path d="M-4 2 L30 34 M30 2 L-4 34" stroke="#d9492c" stroke-width="3.5" stroke-linecap="round"/>'
           '<text x="13" y="54" text-anchor="middle" font-family="Comic Neue,PingFang SC,sans-serif" font-size="12" font-weight="700" fill="#1b1b1b">%s</text></g>'
           '<path d="M2 127 H286" stroke="#1b1b1b" stroke-width="2.5"/></svg>') % (E(L['alt2']), steps, E(L['done']))
    stop = '<figure class="secfig wl-fig wl-climb">%s</figure>' % svg
    # the pictures carry the examples, so each card keeps one short line
    ps = re.findall(r'<p>.*?</p>', block, re.S)
    assert len(ps) == 2, len(ps)
    for p, short in zip(ps, L['short']): block = block.replace(p, '<p>%s</p>' % E(short), 1)
    return into_card(into_card(block, 1, stop), 0, lit)

def loophole(block, pg):
    """Guess how it cheated before the answer shows: the right answer is the page's own demo text."""
    m = re.search(r'var DEMOS = (\[.*?\]);', pg.s, re.S)
    got = [d[1] for d in ast.literal_eval(m.group(1))]
    L = dict(pg.T['wid']['loophole']); L['got'] = got
    assert len(got) == len(L['wrong']) == 5
    return block.replace('<div class="demo-embed"', '<div class="demo-embed" data-lh="%s"' % html.escape(json.dumps(L, ensure_ascii=False)), 1)

def demo_bare(block):
    """The demo's own heading and instruction repeat the chip and Kenji's line, so the deck drops them."""
    out, n = re.subn(r'\s*<h3>[^<]*</h3>\s*<p class="dsub">.*?</p>', '', block, count=1, flags=re.S)
    assert n == 1, 'demo heading not found'
    return out


def tries_fig(T):
    """Crash, fix, repeat: the picture timeline for 2.3."""
    W = 'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"'
    import math
    def pic(inner_): return '<svg class="tp" viewBox="0 0 64 64" aria-hidden="true">%s</svg>' % inner_
    def burst(x, y, r):
        pts = ['%.1f,%.1f' % (x + (r if k % 2 == 0 else r * .45) * math.cos(k * math.pi / 5 - 1.57),
                              y + (r if k % 2 == 0 else r * .45) * math.sin(k * math.pi / 5 - 1.57)) for k in range(10)]
        return '<path class="b" %s d="M%s Z"/>' % (W, ' L'.join(pts))
    CAR = ('<path class="a" %s d="M7 40 L13 28 Q15 24 20 24 H44 Q49 24 51 28 L57 40 V47 H7 Z"/><path %s fill="none" d="M18 38 L22 29 H42 L46 38"/>'
           '<circle cx="18" cy="47" r="5" class="d" %s/><circle cx="46" cy="47" r="5" class="d" %s/>') % (W, W, W, W)
    PLANE = '<path class="a" %s d="M4 34 Q4 29 10 29 H46 L56 20 H61 L55 34 Q54 38 48 38 H10 Q4 38 4 34 Z"/><path class="d" %s d="M24 34 L34 46 H40 L34 34 Z"/>' % (W, W)
    PLANT = '<path class="d" %s d="M14 58 Q20 40 16 22 H40 Q36 40 42 58 Z"/><path class="a" %s d="M18 14 Q22 6 30 10 Q36 4 42 12" fill="none"/>' % (W, W)
    CHECK = '<circle cx="50" cy="16" r="10" class="ok" %s/><path %s fill="none" d="M45 16 L49 20 L56 12"/>' % (W, W)
    P = {
        'car_crash': pic('<g transform="rotate(-10 32 40)">%s</g>%s' % (CAR, burst(52, 22, 11))),
        'seatbelt': pic('<path class="d" %s d="M20 58 V36 Q20 30 26 30 H38 Q44 30 44 36 V58"/><circle cx="32" cy="18" r="8" class="a" %s/>'
                        '<path class="k" stroke-width="5" stroke-linecap="round" d="M24 32 L42 52"/><path class="k" stroke-width="5" stroke-linecap="round" d="M20 50 H44"/>' % (W, W)),
        'airbag': pic('<path %s fill="none" d="M8 14 V50 H34"/><circle cx="17" cy="20" r="7" class="a" %s/><path class="d" %s d="M13 28 H21 L25 46 H13 Z"/>'
                      '<ellipse cx="57" cy="28" rx="3.5" ry="13" class="d" %s/><path %s fill="none" d="M57 41 L61 58"/>'
                      '<path class="k2" %s d="M29 17 Q33 8 41 13 Q50 10 51 20 Q56 28 51 36 Q50 46 41 43 Q33 48 29 39 Q24 28 29 17 Z"/>' % (W, W, W, W, W, W)),
        'safe_car': pic(CAR + CHECK),
        'midair': pic('<g transform="translate(1 2) scale(.55)">%s</g><g transform="translate(63 20) scale(-.55 .55)">%s</g>%s' % (PLANE, PLANE, burst(32, 28, 11))),
        'tower': pic('<path class="d" %s d="M26 60 L29 26 H35 L38 60 Z"/><path class="a" %s d="M20 16 H44 L40 26 H24 Z"/><path %s fill="none" d="M46 10 Q52 16 46 22 M50 6 Q60 16 50 26"/>' % (W, W, W)),
        'runway': pic('<path %s fill="none" d="M4 52 H60"/><g transform="translate(0 12) scale(.6)">%s</g><g transform="translate(64 20) scale(-.6 .6)">%s</g>%s' % (W, PLANE, PLANE, burst(33, 36, 11))),
        'crew': pic('<circle cx="21" cy="26" r="9" class="a" %s/><circle cx="43" cy="26" r="9" class="a" %s/><path class="d" %s d="M8 56 Q8 40 21 40 Q34 40 34 56 Z M30 56 Q30 40 43 40 Q56 40 56 56 Z"/>'
                    '<path %s fill="none" d="M12 24 Q12 14 21 14 Q30 14 30 24 M34 24 Q34 14 43 14 Q52 14 52 24"/>' % (W, W, W, W)),
        'safe_plane': pic('<g transform="translate(0 10)">%s</g>%s' % (PLANE, CHECK)),
        'meltdown': pic(PLANT + burst(46, 44, 12)),
        'inspect': pic('<rect x="14" y="10" width="34" height="46" rx="4" class="d" %s/><rect x="24" y="6" width="14" height="8" rx="2" class="a" %s/>'
                       '<path class="k" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round" fill="none" d="M20 26 L24 30 L30 22 M20 40 L24 44 L30 36"/><path %s fill="none" d="M34 27 H42 M34 41 H42"/>' % (W, W, W)),
        'peer': pic('<g transform="translate(-4 0) scale(.85)">%s</g><circle cx="44" cy="34" r="11" class="k2" %s/><path %s d="M52 42 L60 50"/>' % (PLANT, W, W)),
        'safe_plant': pic(PLANT + CHECK),
        'chip': pic('<rect x="16" y="16" width="32" height="32" rx="5" class="a" %s/><path %s fill="none" d="M24 8 V16 M32 8 V16 M40 8 V16 M24 48 V56 M32 48 V56 M40 48 V56 M8 24 H16 M8 32 H16 M8 40 H16 M48 24 H56 M48 32 H56 M48 40 H56"/>'
                    '<text x="32" y="37" text-anchor="middle" font-family="Archivo,sans-serif" font-weight="800" font-size="13" fill="currentColor" stroke="none">AI</text>' % (W, W)),
    }
    rows = []
    for name, steps in T['tries_rows']:
        cells = ''.join('<li class="tr-%s">%s<span>%s</span></li>' % ({'f': 'fail', 'x': 'fix', 's': 'ok'}[k], P[key],
                        re.sub(r' (’\d\d)$', r' <i>\1</i>', html.escape(cap))) for k, key, cap in steps)
        rows.append('<div class="tr-row"><div class="tr-name">%s</div><ol class="tr-steps">%s</ol></div>' % (name, cells))
    rows.append('<div class="tr-row tr-agi"><div class="tr-name">AI</div><div class="tr-ai"><div class="tr-aic">%s</div>'
                '<div class="tr-rsi"><svg viewBox="0 0 300 80" preserveAspectRatio="none" aria-hidden="true"><path d="M0.0,76.0 L3.0,75.9 L6.0,75.8 L9.0,75.7 L12.0,75.6 L15.0,75.5 L18.0,75.4 L21.0,75.3 L24.0,75.2 L27.0,75.1 L30.0,75.0 L33.0,74.9 L36.0,74.7 L39.0,74.6 L42.0,74.5 L45.0,74.3 L48.0,74.2 L51.0,74.1 L54.0,73.9 L57.0,73.7 L60.0,73.6 L63.0,73.4 L66.0,73.2 L69.0,73.1 L72.0,72.9 L75.0,72.7 L78.0,72.5 L81.0,72.3 L84.0,72.0 L87.0,71.8 L90.0,71.6 L93.0,71.4 L96.0,71.1 L99.0,70.9 L102.0,70.6 L105.0,70.3 L108.0,70.0 L111.0,69.7 L114.0,69.4 L117.0,69.1 L120.0,68.8 L123.0,68.5 L126.0,68.1 L129.0,67.8 L132.0,67.4 L135.0,67.0 L138.0,66.6 L141.0,66.2 L144.0,65.8 L147.0,65.3 L150.0,64.9 L153.0,64.4 L156.0,63.9 L159.0,63.4 L162.0,62.9 L165.0,62.4 L168.0,61.8 L171.0,61.2 L174.0,60.6 L177.0,60.0 L180.0,59.4 L183.0,58.7 L186.0,58.0 L189.0,57.3 L192.0,56.6 L195.0,55.8 L198.0,55.0 L201.0,54.2 L204.0,53.4 L207.0,52.5 L210.0,51.6 L213.0,50.7 L216.0,49.7 L219.0,48.7 L222.0,47.7 L225.0,46.6 L228.0,45.5 L231.0,44.4 L234.0,43.2 L237.0,42.0 L240.0,40.8 L243.0,39.4 L246.0,38.1 L249.0,36.7 L252.0,35.3 L255.0,33.8 L258.0,32.2 L261.0,30.6 L264.0,29.0 L267.0,27.2 L270.0,25.5 L273.0,23.6 L276.0,21.7 L279.0,19.8 L282.0,17.7 L285.0,15.6 L288.0,13.5 L291.0,11.2 L294.0,8.9 L297.0,6.5 L300.0,4.0" fill="none" stroke="#d9492c" stroke-width="4" vector-effect="non-scaling-stroke" stroke-linecap="round"/></svg>''<i class="rsi-c" style="left:30%%;--y:0.895;--z:0.70">AI</i><i class="rsi-c" style="left:62%%;--y:0.725;--z:0.90">AI</i><i class="rsi-c" style="left:86%%;--y:0.403;--z:1.15">AI</i>''<span class="rsi-loop">↻ %s</span><span class="rsi-boom">%s</span><span class="rsi-norun">%s</span></div><div class="tr-cliff"><svg viewBox="0 0 120 64" aria-hidden="true">'
                '<path class="d" %s d="M2 18 H58 L54 30 L60 40 L52 50 L56 62 H2 Z"/><path class="fall" d="M60 16 Q84 18 90 40"/>'
                '<path class="b" %s d="M92 38 L96 48 L106 48 L98 54 L101 63 L92 58 L83 63 L86 54 L78 48 L88 48 Z"/></svg><span>%s</span></div></div></div>'
                % (P['chip'], T['rsi_loop'], T['rsi_boom'], T['tries_norun'], W, W, T['tries_oneshot']))
    legend = '<div class="tr-legend"><span class="lg-f">%s</span><span class="lg-x">%s</span><span class="lg-s">%s</span></div>' % T['tries_legend']
    # the unlock game: tiles lock only once the script runs, so the figure reads fine without it
    count = ('<p class="tr-count" hidden><span>%s</span><button type="button" class="tr-all">%s</button></p>'
             % (T['tries_count'] % ('<b class="tr-n">1</b>', '<b class="tr-t">16</b>'), T['tries_all']))
    return ('<figure class="secfig tr-fig" aria-label="%s" data-reveal="%s" data-tap="%s" data-ai="%s">'
            '<div class="tr-top"><p class="tr-title">%s</p>%s</div>%s%s</figure>'
            % (html.escape(T['tries_alt']), html.escape(T['tries_reveal']), html.escape(T['tries_tap']), html.escape(T['tries_ai_q']),
               T['tries_title'], legend, count, ''.join(rows)))


def iceberg_fig(T):
    """What training can reach: a picture in place of the text-heavy chart in 4.1."""
    I = T['ice']
    F = 'font-family="Comic Neue,Archivo,sans-serif"'
    svg = ('<svg class="ice" data-keep="1" viewBox="0 0 480 300" role="img" aria-label="%s">'
           '<rect x="0" y="120" width="480" height="180" fill="#dbe6f5"/>'
           '<path d="M0 120 H480" stroke="#1b1b1b" stroke-width="2" stroke-dasharray="7 6"/>'
           '<path d="M160 120 L300 120 L362 188 L322 276 L182 286 L118 208 Z" fill="#9fb3f0" stroke="#1b1b1b" stroke-width="2.5" stroke-linejoin="round"/>'
           '<path d="M198 120 L234 66 L262 80 L292 120 Z" fill="#fffdf6" stroke="#1b1b1b" stroke-width="2.5" stroke-linejoin="round"/>'
           '<text x="240" y="232" text-anchor="middle" font-family="Bangers,ZCOOL KuaiLe,sans-serif" font-size="64" fill="#1b1b1b">?</text>'
           '<text x="12" y="62" %s font-size="18" font-weight="700" fill="#1b1b1b">%s</text>'
           '<text x="12" y="80" %s font-size="14" fill="#5c574e">%s</text>'
           '<path d="M104 68 Q170 44 222 78" fill="none" stroke="#1b1b1b" stroke-width="2.5" stroke-linecap="round"/>'
           '<path d="M222 78 L207 76 M222 78 L215 65" fill="none" stroke="#1b1b1b" stroke-width="2.5" stroke-linecap="round"/>'
           '<text x="304" y="84" %s font-size="18" font-weight="700" fill="#1b1b1b">%s</text>'
           '<text x="304" y="102" %s font-size="14" fill="#5c574e">%s</text>'
           '<text x="12" y="112" %s font-size="14" fill="#5c574e">%s</text>'
           '<text x="372" y="202" %s font-size="18" font-weight="700" fill="#1b1b1b">%s</text>'
           '<text x="372" y="220" %s font-size="14" fill="#5c574e">%s</text>'
           '</svg>') % (html.escape(I['alt']), F, I['train'], F, I['train2'], F, I['tip'], F, I['tip2'], F, I['line'], F, I['deep'], F, I['deep2'])
    return '<figure class="secfig ice-fig"><p class="tr-title">%s</p>%s</figure>' % (I['title'], svg)


FONT = 'font-family="Comic Neue,PingFang SC,Microsoft YaHei,Archivo,sans-serif"'
def dk_svg(vb, label, body):
    """A chart redrawn for the deck: sized as drawn, coloured as drawn."""
    return '<svg class="dk-chart" data-keep="1" viewBox="%s" role="img" aria-label="%s">%s</svg>' % (vb, html.escape(label), body)

def fold_fig_src(grid):
    """A card's chart sources join the card's own sources line: the chart's numbered refs move into the card text, and its source line goes."""
    out = grid; moved = 0
    for card in [c for c in kids(grid) if re.match(r'<div[^>]*class="ddc', c)]:
        m = re.search(r'<p class="fig-src">(.*?)</p>', card, re.S)
        if not m: continue
        have = set(re.findall(r'<a class="ref"[^>]*>(\d+)</a>', card[:card.index('<figure')]))
        add = [r for r in re.findall(r'<a class="ref"[^>]*>\d+</a>', m.group(1)) if re.search(r'>(\d+)<', r).group(1) not in have]
        p_end = card.index('</p>')      # end of the card's first paragraph
        new = card[:p_end] + ''.join(add) + card[p_end:]
        new = new.replace(m.group(0), '', 1)
        assert out.count(card) == 1 and '<p class="fig-src">' not in new
        out = out.replace(card, new, 1); moved += 1
    assert moved >= 1, 'no chart source to fold'
    return out

def charts_11(T):
    C = T['ch11']; F = FONT
    def t(x, y, size, txt, fill='#1b1b1b', bold=True, anchor='start'):
        return '<text x="%s" y="%s" %s font-size="%s"%s fill="%s" text-anchor="%s">%s</text>' % (
            x, y, F, size, ' font-weight="700"' if bold else '', fill, anchor, html.escape(txt))
    bars = ''.join('<rect x="%d" y="%d" width="62" height="%d" rx="3" fill="%s" stroke="#1b1b1b" stroke-width="2"/>%s%s'
                   % (x, 136 - h, h, col, t(x + 31, 128 - h, 18, v, anchor='middle'), t(x + 31, 156, 14, yr, '#5c574e', False, 'middle'))
                   for x, h, col, v, yr in ((14, 14, '#b9d6a8', C['c_vals'][0], '2022'), (114, 44, '#8cbf73', C['c_vals'][1], '2024'),
                                            (214, 86, '#4f9440', C['c_vals'][2], '2026')))
    compute = dk_svg('0 0 290 162', C['c_title'] + '. ' + C['c_sub'],
                     t(0, 18, 17, C['c_title']) + t(0, 38, 14, C['c_sub'], '#5c574e', False) +
                     '<path d="M0 136 H290" stroke="#1b1b1b" stroke-width="2"/>' + bars)
    funding = dk_svg('0 0 290 168', C['f_title'],
                     t(0, 18, 17, C['f_title']) +
                     t(0, 44, 14, C['f_build'], '#5c574e', False) +
                     '<rect x="0" y="50" width="288" height="30" rx="3" fill="#4a5fc9" stroke="#1b1b1b" stroke-width="2"/>' +
                     t(278, 71, 16, C['f_bval'], '#fff', anchor='end') +
                     t(0, 104, 14, C['f_safe'], '#5c574e', False) +
                     '<rect x="0" y="110" width="4" height="30" fill="#d9492c" stroke="#1b1b1b" stroke-width="1.5"/>' +
                     t(14, 131, 16, C['f_sval']) +
                     t(0, 164, 20, C['f_ratio']))
    plans = dk_svg('0 0 290 124', C['p_title'],
                   t(0, 18, 17, C['p_title']) +
                   '<text x="0" y="72" font-family="Bangers,ZCOOL KuaiLe,sans-serif" font-size="46" fill="#1b1b1b">12</text>' + t(62, 64, 16, C['p_pub'], bold=False) +
                   '<text x="10" y="120" font-family="Bangers,ZCOOL KuaiLe,sans-serif" font-size="46" fill="#d9492c">0</text>' + t(62, 112, 16, C['p_chk'], bold=False))
    return [compute, funding, plans]

def widget(kind, T, old_fig, extra=None):
    """An interactive chart in place of a static one; deck.js draws it. The source line stays."""
    W = dict(T['wid'][kind]); W.update(extra or {})
    src = re.search(r'<p class="fig-src">.*?</p>', old_fig, re.S)
    title = ('<p class="tr-title">%s</p>' % W['title']) if W.get('title') else ''
    return ('<figure class="secfig dk-int dkw-%s" data-w="%s" data-cfg="%s">%s<div class="dki-body"></div>'
            '<p class="dk-sr">%s</p>%s</figure>') % (kind, kind, html.escape(json.dumps(W, ensure_ascii=False)), title, W['alt'], src.group(0) if src else '')

def widget_plain(kind, T, extra=None):
    """An interactive figure with no source figure behind it; extra adds site text to its data."""
    W = dict(T['wid'][kind]); W.update(extra or {})
    title = ('<p class="tr-title">%s</p>' % W['title']) if W.get('title') else ''
    return ('<figure class="secfig dk-int dkw-%s" data-w="%s" data-cfg="%s">%s<div class="dki-body"></div><p class="dk-sr">%s</p></figure>'
            % (kind, kind, html.escape(json.dumps(W, ensure_ascii=False)), title, W['alt']))

def cards_text(block):
    """(label, heading, body) of each card in a grid, from the page itself."""
    out = []
    for c in kids(block):
        k = re.search(r'<span class="k">(.*?)</span>', c, re.S); h = re.search(r'<h4>(.*?)</h4>', c, re.S); p = re.search(r'<p>(.*?)</p>', c, re.S)
        out.append([text(k.group(1)) if k else '', text(h.group(1)), p.group(1).strip() if p else ''])
    return out

def slim_cards(block, label):
    """Each card keeps its label, heading and picture; paragraphs and examples fold under a small "More"."""
    out = block
    for card in kids(block):
        if not re.match(r'<div[^>]*class="ddc', card): continue
        parts = kids(card)
        keep = [x for x in parts if re.match(r'<(span|h4|figure)\b', x)]
        fold = [x for x in parts if x not in keep]
        if not fold: continue
        open_tag = card[:card.index('>') + 1]
        new = open_tag + ''.join(keep) + '<details class="dk-more"><summary>%s</summary>%s</details></div>' % (label, ''.join(fold))
        assert out.count(card) == 1
        out = out.replace(card, new, 1)
    return out

def short_cards(block, texts):
    """Card copy rewritten short for the deck; [n] becomes the page's own numbered citation link."""
    base = re.search(r'<a class="ref" href="([^"#]+)#s\d+"', block).group(1)
    def refs(t): return re.sub(r'\[(\d+)\]', lambda m: '<a class="ref" href="%s#s%s">%s</a>' % (base, m.group(1), m.group(1)), html.escape(t, quote=False).replace('&amp;', '&'))
    cards = [c for c in kids(block) if re.match(r'<div[^>]*class="ddc', c)]
    assert len(cards) == len(texts), (len(cards), len(texts))
    out = block
    for card, (body, ex) in zip(cards, texts):
        parts = kids(card)
        keep = [x for x in parts if re.match(r'<(span|h4|figure)\b', x)]
        fig = [x for x in keep if x.startswith('<figure')]
        head = [x for x in keep if not x.startswith('<figure')]
        new = card[:card.index('>') + 1] + ''.join(head) + '<p>%s</p>' % refs(body) + ''.join(fig)
        if ex: new += '<p class="dk-ex">%s</p>' % refs(ex)
        new += '</div>'
        assert out.count(card) == 1
        out = out.replace(card, new, 1)
    return out

def refs_html(t, base):
    return re.sub(r'\[(\d+)\]', lambda m: '<a class="ref" href="%s#s%s">%s</a>' % (base, m.group(1), m.group(1)), html.escape(t, quote=False))

def add_example(block, n, text_, base):
    """Append one short example line to the block's nth card."""
    cards = [c for c in kids(block) if re.match(r'<div[^>]*class="ddc', c)]
    c = cards[n]; assert block.count(c) == 1
    return block.replace(c, c[:c.rindex('</div>')] + '<p class="dk-ex">%s</p></div>' % refs_html(text_, base), 1)

def ends_scenes():
    """Four small comic scenes for the four adversaries."""
    K = 'stroke="#1b1b1b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"'
    def man(x, y, c):
        return ('<circle cx="%d" cy="%d" r="7" fill="%s" %s/><path d="M%d %d v18 M%d %d l-7 12 M%d %d l7 12 M%d %d l-9 6 M%d %d l9 -4" fill="none" %s/>'
                % (x, y, c, K, x, y + 7, x, y + 25, x, y + 25, x, y + 12, x, y + 12, K))
    def bot(x, y, c='#9fb3f0'):
        return ('<rect x="%d" y="%d" width="34" height="30" rx="6" fill="%s" %s/><circle cx="%d" cy="%d" r="3" fill="#1b1b1b"/><circle cx="%d" cy="%d" r="3" fill="#1b1b1b"/>'
                '<path d="M%d %d v-6" %s/><circle cx="%d" cy="%d" r="3" fill="#e8b53a" %s/><path d="M%d %d h14" %s/>'
                % (x, y, c, K, x + 11, y + 12, x + 23, y + 12, x + 17, y, K, x + 17, y - 8, K, x + 10, y + 22, K))
    def arrow(x1, y1, x2, y2, c='#1b1b1b'):
        return '<path d="M%d %d L%d %d" stroke="%s" stroke-width="3" stroke-linecap="round" marker-end="url(#dka)"/>' % (x1, y1, x2, y2, c)
    DEF = '<defs><marker id="dka" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="context-stroke"/></marker></defs>'
    burst = lambda x, y: '<path d="M%d %d l4 9 9 -2 -6 7 6 8 -9 -2 -4 9 -4 -9 -9 2 6 -8 -6 -7 9 2z" fill="#ffd166" %s/>' % (x, y - 12, K)
    s1 = DEF + man(22, 34, '#e07a5f') + arrow(38, 50, 66, 50, '#d9492c') + bot(72, 36) + arrow(112, 50, 150, 50, '#d9492c') + \
         '<circle cx="176" cy="50" r="18" fill="#fffdf6" %s/><circle cx="176" cy="50" r="10" fill="#f6d5cc" %s/><circle cx="176" cy="50" r="3" fill="#d9492c"/>' % (K, K) + burst(196, 30)
    s2 = DEF + man(30, 44, '#e8b53a') + '<ellipse cx="46" cy="18" rx="22" ry="13" fill="#fffdf6" %s/><path d="M40 16 a4 4 0 0 1 6 -3 a4 4 0 0 1 6 3 l-6 7z" fill="#d9492c" %s/>' % (K, K) + \
         '<text x="100" y="58" text-anchor="middle" font-family="Comic Neue,sans-serif" font-weight="700" font-size="26" fill="#1b1b1b">&#8800;</text>' + bot(140, 46) + \
         '<ellipse cx="170" cy="18" rx="24" ry="13" fill="#fffdf6" %s/><path d="M160 20 h20 M163 14 h14 M166 24 h8" %s/>' % (K, K) + \
         '<rect x="134" y="42" width="46" height="16" rx="8" fill="#fffdf6" %s/><path d="M146 50 q6 5 12 0" fill="none" %s/>' % (K, K)
    s3 = DEF + man(24, 40, '#6fae5a') + arrow(40, 58, 70, 58) + bot(80, 44) + '<path d="M92 46 l6 8 -5 6 7 8" fill="none" stroke="#d9492c" stroke-width="3"/>' + \
         '<circle cx="150" cy="56" r="11" fill="#fffdf6" %s/><path d="M158 64 l10 10" %s/><text x="150" y="61" text-anchor="middle" font-family="Comic Neue,sans-serif" font-weight="700" font-size="14" fill="#1b1b1b">?</text>' % (K, K) + \
         '<ellipse cx="196" cy="70" rx="7" ry="5" fill="#1b1b1b"/><path d="M190 66 l-4 -4 M202 66 l4 -4" %s/>' % K
    s4 = DEF + ''.join(bot(10 + i * 46, 50 - i * 2, c) + arrow(46 + i * 46, 66 - i * 2, 54 + i * 46, 66 - i * 2) for i, c in enumerate(('#9fb3f0', '#b9d6a8', '#f2cc6a'))) + \
         '<path d="M158 88 L158 80 L200 80" fill="none" %s/><path d="M170 80 l-4 8 6 6 -5 10" fill="none" stroke="#1b1b1b" stroke-width="2.5"/>' % K + \
         '<path d="M178 80 v40" stroke="#d9492c" stroke-width="2.5" stroke-dasharray="4 4"/>'
    return [dk_svg('0 0 210 104', '', x.replace('dka', 'dka%d' % n)).replace('<svg ', '<svg class="dk-chart dk-scene" ', 1).replace('class="dk-chart" ', '', 1)
            for n, x in enumerate((s1, s2, s3, s4))]

def feel_scenes():
    """Five small comic scenes for where people would feel it, drawn like the 2.2a adversary scenes."""
    K = 'stroke="#1b1b1b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"'
    def man(x, y, c):
        return ('<circle cx="%d" cy="%d" r="7" fill="%s" %s/><path d="M%d %d v18 M%d %d l-7 12 M%d %d l7 12 M%d %d l-9 6 M%d %d l9 -4" fill="none" %s/>'
                % (x, y, c, K, x, y + 7, x, y + 25, x, y + 25, x, y + 12, x, y + 12, K))
    def bot(x, y, c='#9fb3f0'):
        return ('<rect x="%d" y="%d" width="34" height="30" rx="6" fill="%s" %s/><circle cx="%d" cy="%d" r="3" fill="#1b1b1b"/><circle cx="%d" cy="%d" r="3" fill="#1b1b1b"/>'
                '<path d="M%d %d v-6" %s/><circle cx="%d" cy="%d" r="3" fill="#e8b53a" %s/><path d="M%d %d q7 5 14 0" fill="none" %s/>'
                % (x, y, c, K, x + 11, y + 12, x + 23, y + 12, x + 17, y, K, x + 17, y - 8, K, x + 10, y + 21, K))
    def arrow(n, x1, y1, x2, y2):
        return '<path d="M%d %d L%d %d" stroke="#1b1b1b" stroke-width="3" stroke-linecap="round" marker-end="url(#fsa%d)"/>' % (x1, y1, x2, y2, n)
    DEF = lambda n: '<defs><marker id="fsa%d" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="#1b1b1b"/></marker></defs>' % n
    spark = lambda x, y: '<path d="M%d %d l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z" fill="#ffd166" %s/>' % (x, y - 10, K)
    goods = ''.join('<circle cx="%d" cy="%d" r="%d" fill="%s" %s/>' % (x, y, r, c, K) for x, y, r, c in
                    ((100, 58, 8, '#e07a5f'), (117, 54, 9, '#6fae5a'), (134, 58, 8, '#9fb3f0'), (150, 54, 8, '#f2cc6a'), (110, 42, 7, '#f2cc6a'), (128, 40, 8, '#e07a5f'), (144, 42, 7, '#6fae5a')))
    s1 = DEF(0) + bot(10, 46) + arrow(0, 50, 62, 76, 62) + goods + '<path d="M84 64 H166 L156 94 H94 Z" fill="#e8b53a" %s/>' % K + man(188, 44, '#6fae5a') + spark(176, 22)
    s2 = (DEF(1) + man(26, 42, '#e07a5f') +
          '<path d="M76 72 C56 58 52 40 66 36 C72 34 76 38 76 42 C76 38 80 34 86 36 C100 40 96 58 76 72 Z" fill="#d9492c" %s/>' % K +
          '<path d="M106 56 h16 l6 -14 l8 28 l6 -14 h24" fill="none" stroke="#d9492c" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>' + arrow(1, 166, 56, 194, 56) +
          '<text x="178" y="42" text-anchor="middle" font-family="Bangers,ZCOOL KuaiLe,sans-serif" font-size="22" fill="#1b1b1b">×2</text>')
    s3 = (DEF(2) + bot(14, 46, '#b9d6a8') + '<path d="M40 30 q18 -20 40 -6 q-6 10 -22 12 l-6 8 z" fill="#fffdf6" %s/>' % K +
          '<text x="62" y="30" text-anchor="middle" font-family="Bangers,ZCOOL KuaiLe,sans-serif" font-size="16" fill="#1b1b1b">A+</text>' +
          '<path d="M86 66 Q106 56 126 66 V92 Q106 82 86 92 Z M126 66 Q146 56 166 66 V92 Q146 82 126 92 Z" fill="#fffdf6" %s/>' % K +
          '<path d="M94 72 h22 M94 78 h22 M134 72 h22 M134 78 h22" stroke="#9aa3ab" stroke-width="2" stroke-linecap="round"/>' + man(188, 44, '#e8b53a'))
    s4 = (DEF(3) + bot(10, 46) + '<rect x="58" y="88" width="44" height="8" rx="2" fill="#cfc4ab" %s/><path d="M80 88 V64 L90 46" fill="none" %s/>' % (K, K) +
          '<rect x="84" y="34" width="12" height="16" rx="3" fill="#fffdf6" %s/><rect x="72" y="72" width="22" height="5" rx="2" fill="#fffdf6" %s/>' % (K, K) +
          '<path d="M118 70 c8 -22 18 22 26 0 s18 22 26 0 s18 22 26 0" fill="none" stroke="#4a5fc9" stroke-width="4" stroke-linecap="round"/>' +
          ''.join('<circle cx="%d" cy="%d" r="4" fill="#e07a5f" %s/>' % (x, y, K) for x, y in ((118, 70), (144, 70), (170, 70), (196, 70))) + spark(160, 34))
    s5 = (DEF(4) + ''.join('<rect x="%d" y="%d" width="30" height="7" rx="1" fill="#fffdf6" %s/>' % (16 + (i % 2) * 3, 42 - i * 8, K) for i in range(5)) + bot(14, 50) +
          arrow(4, 58, 66, 82, 66) + '<path d="M100 92 h60 M110 92 l-6 -26 M150 92 l6 -26 M104 66 h52" fill="none" %s/>' % K + man(132, 40, '#6fae5a') +
          '<path d="M172 70 h14 v14 a6 6 0 0 1 -6 6 h-2 a6 6 0 0 1 -6 -6 z M186 74 h4 a3 3 0 0 1 0 6 h-4" fill="#fffdf6" %s/>' % K +
          '<path d="M176 64 q3 -5 0 -10 M182 64 q3 -5 0 -10" fill="none" stroke="#9aa3ab" stroke-width="2" stroke-linecap="round"/>')
    # energy: the AI tunes the reactor, and the lights come on
    s6 = (DEF(5) + bot(8, 46) + arrow(5, 48, 62, 66, 62) +
          '<ellipse cx="104" cy="62" rx="30" ry="16" fill="#ffd166" %s/><ellipse cx="104" cy="62" rx="15" ry="7" fill="#e07a5f" %s/>' % (K, K) +
          '<path d="M140 50 l-8 12 h8 l-6 12" fill="none" stroke="#e8b53a" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>' +
          man(184, 50, '#6fae5a') + '<circle cx="168" cy="26" r="9" fill="#fff6d8" %s/><path d="M165 35 h6" %s/>' % (K, K) + spark(192, 20))
    return [dk_svg('0 0 210 104', '', x).replace('<svg ', '<svg class="dk-chart dk-scene" ', 1).replace('class="dk-chart" ', '', 1) for x in (s1, s2, s3, s4, s5, s6)]

def care_scenes():
    """Three small comic scenes for the why-care cards, in the 2.2a style."""
    K = 'stroke="#1b1b1b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"'
    def man(x, y, c):
        return ('<circle cx="%d" cy="%d" r="7" fill="%s" %s/><path d="M%d %d v18 M%d %d l-7 12 M%d %d l7 12 M%d %d l-9 6 M%d %d l9 -4" fill="none" %s/>'
                % (x, y, c, K, x, y + 7, x, y + 25, x, y + 25, x, y + 12, x, y + 12, K))
    def bot(x, y, c='#9fb3f0'):
        return ('<rect x="%d" y="%d" width="34" height="30" rx="6" fill="%s" %s/><circle cx="%d" cy="%d" r="3" fill="#1b1b1b"/><circle cx="%d" cy="%d" r="3" fill="#1b1b1b"/>'
                '<path d="M%d %d v-6" %s/><circle cx="%d" cy="%d" r="3" fill="#e8b53a" %s/><path d="M%d %d h14" %s/>'
                % (x, y, c, K, x + 11, y + 12, x + 23, y + 12, x + 17, y, K, x + 17, y - 8, K, x + 10, y + 22, K))
    Q = lambda x, y, s=22: '<text x="%d" y="%d" text-anchor="middle" font-family="Bangers,ZCOOL KuaiLe,sans-serif" font-size="%d" fill="#1b1b1b">?</text>' % (x, y, s)
    DEF = '<defs><marker id="csa0" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="#1b1b1b"/></marker></defs>'
    s1 = (DEF + '<rect x="14" y="22" width="56" height="62" rx="5" fill="#fffdf6" %s/><rect x="14" y="22" width="56" height="16" rx="5" fill="#e07a5f" %s/>' % (K, K) +
          '<path d="M28 16 v10 M56 16 v10" %s/><text x="42" y="70" text-anchor="middle" font-family="Bangers,ZCOOL KuaiLe,sans-serif" font-size="22" fill="#1b1b1b">2027</text>' % K +
          '<path d="M128 60 L84 60" stroke="#1b1b1b" stroke-width="3" stroke-linecap="round" marker-end="url(#csa0)"/>' + bot(136, 44) +
          '<path d="M178 50 h22 M182 60 h18 M178 70 h22" stroke="#9aa3ab" stroke-width="3" stroke-linecap="round"/>')
    goods = ''.join('<circle cx="%d" cy="%d" r="%d" fill="%s" %s/>' % (x, y, r, c, K) for x, y, r, c in ((38, 62, 7, '#6fae5a'), (52, 60, 8, '#f2cc6a'), (66, 62, 7, '#e07a5f'), (45, 50, 6, '#9fb3f0'), (59, 49, 6, '#6fae5a')))
    s2 = ('<path d="M105 92 L93 100 H117 Z" fill="#cfc4ab" %s/><path d="M105 92 V34 M30 34 H180" fill="none" %s/>' % (K, K) +
          '<path d="M30 34 L20 68 H76 L66 34 M144 34 L134 68 H190 L180 34" fill="none" stroke="#9aa3ab" stroke-width="2"/>' +
          '<path d="M18 68 H78 L72 76 H24 Z" fill="#b9d6a8" %s/>' % K + goods +
          '<path d="M132 68 H192 L186 76 H138 Z" fill="#f6d5cc" %s/>' % K +
          '<path d="M150 66 l6 -12 -5 -6 8 -10 M166 66 l-4 -10 6 -8" fill="none" stroke="#d9492c" stroke-width="3" stroke-linecap="round"/>' +
          '<path d="M60 18 l3 7 7 3 -7 3 -3 7 -3 -7 -7 -3 7 -3z" fill="#ffd166" %s/>' % K)
    s3 = man(28, 44, '#e8b53a') + Q(44, 30) + bot(88, 50) + Q(105, 34, 26) + man(182, 44, '#6fae5a') + Q(166, 30)
    return [dk_svg('0 0 210 104', '', x).replace('<svg ', '<svg class="dk-chart dk-scene" ', 1).replace('class="dk-chart" ', '', 1) for x in (s1, s2, s3)]

def card_scenes(which):
    """Small comic scenes for the 3.1 race cards and the 3.2 values cards, drawn like the 2.2a adversary scenes."""
    K = 'stroke="#1b1b1b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"'
    def man(x, y, c):
        return ('<circle cx="%d" cy="%d" r="7" fill="%s" %s/><path d="M%d %d v18 M%d %d l-7 12 M%d %d l7 12 M%d %d l-9 6 M%d %d l9 -4" fill="none" %s/>'
                % (x, y, c, K, x, y + 7, x, y + 25, x, y + 25, x, y + 12, x, y + 12, K))
    def bot(x, y, c='#9fb3f0'):
        return ('<rect x="%d" y="%d" width="34" height="30" rx="6" fill="%s" %s/><circle cx="%d" cy="%d" r="3" fill="#1b1b1b"/><circle cx="%d" cy="%d" r="3" fill="#1b1b1b"/>'
                '<path d="M%d %d v-6" %s/><circle cx="%d" cy="%d" r="3" fill="#e8b53a" %s/><path d="M%d %d h14" %s/>'
                % (x, y, c, K, x + 11, y + 12, x + 23, y + 12, x + 17, y, K, x + 17, y - 8, K, x + 10, y + 22, K))
    def arrow(m, x1, y1, x2, y2):
        return '<path d="M%d %d L%d %d" stroke="#1b1b1b" stroke-width="3" stroke-linecap="round" marker-end="url(#%s)"/>' % (x1, y1, x2, y2, m)
    DEF = lambda m: '<defs><marker id="%s" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="#1b1b1b"/></marker></defs>' % m
    shield = lambda x, y, c: '<path d="M%d %d l9 -3 9 3 v8 c0 6 -4 10 -9 12 c-5 -2 -9 -6 -9 -12 z" fill="%s" %s/>' % (x, y, c, K)
    sym = lambda x, y, t, c='#1b1b1b', s=22: '<text x="%d" y="%d" text-anchor="middle" font-family="Bangers,ZCOOL KuaiLe,sans-serif" font-size="%d" fill="%s">%s</text>' % (x, y, s, c, t)
    if which == 'race':
        # caution as a handicap: the careful runner carries the safety shield and falls behind; the leader dropped it
        s1 = ('<path d="M6 92 H204" stroke="#9aa3ab" stroke-width="2.5" stroke-linecap="round"/>' +
              '<path d="M190 92 V40" %s/><path d="M190 40 h16 l-4 6 4 6 h-16 z" fill="#fffdf6" %s/>' % (K, K) +
              man(40, 55, '#6fae5a') + shield(50, 62, '#b9d6a8') + '<path d="M28 46 q-3 5 0 7 M23 52 q-3 5 0 7" fill="none" stroke="#4a5fc9" stroke-width="2" stroke-linecap="round"/>' +
              '<g transform="rotate(-70 112 86)">%s</g>' % shield(104, 82, '#b9d6a8') +
              '<path d="M128 62 h-16 M130 70 h-20" stroke="#9aa3ab" stroke-width="2.5" stroke-linecap="round"/>' + man(150, 55, '#e07a5f'))
        # the rope: one lab goes over the edge and drags everyone tied to it
        s2 = ('<path d="M0 74 H150 L156 84 L150 92 L158 104 H0 Z" fill="#e3d6b8" %s/>' % K +
              ''.join(man(x, 37, c) for x, c in ((26, '#6fae5a'), (60, '#e8b53a'), (94, '#9fb3f0'))) +
              '<path d="M26 52 Q43 56 60 52 Q77 56 94 52 Q134 54 170 78" fill="none" stroke="#5c574e" stroke-width="2.5" stroke-dasharray="5 4" stroke-linecap="round"/>' +
              '<g transform="rotate(32 178 84)">%s</g>' % bot(162, 70, '#f6d5cc') +
              '<path d="M196 58 l6 -6 M200 68 l8 -2 M186 52 l2 -8" stroke="#d9492c" stroke-width="2.5" stroke-linecap="round"/>' + sym(60, 22, '!', '#d9492c', 24))
        return [s1, s2]
    # the prior problem: everyone values something different, and the AI has to pick
    bub = lambda x, y: '<ellipse cx="%d" cy="%d" rx="16" ry="11" fill="#fffdf6" %s/>' % (x, y, K)
    s3 = (man(22, 52, '#e07a5f') + bub(36, 20) + '<path d="M36 27 c-6 -4 -8 -8 -5 -10 c2 -1 4 0 5 2 c1 -2 3 -3 5 -2 c3 2 1 6 -5 10z" fill="#d9492c" %s/>' % K +
          man(70, 52, '#e8b53a') + bub(84, 20) + '<path d="M76 17 h16 M84 13 v12 M79 17 l-3 6 h6z M89 17 l-3 6 h6z" fill="none" stroke="#1b1b1b" stroke-width="2" stroke-linejoin="round"/>' +
          bot(116, 58) + sym(133, 44, '?', '#1b1b1b', 24) +
          man(188, 52, '#6fae5a') + bub(174, 20) + '<path d="M166 26 c0 -8 6 -12 14 -12 c0 8 -6 12 -14 12z M166 26 l9 -8" fill="#b9d6a8" stroke="#1b1b1b" stroke-width="2" stroke-linejoin="round"/>')
    # the power problem: one party on the podium writes the rules, and the AI applies them to everyone
    crowd = ''.join('<circle cx="%d" cy="%d" r="5" fill="%s" %s/><path d="M%d %d q6 -7 12 0" fill="none" %s/>' % (x, y, c, K, x - 6, y + 13, K)
                    for x, y, c in ((156, 30, '#6fae5a'), (180, 28, '#e07a5f'), (200, 34, '#9fb3f0'), (150, 58, '#e8b53a'), (172, 56, '#9fb3f0'), (194, 60, '#6fae5a'),
                                    (160, 84, '#e07a5f'), (184, 84, '#e8b53a')))
    s4 = (DEF('vsa3') + '<rect x="8" y="70" width="44" height="26" rx="3" fill="#e3d6b8" %s/>' % K + man(30, 33, '#e8b53a') +
          '<path d="M23 26 l1 -9 4 4 3 -6 3 6 4 -4 1 9z" fill="#ffd166" %s/>' % K +
          '<rect x="40" y="38" width="14" height="18" rx="2" fill="#fffdf6" %s/><path d="M43 44 h8 M43 49 h8" stroke="#9aa3ab" stroke-width="1.8" stroke-linecap="round"/>' % K +
          arrow('vsa3', 58, 50, 76, 50) + bot(82, 36) +
          arrow('vsa3', 120, 46, 140, 34) + arrow('vsa3', 120, 52, 140, 60) + arrow('vsa3', 120, 58, 146, 84) + crowd)
    return [s3, s4]

def scenes_in(block, scenes):
    """A scene under each card title, kept outside the card's fold."""
    hs = list(re.finditer(r'</h4>', block))
    assert len(hs) == len(scenes), (len(hs), len(scenes))
    for m, s in reversed(list(zip(hs, scenes))):
        svg = dk_svg('0 0 210 104', '', s).replace('<svg ', '<svg class="dk-chart dk-scene dk-keep" ', 1).replace('class="dk-chart" ', '', 1)
        block = block[:m.end()] + svg + block[m.end():]
    return block

def feel_scenes_in(block):
    """A scene under each card title, marked to stay outside the card's fold."""
    hs = list(re.finditer(r'</h4>', block)); sc = feel_scenes()
    assert len(hs) == 6, len(hs)
    for m, s in reversed(list(zip(hs, sc))):
        block = block[:m.end()] + s.replace('class="dk-scene"', 'class="dk-scene dk-keep"', 1).replace('class="dk-chart dk-scene"', 'class="dk-chart dk-scene dk-keep"', 1) + block[m.end():]
    return block

def slim_ends(block, T):
    """Each adversary card: label, heading, a scene and one short line; the outcome icons stay."""
    scenes = ends_scenes(); base = '/reference' if 'reference#' in block or 'reference"' in block else '/reference-zh'
    base = re.search(r'href="(/reference(?:-zh)?)#', block).group(1) if re.search(r'href="(/reference(?:-zh)?)#', block) else base
    cards = re.findall(r'<(div|a) class="endc"[^>]*>.*?</\1>(?=\s*<(?:div|a) class="endc"|\s*</div>\s*<div class="ends-arrows")', block, re.S)
    ms = list(re.finditer(r'<(div|a) class="endc"[^>]*>.*?</\1>(?=\s*<(?:div|a) class="endc"|\s*</div>\s*<div class="ends-arrows")', block, re.S))
    assert len(ms) == 4, len(ms)
    out = block
    for m, sc, line in reversed(list(zip(ms, scenes, T['ends4']))):
        c = m.group(0); tag = m.group(1)
        head = re.search(r'<span class="ek">.*?</span><h4>.*?</h4>', c, re.S).group(0)
        icons = re.search(r'<span class="endc-icons">.*?</span></span></span>', c, re.S)
        paras = ''.join(re.findall(r'<p\b[^>]*>.*?</p>', c, re.S))
        more = ('<button type="button" class="dk-more-btn" aria-expanded="false" data-more="%s" data-less="%s">%s +</button><div class="dk-more-body" hidden>%s</div>'
                % (E(T['more_detail']), E(T['less_detail']), E(T['more_detail']), paras)) if paras else ''
        new = c[:c.index('>') + 1].replace('class="endc"', 'data-auto="1" class="endc"', 1) + head + sc + '<p>%s</p>' % refs_html(line, base) + more + (icons.group(0) if icons else '') + '</%s>' % tag
        out = out[:m.start()] + new + out[m.end():]
    return out

def subgoal_tabs(block, pg):
    fig = re.findall(r'<figure\b.*?</figure>', block, re.S)[0]
    return swap_fig_svgs(block, 0, H('subgoals', pg.lang, svg_texts(fig), (pg.T['subtabs'], pg.refbase)))

def J2(a, b, lang): return (a + b) if lang == 'zh' else (a + ' ' + b)

def card_heading(block, n, new):
    """Replace the heading of the block's nth card (the chart now carries its old point)."""
    hs = [m for m in re.finditer(r'<h4>.*?</h4>', block, re.S)]
    m = hs[n]
    return block[:m.start()] + '<h4>%s</h4>' % html.escape(new) + block[m.end():]

def card_nohead(block, n):
    """Drop the nth card's label and heading; its chart title says the same thing."""
    hs = [m for m in re.finditer(r'<h4>.*?</h4>', block, re.S)]
    m = hs[n]; k = block.rfind('<span class="k">', 0, m.start())
    assert k >= 0 and re.fullmatch(r'<span class="k">[^<]*</span>\s*', block[k:m.start()]), 'label then heading'
    return block[:k] + block[m.end():]

def swap_fig(block, n, kind, T, texts=False):
    """Replace the block's nth figure with an interactive one; texts=True hands it the original labels."""
    starts = [m.start() for m in re.finditer(r'<figure\b', block)]
    assert len(starts) > n, ('figure', n, len(starts))
    a = starts[n]; b = block.index('</figure>', a) + 9
    assert block[a:b].count('<figure') == 1
    return block[:a] + widget(kind, T, block[a:b], {'t': svg_texts(block[a:b])} if texts else None) + block[b:]

def risk_chart(T, src_svg):
    """How likely is disaster: one tile per person, the number big and the odds in plain words."""
    t = [text(x) for x in re.findall(r'<text\b[^>]*>(.*?)</text>', src_svg, re.S)]
    rows = [(t[1], t[2], t[3], T['odds'][0]), (t[4], t[5], t[6], T['odds'][1]), (t[7], t[8], t[9], T['odds'][2]), (t[10], t[11], t[12], T['odds'][3])]
    tiles = ''.join('<div class="dkr-tile"><b class="dkr-v">%s</b><span class="dkr-odds">%s</span><b class="dkr-n">%s</b><span class="dkr-q">%s</span></div>'
                    % (E(v.replace(' to ', '\u2013')), E(o), E(n), E(q)) for n, q, v, o in rows)
    return '<div class="dkh"><p class="dkh-t">%s</p><div class="dkr">%s</div></div>' % (E(T['risk_title']), tiles)

def econ_chart(T):
    """The world economy by 2055: three squares, each sized by area, so x190 dwarfs the rest."""
    Ec = T['econ']; top = 1.3 ** 20
    sq = ''
    for lab, r in zip(Ec['rows'], (3, 12, 30)):
        m = (1 + r / 100.0) ** 20
        side = (m / top) ** .5 * 100
        sq += ('<div class="dke-item"><i style="--f:%.4f"></i><b class="dkr-v">×%s</b><span class="dkr-q">%s</span></div>'
               % (side / 100, ('%.1f' % m) if m < 10 else ('%d' % round(m)), E(lab)))
    return '<div class="dkh"><p class="dkh-t">%s</p><p class="dkh-q">%s</p><div class="dke">%s</div></div>' % (E(Ec['title']), E(Ec['sub']), sq)

# ---------------------------------------------------------------- charts rebuilt in HTML
def svg_texts(fig):
    """Label strings of a figure's desktop chart, in drawing order."""
    m = re.search(r'<svg class="lx-d"[^>]*>(.*?)</svg>', fig, re.S) or re.search(r'<svg\b[^>]*>(.*?)</svg>', fig, re.S)
    return [text(x) for x in re.findall(r'<text\b[^>]*>(.*?)</text>', m.group(1), re.S)]

def E(x): return html.escape(x)

def H(kind, lang, t, extra=None):
    """One chart as HTML, from the labels of the original drawing."""
    j = '' if lang == 'zh' else ' '
    J = lambda *k: j.join(t[i] for i in k)
    T0 = lambda i: '<p class="dkh-t">%s</p>' % E(t[i])
    if kind == 'funding':
        return ('<div class="dkh">%s<div class="dkh-row"><div class="dkh-top"><span>%s</span><b class="dkh-v">%s</b></div><div class="dkh-bar dkh-fill dkh-blue"><i style="width:100%%"></i></div></div>'
                '<div class="dkh-row"><div class="dkh-top"><span>%s</span><b class="dkh-v">%s</b></div><div class="dkh-bar dkh-fill"><i style="width:1%%"></i></div></div></div>') % (T0(0), E(t[1]), E(t[2]), E(t[3]), E(t[4]))
    if kind == 'timeline':
        items = [(t[1], t[2]), (t[3], t[4]), (t[5], t[6]), (t[7], J(8, 9))]
        return '<div class="dkh">%s<ol class="dkh-tl">%s</ol></div>' % (T0(0), ''.join('<li><b>%s</b><span>%s</span></li>' % (E(y), E(x)) for y, x in items))
    if kind in ('payoff4', 'payoff3'):
        if kind == 'payoff4':
            cols, rows = (t[1], t[2]), (t[3], t[7]); cells = [[(t[4], t[5], 'bad'), (t[6], '', '')], [(t[8], '', ''), (t[9], t[10], 'good')]]; note = t[11]
        else:
            cols, rows = (t[1], t[2]), (t[3], t[4]); cells = [[(t[5], t[6], 'good'), (t[7], t[8], '')], [(t[9], t[10], ''), (t[11], t[12], 'bad')]]; note = t[13]
        g = '<div></div>' + ''.join('<div class="dkh-ch">%s</div>' % E(c) for c in cols)
        for r, row in zip(rows, cells):
            g += '<div class="dkh-rh">%s</div>' % E(r) + ''.join('<div class="dkh-cell %s"><b>%s</b>%s</div>' % (k, E(a), ('<span>%s</span>' % E(b)) if b else '') for a, b, k in row)
        return '<div class="dkh">%s<div class="dkh-grid">%s</div><p class="dkh-note">%s</p></div>' % (T0(0), g, E(note))
    if kind == 'problems':
        L = extra
        import random
        rnd = random.Random(3)
        cols = ['#4a5fc9', '#6fae5a', '#e8b53a', '#e07a5f', '#1f9c96']
        many = ''.join('<i style="left:%d%%;top:%d%%;background:%s"></i>' % (rnd.randint(8, 84), rnd.randint(10, 80), rnd.choice(cols)) for _ in range(16))
        few = ''.join('<i style="left:%d%%;top:%d%%;background:%s"></i>' % (x, y, c) for x, y, c in ((24, 30, '#4a5fc9'), (58, 52, '#6fae5a'), (36, 70, '#e8b53a')))
        d1 = ('<div class="dpb-row"><div class="dpb-fig"><div class="dpb-cloud">%s</div><span>%s</span></div><span class="dpb-to" aria-hidden="true">→</span>'
              '<div class="dpb-fig"><div class="dpb-note">%s</div><span>%s</span></div></div>') % (many, E(L[0]), few, E(L[1]))
        d2 = ('<div class="dpb-row"><div class="dpb-fig"><div class="dpb-out">✓ 100%%</div><span>%s</span></div><span class="dpb-to" aria-hidden="true">≠?</span>'
              '<div class="dpb-fig"><div class="dpb-in">?</div><span>%s</span></div></div>') % (E(L[2]), E(L[3]))
        box = lambda a, d: '<div class="dkh-box"><span class="dkh-k">%s</span><b>%s</b>%s<span>%s</span></div>' % (E(t[a]), E(t[a + 1]), d, E(t[a + 2]))
        return '<div class="dkh dkh-two">%s%s</div>' % (box(0, d1), box(3, d2))
    if kind == 'subgoals':
        ST, base = extra
        res = [(6, 7, 8), (9, 10, 11), (12, 13, 14), (15, 16, 17)]
        panels = [(ST['head'], list(tab)) for tab in ST['tabs']]
        panels.append((ST['head'], [(h, J(b, c)) for h, (a, b, c) in zip(ST['res'], res)]))
        # one picture per subgoal: power button, shield, lightbulb, wrench, factory
        ico = ['<path d="M12 3v8"/><path d="M6.3 6.8a8 8 0 1 0 11.4 0"/>',
               '<path d="M12 3l7 3v5c0 5-3.4 8.3-7 10-3.6-1.7-7-5-7-10V6z"/><circle cx="12" cy="11.5" r="2.6"/>',
               '<path d="M9.5 18h5M10.5 21h3"/><path d="M12 3a6 6 0 0 0-3.8 10.6c.6.6 1 1.4 1 2.4h5.6c0-1 .4-1.8 1-2.4A6 6 0 0 0 12 3z"/>',
               '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9z"/>',
               '<path d="M3 20V9l5 3V9l5 3V5h4l1 7h3v8z"/><path d="M7 16h2M12 16h2M17 16h1"/>']
        # hub positions (percent of a 16:9 box) and the spoke ends in a 640x360 drawing
        pos = [(50, 11), (87.5, 30.5), (81, 86), (19, 86), (12.5, 30.5)]
        chips = ''.join('<button type="button" class="dkh-chip dsg-tab" data-i="%d" aria-pressed="%s" style="--x:%s%%;--y:%s%%">'
                        '<svg class="dk-chart dsg-ico" viewBox="0 0 24 24" aria-hidden="true">%s</svg><span>%s</span></button>'
                        % (i, 'true' if i == 4 else 'false', pos[i][0], pos[i][1], ico[i], E(t[i])) for i in range(5))
        spokes = ('<svg class="dk-chart dsg-spokes" data-keep="1" viewBox="0 0 640 360" preserveAspectRatio="none" aria-hidden="true">%s</svg>'
                  % ''.join('<line data-i="%d" x1="320" y1="180" x2="%d" y2="%d"/>' % (i, x * 6.4, y * 3.6) for i, (x, y) in enumerate(pos)))
        core = '<div class="dsg-core"><strong>%s</strong></div>' % E(ST['hub_k'])
        body = ''.join('<div class="dsg-panel" data-i="%d"%s><p class="dkh-t dkh-arrow">%s</p><div class="dkh-four">%s</div></div>' % (
            i, '' if i == 4 else ' hidden', E(h), ''.join('<div class="dkh-box"><b>%s</b><span>%s</span></div>' % (E(a), refs_html(b, base)) for a, b in cards))
            for i, (h, cards) in enumerate(panels))
        return '<div class="dkh dsg"><p class="dsg-hint">%s</p><div class="dkh-chips dsg-tabs dsg-hub" data-on="4">%s%s%s</div>%s</div>' % (E(ST['tap']), spokes, core, chips, body)
    if kind == 'whose':
        groups = ''.join('<span class="dkh-chip">%s</span>' % E(t[i]) for i in range(1, 5))
        return ('<div class="dkh">%s<div class="dkh-flow"><div class="dkh-col">%s</div><span class="dkh-to" aria-hidden="true">→</span>'
                '<div class="dkh-q-box"><b>?</b><span>%s</span></div><span class="dkh-to" aria-hidden="true">→</span><span class="dkh-chip dkh-hot">%s</span></div></div>') % (T0(0), groups, E(t[6]), E(t[7]))
    if kind == 'decide':
        few = [J(1, 2), J(3, 4), J(5, 6), J(7, 8, 10)]
        dots = ''.join('<div class="dkh-few"><i></i><span>%s</span></div>' % (E(x) if '<small>' not in x else E(x.split('<small>')[0]) + '<small>' + x.split('<small>')[1]) for x in few)
        if not extra:
            return '<div class="dkh">%s<div class="dkh-fewrow">%s</div><div class="dkh-many"><span>%s</span></div></div>' % (T0(0), dots, E(t[9]))
        # the reader's pick lights up whoever actually holds that power today
        q, opts, cfg = extra
        ask = '<div class="dkh-ask"><p class="dkh-q">%s</p><div class="dkh-opts">%s</div></div>' % (E(q), ''.join(
            '<button type="button" class="dki-case dkh-opt" data-k="%d" aria-pressed="false">%s</button>' % (k, E(o)) for k, o in enumerate(opts)))
        return ('<div class="dkh" data-ask="%s">%s%s<div class="dkh-fewrow">%s</div><div class="dkh-many"><span>%s</span></div><p class="dkh-reply" aria-live="polite"></p></div>'
                % (html.escape(json.dumps(cfg, ensure_ascii=False)), ask, T0(0), dots, E(t[9])))
    if kind == 'twoways':
        return ('<div class="dkh">%s<div class="dkh-two"><div class="dkh-box"><span class="dkh-k">%s</span><div class="dkh-eq"><b>%s</b><em>≠</em><b>%s</b></div><span>%s</span></div>'
                '<div class="dkh-box"><span class="dkh-k">%s</span><div class="dkh-eq"><b>%s</b><em>%s</em><b>%s</b></div><span>%s</span></div></div></div>') % (
                T0(0), E(t[1]), E(J(2, 3)), E(J(4, 5)), E(t[6]), E(t[7]), E(J(8, 9)), E(t[10]), E(J(11, 12)), E(t[13]))
    if kind == 'lost':
        import random
        rnd = random.Random(7)
        dots = ''.join('<i style="left:%d%%;top:%d%%;--d:%s"></i>' % (rnd.randint(6, 90), rnd.randint(8, 86), rnd.choice(['#4a5fc9', '#6fae5a', '#e8b53a', '#e07a5f', '#1f9c96']))
                       for _ in range(26))
        fork = ('<svg class="dkf-fork" viewBox="0 0 60 100" preserveAspectRatio="none" aria-hidden="true">'
                '<path d="M0 50 C30 50 30 18 60 18" stroke="#1f9c96" stroke-width="4" fill="none" vector-effect="non-scaling-stroke"/>'
                '<path d="M0 50 C30 50 30 82 60 82" stroke="#d9492c" stroke-width="4" fill="none" vector-effect="non-scaling-stroke"/></svg>')
        return ('<div class="dkh">%s<div class="dkf">'
                '<div class="dkf-cloud"><div class="dkf-dots">%s</div><span>%s</span></div>'
                '<div class="dkf-funnel"><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><path class="dkf-h" d="M2 2 L98 36 L98 64 L2 98 Z"/><path class="dkf-v" d="M2 2 L98 2 L64 98 L36 98 Z"/></svg><span>%s</span></div>'
                '<div class="dkf-score"><b>%s</b><span>%s</span></div>%s'
                '<div class="dkf-ends"><span class="dkh-chip dkh-ok">%s</span><span class="dkh-chip dkh-hot">%s</span></div>'
                '</div></div>') % (T0(0), dots, E(t[1]), E(t[2]), E(t[3]), E(t[4]), fork, E(t[5]), E(t[6]))
    if kind == 'talk':
        return ('<div class="dkh">%s<div class="dkh-two"><div class="dkh-box"><span class="dkh-k">%s</span><b>✕</b><span>%s</span></div>'
                '<div class="dkh-box"><span class="dkh-k">%s</span><b>%s</b><span>%s</span></div></div></div>') % (T0(0), E(t[1]), E(t[2]), E(t[3]), E(J(4, 5)), E(t[6]))
    if kind == 'grader':
        box = lambda a, b, c='': '<div class="dkh-box"><span class="dkh-k">%s</span><b class="dkh-big">%s</b>%s</div>' % (E(a), E(b), ('<span>%s</span>' % E(c)) if c else '')
        return ('<div class="dkh">%s<div class="dkh-steps">%s<span class="dkh-to">%s</span>%s<span class="dkh-to">%s</span>%s</div><p class="dkh-note">%s</p></div>') % (
                T0(0), box(t[1], t[2]), E(t[9]), box(t[3], t[4]), E(t[10]), box(t[5], t[6], t[7]), E(t[8]))
    if kind == 'levers':
        rows = [(3, 4, (5, 6), (7, 8)), (9, 10, (11, 12), (13, 14)), (15, 16, (17, 18), (19, 20)), (21, 22, (23, 24), (25, 26))]
        body = ''.join('<tr><th><b>%s</b><span>%s</span></th><td>%s</td><td>%s</td></tr>' % (E(t[a]), E(t[b]), E(J(*c)), E(J(*d))) for a, b, c, d in rows)
        return '<div class="dkh"><div class="dkh-scroll"><table class="dkh-tab"><thead><tr><th></th><th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table></div><p class="dkh-note">%s</p></div>' % (
               E(t[1]), E(t[2]), body, E(t[27]))
    if kind == 'orgs':
        cols, names, grid = extra
        head = '<tr><th></th>%s</tr>' % ''.join('<th>%s</th>' % E(c) for c in cols)
        body = ''.join('<tr><th>%s</th>%s</tr>' % (E(n), ''.join('<td><i class="dkh-o%d"></i></td>' % v for v in row)) for n, row in zip(names, grid))
        return ('<div class="dkh"><div class="dkh-scroll"><table class="dkh-tab dkh-dots"><thead>%s</thead><tbody>%s</tbody></table></div>'
                '<p class="dkh-note"><i class="dkh-o2"></i> %s &nbsp; <i class="dkh-o1"></i> %s</p><p class="dkh-note">%s</p></div>') % (head, body, E(t[12]), E(t[13]), E(t[14]))
    if kind == 'numbers':
        def num(x): return float(re.search(r'[\d.]+', x.replace(',', '')).group(0))
        rows = [(1, 2, 3), (4, 5, 6), (7, 8, 9)]
        body = ''.join('<div class="dkh-row"><div class="dkh-top"><b>%s</b></div><div class="dkh-bar dkh-fill dkh-pale"><i style="width:%.1f%%"></i></div><span class="dkh-q">%s</span>'
                       '<div class="dkh-bar dkh-fill"><i style="width:%.2f%%"></i></div><span class="dkh-q">%s</span></div>' % (E(t[a]), num(t[b]), E(t[b]), max(.8, num(t[c])), E(t[c])) for a, b, c in rows)
        return '<div class="dkh">%s<p class="dkh-note">%s</p></div>' % (body, E(t[10]))
    raise ValueError(kind)

def orgs_grid(fig, t):
    """Which organisation works where, read dot by dot from the original chart: 2 primary, 1 secondary, 0 none."""
    sv = re.search(r'<svg class="lx-d"[^>]*>(.*?)</svg>', fig, re.S).group(1)
    colx = [float(x) for x in re.findall(r'<text x="([\d.]+)" y="20" text-anchor="middle"', sv)]
    rowy = [float(y) for y in re.findall(r'<text x="0" y="([\d.]+)"[^>]*>[^<]+</text>', sv)][:8]
    assert len(colx) == 4 and len(rowy) == 8, (colx, rowy)
    grid = [[0] * 4 for _ in rowy]
    for cx, cy, rest in re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="6.5"([^>]*)/>', sv):
        c = min(range(4), key=lambda k: abs(colx[k] - float(cx))); r = min(range(8), key=lambda k: abs(rowy[k] - 4 - float(cy)))
        grid[r][c] = 1 if 'opacity=' in rest else 2
    return (t[0:4], t[4:12], grid)

def decide_ask(B, T):
    """The page's who-should-decide question, folded into the who-actually-decides chart."""
    qb = one(B, '<div class="rv" style="margin-top:24px">')
    q = text(re.search(r'<p\b[^>]*>(.*?)</p>', qb, re.S).group(1))
    opts = [text(x) for x in re.findall(r'<button type="button" class="pbtn"[^>]*>(.*?)</button>', qb, re.S)]
    assert len(opts) == 4 and len(T['decide_ask']['replies']) == 4, opts
    return (q, opts, T['decide_ask'])

def rebuild(block, n, kind, lang, extra=None):
    """Swap the block's nth figure drawing for its HTML rebuild; the source line stays."""
    figs = re.findall(r'<figure\b.*?</figure>', block, re.S)
    t = svg_texts(figs[n])
    extra = orgs_grid(figs[n], t) if kind == 'orgs' else extra
    return swap_fig_svgs(block, n, H(kind, lang, t, extra))

def swap_fig_svgs(block, n, new_svg):
    """Put one deck-drawn svg in place of every svg inside the block's nth figure."""
    figs = [m for m in re.finditer(r'<figure\b.*?</figure>', block, re.S)]
    f = figs[n]; inner = re.sub(r'<svg\b.*?</svg>\s*', '', f.group(0), flags=re.S)
    inner = inner.replace('>', '>' + new_svg, 1)
    return block[:f.start()] + inner + block[f.end():]

def swap_svgs(block, new):
    """Replace the block's charts, in order, with deck redraws."""
    old = re.findall(r'<svg\b.*?</svg>', block, re.S)
    assert len(old) == len(new), ('chart count', len(old), len(new))
    for o, n in zip(old, new): block = block.replace(o, n, 1)
    return block


# ---------------------------------------------------------------- the slide plan
def plan(pg):
    """Every slide in order: dict(key, sec, chip, head, body)."""
    T = pg.T; S = []
    s = pg.s

    # -- opening: the masthead, then the three claims, then the answer
    m = s.index('<header class="masthead'); mh = s[m:s.index('</header>', m) + 9]
    mw = kids(kids(mh)[0]) if kids(mh)[0].startswith('<div class="wrap') else None
    assert mw, 'masthead wrap'
    care = one(mw, '<div class="mh-care')
    cover = ''.join(b for b in mw if b is not care)
    # the brain drawing beside the title is dropped from the deck cover
    cover, nb = re.subn(r'<(div|svg|figure|span)\b[^>]*class="[^"]*mh-brain[^"]*"[^>]*>.*?</\1>', '', cover, count=1, flags=re.S)
    assert nb == 1, 'brain drawing not found'
    # the cliff is an illustration, so it gets a hand-picked paper palette rather than the chart rules
    ci = cover.index('<figure class="cliff'); cj = cover.index('</figure>', ci)
    fig = cover[ci:cj].replace('<svg', '<svg data-keep="1"')
    # the cliff-edge label sits low on the rock face, away from the climbers
    fig, nlab = re.subn(r'<text x="548" y="150" text-anchor="end"', '<text x="564" y="420" text-anchor="start"', fig)
    assert nlab == 1, ('cliff edge label', nlab)
    def cliff_colour(m):
        v = m.group(2).lower()
        assert v in CLIFF, ('cliff colour with no paper mapping', v)
        return '%s="%s"' % (m.group(1), CLIFF[v])
    # the roped runners become one group the deck can move
    ri = fig.index('<!-- rope + runners -->'); rj = fig.index('<g stroke=', ri); rk = fig.index('</g>\n', fig.index('translate(500,206)', rj)) + 4
    team = fig[rj:rk]; assert team.count('<g transform=') == 6, team.count('<g transform=')
    rope = re.search(r'<path d="M70,206[^>]*/>', fig).group(0)
    fig = fig.replace(rope, '<g class="cr-rope">%s</g>' % rope, 1).replace(team, '<g class="cr-team">%s</g>' % team, 1)
    # the figure already over the edge moves with the group; its drop arrow and the prize lines can fade
    assert fig.count('<g transform="translate(606,214) rotate(38)">') == 1
    fig = fig.replace('<g transform="translate(606,214) rotate(38)">', '<g class="cr-fall" transform="translate(606,214) rotate(38)">', 1)
    fig, na = re.subn(r'<path d="M628,236 C640,256', '<path class="cr-arrow" d="M628,236 C640,256', fig); assert na == 1
    fig, npz = re.subn(r'<text x="668" y="(\d+)"', lambda m: ('<text class="cr-ptext" x="668" y="%s"' % m.group(1)) if 60 <= int(m.group(1)) <= 140 else m.group(0), fig)
    assert fig.count('class="cr-ptext"') >= 4, fig.count('class="cr-ptext"')
    C = T['cliffgame']
    ctl = ('<div class="cr-ctl" data-c="%s"></div>' % html.escape(json.dumps(C, ensure_ascii=False)))
    fig = fig + ctl
    fig = re.sub(r'<text\b[^>]*>', lambda t: t.group(0).replace('fill="#ffd88a"', 'fill="#8a5d00"'), fig)   # the prize heading, not its glow
    fig = re.sub(r'\b(fill|stroke|stop-color)="(#[0-9a-fA-F]{3,6})"', cliff_colour, fig)
    fig = re.sub(r'<text\b[^>]*>', lambda t: re.sub(r'fill="(?!#1b1b1b|#5c574e|#6f6a60)#[0-9a-fA-F]{3,6}"', 'fill="#1b1b1b"', t.group(0)), fig)   # text: ink or grey
    cover = cover[:ci] + fig + cover[cj:]
    intro = dict(id='crossroads', num='', label=pg.label['crossroads'], acc=T['intro_acc'])
    S.append(dict(key='cover', sec=intro, wrap='mast', anchor='top', body=cover))
    # a comic scene under each card title, like the 2.2a adversary cards
    ends = list(re.finditer(r'</h3>', care)); assert len(ends) == 3, len(ends)
    for m, sc in reversed(list(zip(ends, care_scenes()))): care = care[:m.end()] + sc + care[m.end():]
    care_title = re.search(r'<h2 class="mh-h"><span>(.*?)</span></h2>', care, re.S)
    assert care_title
    S.append(dict(key='care', sec=intro, wrap='mast', kicker=T['intro_kick'], title=care_title.group(1),
                  body=care.replace(care_title.group(0), '', 1)))
    cross = pg.section('crossroads')
    claims = kids(one(cross, '<div class="claims'))
    assert len(claims) == 3
    def claim_card(c):
        if 'claim-1' in c[:80]:
            c = rebuild(c, 1, 'timeline', pg.lang); c = rebuild(c, 0, 'funding', pg.lang)
            I = T['incidents']
            # the "!" is drawn upright and centred; the comic font slants it off the middle of the dot
            BANG = '<svg viewBox="0 0 10 10" aria-hidden="true"><rect x="3.9" y="0.8" width="2.2" height="5.6" rx="1.1" fill="#fffdf6"/><circle cx="5" cy="8.5" r="1.2" fill="#fffdf6"/></svg>'
            items = ''.join('<li class="dtl-%s"><i aria-hidden="true">%s</i><b>%s</b><span>%s</span></li>' % (
                ('esc' if k else 'warn'), (BANG if k else ''), E(y), E(x)) for y, x, k, r in I['timeline'])
            # what the labs expect next, drawn as a range at the end of the line
            ay, ax, ar = I['ahead']
            items += '<li class="dtl-fut"><i aria-hidden="true"></i><b>%s</b><span>%s</span></li>' % (E(ay), E(ax))
            nums = sorted(set(int(n) for y, x, k, r in I['timeline'] + [(ay, ax, 0, ar)] for n in re.findall(r'\d+', r)))
            srcline = '<p class="dtl-src">%s %s</p>' % (E(T['src_word']), ' '.join('<a href="%s#s%d">%d</a>' % (pg.refbase, n, n) for n in nums))
            key = ('<p class="dtl-key"><span class="dtl-warn"><i></i>%s</span><span class="dtl-esc"><i>%s</i>%s</span><span class="dtl-fut"><i></i>%s</span></p>'
                   % (E(I['tl_key'][0]), BANG, E(I['tl_key'][1]), E(I['tl_key'][2])))
            c, ntl = re.subn(r'<ol class="dkh-tl">.*?</ol>', lambda m: key + '<ol class="dkh-tl dtl">%s</ol>' % items + srcline, c, flags=re.S)
            assert ntl == 1
            # no separate sources lines on this slide: the timeline's own list carries 104 and 105, and the funding chart is sourced on 1.1
            c, nr = re.subn(r'(<p class="cl-sub">.*?)</p>', lambda m: re.sub(r'<a class="ref"[^>]*>\d+</a>', '', m.group(1)) + '</p>', c, count=1, flags=re.S)
            c, nf = re.subn(r'<p class="fig-src">.*?</p>', '', c, flags=re.S)
            assert nr == 1 and nf == 1, (nr, nf)
            # the timeline takes the left panel, under its own title
            figs = re.findall(r'<figure\b.*?</figure>', c, re.S)
            assert len(figs) == 2 and c.count(figs[0]) == 1 and c.count(figs[1]) == 1 and 'dtl' in figs[1]
            tl, nt = re.subn(r'<p class="dkh-t">.*?</p>', '<p class="dkh-t">%s</p>' % E(I['tl_title']), figs[1], count=1, flags=re.S)
            assert nt == 1
            i0 = c.index(figs[0]); i1 = c.index(figs[1])
            c = c[:i0] + tl + c[i0 + len(figs[0]):i1] + figs[0] + c[i1 + len(figs[1]):]
        if 'claim-3' in c[:80]:
            figs3 = re.findall(r'<figure\b.*?</figure>', c, re.S)
            c = swap_fig_svgs(c, 1, globals()['H']('problems', pg.lang, svg_texts(figs3[1]), T['prob'])); c = rebuild(c, 0, 'payoff4', pg.lang)
        if 'claim-2' in c[:80]:
            figs = re.findall(r'<figure\b.*?</figure>', c, re.S)
            src = re.search(r'<svg class="lx-d"[^>]*>(.*?)</svg>', figs[1], re.S).group(1)
            c = swap_fig_svgs(c, 1, risk_chart(T, src))
            c = swap_fig_svgs(c, 0, econ_chart(T))
        # open the halves, and turn "Read the chapter" into a real link to the chapter's slide
        c = c.replace('<div class="cl-half"', '<div data-auto="1" class="cl-half"')
        href = re.search(r'<h3><a href="(#[^"]+)"', c).group(1)
        c, ng = re.subn(r'<span class="cl-go">(.*?)</span>', r'<a class="cl-go" href="%s">\1</a>' % href, c)
        assert ng == 1, 'claim link'
        return c
    claims = [claim_card(c) for c in claims]
    for i, c in enumerate(claims):
        h3 = re.search(r'<h3><a href="#[^"]+">(.*?)</a></h3>', c, re.S); num = re.search(r'<span class="cl-n">\d</span>\s*', c)
        assert h3 and num
        c = c.replace(h3.group(0), '', 1).replace(num.group(0), '', 1)
        S.append(dict(key='claim%d' % (i + 1), sec=intro, wrap='cross', anchor='crossroads' if i == 0 else '',
                      kicker=T['claim_kick'] % (i + 1), title=h3.group(1), body='<div class="claims">%s</div>' % c))
    close = one(cross, '<div class="mh-close'); mk = re.search(r'<span class="mc-k">(.*?)</span>\s*', close, re.S)
    assert mk
    close = close.replace(mk.group(0), '', 1)
    hs = [text(h) for h in re.findall(r'<h3>(.*?)</h3>', close, re.S)]; ps = [text(p) for p in re.findall(r'<p>(.*?)</p>', close, re.S)]
    assert len(hs) == 2 and len(ps) == 2, (len(hs), len(ps))
    S.append(dict(key='solution', sec=intro, wrap='cross', kicker=T['intro_kick'], title=mk.group(1),
                  body=widget_plain('fork', T, {'ends': hs, 'subs': ps})))
    fork_hs, fork_ps = list(hs), list(ps)     # kept for 5.3; later chapters reuse these names

    def add(ch, parts):
        for j, (chip, body) in enumerate(parts):
            S.append(dict(key='%s%s' % (ch['num'], 'abcdefgh'[j] if len(parts) > 1 else ''), sec=ch, wrap='dd',
                          anchor=ch['id'] if j == 0 else '', chip=chip, part=j, parts=len(parts), body=body))

    P = T['parts']
    def stand(ch): return '<p class="stand">%s</p>' % ch['stand']
    def key(ch): k = [b for b in ch['blocks'] if b.startswith('<div class="keyline')]; return k[0] if k else ''

    # 1.1
    ch = pg.chapter('why-irresistible'); B = ch['blocks']
    bet = one(B, '<div class="bet').replace('<div class="bet rv"', '<div class="bet rv t-compact"', 1)
    add(ch, [('', stand(ch) + auto(swap_svgs(fold_fig_src(one(B, '<div class="ddgrid')), charts_11(T))) + key(ch) + bet)])        # the funding guess closes the chapter, in place of a quick check on the same question
    # 2.1
    ch = pg.chapter('why-upside'); B = ch['blocks']
    add(ch, [(P['2.1'][0], stand(ch) + swap_fig(one(B, '<figure'), 0, 'growth', T)),
             (P['2.1'][1], part_head(*T['heads']['2.1b']) + feel_scenes_in(feel_icons(one(B, '<div class="ddgrid'), pg.lang)))])             # six cards start closed
    # 2.2
    ch = pg.chapter('why-it-ends-badly'); B = ch['blocks']
    bodies = [b for b in B if b.startswith('<p class="body')]
    k, t = T['heads']['2.2c']
    # the six scenario cards: the band's icon for each outcome, and a button that says what it opens
    ends = one(B, '<div class="ends')
    icons = re.findall(r'<span class="eo-w">(<svg\b.*?</svg>)', ends, re.S)
    assert len(icons) == 6, len(icons)
    six = one(B, '<div class="ddgrid')
    cards = [m for m in re.finditer(r'<div class="ddc [a-z]"><span class="k">([^<]*)</span>', six)]
    assert len(cards) == 6, len(cards)
    if pg.lang == 'en':
        assert [c.group(1) for c in cards] == ['Engineered pandemic', 'Nuclear and autonomous weapons', 'Resources', 'Self-preservation', 'Infrastructure', 'Geoengineering']
    ICON_FOR = [0, 5, 2, 3, 1, 4]          # card order -> band icon order
    for c, n in reversed(list(zip(cards, ICON_FOR))):
        six = six[:c.start()] + c.group(0).replace('<div class="ddc', '<div data-more="%s" class="ddc' % T['more_how'], 1).replace(
            '<span class="k">', '<span class="sc-ic">%s</span><span class="k">' % icons[n], 1) + six[c.end():]
    add(ch, [(P['2.2'][0], stand(ch) + slim_ends(one(B, '<div class="ends'), T)),
             (P['2.2'][1], part_head(*T['heads']['2.2b']) + auto(subgoal_tabs(one(B, '<div class="ddc b rv" id="route-two"'), pg)) + widget_plain('beai', T)),
             (P['2.2'][2], part_head(k, t, text(bodies[0]) + T['open_any']) + six + key(ch) + bodies[1])])
    # 2.3
    ch = pg.chapter('why-one-try'); B = ch['blocks']
    h3s = [text(x) for x in B if x.startswith('<h3')]
    grids = [x for x in B if x.startswith('<div class="ddgrid')]
    para = [x for x in B if x.startswith('<p class="rv" style="max-width:68ch')][0]
    add(ch, [(P['2.3'][0], stand(ch) + tries_fig(T)),   # the "two things explain why" line stays on the long page only
             (P['2.3'][1], part_head(T['heads']['2.3b'][0]) + auto(swap_fig(swap_fig(grids[0], 1, 'loop', T, True), 0, 'trend', T))),   # Kenji carries the reason
             (P['2.3'][2], part_head(T['heads']['2.3c'], '', unp(para)) + auto(swap_fig(swap_fig(card_heading(grids[1], 1, T['wid']['layers']['card_h']), 1, 'layers', T, True), 0, 'speed', T)))])
    # 3.1
    ch = pg.chapter('why-race'); B = ch['blocks']
    quiz = one(B, '<div class="rv" style="margin-top:24px">')
    add(ch, [(P['3.1'][0], stand(ch) + rebuild(one(B, '<figure'), 0, 'payoff3', pg.lang) + widget_plain('race', T)),
             (P['3.1'][1], quiz + part_head(*T['heads']['3.1b']) + auto(scenes_in(one(B, '<div class="ddgrid'), card_scenes('race'))) + key(ch))])
    # 3.2
    ch = pg.chapter('why-human-misalignment'); B = ch['blocks']
    grids = [x for x in B if x.startswith('<div class="ddgrid')]; figs = [x for x in B if x.startswith('<figure')]
    add(ch, [(P['3.2'][0], stand(ch) + one(B, '<div class="body') + scenes_in(grids[0], card_scenes('values'))),
             (P['3.2'][1], part_head(*T['heads']['3.2b']) + widget_plain('chain', T, {'cards': cards_text(grids[1])})),
             (P['3.2'][2], part_head(*T['heads']['3.2c']) + rebuild(figs[0], 0, 'whose', pg.lang) + re.sub(r'(<div class="dkh-many"><span>).*?(</span>)', lambda m: m.group(1) + E(T['many']) + m.group(2), rebuild(figs[1], 0, 'decide', pg.lang, decide_ask(B, T)), count=1, flags=re.S))])
    # 4.1
    ch = pg.chapter('why-translation'); B = ch['blocks']
    figs = [x for x in B if x.startswith('<figure')]; h3s = [x for x in B if x.startswith('<h3')]
    ps = [x for x in B if x.startswith('<p class="rv"')]; grids = [x for x in B if x.startswith('<div class="ddgrid')]
    assert len(figs) == 3 and len(h3s) == 2 and len(ps) == 3 and len(grids) == 2
    H = T['heads']
    add(ch, [(P['4.1'][0], stand(ch) + rebuild(figs[0], 0, 'twoways', pg.lang)),
             (P['4.1'][1], part_head(H['4.1b']) + rebuild(figs[1], 0, 'lost', pg.lang)),                                     # Kenji carries outer alignment
             (P['4.1'][2], part_head(H['4.1c'], '', unp(ps[1])) + auto(worded_figs(grids[0], T))),
             (P['4.1'][3], part_head(H['4.1d']) + loophole(demo_bare(one(B, '<div class="demo-embed')), pg)),
             (P['4.1'][4], part_head(H['4.1e'], '', unp(ps[2])) + iceberg_fig(T)),
             (P['4.1'][5], part_head(H['4.1f']) + grids[1] + one(B, '<div class="ghwrap'))])
    # 4.2
    ch = pg.chapter('why-safety-hard'); B = ch['blocks']
    body = kids(one(B, '<div class="body'))
    add(ch, [(P['4.2'][0], stand(ch) + swap_fig(one(body, '<figure'), 0, 'gap', T)),
             (P['4.2'][1], part_head(H['4.2b']) + auto_first(short_cards(rebuild(rebuild(one(body, '<div class="ddgrid'), 1, 'grader', pg.lang), 0, 'talk', pg.lang), T['short42']), 2)),   # the two with charts open; the monitor and the circuits start folded
             (P['4.2'][2], part_head(H['4.2c']) + widget_plain('inside', T) + one(body, '<p'))])
    # 5.1
    ch = pg.chapter('response'); B = ch['blocks']
    layers = kids(one(B, '<div class="tinv'))
    assert len(layers) == 4
    lname = [text(re.search(r'<h4>(.*?)</h4>', l, re.S).group(1)).split(' ', 1)[-1].strip() for l in layers]
    parts = [(P['5.1'][0], stand(ch) + swap_fig(one(B, '<figure'), 0, 'cheese', T))]
    for i, l in enumerate(layers):
        assert l.count('<div class="tlayer"') == 1
        l = l.replace('<div class="tlayer"', '<div data-li="%d" data-crack="%s" class="tlayer"' % (i, html.escape(json.dumps(dict(T['crack'], castle=T['games51']['castle'], stamps=T['games51']['stamps'], **T['crack2']), ensure_ascii=False))), 1)
        parts.append((lname[i], part_head(H['5.1layer'] % (i + 2, i + 1)) + l))
    dets = [b for b in B if b.startswith('<details') and 'aside-note' not in b[:60]]      # the older-framing footnote stays on the long page only
    dets = [rebuild(d, 0, 'levers', pg.lang) if 'exfold' in d[:40] and k == 0 else (rebuild(d, 0, 'orgs', pg.lang) if 'exfold' in d[:40] and k == 1 else d) for k, d in enumerate(dets)]
    # build-your-defence: only techniques the 5.2 safeguards table scores
    g = pg.section('response-gaps'); gf = one(g, '<figure'); gt = svg_texts(gf)
    D = dict(T['defend'], rows=gt[7:14], cases=[J2(gt[1], gt[2], pg.lang), J2(gt[3], gt[4], pg.lang), J2(gt[5], gt[6], pg.lang)],
             layer=[0, 0, 1, 1, 2, 2, 3], layers=lname, G=[[2, 2, 2], [1, 2, 2], [2, 1, 2], [0, 1, 2], [0, 2, 2], [0, 1, 2], [0, 0, 1]])
    game = '<figure class="secfig dk-int dkw-defend" data-w="defend" data-cfg="%s"><p class="tr-title">%s</p><div class="dki-body"></div></figure>' % (
        html.escape(json.dumps(D, ensure_ascii=False)), E(D['title']))
    parts.append((P['5.1'][1], part_head(H['5.1f']) + game + ''.join(dets)))
    # games built from the techniques' own names and weak spots
    techs = []
    for li, l in enumerate(layers):
        for tc in re.findall(r'<div class="tcard"[^>]*>.*?<button type="button" class="tmore-btn"', l, re.S):
            nm = text(re.search(r'<p class="tn">(.*?)</p>', tc, re.S).group(1))
            st = re.search(r'<p class="tstop"><b>.*?</b>(.*?)</p>', tc, re.S)
            if st: techs.append(dict(n=nm, l=li, w=text(re.sub(r'<a class="ref"[^>]*>.*?</a>|<span class="term-tip"[^>]*>.*?</span>', '', st.group(1)))))
    assert len(techs) >= 12, len(techs)
    G5 = T['games51']
    def gfig(kind, cfg):
        return '<figure class="secfig dk-int dkw-%s" data-w="%s" data-cfg="%s" aria-label="%s"><div class="dki-body"></div></figure>' % (
            kind, kind, html.escape(json.dumps(cfg, ensure_ascii=False)), E(cfg['title']))
    # (5.1g "The heist" was removed on 2026-10-05; 5.1 now ends on Build your defence)
    add(ch, parts)
    # 5.2
    ch = pg.chapter('response-gaps'); B = ch['blocks']
    add(ch, [(P['5.2'][0], stand(ch) + add_example(one(B, '<div class="ddgrid'), 0, T['incidents']['hard'], pg.refbase)),
             (P['5.2'][1], part_head(H['5.2b']) + swap_fig(one(B, '<figure'), 0, 'guards', T) + rebuild(one(B, '<details'), 0, 'numbers', pg.lang).replace('<details class="exfold rv">', '<details class="exfold dk-quiet rv">', 1) + key(ch))])
    # 5.3 ask: no sec-head, an eyebrow and a big heading
    B = pg.section('ask')
    eb = inner(one(B, '<p class="eyebrow'))
    ask = dict(id='ask', num=re.search(r'(\d\.\d)', eb).group(1), chapno=eb, h2=inner(one(B, '<h2')), label=pg.label['ask'],
               group=pg.group['5'][0], acc=pg.group['5'][1], blocks=B)
    firsts = [text(h) for h in re.findall(r'<h3>(.*?)</h3>', one(B, '<div class="firsts'), re.S)]
    assert len(firsts) == 2
    # same two branches as the opening fork; the second spells out that narrow AI carries on
    add(ask, [('', widget_plain('fork', T, {'ends': [fork_hs[0], T['fork53_no'][0]], 'subs': [fork_ps[0], T['fork53_no'][1]]}))])
    # 5.4 do: one slide per group of people
    ch = pg.chapter('do'); B = ch['blocks']
    blocks = [b for b in B if b.startswith('<div class="cando-block')]
    assert len(blocks) == 4
    who = [text(re.search(r'<span class="ch-n">(.*?)</span>', b).group(1)) for b in blocks]
    parts = [(who[0], stand(ch) + blocks[0])] + [(who[i], blocks[i]) for i in (1, 2)]
    parts.append((who[3], blocks[3] + one(B, '<a class="refjump"')))
    add(ch, parts)
    # the close: stay in touch, then the footer
    an = pg.section('anthem')
    foot = s[s.index('<footer>'): s.index('</footer>') + 9]
    S.append(dict(key='anthem', sec=dict(id='anthem', num='', label=T['anthem_label'], acc=T['intro_acc']), wrap='anthem',
                  anchor='anthem', body=''.join(an) + '<div class="deck-foot">%s</div>' % inner(foot)))
    return S


# the cover's cliff drawing, redrawn for cream paper
CLIFF = {'#171d22': '#efe3c6', '#2a333a': '#d9c9a3',          # ground and abyss gradients
         '#bd3a20': '#e07a5f', '#ffd88a': '#ffd88a',
         '#fff': '#1b1b1b', '#e2e8ec': '#1b1b1b', '#c3ccd2': '#5c574e', '#aeb9c0': '#5c574e', '#8a959c': '#5c574e',
         '#6c7880': '#6f6a60', '#3a444c': '#9c8a5f',
         '#3fd0c9': '#1f9c96', '#9cc4ff': '#4a6fc9', '#ff8a6b': '#d9492c', '#ffb59e': '#e07a5f',
         '#e59079': '#c9573c', '#e8c98a': '#a87812', '#8a5d00': '#8a5d00'}


# ---------------------------------------------------------------- card colours
# colour identifies the idea a card stands for, and keeps it wherever it appears
KMAP = {'The pull': 1, 'The starve': 2, 'The gap': 4,
        'Abundance': 2, 'Health': 1, 'Education': 5, 'Scientific progress': 3, 'Work': 6,
        'The user is the adversary': 1, 'The AI is the adversary': 4, 'Nobody is the adversary': 3, 'The incentives are the adversary': 2,
        'Engineered pandemic': 1, 'Infrastructure': 2, 'Resources': 3, 'Self-preservation': 4, 'Geoengineering': 5, 'Nuclear and autonomous weapons': 6,
        'The trend': 4, 'What it costs': 2, 'The speed gap': 3, 'What it runs on': 5,
        'Corner-cutting': 1, 'The rope': 4}
CYCLE = [4, 3, 5, 2, 6, 1]
CARD_RE = r'<div(?: [\w-]+="[^"]*")* class="(?:ddc|endc)\b[^"]*"'

def colorize(h, seq=None):
    """English: colour from the card's label. Chinese: the same colours, card by card."""
    out = []; i = 0; got = []
    for n, m in enumerate(re.finditer(CARD_RE, h)):
        out.append(h[i:m.end()]); i = m.end()
        if seq is not None:
            k = seq[n]
        elif 'id="route-two"' in h[m.start():m.start() + 200]:
            k = 3
        else:
            km = re.search(r'<span class="(?:k|ek)">([^<]*)</span>', h[m.end():m.end() + 600])
            k = KMAP.get(km.group(1) if km else '', CYCLE[n % len(CYCLE)])
        out.append(' data-k="%d"' % k); got.append(k)
    out.append(h[i:])
    if seq is not None: assert len(got) == len(seq), ('card count differs from English', len(got), len(seq))
    return ''.join(out), got


# ---------------------------------------------------------------- charts on paper
PAPER = (0xff, 0xfd, 0xf6)
def lum(rgb):
    def ch(c):
        c = c / 255; return c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    r, g, b = rgb; return .2126 * ch(r) + .7152 * ch(g) + .0722 * ch(b)
def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True); return (la + .05) / (lb + .05)
def hexrgb(h):
    h = h.lstrip('#')
    if len(h) == 3: h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def rgbhex(c): return '#%02x%02x%02x' % tuple(max(0, min(255, round(v))) for v in c)

def darken(rgb, target):
    h, l, s = colorsys.rgb_to_hls(*[v / 255 for v in rgb])
    while l > .05:
        c = tuple(v * 255 for v in colorsys.hls_to_rgb(h, l, s))
        if contrast(c, PAPER) >= target: return rgbhex(c)
        l -= .02
    return '#1b1b1b'

def repaint(tag, attr, value):
    """A colour drawn for the dark page, redrawn for cream paper."""
    if not value.startswith('#') or value.lower() in ('#fff', '#ffffff'): return value
    rgb = hexrgb(value); h, l, s = colorsys.rgb_to_hls(*[v / 255 for v in rgb])
    words = tag == 'text' or tag == 'tspan'
    if s < .2 or l < .12:                   # greys
        if l < .35: return '#cfc4ab' if attr == 'stroke' or not words else '#1b1b1b'
        if l < .72: return '#5c574e'
        return '#1b1b1b' if words or attr == 'stroke' else '#d8cdb3'
    if not words and attr == 'fill' and l > .85: return value      # pale cells keep their tint
    if words: return '#1b1b1b'              # chart text is ink or grey; colour stays on the marks
    return darken(rgb, 2.6 if attr == 'stroke' else 2.1)

def paper_svg(m):
    tag, vbw, body = m.group(1), float(m.group(2)), m.group(3)
    if vbw <= 130 or 'data-keep=' in tag: return m.group(0)   # icons, pictograms and the cliff keep their own colours
    def el(e):
        t = e.group(0); name = e.group(1)
        t = re.sub(r'\b(fill|stroke)="(#[0-9a-fA-F]{3,6})"', lambda k: '%s="%s"' % (k.group(1), repaint(name, k.group(1), k.group(2))), t)
        fillm = re.search(r'fill="(#[0-9a-fA-F]{3,6})"', t)
        solid = fillm and 'opacity=' not in t and colorsys.rgb_to_hls(*[v / 255 for v in hexrgb(fillm.group(1))])[1] < .8
        if name == 'rect' and 'stroke=' not in t and solid:
            w = re.search(r' width="([\d.]+)"', t); hh = re.search(r' height="([\d.]+)"', t)
            if w and hh and float(w.group(1)) >= 6 and float(hh.group(1)) >= 6:
                t = t[:-2] + ' stroke="#1b1b1b" stroke-width="1.5" vector-effect="non-scaling-stroke"/>' if t.endswith('/>') else t
        return t
    body = re.sub(r'<(\w+)\b[^>]*>', el, body)
    body = re.sub(r'font-family="[^"]*(?:IBM Plex Mono|Archivo)[^"]*"', 'font-family="Comic Neue,PingFang SC,Microsoft YaHei,sans-serif"', body)
    return tag + body + '</svg>'

def paper(h):
    n0 = re.sub(r'<script\b.*?</script>', '', h, flags=re.S).count('<svg')   # svg strings inside scripts are drawn later
    parts = re.split(r'(<script\b.*?</script>)', h, flags=re.S); n = 0
    for k in range(0, len(parts), 2):
        parts[k], c = re.subn(r'(<svg\b[^>]*viewBox="-?[\d.]+ -?[\d.]+ ([\d.]+)[^"]*"[^>]*>)(.*?)</svg>', paper_svg, parts[k], flags=re.S); n += c
    h = ''.join(parts)
    assert n == n0, ('svg without a viewBox', n, n0)
    # Archivo and Newsreader are not loaded on the deck: the few drawing words set in them (the cover cliff, one icon) use Comic Neue
    parts = re.split(r'(<script\b.*?</script>)', h, flags=re.S)
    for k in range(0, len(parts), 2):
        parts[k] = re.sub(r'font-family="[^"]*(?:Archivo|Newsreader)[^"]*"', 'font-family="Comic Neue,PingFang SC,Microsoft YaHei,sans-serif"', parts[k])
    return ''.join(parts)


# ---------------------------------------------------------------- assemble
def build(pg, en_colors=None):
    T = pg.T; S = plan(pg); L = TXT.LINES[pg.lang]
    assert [x['key'] for x in S] == [k for k, *_ in L], ('narration out of step with slides',
        [x['key'] for x in S], [k for k, *_ in L])
    first = {}
    for i, x in enumerate(S): first.setdefault(x['sec']['id'], i)
    colors = {}
    out = []
    for i, x in enumerate(S):
        sec = x['sec']; _, mood, line, capy = L[i]
        nar = '' if not line else ('<div class="cx-nar"><img class="cx-kenji" src="/deck-img/kenji-%s.jpg" alt="%s" width="72" height="72" decoding="async">'
               '<p class="cx-bubble">%s</p>%s</div>') % (mood, html.escape(T['kenji_alt'] % T['moods'][mood]), html.escape(line),
               ('<div class="cx-capy"><img src="/deck-img/capy.jpg" alt="Capy" width="54" height="54" decoding="async"><span>%s</span></div>' % html.escape(capy)) if capy else '')
        body, got = colorize(x['body'], None if en_colors is None else en_colors[x['key']])
        # a quick check at the end of each chapter; the results card on the last slide
        num = sec.get('num')
        if x['wrap'] == 'dd' and x['part'] == x['parts'] - 1 and num in T['checks']:
            q, opts, right, why = T['checks'][num]
            body += '<div class="dk-check" data-id="c-%s" data-c="%s"></div>' % (num, html.escape(json.dumps(
                dict(k=T['checks_k'], q=q, opts=opts, right=right, why=why, ok=T['right'], no=T['wrongp']), ensure_ascii=False)))
        if x['key'] == 'anthem':
            total = len([1 for y in S if y is S[first[y['sec']['id']]] and y['sec'].get('num')])
            body = '<div class="dk-results" data-c="%s"></div>' % html.escape(json.dumps(dict(T['results'], total=total, nchecks=len(T['checks']), badge=T['games51']['badge'], badge_row=T['games51']['badge_row']), ensure_ascii=False)) + body
            # after staying in the loop, the way into the reference material
            refs = []
            for rid in ('change-my-mind', 'faq', 'glossary', 'resources', 'sources'):
                m = re.search(r'<a href="(/reference(?:-zh)?#%s)"[^>]*>(.*?)</a>' % rid, pg.s)
                assert m, ('reference link', rid); refs.append((m.group(1), text(m.group(2))))
            D = T['deeper']
            refs.append(('/guide-zh' if pg.lang == 'zh' else '/guide', D['guide']))   # the long page, so it is reachable from the home page
            deeper = ('<div class="dk-deeper"><h3>%s</h3><p>%s</p><div class="dk-deeper-links">%s</div></div>'
                      % (E(D['title']), E(D['sub']), ''.join('<a href="%s">%s <span aria-hidden="true">&rarr;</span></a>' % (h, E(t)) for h, t in refs)))
            assert body.count('<div class="deck-foot">') == 1
            body = body.replace('<div class="deck-foot">', deeper + '<div class="deck-foot">', 1)
            # the join, share and petition column sits beside the results; the poem follows underneath
            a = body.index('<div class="anthem-act'); depth = 0
            for m in re.finditer(r'<(/?)div\b', body[a:]):
                depth += -1 if m.group(1) else 1
                if depth == 0: b = a + m.end() + body[a + m.end():].index('>') + 1; break
            act = body[a:b]
            assert act.count('<div') == act.count('</div>') and 'join-form' in act, 'anthem-act slice'
            r0 = body.index('<div class="dk-results"'); r1 = body.index('</div>', r0) + 6
            assert body[r0:r1].count('<div') == 1
            body = body[:r0] + '<div class="an-top">' + body[r0:r1] + act + '</div>' + body[r1:a] + body[b:]
        colors[x['key']] = got
        same = [y for y in S if y['sec'] is sec]
        chips = ''
        if len(same) > 1:
            names = T['intro_parts'] if sec['id'] == 'crossroads' else [y.get('chip') for y in same]
            cl = []; num = 0
            for k, (y, nm) in enumerate(zip(same, names)):
                sub = is_sub(sec['id'], k)
                if not sub: num += 1
                if sub and not is_sub(sec['id'], k - 1): cl.append('<span class="t-subchips">')
                cl.append('<button type="button" class="t-chip%s%s" data-go="%d">%s%s</button>' % (' on' if y is x else '', ' t-chip-sub' if sub else '', S.index(y),
                           '' if sub else '<b>%d</b>' % num, html.escape(nm)))
                if sub and (k == len(same) - 1 or not is_sub(sec['id'], k + 1)): cl.append('</span>')
            chips = '<div class="t-chips" aria-label="%s">%s</div>' % (T['chips_aria'], ''.join(cl))
        ihead = ('<div class="wrap t-head"><div class="sec-head"><span class="chapno">%s</span><h2>%s</h2>%s</div></div>'
                 % (x['kicker'], x['title'], chips)) if x.get('title') else ''
        if x['wrap'] == 'dd' and sec['id'] in SUBS:
            # the part kicker carries the nested number (Part 2.1), computed from SUBS
            pn = part_nums(sec['id'], len(same))[x['part']]
            body = re.sub(r'(<span class="t-pk">)(?:Part \d+|第 \d+ 部分)', lambda m: m.group(1) + (T['part_word'] % pn), body, count=1)
        if x['wrap'] == 'dd':
            n, parts, j = x['parts'], None, x['part']
            if j == 0:
                head = ('<div class="wrap t-head"><div class="sec-head"><span class="chapno">%s<span class="t-grp">%s</span></span><h2>%s</h2>%s</div></div>'
                        % (sec['chapno'], sec['group'], sec['h2'], chips))
            else:
                head = '<div class="wrap t-head t-mini"><p class="t-run"><b>%s</b> · %s</p>%s</div>' % (sec['num'], text(sec['h2']), chips)
            inside = '<section%s class="dd">%s<div class="wrap t-body">%s%s</div></section>' % (
                (' id="%s"' % x['anchor']) if x.get('anchor') else '', head, nar, body)
        elif x['wrap'] == 'mast':
            # on the cover the chart comes first; Kenji and Capy introduce themselves below it
            top_part, low_part = (body, nar) if x['key'] == 'cover' else (nar, body)
            inside = '<header class="masthead"%s>%s<div class="wrap t-body">%s%s</div></header>' % (
                (' id="%s"' % x['anchor']) if x.get('anchor') else '', ihead, top_part, low_part)
        elif x['wrap'] == 'cross':
            inside = '<section class="cross"%s>%s<div class="wrap t-body">%s%s</div></section>' % (
                (' id="%s"' % x['anchor']) if x.get('anchor') else '', ihead, nar, body)
        else:
            inside = '<section class="cross anthem" id="anthem"><div class="wrap t-body">%s%s</div></section>' % (nar, body)
        # buttons: back, then the next step
        btns = []
        if i > 0: btns.append('<button type="button" class="p-btn t-back" data-go="%d"><span aria-hidden="true">&larr;</span> %s</button>' % (i - 1, T['back']))
        if i < len(S) - 1:
            nx = S[i + 1]
            if nx['sec'] is sec:
                lab = T['cont_part'] % part_nums(sec['id'], len(same))[x['part'] + 1] if x['wrap'] == 'dd' else T['cont']
                btns.append('<button type="button" class="p-btn t-cont" data-go="%d">%s <span aria-hidden="true">&rarr;</span></button>' % (i + 1, lab))
            else:
                ns = nx['sec']
                lab = (T['next'] % ('%s %s' % (ns['num'], ns['label']))) if ns.get('num') else T['next'] % ns['label']
                btns.append('<button type="button" class="p-btn" data-go="%d">%s <span aria-hidden="true">&rarr;</span></button>' % (i + 1, html.escape(lab)))
        else:
            btns.append('<a class="p-btn" href="%s">%s <span aria-hidden="true">&rarr;</span></a>' % ('/reference-zh' if pg.lang == 'zh' else '/reference', T['deeper']['btn']))
            btns.append('<button type="button" class="p-btn t-back" data-go="0">%s <span aria-hidden="true">&uarr;</span></button>' % T['restart'])
        # after "You", the next step is Stay in the loop; researchers, labs and governments are optional
        extra_attr = ''
        if x['key'] == '5.4a':
            ai = [k for k, y in enumerate(S) if y['key'] == 'anthem'][0]
            btns = [b for b in btns if 't-back' in b] + ['<button type="button" class="p-btn" data-go="%d">%s <span aria-hidden="true">&rarr;</span></button>' % (ai, html.escape(T['next'] % S[ai]['sec']['label']))]
            btns.append('<button type="button" class="t-opt" data-go="%d">%s</button>' % (i + 1, E(T['opt_more'])))
            extra_attr = ' data-next="%d"' % ai
        if x['key'] in ('5.4b', '5.4c', '5.4d'): extra_attr = ' data-optional="1"'
        where = ('<b>%s</b> %s' % (sec['num'], html.escape(sec['label']))) if sec.get('num') else html.escape(sec['label'])
        out.append('<div class="slide" data-key="%s" data-acc="%s" style="--c-acc:%s" data-where="%s"%s>%s<div class="b2-next">%s</div></div>'
                   % (x['key'], sec['acc'], sec['acc'], html.escape(where), extra_attr, balanced(inside), ''.join(btns)))
    # progress: one segment per section
    segs = []; seen = []
    for x in S:
        if x['sec']['id'] not in seen: seen.append(x['sec']['id'])
    for sid in seen:
        idx = [i for i, x in enumerate(S) if x['sec']['id'] == sid]
        segs.append('<div class="d-seg" style="flex:%d;--c:%s" data-first="%d" data-count="%d"><i></i></div>' % (len(idx), S[idx[0]]['sec']['acc'], idx[0], len(idx)))
    return S, ''.join(out), ''.join(segs), colors


def toc(pg, S):
    """Left-hand contents: every section, grouped as in the site nav; the current one opens to its parts."""
    T = pg.T; out = []; last_group = None; secs = []
    for x in S:
        if x['sec'] not in secs: secs.append(x['sec'])
    for sec in secs:
        idx = [i for i, x in enumerate(S) if x['sec'] is sec]
        grp = sec.get('group') or (T['toc_intro'] if sec['id'] == 'crossroads' else T['toc_end'])
        if grp != last_group:
            out.append('<p class="tc-g">%s</p>' % html.escape(grp)); last_group = grp
        lab = ('<b>%s</b> %s' % (sec['num'], html.escape(sec['label']))) if sec.get('num') else html.escape(sec['label'])
        parts = ''
        if len(idx) > 1:
            names = T['intro_parts'] if sec['id'] == 'crossroads' else [S[i].get('chip') or '' for i in idx]
            assert len(names) == len(idx) and all(names), ('toc part names', sec['id'])
            items = []
            for k, (i, nm) in enumerate(zip(idx, names)):
                sub = is_sub(sec['id'], k)
                items.append('<li%s><button type="button" class="tc-p" data-go="%d" data-i="%d">%s</button></li>' % (' class="tc-sub"' if sub else '', i, i, html.escape(nm)))
            parts = '<ol class="tc-parts">%s</ol>' % ''.join(items)
        out.append('<div class="tc-sec" data-first="%d" data-last="%d"><button type="button" class="tc-s" data-go="%d" style="--c:%s">%s</button>%s</div>'
                   % (idx[0], idx[-1], idx[0], sec['acc'], lab, parts))
    hide = '<button type="button" class="tc-hide" data-toc="off" aria-controls="dk-toc"><span aria-hidden="true">&laquo;</span> %s</button>' % html.escape(T['toc_hide'])
    edge = '<button type="button" class="tc-edge" data-toc="on" aria-controls="dk-toc" title="%s"><span aria-hidden="true">&raquo;</span><b>%s</b></button>' % (html.escape(T['toc_show']), html.escape(T['toc_show']))
    return '<nav class="dk-toc" id="dk-toc" aria-label="%s">%s%s%s</nav>\n%s%s\n' % (T['contents'], hide, ''.join(out), pg.toc_tail, edge, TOC_JS)

# the left contents can be folded away on wide screens; the choice is remembered across pages
TOC_JS = ('<script>(function(){var h=document.documentElement;try{if(localStorage.getItem("toc-off")==="1")h.classList.add("toc-off")}catch(e){}'
          'document.addEventListener("click",function(e){var b=e.target.closest&&e.target.closest("[data-toc]");if(!b)return;var off=b.getAttribute("data-toc")==="off";'
          'h.classList.toggle("toc-off",off);try{localStorage.setItem("toc-off",off?"1":"0")}catch(x){}'
          'setTimeout(function(){window.dispatchEvent(new Event("resize"));if(window.__lxFitAll)window.__lxFitAll()},50)})})();</script>')

def toc_show(T, ctl):
    return '<button type="button" class="tc-show" data-toc="on" aria-controls="%s"><span aria-hidden="true">&raquo;</span> %s</button>' % (ctl, html.escape(T['toc_show']))


def deck_bar(pg, segs):
    """One compact row: brand, where you are, contents, language, act now; progress under it."""
    s = pg.s; T = pg.T
    old = s[s.index('<div class="bar" id="bar">'): s.index('<div class="chapnum"')]
    lang = re.search(r'<a class="hbtn hbtn-lang" href="([^"]*)"[^>]*>(.*?)</a>', old, re.S)
    assert lang.group(1) == T['lang_from']
    act = text(re.search(r'<a class="hbtn hbtn-act"[^>]*>(.*?)</a>', old, re.S).group(1))
    primer = re.search(r'<a class="brand"[^>]*>(.*?)</a>', old, re.S).group(1).strip()
    cols = []
    for g in re.finditer(r'<li class="ng">\s*<button[^>]*>(.*?)<span class="ng-caret".*?<ul class="ng-menu">(.*?)</ul>', old, re.S):
        items = ''.join('<li%s><a href="%s">%s</a></li>' % (' class="dk-g"' if 'ng-grp' in li.group(1) else '', li.group(2), text(li.group(3)))
                        for li in re.finditer(r'<li([^>]*)><a href="([^"]+)">(.*?)</a></li>', g.group(2)))
        cols.append('<div class="dk-col"><p class="dk-h">%s</p><ul>%s</ul></div>' % (text(g.group(1)), items))
    assert len(cols) == 3, len(cols)
    extra = ''.join(re.findall(r'<a class="nav-xbtn".*?</a>', old, re.S))
    assert extra.count('nav-xbtn') == 2
    pg.toc_tail = cols[2].replace('class="dk-col"', 'class="dk-col tc-ref"') + '<div class="dk-x tc-x">%s</div>' % extra
    return ('<header class="dk-bar" id="dk-bar"><div class="dk-row">'
            '<a class="dk-brand" href="#top"><span class="dk-logo">SafeAGI</span><span class="dk-primer">%s</span></a><span class="d-where" id="d-where"></span>'
            '<div class="dk-acts">' + toc_show(T, 'dk-toc') + '<button type="button" class="dk-btn dk-menu-btn" id="dk-menu-btn" aria-expanded="false" aria-controls="dk-menu">%s</button>'
            '<a class="dk-btn" href="%s" hreflang="%s">%s</a><a class="dk-btn dk-go" href="#what-you-can-do">%s</a></div></div>'
            '<div class="d-segs">%s</div></header>\n'
            '<nav class="dk-menu" id="dk-menu" aria-label="%s" hidden><div class="dk-menu-in">%s<div class="dk-x">%s</div></div></nav>\n') % (
            primer, T['contents'], T['lang_to'], 'zh-Hans' if pg.lang == 'en' else 'en', text(lang.group(2)), act, segs, T['contents'], ''.join(cols), extra)


def page(pg, slides, segs, S):
    s = pg.s; T = pg.T
    head = s[:s.index('<body')]
    assert head.count('name="robots"') == 1        # the deck is the home page: it keeps the long page's indexable robots tag
    # the long page's Archivo and Newsreader set only a few chart words in the deck (redrawn in Comic Neue below), so the deck
    # skips them: the Newsreader preload, its stylesheet, and Archivo's half of the shared one. IBM Plex Mono stays for chart labels.
    a = head.index('<!-- The stylesheet below is async'); b = head.index('</noscript>', a) + len('</noscript>')
    old_fonts = head[a:b]
    assert old_fonts.count('<link') == 5 and 'newsreader' in old_fonts and old_fonts.count('<noscript>') == 1, old_fonts[:200]
    plex = 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap'
    head = head[:a] + ('<link href="%s" rel="stylesheet" media="print" onload="this.media=\'all\'">'
                       '<noscript><link href="%s" rel="stylesheet"></noscript>') % (plex, plex) + head[b:]
    assert 'family=Newsreader' not in head and 's/newsreader/' not in head and 'Archivo:wght' not in head
    fonts = T['fonts']
    head = head.replace('</head>', ('<link rel="stylesheet" href="%s" media="print" onload="this.media=\'all\'">'
                                    '<noscript><link rel="stylesheet" href="%s"></noscript>\n'
                                    '<style id="deck-css">\n%s\n%s\n</style>\n</head>') % (
        fonts, fonts, open(os.path.join(ROOT, 'tools', 'deck', 'deck.css'), encoding='utf-8').read(), T['css']), 1)
    body = s[s.index('<body'):]
    btag = body[:body.index('>') + 1]
    bar = deck_bar(pg, segs) + toc(pg, S)
    toast = re.search(r'<div id="toast"[^>]*>.*?</div>', s, re.S).group(0)
    skip = re.search(r'<a class="skip" href="#main">.*?</a>', s, re.S).group(0)
    scripts = re.findall(r'<script\b[^>]*>.*?</script>', s[s.index('</footer>'):], re.S)
    assert len(scripts) == 3 and scripts[0].startswith('<script id="lx-layered">')
    lx = scripts[0]
    for a, b in [
        ('var TIER = { caption: 10.5, label: 11.5, emphasis: 12.5, value: 15, display: 21 };',
         'var TIER = { caption: 13, label: 14.5, emphasis: 15.5, value: 18.5, display: 26 };'),
        ('if (first && !NO_HOIST[sec.id]) {', 'if (false) {'),               # charts stay where the slide puts them
        ('var CARD = ".ddc,.endc,.tcard,.cl-half";', 'var CARD = ".ddc,.endc,.cl-half";'),   # technique cards are the weak-spot game
        ('if (svg.closest(".cross-hero,.endc-icons,.ends-out,.tix,.tlayer-h,.tcard-h")) return false;',
         'if (svg.closest(".cross-hero,.endc-icons,.ends-out,.tix,.tlayer-h,.tcard-h,.ice-fig,.tr-fig,.dk-chart,.dk-int")) return false;'),   # deck drawings size themselves
        ('$$(".cando-block:not(#what-you-can-do)", main)', '$$(".cando-block.lx-never", main)'),   # each group has its own slide
        ('    if (card.classList.contains("tcard")) {', '    after = after.filter(function(x){ return !(x.nodeType === 1 && x.classList.contains("dk-keep")); });   /* deck scenes stay in view */\n    if (card.classList.contains("tcard")) {'),
        ('  function refitAll(){ $$("svg", main).forEach(function(svg){ svg._lxIgnore = null; }); fitAll(main); }',
         '  function refitAll(){ $$("svg", main).forEach(function(svg){ svg._lxIgnore = null; }); fitAll(main); }\n  window.__lxFitAll = refitAll;'),
    ]:
        assert lx.count(a) == 1, ('lx patch', a[:50])
        lx = lx.replace(a, b)
    # the lab quiz: shorter answers in the deck
    main_js = scripts[1]
    i = main_js.index('var REVEAL = ['); j = main_js.index('];', i) + 2
    main_js = main_js[:i] + 'var REVEAL = ' + json.dumps(T['race_reveal'], ensure_ascii=False) + ';' + main_js[j:]
    main_js, nc = re.subn(r'var CLOSER = "[^"]*";', lambda m: 'var CLOSER = ' + json.dumps(T['race_closer'], ensure_ascii=False) + ';', main_js)
    assert nc == 1, nc
    scripts[1] = main_js
    js = open(os.path.join(ROOT, 'tools', 'deck', 'deck.js'), encoding='utf-8').read()
    doc = (head + btag + '\n' + toast + '\n' + skip + '\n' + bar +
           '<main id="main"><div class="deck"><div class="track">%s</div></div></main>\n' % slides +
           '<nav class="d-nav" aria-label="%s"><button type="button" id="d-prev" aria-label="%s">&larr;</button>'
           '<button type="button" id="d-next" class="next" aria-label="%s">&rarr;</button></nav>\n'
           '<p class="d-hint">%s</p>\n' % (T['nav_aria'], T['prev'], T['next_aria'], T['keys']) +
           lx + '\n' + scripts[1] + '\n' + scripts[2] + '\n<script>\n' + js + '\n</script>\n</body>\n</html>\n')
    return doc


REF_START, REF_END = '<!-- dk-ref: comic look, added by tools/build_deck.py -->', '<!-- /dk-ref -->'

def comic_reference(fname, fonts):
    """Give a Reference page the deck's comic look. Idempotent: the marked block is stripped, then re-added."""
    path = os.path.join(ROOT, fname); s = open(path, encoding='utf-8').read()
    s = re.sub(re.escape(REF_START) + r'.*?' + re.escape(REF_END) + r'\n?', '', s, flags=re.S)
    css = open(os.path.join(ROOT, 'tools', 'deck', 'ref.css'), encoding='utf-8').read()
    js = ('<script>document.querySelectorAll(".resbar[data-res]").forEach(function(b){var body=b.nextElementSibling;'
          'if(!body)return;b.addEventListener("click",function(){var open=body.classList.contains("closed");body.classList.toggle("closed",!open);'
          'b.setAttribute("aria-expanded",open?"true":"false");var x=b.querySelector(".rbx");if(x)x.textContent=open?"\u2013":"+";});});</script>')
    block = '%s\n<link rel="stylesheet" href="%s">\n<style>\n%s</style>\n%s\n' % (REF_START, fonts, css, REF_END)
    assert s.count('</head>') == 1 and s.count('</body>') == 1
    s = s.replace('</head>', block + '</head>', 1)
    s = s.replace('</body>', REF_START + js + REF_END + '\n</body>', 1)
    open(path, 'w', encoding='utf-8').write(s)
    assert s.count(REF_START) == 2
    print('styled %s' % fname)

REFTOC_START, REFTOC_END = '<!-- dk-reftoc: the deck contents, added by tools/build_deck.py -->', '<!-- /dk-reftoc -->'

def ref_toc(fname, pg, S):
    """The deck's left-hand contents on a Reference page, each entry linking back to its slide. Idempotent."""
    path = os.path.join(ROOT, fname); s = open(path, encoding='utf-8').read()
    s = re.sub(re.escape(REFTOC_START) + r'.*?' + re.escape(REFTOC_END) + r'\n?', '', s, flags=re.S)
    home = '/' if pg.lang == 'en' else '/index-zh'
    t = toc(pg, S)
    n0 = t.count('data-go=')
    t, n = re.subn(r'<button type="button" class="(tc-[sp])" data-go="(\d+)"(?: data-i="\d+")?([^>]*)>(.*?)</button>',
                   lambda m: '<a class="%s" href="%s#s=%d"%s>%s</a>' % (m.group(1), home, int(m.group(2)) + 1, m.group(3), m.group(4)), t, flags=re.S)
    assert n == n0 and n > 40 and 'data-go=' not in t, (n, n0)
    t = t.replace('<nav class="dk-toc" id="dk-toc"', '<nav class="ref-toc" id="ref-toc"', 1).replace('aria-controls="dk-toc"', 'aria-controls="ref-toc"')
    assert 'id="ref-toc"' in t and 'aria-controls="dk-toc"' not in t
    # the "show contents" button sits in the page's own header
    s = re.sub(r'<button type="button" class="tc-show"[^>]*>.*?</button>', '', s, flags=re.S)
    assert s.count('<div class="bar-actions">') == 1
    s = s.replace('<div class="bar-actions">', '<div class="bar-actions">' + toc_show(pg.T, 'ref-toc'), 1)
    assert s.count('<main id="main">') == 1
    s = s.replace('<main id="main">', REFTOC_START + '\n' + t + '\n' + REFTOC_END + '\n<main id="main">', 1)
    open(path, 'w', encoding='utf-8').write(s)
    print('contents on %s: %d links' % (fname, n))

FAQ_START, FAQ_END = '<!-- dk-faq-ld: built from the visible questions by tools/build_deck.py -->', '<!-- /dk-faq-ld -->'

def ref_faq(fname, url, lang):
    """FAQ structured data for a Reference page, read from the questions it shows. Idempotent."""
    path = os.path.join(ROOT, fname); s = open(path, encoding='utf-8').read()
    s = re.sub(re.escape(FAQ_START) + r'.*?' + re.escape(FAQ_END) + r'\n?', '', s, flags=re.S)
    a = s.index('<section id="faq">'); sec = s[a:s.index('</section>', a)]
    qa = re.findall(r'<details><summary><span class="qn">\d+</span>(.*?)</summary><div class="fa">(.*?)</div></details>', sec, re.S)
    assert len(qa) >= 7, (fname, 'faq questions found', len(qa))
    def plain(h):
        h = re.sub(r'<span class="term-tip">.*?</span>', '', h, flags=re.S)
        h = re.sub(r'<a class="ref"[^>]*>.*?</a>', '', h, flags=re.S)
        return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h))).replace(' ,', ',').replace(' .', '.').strip()
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "@id": url + "#faq", "inLanguage": lang,
          "mainEntity": [{"@type": "Question", "name": plain(q), "acceptedAnswer": {"@type": "Answer", "text": plain(t)}} for q, t in qa]}
    assert all(x["name"] and len(x["acceptedAnswer"]["text"]) > 40 for x in ld["mainEntity"])
    block = '%s\n<script type="application/ld+json">\n%s\n</script>\n%s\n' % (FAQ_START, json.dumps(ld, indent=1, ensure_ascii=False).replace('</', '<\\/'), FAQ_END)
    assert s.count('</head>') == 1
    s = s.replace('</head>', block + '</head>', 1)
    open(path, 'w', encoding='utf-8').write(s)
    print('faq markup %s: %d questions' % (fname, len(qa)))

def gh_deck(doc, T):
    """4.1 Goodhart slider for the deck: a short heading, sentence-case labels and short messages. The long page keeps its own."""
    G = T['gh']
    def one(pat, rep, flags=re.S):
        nonlocal doc
        doc, n = re.subn(pat, rep, doc, count=1, flags=flags); assert n == 1, pat
    lead = re.search(r'<p class="ghlead">.*?</p>', doc, re.S).group(0)
    refs = ''.join(re.findall(r'<a class="ref"[^>]*>\d+</a>', lead)); assert refs
    one(re.escape(lead), lambda m: '<p class="gh-h">%s</p><p class="gh-d">%s</p>' % (E(G['h']), E(G['d'])))
    one(r'(<label for="gh">)[^<]*(<span id="gh-pct")', lambda m: m.group(1) + E(G['ctl']) + ' ' + m.group(2))
    one(r'(<div class="gh-card proxy">\s*<span class="lbl">)[^<]*', lambda m: m.group(1) + E(G['proxy']))
    one(r'(<div class="gh-card real">\s*<span class="lbl">)[^<]*', lambda m: m.group(1) + E(G['real']))
    one(r'(<p class="gh-say" id="gh-say"[^>]*>)[^<]*(</p>)', lambda m: m.group(1) + E(G['say'][0]) + m.group(2) + '<p class="gh-src">%s</p>' % refs)
    # the messages live in the page script: replace the array that follows the slider's own setup
    i = doc.index('var gh = $("#gh");'); a = doc.index('var SAY = [', i); b = doc.index('];', a) + 2
    n_old = doc[a:b].count('",') + 1
    says = G['say'][1:] if n_old == len(G['say']) - 1 else G['say']
    assert len(says) == n_old, (n_old, len(G['say']))
    doc = doc[:a] + 'var SAY = [' + ', '.join(json.dumps(x, ensure_ascii=False) for x in says) + '];' + doc[b:]
    return doc

def main():
    en = Page('en'); zh = Page('zh')
    S_en, sl_en, sg_en, colors = build(en)
    S_zh, sl_zh, sg_zh, _ = build(zh, colors)
    assert [x['key'] for x in S_en] == [x['key'] for x in S_zh]
    for pg, sl, sg, S in ((en, sl_en, sg_en, S_en), (zh, sl_zh, sg_zh, S_zh)):
        doc = gh_deck(paper(page(pg, sl, sg, S)).replace(pg.old_intro, pg.T['intro_label']), pg.T)
        assert doc.count('<div class="slide" data-key=') == len(S_en), ('slides missing', doc.count('<div class="slide" data-key='))
        ids = re.findall(r'\bid="([^"]+)"', doc)
        dup = sorted(set(i for i in ids if ids.count(i) > 1))
        assert not dup, ('duplicate ids', dup[:10])
        open(os.path.join(ROOT, pg.out), 'w', encoding='utf-8').write(doc)
        print('wrote %s: %d slides, %d KB' % (pg.out, len(S_en), len(doc) // 1024))
    comic_reference('reference.html', TXT.EN_FONTS)
    comic_reference('reference-zh.html', TXT.ZH_FONTS)
    ref_toc('reference.html', en, S_en); ref_toc('reference-zh.html', zh, S_zh)
    ref_faq('reference.html', 'https://safeagi.ca/reference', 'en')
    ref_faq('reference-zh.html', 'https://safeagi.ca/reference-zh', 'zh-Hans')
    make_guides()

GUIDE_SWAPS = {
    'index.html': ('guide.html', [
        ('<link rel="canonical" href="https://safeagi.ca/">', '<link rel="canonical" href="https://safeagi.ca/guide">'),
        ('hreflang="en" href="https://safeagi.ca/">', 'hreflang="en" href="https://safeagi.ca/guide">'),
        ('hreflang="zh-Hans" href="https://safeagi.ca/index-zh">', 'hreflang="zh-Hans" href="https://safeagi.ca/guide-zh">'),
        ('hreflang="x-default" href="https://safeagi.ca/">', 'hreflang="x-default" href="https://safeagi.ca/guide">'),
        ('<meta property="og:url" content="https://safeagi.ca/">', '<meta property="og:url" content="https://safeagi.ca/guide">'),
        ('"@id": "https://safeagi.ca/#article"', '"@id": "https://safeagi.ca/guide#article"'),
        ('"mainEntityOfPage": "https://safeagi.ca/"', '"mainEntityOfPage": "https://safeagi.ca/guide"'),
        ('<title>Superintelligence Safety: the problem we haven&#39;t solved | SafeAGI</title>', '<title>The full guide to superintelligence safety | SafeAGI</title>'),
        ('<meta property="og:title" content="Superintelligence Safety: the problem we haven&#39;t solved">', '<meta property="og:title" content="The full guide to superintelligence safety">'),
        ('<meta name="twitter:title" content="Superintelligence Safety: the problem we haven&#39;t solved">', '<meta name="twitter:title" content="The full guide to superintelligence safety">'),
        ('"headline": "Superintelligence Safety: the problem we haven\'t solved"', '"headline": "The full guide to superintelligence safety"'),
        ('<meta name="description" content="Superintelligence may arrive within years, and nobody yet knows how to make it safe. A short illustrated guide to the risks and what you can do this week.">', '<meta name="description" content="The whole case in one long read: why superintelligence could go wrong, the evidence behind it, where experts disagree, and what you can do this week.">'),
        ('<meta property="og:description" content="Superintelligence may arrive within years, and nobody yet knows how to make it safe. A short illustrated guide to the risks and what you can do this week.">', '<meta property="og:description" content="The whole case in one long read: why superintelligence could go wrong, the evidence behind it, where experts disagree, and what you can do this week.">'),
        ('<meta name="twitter:description" content="Superintelligence may arrive within years, and nobody yet knows how to make it safe. A short illustrated guide to the risks and what you can do this week.">', '<meta name="twitter:description" content="The whole case in one long read: why superintelligence could go wrong, the evidence behind it, where experts disagree, and what you can do this week.">'),
        ('"description": "Superintelligence may arrive within years, and nobody yet knows how to make it safe. A short illustrated guide to the risks and what you can do this week."', '"description": "The whole case in one long read: why superintelligence could go wrong, the evidence behind it, where experts disagree, and what you can do this week."'),
        ('<a class="brand" href="#top">', '<a class="brand" href="/">'),
        ('<a class="hbtn hbtn-lang" href="/index-zh" hreflang="zh-Hans">', '<a class="hbtn hbtn-lang" href="/guide-zh" hreflang="zh-Hans">')]),
    'index-zh.html': ('guide-zh.html', [
        ('<link rel="canonical" href="https://safeagi.ca/index-zh">', '<link rel="canonical" href="https://safeagi.ca/guide-zh">'),
        ('hreflang="en" href="https://safeagi.ca/">', 'hreflang="en" href="https://safeagi.ca/guide">'),
        ('hreflang="zh-Hans" href="https://safeagi.ca/index-zh">', 'hreflang="zh-Hans" href="https://safeagi.ca/guide-zh">'),
        ('hreflang="x-default" href="https://safeagi.ca/">', 'hreflang="x-default" href="https://safeagi.ca/guide">'),
        ('<meta property="og:url" content="https://safeagi.ca/index-zh">', '<meta property="og:url" content="https://safeagi.ca/guide-zh">'),
        ('"@id": "https://safeagi.ca/index-zh#article"', '"@id": "https://safeagi.ca/guide-zh#article"'),
        ('"mainEntityOfPage": "https://safeagi.ca/index-zh"', '"mainEntityOfPage": "https://safeagi.ca/guide-zh"'),
        ('<title>超级智能安全：我们尚未解决的难题 | SafeAGI</title>', '<title>超级智能安全完整指南 | SafeAGI</title>'),
        ('<meta property="og:title" content="超级智能安全：我们尚未解决的难题">', '<meta property="og:title" content="超级智能安全完整指南">'),
        ('<meta name="twitter:title" content="超级智能安全：我们尚未解决的难题">', '<meta name="twitter:title" content="超级智能安全完整指南">'),
        ('"headline": "超级智能安全：我们尚未解决的难题"', '"headline": "超级智能安全完整指南"'),
        ('<meta name="description" content="超级智能可能在几年内到来，而至今没有人知道怎样让它变得安全。一份简明的图解指南，讲清其中的风险，以及你本周就能做的事。">', '<meta name="description" content="一篇长文读完全部内容：超级智能为何可能失控、背后的证据、专家之间的分歧，以及你本周就能做的事。">'),
        ('<meta property="og:description" content="超级智能可能在几年内到来，而至今没有人知道怎样让它变得安全。一份简明的图解指南，讲清其中的风险，以及你本周就能做的事。">', '<meta property="og:description" content="一篇长文读完全部内容：超级智能为何可能失控、背后的证据、专家之间的分歧，以及你本周就能做的事。">'),
        ('<meta name="twitter:description" content="超级智能可能在几年内到来，而至今没有人知道怎样让它变得安全。一份简明的图解指南，讲清其中的风险，以及你本周就能做的事。">', '<meta name="twitter:description" content="一篇长文读完全部内容：超级智能为何可能失控、背后的证据、专家之间的分歧，以及你本周就能做的事。">'),
        ('"description": "超级智能可能在几年内到来，而至今没有人知道怎样让它变得安全。一份简明的图解指南，讲清其中的风险，以及你本周就能做的事。"', '"description": "一篇长文读完全部内容：超级智能为何可能失控、背后的证据、专家之间的分歧，以及你本周就能做的事。"'),
        ('<a class="brand" href="#top">', '<a class="brand" href="/index-zh">'),
        ('<a class="hbtn hbtn-lang" href="/" hreflang="en">', '<a class="hbtn hbtn-lang" href="/guide" hreflang="en">')])}

def make_guides():
    """The long page, published at /guide and /guide-zh now that the deck is the home page: same file, its own address."""
    for src, (out, swaps) in GUIDE_SWAPS.items():
        s = open(os.path.join(ROOT, src), encoding='utf-8').read()
        for a, b in swaps:
            assert s.count(a) == 1, (src, a, s.count(a))
        for a, b in swaps:
            s = s.replace(a, b, 1)
        open(os.path.join(ROOT, out), 'w', encoding='utf-8').write(s)
        print('wrote %s' % out)

if __name__ == '__main__':
    main()
