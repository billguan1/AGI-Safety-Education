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
def part_head(kicker, title='', lead=''):
    return ('<div class="t-parthead"><span class="t-pk">%s</span>%s%s</div>'
            % (kicker, ('<h3 class="t-ph">%s</h3>' % title) if title else '', ('<p class="t-lead">%s</p>' % lead) if lead else ''))

def auto(block):
    """Cards that carry a chart, or are short, open by default."""
    return re.sub(r'<div class="(ddc|endc)', r'<div data-auto="1" class="\1', block)

def unp(p): return re.sub(r'^<p[^>]*>|</p>$', '', p.strip())

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
    return ('<figure class="secfig dk-int dkw-%s" data-w="%s" data-cfg="%s"><p class="tr-title">%s</p><div class="dki-body"></div>'
            '<p class="dk-sr">%s</p>%s</figure>') % (kind, kind, html.escape(json.dumps(W, ensure_ascii=False)), W['title'], W['alt'], src.group(0) if src else '')

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
        new = c[:c.index('>') + 1].replace('class="endc"', 'data-auto="1" class="endc"', 1) + head + sc + '<p>%s</p>' % refs_html(line, base) + (icons.group(0) if icons else '') + '</%s>' % tag
        out = out[:m.start()] + new + out[m.end():]
    return out

def subgoal_tabs(block, pg):
    fig = re.findall(r'<figure\b.*?</figure>', block, re.S)[0]
    return swap_fig_svgs(block, 0, H('subgoals', pg.lang, svg_texts(fig), (pg.T['subtabs'], pg.refbase)))

def card_heading(block, n, new):
    """Replace the heading of the block's nth card (the chart now carries its old point)."""
    hs = [m for m in re.finditer(r'<h4>.*?</h4>', block, re.S)]
    m = hs[n]
    return block[:m.start()] + '<h4>%s</h4>' % html.escape(new) + block[m.end():]

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
        panels.append((t[5], [(t[a], J(b, c)) for a, b, c in res]))
        chips = ''.join('<button type="button" class="dkh-chip dsg-tab" data-i="%d" aria-pressed="%s">%s</button>' % (i, 'true' if i == 4 else 'false', E(t[i])) for i in range(5))
        body = ''.join('<div class="dsg-panel" data-i="%d"%s><p class="dkh-t dkh-arrow">%s</p><div class="dkh-four">%s</div></div>' % (
            i, '' if i == 4 else ' hidden', E(h), ''.join('<div class="dkh-box"><b>%s</b><span>%s</span></div>' % (E(a), refs_html(b, base)) for a, b in cards))
            for i, (h, cards) in enumerate(panels))
        return '<div class="dkh dsg"><div class="dkh-chips">%s</div>%s</div>' % (chips, body)
    if kind == 'whose':
        groups = ''.join('<span class="dkh-chip">%s</span>' % E(t[i]) for i in range(1, 5))
        return ('<div class="dkh">%s<div class="dkh-flow"><div class="dkh-col">%s</div><span class="dkh-to" aria-hidden="true">→</span>'
                '<div class="dkh-q-box"><b>?</b><span>%s</span></div><span class="dkh-to" aria-hidden="true">→</span><span class="dkh-chip dkh-hot">%s</span></div></div>') % (T0(0), groups, E(t[6]), E(t[7]))
    if kind == 'decide':
        few = [J(1, 2), J(3, 4), J(5, 6), J(7, 8) + '<small>' + E(J(10, 11, 12, 13)) + '</small>']
        dots = ''.join('<div class="dkh-few"><i></i><span>%s</span></div>' % (E(x) if '<small>' not in x else E(x.split('<small>')[0]) + '<small>' + x.split('<small>')[1]) for x in few)
        return '<div class="dkh">%s<div class="dkh-fewrow">%s</div><div class="dkh-many"><span>%s</span></div></div>' % (T0(0), dots, E(t[9]))
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
        return '<div class="dkh">%s<div class="dkh-scroll"><table class="dkh-tab"><thead><tr><th></th><th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table></div><p class="dkh-note">%s</p></div>' % (
               T0(0), E(t[1]), E(t[2]), body, E(t[27]))
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
        return '<div class="dkh">%s%s<p class="dkh-note">%s</p></div>' % (T0(0), body, E(t[10]))
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

def rebuild(block, n, kind, lang):
    """Swap the block's nth figure drawing for its HTML rebuild; the source line stays."""
    figs = re.findall(r'<figure\b.*?</figure>', block, re.S)
    t = svg_texts(figs[n])
    extra = orgs_grid(figs[n], t) if kind == 'orgs' else None
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
    CARE_ICONS = [
        '<circle cx="16" cy="16" r="11"/><path d="M16 9v7l5 3"/>',                                   # clock: arriving soon
        '<path d="M16 5v22M9 27h14M6 10h20"/><path d="M6 10l-4 8h8zM26 10l-4 8h8z"/>',               # scales: abundance or destruction
        '<rect x="5" y="5" width="22" height="22" rx="4"/><path d="M12.5 13a3.5 3.5 0 1 1 5 3.2c-1 .5-1.5 1.2-1.5 2.3M16 22.5v.5"/>',  # unknown
    ]
    for n, ic in enumerate(CARE_ICONS, 1):
        old = '<span class="care-n">%d</span>' % n
        assert care.count(old) == 1, ('care badge', n)
        care = care.replace(old, '<span class="care-top">%s<span class="care-ic" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">%s</svg></span></span>' % (old, ic))
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
            items = ''.join('<li class="dtl-%s"><i aria-hidden="true">%s</i><b>%s</b><span>%s</span></li>' % (
                ('esc' if k else 'warn'), ('!' if k else ''), E(y), E(x)) for y, x, k, r in I['timeline'])
            nums = sorted(set(int(n) for y, x, k, r in I['timeline'] for n in re.findall(r'\d+', r)))
            srcline = '<p class="dtl-src">%s %s</p>' % (E(T['src_word']), ' '.join('<a href="%s#s%d">%d</a>' % (pg.refbase, n, n) for n in nums))
            key = '<p class="dtl-key"><span class="dtl-warn"><i></i>%s</span><span class="dtl-esc"><i>!</i>%s</span></p>' % (E(I['tl_key'][0]), E(I['tl_key'][1]))
            c, ntl = re.subn(r'<ol class="dkh-tl">.*?</ol>', lambda m: key + '<ol class="dkh-tl dtl">%s</ol>' % items + srcline, c, flags=re.S)
            assert ntl == 1
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
    add(ch, [(P['2.1'][0], stand(ch) + swap_fig(one(B, '<figure'), 0, 'growth', T)),
             (P['2.1'][1], part_head(*T['heads']['2.1b']) + one(B, '<div class="ddgrid'))])             # six cards start closed
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
    bold = [x for x in B if x.startswith('<p class="rv" style="max-width:62ch')][0]
    h3s = [text(x) for x in B if x.startswith('<h3')]
    grids = [x for x in B if x.startswith('<div class="ddgrid')]
    para = [x for x in B if x.startswith('<p class="rv" style="max-width:68ch')][0]
    add(ch, [(P['2.3'][0], stand(ch) + tries_fig(T) + bold),
             (P['2.3'][1], part_head(T['heads']['2.3b'][0]) + auto(add_example(swap_fig(swap_fig(grids[0], 1, 'loop', T, True), 0, 'trend', T), 1, T['incidents']['loop'], pg.refbase))),   # Kenji carries the reason
             (P['2.3'][2], part_head(T['heads']['2.3c'], '', unp(para)) + auto(swap_fig(swap_fig(card_heading(grids[1], 1, T['wid']['layers']['card_h']), 1, 'layers', T, True), 0, 'speed', T)))])
    # 3.1
    ch = pg.chapter('why-race'); B = ch['blocks']
    quiz = one(B, '<div class="rv" style="margin-top:24px">')
    add(ch, [(P['3.1'][0], stand(ch) + rebuild(one(B, '<figure'), 0, 'payoff3', pg.lang) + widget_plain('race', T)),
             (P['3.1'][1], quiz + part_head(*T['heads']['3.1b']) + auto(one(B, '<div class="ddgrid')) + key(ch))])
    # 3.2
    ch = pg.chapter('why-human-misalignment'); B = ch['blocks']
    grids = [x for x in B if x.startswith('<div class="ddgrid')]; figs = [x for x in B if x.startswith('<figure')]
    add(ch, [(P['3.2'][0], stand(ch) + one(B, '<div class="body') + grids[0]),
             (P['3.2'][1], part_head(*T['heads']['3.2b']) + widget_plain('chain', T, {'cards': cards_text(grids[1])})),
             (P['3.2'][2], one(B, '<div class="rv" style="margin-top:24px">') + part_head(*T['heads']['3.2c']) + rebuild(figs[0], 0, 'whose', pg.lang) + rebuild(figs[1], 0, 'decide', pg.lang))])
    # 4.1
    ch = pg.chapter('why-translation'); B = ch['blocks']
    figs = [x for x in B if x.startswith('<figure')]; h3s = [x for x in B if x.startswith('<h3')]
    ps = [x for x in B if x.startswith('<p class="rv"')]; grids = [x for x in B if x.startswith('<div class="ddgrid')]
    assert len(figs) == 3 and len(h3s) == 2 and len(ps) == 3 and len(grids) == 2
    H = T['heads']
    add(ch, [(P['4.1'][0], stand(ch) + rebuild(figs[0], 0, 'twoways', pg.lang)),
             (P['4.1'][1], part_head(H['4.1b']) + rebuild(figs[1], 0, 'lost', pg.lang)),                                     # Kenji carries outer alignment
             (P['4.1'][2], part_head(H['4.1c'], '', unp(ps[1])) + grids[0]),
             (P['4.1'][3], part_head(H['4.1d']) + loophole(demo_bare(one(B, '<div class="demo-embed')), pg)),
             (P['4.1'][4], part_head(H['4.1e'], '', unp(ps[2])) + iceberg_fig(T)),
             (P['4.1'][5], part_head(H['4.1f']) + grids[1])])
    # 4.2
    ch = pg.chapter('why-safety-hard'); B = ch['blocks']
    body = kids(one(B, '<div class="body'))
    add(ch, [(P['4.2'][0], stand(ch) + swap_fig(one(body, '<figure'), 0, 'gap', T)),
             (P['4.2'][1], part_head(H['4.2b']) + auto(short_cards(rebuild(rebuild(one(body, '<div class="ddgrid'), 1, 'grader', pg.lang), 0, 'talk', pg.lang), T['short42']))),
             (P['4.2'][2], part_head(H['4.2c']) + widget_plain('inside', T) + one(body, '<p') + one(B, '<div class="core'))])
    # 5.1
    ch = pg.chapter('response'); B = ch['blocks']
    layers = kids(one(B, '<div class="tinv'))
    assert len(layers) == 4
    lname = [text(re.search(r'<h4>(.*?)</h4>', l, re.S).group(1)).split(' ', 1)[-1].strip() for l in layers]
    parts = [(P['5.1'][0], stand(ch) + swap_fig(one(B, '<figure'), 0, 'cheese', T))]
    for i, l in enumerate(layers):
        l = l.replace('<div class="tlayer"', '<div data-crack="%s" class="tlayer"' % html.escape(json.dumps(T['crack'], ensure_ascii=False)), 1)
        parts.append((lname[i], part_head(H['5.1layer'] % (i + 2, i + 1)) + l))
    dets = [b for b in B if b.startswith('<details') and 'aside-note' not in b[:60]]      # the older-framing footnote stays on the long page only
    dets = [rebuild(d, 0, 'levers', pg.lang) if 'exfold' in d[:40] and k == 0 else (rebuild(d, 0, 'orgs', pg.lang) if 'exfold' in d[:40] and k == 1 else d) for k, d in enumerate(dets)]
    parts.append((P['5.1'][1], part_head(H['5.1f']) + ''.join(dets)))
    add(ch, parts)
    # 5.2
    ch = pg.chapter('response-gaps'); B = ch['blocks']
    add(ch, [(P['5.2'][0], stand(ch) + add_example(one(B, '<div class="ddgrid'), 0, T['incidents']['hard'], pg.refbase)),
             (P['5.2'][1], part_head(H['5.2b']) + swap_fig(one(B, '<figure'), 0, 'guards', T) + rebuild(one(B, '<details'), 0, 'numbers', pg.lang) + key(ch))])
    # 5.3 ask: no sec-head, an eyebrow and a big heading
    B = pg.section('ask')
    eb = inner(one(B, '<p class="eyebrow'))
    ask = dict(id='ask', num=re.search(r'(\d\.\d)', eb).group(1), chapno=eb, h2=inner(one(B, '<h2')), label=pg.label['ask'],
               group=pg.group['5'][0], acc=pg.group['5'][1], blocks=B)
    firsts = [text(h) for h in re.findall(r'<h3>(.*?)</h3>', one(B, '<div class="firsts'), re.S)]
    assert len(firsts) == 2
    add(ask, [('', widget_plain('fork', T, {'ends': firsts}))])
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
        # a quick check at the end of each chapter; the results card on the last slide
        num = sec.get('num')
        if x['wrap'] == 'dd' and x['part'] == x['parts'] - 1 and num in T['checks']:
            q, opts, right, why = T['checks'][num]
            body += '<div class="dk-check" data-id="c-%s" data-c="%s"></div>' % (num, html.escape(json.dumps(
                dict(k=T['checks_k'], q=q, opts=opts, right=right, why=why, ok=T['right'], no=T['wrongp']), ensure_ascii=False)))
        if x['key'] == 'anthem':
            total = len([1 for y in S if y is S[first[y['sec']['id']]] and y['sec'].get('num')])
            body = '<div class="dk-results" data-c="%s"></div>' % html.escape(json.dumps(dict(T['results'], total=total, nchecks=len(T['checks'])), ensure_ascii=False)) + body
        colors[x['key']] = got
        same = [y for y in S if y['sec'] is sec]
        chips = ''
        if len(same) > 1:
            names = T['intro_parts'] if sec['id'] == 'crossroads' else [y.get('chip') for y in same]
            cl = []; num = 0
            for k, (y, nm) in enumerate(zip(same, names)):
                sub = sec['id'] == 'crossroads' and 2 <= k <= 4
                if not sub: num += 1
                if sec['id'] == 'crossroads' and k == 2: cl.append('<span class="t-subchips">')
                cl.append('<button type="button" class="t-chip%s%s" data-go="%d">%s%s</button>' % (' on' if y is x else '', ' t-chip-sub' if sub else '', S.index(y),
                           '' if sub else '<b>%d</b>' % num, html.escape(nm)))
                if sec['id'] == 'crossroads' and k == 4: cl.append('</span>')
            chips = '<div class="t-chips" aria-label="%s">%s</div>' % (T['chips_aria'], ''.join(cl))
        ihead = ('<div class="wrap t-head"><div class="sec-head"><span class="chapno">%s</span><h2>%s</h2>%s</div></div>'
                 % (x['kicker'], x['title'], chips)) if x.get('title') else ''
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
            inside = '<header class="masthead"%s>%s<div class="wrap t-body">%s%s</div></header>' % (
                (' id="%s"' % x['anchor']) if x.get('anchor') else '', ihead, nar, body)
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
            items = []
            for k, (i, nm) in enumerate(zip(idx, names)):
                sub = sec['id'] == 'crossroads' and 2 <= k <= 4
                items.append('<li%s><button type="button" class="tc-p" data-go="%d" data-i="%d">%s</button></li>' % (' class="tc-sub"' if sub else '', i, i, html.escape(nm)))
            parts = '<ol class="tc-parts">%s</ol>' % ''.join(items)
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
        ('var CARD = ".ddc,.endc,.tcard,.cl-half";', 'var CARD = ".ddc,.endc,.cl-half";'),   # technique cards are the weak-spot game
        ('if (svg.closest(".cross-hero,.endc-icons,.ends-out,.tix,.tlayer-h,.tcard-h")) return false;',
         'if (svg.closest(".cross-hero,.endc-icons,.ends-out,.tix,.tlayer-h,.tcard-h,.ice-fig,.tr-fig,.dk-chart,.dk-int")) return false;'),   # deck drawings size themselves
        ('$$(".cando-block:not(#what-you-can-do)", main)', '$$(".cando-block.lx-never", main)'),   # each group has its own slide
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

def main():
    en = Page('en'); zh = Page('zh')
    S_en, sl_en, sg_en, colors = build(en)
    S_zh, sl_zh, sg_zh, _ = build(zh, colors)
    assert [x['key'] for x in S_en] == [x['key'] for x in S_zh]
    for pg, sl, sg, S in ((en, sl_en, sg_en, S_en), (zh, sl_zh, sg_zh, S_zh)):
        doc = paper(page(pg, sl, sg, S)).replace(pg.old_intro, pg.T['intro_label'])
        assert doc.count('<div class="slide" data-key=') == len(S_en), ('slides missing', doc.count('<div class="slide" data-key='))
        ids = re.findall(r'\bid="([^"]+)"', doc)
        dup = sorted(set(i for i in ids if ids.count(i) > 1))
        assert not dup, ('duplicate ids', dup[:10])
        open(os.path.join(ROOT, pg.out), 'w', encoding='utf-8').write(doc)
        print('wrote %s: %d slides, %d KB' % (pg.out, len(S_en), len(doc) // 1024))
    comic_reference('reference.html', TXT.EN_FONTS)
    comic_reference('reference-zh.html', TXT.ZH_FONTS)

if __name__ == '__main__':
    main()
