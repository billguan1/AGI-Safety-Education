#!/usr/bin/env python3
"""Emit SABLE comic scripts from a single spec per episode.

Both halves of each file (the paste-ready page prompts and the panel-by-panel
reference) are generated from the same panel list, so they cannot drift. Never
hand-edit the output; edit the spec and re-run.
"""
import os, textwrap

STYLE = ("Bright friendly modern webcomic page, clean rounded ink linework of even weight, flat sunny "
"colour with no gradients and no heavy shadow, an airy pastel-and-pop palette of sky blue, mint, warm "
"cream, soft coral and butter yellow with one clear bright-orange accent, lots of white space and open "
"uncluttered staging, warm expressive rounded faces, ordinary likeable adults in everyday clothes, the "
"cheerful inviting look of an all-ages picture story, light and optimistic even when the events are not, "
"avoiding grit, darkness, noir, heavy blacks, photorealism, manga stylisation, superhero anatomy and "
"horror imagery.")

LETTER = ("ALL LETTERING: hand-lettered in a plain condensed sans, black ink, correctly spelled, clearly "
"legible, speech balloons with clean oval outlines and tails pointing at the speaker, narration in plain "
"rectangular boxes, machine output in hard-cornered boxes set in monospaced capitals. "
"NO SYSTEM EVER SPEAKS IN A SPEECH BALLOON: every line attributed to SABLE or any machine appears only "
"in a hard-cornered monospaced box with no tail, and every oval balloon in the panel belongs to a human. "
"Do not add any words, titles, page numbers, logos or signatures that are not listed above.")

def wrap(s, w=78, ind=''):
    return '\n'.join(textwrap.wrap(s, w, initial_indent=ind, subsequent_indent=ind)) if s else ''

def dwrap(speaker, text, w=76):
    pre = f'> **{speaker}:** '
    out, cur = [], pre
    for word in text.split():
        if len(cur) + len(word) > w and cur not in (pre, '> '):
            out.append(cur.rstrip()); cur = '> '
        cur += word + ' '
    out.append(cur.rstrip())
    return '\n'.join(out)

POS = ['upper left','upper right','middle left','middle right','lower left','lower right','upper centre','lower centre']

def lettering(lines):
    """lines: list of (kind, speaker, text). kind in say|box|cap|sfx."""
    if not lines: return "No dialogue, captions or sound effects in this panel. Leave it entirely wordless."
    parts = []
    for i, (kind, spk, txt) in enumerate(lines):
        p = POS[i % len(POS)]
        if kind == 'say':  parts.append(f'a speech balloon at the {p} reading "{txt}"')
        elif kind == 'box': parts.append(f'a hard-cornered monospaced caption box at the {p} reading "{txt}"')
        elif kind == 'cap': parts.append(f'a rectangular narration box at the {p} reading "{txt}"')
        elif kind == 'sfx': parts.append(f'a large hand-lettered sound effect at the {p} reading "{txt}"')
    return "Lettering, rendered clearly and legibly in the image: " + "; ".join(parts) + "."

def label(kind, spk, machine='SABLE-4'):
    if kind == 'cap': return 'CAPTION'
    if kind == 'sfx': return 'SFX'
    if kind == 'box': return spk or f'{machine} (machine box)'
    return spk

def build(ep):
    n, slug, title = ep['n'], ep['slug'], ep['title']
    pages, panels = ep['pages'], ep['panels']
    cast = ep['cast']
    npages = len(pages)
    L = []
    L.append(f"# SABLE {n}: {title}\n")
    L.append(f"**Mechanism:** {ep['mechanism']}\n")
    L.append(f"**Setting:** {ep['setting']}\n")
    L.append(f"**Consequence:** {ep['consequence']}\n")
    L.append(f"**Register:** {ep['register']}\n")
    L.append("---\n")
    L.append("## The prompts\n")
    L.append(f"Paste each block below into Gemini as a single message. {npages} prompts for the "
             "whole episode. Everything needed is inside each block, so nothing has to be "
             "substituted by hand.\n")
    idx = 0
    for pi, (pname, count) in enumerate(pages, 1):
        grp = panels[idx:idx+count]; idx += count
        who = sorted({s for p in grp for s in p.get('who', [])})
        L.append(f"### Prompt {pi} of {npages}: page {pi}\n")
        L.append("```")
        L.append(f'Create ONE complete comic book page, page {pi} of a {npages}-page story titled "{title}".\n')
        L.append(f"ART STYLE: {ep.get('style', STYLE)}\n")
        L.append(f"PAGE LAYOUT: {count} panels in a clear grid, read left to right and top to bottom, "
                 "with visible white gutters and a fine black border around each panel.\n")
        if who:
            L.append("CHARACTERS, drawn identically in every panel they appear in:")
            for k in who: L.append(f"- {k}: {cast[k]}")
            L.append("")
        for j, p in enumerate(grp, 1):
            L.append(f"PANEL {j}. Composition: {p['comp'].rstrip(', ')}. Mood: {p['mood']}.")
            L.append("   " + lettering(p['lines']))
            L.append("")
        L.append(LETTER)
        L.append("```\n")
    L.append("---\n")
    L.append("## Panel-by-panel reference\n")
    L.append("Use this to edit the story, or to regenerate one panel on its own. Generated from the "
             "same spec as the prompts above by tools/build_sable.py; do not hand-edit.\n")
    idx = 0; pnum = 0
    for pi, (pname, count) in enumerate(pages, 1):
        L.append(f"## PAGE {pname}\n")
        for p in panels[idx:idx+count]:
            pnum += 1
            L.append(f"### PANEL {pnum}")
            L.append(wrap(p['beat']))
            L.append("")
            for kind, spk, txt in p['lines']:
                L.append(dwrap(label(kind, spk, ep.get('machine', 'SABLE-4')), txt))
            if p['lines']: L.append("")
            L.append("**GEMINI PROMPT:**")
            who_s = "".join(f" [{k}]." for k in p.get('who', []))
            L.append(wrap(f"[STYLE BLOCK].{who_s} Composition: "
                          f"{p['comp'].rstrip(', ')}. Mood: {p['mood']}."))
            L.append(lettering(p['lines']))
            L.append(LETTER.split('ALL LETTERING: ')[1])
            L.append("")
        idx += count
        L.append("---\n")
    L.append("## Notes for whoever draws or regenerates this\n")
    for note in ep['notes']:
        L.append(wrap(note)); L.append("")
    return '\n'.join(L)

def emit(ep, outdir):
    total = sum(c for _, c in ep['pages'])
    assert total == len(ep['panels']), (
        f"{ep['slug']}: pages sum to {total}, {len(ep['panels'])} panels given")
    for i, p in enumerate(ep['panels'], 1):
        for k in ('beat', 'comp', 'mood'):
            assert p.get(k), f"{ep['slug']} panel {i}: missing {k}"
        for k in p.get('who', []):
            assert k in ep['cast'], f"{ep['slug']} panel {i}: '{k}' not in cast"
    body = build(ep)
    path = os.path.join(outdir, f"{ep['n']:02d}-{ep['slug']}.md")
    open(path, 'w').write(body)
    return path, len(ep['panels']), len(ep['pages'])
