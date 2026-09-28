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
import re, os, sys, html, colorsys
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
def part_head(kicker, title='', lead=''):
    return ('<div class="t-parthead"><span class="t-pk">%s</span>%s%s</div>'
            % (kicker, ('<h3 class="t-ph">%s</h3>' % title) if title else '', ('<p class="t-lead">%s</p>' % lead) if lead else ''))

def auto(block):
    """Cards that carry a chart, or are short, open by default."""
    return re.sub(r'<div class="(ddc|endc)', r'<div data-auto="1" class="\1', block)

def unp(p): return re.sub(r'^<p[^>]*>|</p>$', '', p.strip())

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
                '<div class="tr-line"><span>%s</span></div><div class="tr-cliff"><svg viewBox="0 0 120 64" aria-hidden="true">'
                '<path class="d" %s d="M2 18 H58 L54 30 L60 40 L52 50 L56 62 H2 Z"/><path class="fall" d="M60 16 Q84 18 90 40"/>'
                '<path class="b" %s d="M92 38 L96 48 L106 48 L98 54 L101 63 L92 58 L83 63 L86 54 L78 48 L88 48 Z"/></svg><span>%s</span></div></div></div>'
                % (P['chip'], T['tries_norun'], W, W, T['tries_oneshot']))
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
    fig = re.sub(r'<text\b[^>]*>', lambda t: t.group(0).replace('fill="#ffd88a"', 'fill="#8a5d00"'), fig)   # the prize heading, not its glow
    fig = re.sub(r'\b(fill|stroke|stop-color)="(#[0-9a-fA-F]{3,6})"', cliff_colour, fig)
    fig = re.sub(r'<text\b[^>]*>', lambda t: re.sub(r'fill="(?!#1b1b1b|#5c574e|#6f6a60)#[0-9a-fA-F]{3,6}"', 'fill="#1b1b1b"', t.group(0)), fig)   # text: ink or grey
    cover = cover[:ci] + fig + cover[cj:]
    intro = dict(id='crossroads', num='', label=pg.label['crossroads'], acc=T['intro_acc'])
    S.append(dict(key='cover', sec=intro, wrap='mast', anchor='top', body=cover))
    S.append(dict(key='care', sec=intro, wrap='mast', body=care))
    cross = pg.section('crossroads')
    claims = kids(one(cross, '<div class="claims'))
    assert len(claims) == 3
    for i, c in enumerate(claims):
        S.append(dict(key='claim%d' % (i + 1), sec=intro, wrap='cross', anchor='crossroads' if i == 0 else '',
                      body='<div class="claims">%s</div>' % c))
    S.append(dict(key='solution', sec=intro, wrap='cross', body=one(cross, '<div class="mh-close')))

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
    add(ch, [('', bet + stand(ch) + auto(swap_svgs(one(B, '<div class="ddgrid'), charts_11(T))) + key(ch))])        # the question comes first, then the detail
    # 2.1
    ch = pg.chapter('why-upside'); B = ch['blocks']
    add(ch, [(P['2.1'][0], stand(ch) + one(B, '<figure')),
             (P['2.1'][1], part_head(*T['heads']['2.1b']) + auto(one(B, '<div class="ddgrid')))])
    # 2.2
    ch = pg.chapter('why-it-ends-badly'); B = ch['blocks']
    bodies = [b for b in B if b.startswith('<p class="body')]
    k, t = T['heads']['2.2c']
    add(ch, [(P['2.2'][0], stand(ch) + one(B, '<div class="ends')),
             (P['2.2'][1], part_head(*T['heads']['2.2b']) + auto(one(B, '<div class="ddc b rv" id="route-two"'))),
             (P['2.2'][2], part_head(k, t, text(bodies[0]) + T['open_any']) + one(B, '<div class="ddgrid') + key(ch) + bodies[1])])
    # 2.3
    ch = pg.chapter('why-one-try'); B = ch['blocks']
    bold = [x for x in B if x.startswith('<p class="rv" style="max-width:62ch')][0]
    h3s = [text(x) for x in B if x.startswith('<h3')]
    grids = [x for x in B if x.startswith('<div class="ddgrid')]
    para = [x for x in B if x.startswith('<p class="rv" style="max-width:68ch')][0]
    add(ch, [(P['2.3'][0], stand(ch) + tries_fig(T) + bold),
             (P['2.3'][1], part_head(T['heads']['2.3b'][0], h3s[0], T['heads']['2.3b'][1]) + auto(grids[0])),
             (P['2.3'][2], part_head(T['heads']['2.3c'], h3s[1], unp(para)) + auto(grids[1]))])
    # 3.1
    ch = pg.chapter('why-race'); B = ch['blocks']
    quiz = one(B, '<div class="rv" style="margin-top:24px">')
    add(ch, [(P['3.1'][0], stand(ch) + one(B, '<figure')),
             (P['3.1'][1], quiz + part_head(*T['heads']['3.1b']) + auto(one(B, '<div class="ddgrid')) + key(ch))])
    # 3.2
    ch = pg.chapter('why-human-misalignment'); B = ch['blocks']
    grids = [x for x in B if x.startswith('<div class="ddgrid')]; figs = [x for x in B if x.startswith('<figure')]
    add(ch, [(P['3.2'][0], stand(ch) + one(B, '<div class="body') + grids[0]),
             (P['3.2'][1], part_head(*T['heads']['3.2b']) + grids[1]),
             (P['3.2'][2], one(B, '<div class="rv" style="margin-top:24px">') + part_head(*T['heads']['3.2c']) + figs[0] + figs[1])])
    # 4.1
    ch = pg.chapter('why-translation'); B = ch['blocks']
    figs = [x for x in B if x.startswith('<figure')]; h3s = [x for x in B if x.startswith('<h3')]
    ps = [x for x in B if x.startswith('<p class="rv"')]; grids = [x for x in B if x.startswith('<div class="ddgrid')]
    assert len(figs) == 3 and len(h3s) == 2 and len(ps) == 3 and len(grids) == 2
    H = T['heads']
    add(ch, [(P['4.1'][0], stand(ch) + figs[0]),
             (P['4.1'][1], part_head(H['4.1b'], text(h3s[0]), unp(ps[0])) + figs[1]),
             (P['4.1'][2], part_head(H['4.1c'], '', unp(ps[1])) + grids[0]),
             (P['4.1'][3], part_head(H['4.1d']) + demo_bare(one(B, '<div class="demo-embed'))),
             (P['4.1'][4], part_head(H['4.1e'], text(h3s[1]), unp(ps[2])) + iceberg_fig(T)),
             (P['4.1'][5], part_head(H['4.1f']) + grids[1])])
    # 4.2
    ch = pg.chapter('why-safety-hard'); B = ch['blocks']
    body = kids(one(B, '<div class="body'))
    add(ch, [(P['4.2'][0], stand(ch) + one(body, '<figure')),
             (P['4.2'][1], part_head(H['4.2b']) + auto(one(body, '<div class="ddgrid'))),
             (P['4.2'][2], part_head(H['4.2c']) + one(body, '<p') + one(B, '<div class="core'))])
    # 5.1
    ch = pg.chapter('response'); B = ch['blocks']
    layers = kids(one(B, '<div class="tinv'))
    assert len(layers) == 4
    lname = [text(re.search(r'<h4>(.*?)</h4>', l, re.S).group(1)).split(' ', 1)[-1].strip() for l in layers]
    parts = [(P['5.1'][0], stand(ch) + one(B, '<figure'))]
    for i, l in enumerate(layers):
        parts.append((lname[i], part_head(H['5.1layer'] % (i + 2, i + 1), text(one(B, '<h3')) if i == 0 else '') + l))
    parts.append((P['5.1'][1], part_head(H['5.1f']) + ''.join(b for b in B if b.startswith('<details'))))
    add(ch, parts)
    # 5.2
    ch = pg.chapter('response-gaps'); B = ch['blocks']
    add(ch, [(P['5.2'][0], stand(ch) + one(B, '<div class="ddgrid')),
             (P['5.2'][1], part_head(H['5.2b']) + one(B, '<figure') + one(B, '<details') + key(ch))])
    # 5.3 ask: no sec-head, an eyebrow and a big heading
    B = pg.section('ask')
    eb = inner(one(B, '<p class="eyebrow'))
    ask = dict(id='ask', num=re.search(r'(\d\.\d)', eb).group(1), chapno=eb, h2=inner(one(B, '<h2')), label=pg.label['ask'],
               group=pg.group['5'][0], acc=pg.group['5'][1], blocks=B)
    add(ask, [('', one(B, '<div class="firsts'))])
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
        'Abundance': 2, 'Health': 1, 'Productivity': 4, 'Education': 5, 'Scientific progress': 3, 'Labour': 6,
        'The user is the adversary': 1, 'The AI is the adversary': 4, 'Nobody is the adversary': 3, 'The incentives are the adversary': 2,
        'Engineered pandemic': 1, 'Infrastructure': 2, 'Resources': 3, 'Self-preservation': 4, 'Geoengineering': 5, 'Nuclear and autonomous weapons': 6,
        'The trend': 4, 'What it costs': 2, 'The speed gap': 3, 'What it runs on': 5,
        'Corner-cutting': 1, 'The rope': 4}
CYCLE = [4, 3, 5, 2, 6, 1]
CARD_RE = r'<div(?: data-auto="1")? class="(?:ddc|endc)\b[^"]*"'

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
        if name == 'rect' and 'stroke=' not in t and 'fill="none"' not in t:
            w = re.search(r' width="([\d.]+)"', t); hh = re.search(r' height="([\d.]+)"', t)
            if w and hh and float(w.group(1)) >= 6 and float(hh.group(1)) >= 6:
                t = t[:-2] + ' stroke="#1b1b1b" stroke-width="1.5" vector-effect="non-scaling-stroke"/>' if t.endswith('/>') else t
        return t
    body = re.sub(r'<(\w+)\b[^>]*>', el, body)
    body = body.replace('font-family="Archivo,sans-serif"', 'font-family="Comic Neue,Archivo,sans-serif"')
    return tag + body + '</svg>'

def paper(h):
    n0 = h.count('<svg')
    h, n = re.subn(r'(<svg\b[^>]*viewBox="-?[\d.]+ -?[\d.]+ ([\d.]+)[^"]*"[^>]*>)(.*?)</svg>', paper_svg, h, flags=re.S)
    assert n == n0, ('svg without a viewBox', n, n0)
    return h


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
        nar = ('<div class="cx-nar"><img class="cx-kenji" src="/deck-img/kenji-%s.jpg" alt="%s" width="72" height="72" decoding="async">'
               '<p class="cx-bubble">%s</p>%s</div>') % (mood, html.escape(T['kenji_alt'] % T['moods'][mood]), html.escape(line),
               ('<div class="cx-capy"><img src="/deck-img/capy.jpg" alt="Capy" width="54" height="54" decoding="async"><span>%s</span></div>' % html.escape(capy)) if capy else '')
        body, got = colorize(x['body'], None if en_colors is None else en_colors[x['key']])
        colors[x['key']] = got
        if x['wrap'] == 'dd':
            n, parts, j = x['parts'], None, x['part']
            same = [y for y in S if y['sec'] is sec]
            chips = ''
            if len(same) > 1:
                chips = '<div class="t-chips" aria-label="%s">%s</div>' % (T['chips_aria'], ''.join(
                    '<button type="button" class="t-chip%s" data-go="%d"><b>%d</b>%s</button>' % (' on' if y is x else '', S.index(y), k + 1, html.escape(y['chip']))
                    for k, y in enumerate(same)))
            if j == 0:
                head = ('<div class="wrap t-head"><div class="sec-head"><span class="chapno">%s<span class="t-grp">%s</span></span><h2>%s</h2>%s</div></div>'
                        % (sec['chapno'], sec['group'], sec['h2'], chips))
            else:
                head = '<div class="wrap t-head t-mini"><p class="t-run"><b>%s</b> · %s</p>%s</div>' % (sec['num'], text(sec['h2']), chips)
            inside = '<section%s class="dd">%s<div class="wrap t-body">%s%s</div></section>' % (
                (' id="%s"' % x['anchor']) if x.get('anchor') else '', head, nar, body)
        elif x['wrap'] == 'mast':
            inside = '<header class="masthead"%s><div class="wrap t-body">%s%s</div></header>' % (
                (' id="%s"' % x['anchor']) if x.get('anchor') else '', nar, body)
        elif x['wrap'] == 'cross':
            inside = '<section class="cross"%s><div class="wrap t-body">%s%s</div></section>' % (
                (' id="%s"' % x['anchor']) if x.get('anchor') else '', nar, body)
        else:
            inside = '<section class="cross anthem" id="anthem"><div class="wrap t-body">%s%s</div></section>' % (nar, body)
        # buttons: back, then the next step
        btns = []
        if i > 0: btns.append('<button type="button" class="p-btn t-back" data-go="%d"><span aria-hidden="true">&larr;</span> %s</button>' % (i - 1, T['back']))
        if i < len(S) - 1:
            nx = S[i + 1]
            if nx['sec'] is sec:
                lab = T['cont_part'] % (x['part'] + 2) if x['wrap'] == 'dd' else T['cont']
                btns.append('<button type="button" class="p-btn t-cont" data-go="%d">%s <span aria-hidden="true">&rarr;</span></button>' % (i + 1, lab))
            else:
                ns = nx['sec']
                lab = (T['next'] % ('%s %s' % (ns['num'], ns['label']))) if ns.get('num') else T['next'] % ns['label']
                btns.append('<button type="button" class="p-btn" data-go="%d">%s <span aria-hidden="true">&rarr;</span></button>' % (i + 1, html.escape(lab)))
        else:
            btns.append('<button type="button" class="p-btn t-back" data-go="0">%s <span aria-hidden="true">&uarr;</span></button>' % T['restart'])
        where = ('<b>%s</b> %s' % (sec['num'], html.escape(sec['label']))) if sec.get('num') else html.escape(sec['label'])
        out.append('<div class="slide" data-key="%s" data-acc="%s" style="--c-acc:%s" data-where="%s">%s<div class="b2-next">%s</div></div>'
                   % (x['key'], sec['acc'], sec['acc'], html.escape(where), balanced(inside), ''.join(btns)))
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
            parts = '<ol class="tc-parts">%s</ol>' % ''.join(
                '<li><button type="button" class="tc-p" data-go="%d" data-i="%d">%s</button></li>' % (i, i, html.escape(nm)) for i, nm in zip(idx, names))
        out.append('<div class="tc-sec" data-first="%d" data-last="%d"><button type="button" class="tc-s" data-go="%d" style="--c:%s">%s</button>%s</div>'
                   % (idx[0], idx[-1], idx[0], sec['acc'], lab, parts))
    return '<nav class="dk-toc" id="dk-toc" aria-label="%s">%s%s</nav>\n' % (T['contents'], ''.join(out), pg.toc_tail)


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
            '<div class="dk-acts"><button type="button" class="dk-btn dk-menu-btn" id="dk-menu-btn" aria-expanded="false" aria-controls="dk-menu">%s</button>'
            '<a class="dk-btn" href="%s" hreflang="%s">%s</a><a class="dk-btn dk-go" href="#what-you-can-do">%s</a></div></div>'
            '<div class="d-segs">%s</div></header>\n'
            '<nav class="dk-menu" id="dk-menu" aria-label="%s" hidden><div class="dk-menu-in">%s<div class="dk-x">%s</div></div></nav>\n') % (
            primer, T['contents'], T['lang_to'], 'zh-Hans' if pg.lang == 'en' else 'en', text(lang.group(2)), act, segs, T['contents'], ''.join(cols), extra)


def page(pg, slides, segs, S):
    s = pg.s; T = pg.T
    head = s[:s.index('<body')]
    head, nr = re.subn(r'<meta name="robots" content="[^"]*">', '<meta name="robots" content="noindex, nofollow">', head)
    assert nr == 1 and head.count('name="robots"') == 1
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
        ('if (svg.closest(".cross-hero,.endc-icons,.ends-out,.tix,.tlayer-h,.tcard-h")) return false;',
         'if (svg.closest(".cross-hero,.endc-icons,.ends-out,.tix,.tlayer-h,.tcard-h,.ice-fig,.tr-fig,.dk-chart")) return false;'),   # deck drawings size themselves
        ('$$(".cando-block:not(#what-you-can-do)", main)', '$$(".cando-block.lx-never", main)'),   # each group has its own slide
        ('  function refitAll(){ $$("svg", main).forEach(function(svg){ svg._lxIgnore = null; }); fitAll(main); }',
         '  function refitAll(){ $$("svg", main).forEach(function(svg){ svg._lxIgnore = null; }); fitAll(main); }\n  window.__lxFitAll = refitAll;'),
    ]:
        assert lx.count(a) == 1, ('lx patch', a[:50])
        lx = lx.replace(a, b)
    js = open(os.path.join(ROOT, 'tools', 'deck', 'deck.js'), encoding='utf-8').read()
    doc = (head + btag + '\n' + toast + '\n' + skip + '\n' + bar +
           '<main id="main"><div class="deck"><div class="track">%s</div></div></main>\n' % slides +
           '<nav class="d-nav" aria-label="%s"><button type="button" id="d-prev" aria-label="%s">&larr;</button>'
           '<button type="button" id="d-next" class="next" aria-label="%s">&rarr;</button></nav>\n'
           '<p class="d-hint">%s</p>\n' % (T['nav_aria'], T['prev'], T['next_aria'], T['keys']) +
           lx + '\n' + scripts[1] + '\n' + scripts[2] + '\n<script>\n' + js + '\n</script>\n</body>\n</html>\n')
    return doc


def main():
    en = Page('en'); zh = Page('zh')
    S_en, sl_en, sg_en, colors = build(en)
    S_zh, sl_zh, sg_zh, _ = build(zh, colors)
    assert [x['key'] for x in S_en] == [x['key'] for x in S_zh]
    for pg, sl, sg, S in ((en, sl_en, sg_en, S_en), (zh, sl_zh, sg_zh, S_zh)):
        doc = paper(page(pg, sl, sg, S))
        ids = re.findall(r'\bid="([^"]+)"', doc)
        dup = sorted(set(i for i in ids if ids.count(i) > 1))
        assert not dup, ('duplicate ids', dup[:10])
        open(os.path.join(ROOT, pg.out), 'w', encoding='utf-8').write(doc)
        print('wrote %s: %d slides, %d KB' % (pg.out, len(S_en), len(doc) // 1024))

if __name__ == '__main__':
    main()
