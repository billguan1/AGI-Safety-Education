#!/usr/bin/env python3
"""Regenerate comics/story_review.md from the episode files.

Run from the comics/ directory. story_review.md is generated and must never
be edited by hand: it is the flat reading copy of every panel and every line,
used for story review and for checking the two halves of each episode file
(the paste-ready page prompts and the panel-by-panel reference) agree.
"""
import re, glob
def flat(t): return re.sub(r'\s+',' ',t).strip()
files=sorted(f for f in glob.glob('[0-2][0-9]-*.md') if not f.startswith('00-'))
out=["# CAPY — Story & Dialogue Review",
     "29 episodes. For each: setting, concept, and every character line in reading order.",
     "", "Generated from the episode files by tools/gen_story_review.py. Do not edit by hand.",
     "", "---", ""]
words={'ONE':'One','TWO':'Two','THREE':'Three','FOUR':'Four','FIVE':'Five'}
for f in files:
    s=open(f).read(); num=int(f[:2])
    title=re.search(r'^# Episode \d+: (.+)$', s, re.M).group(1)
    concept=re.search(r'\*\*Concept:\*\*(.*?)(?=\n\n)', s, re.S)
    reg=re.search(r'\*\*Register:\*\*(.*?)(?=\n\n)', s, re.S)
    body=s[s.index('## PAGE ONE'):]
    if '\n## Teaching note' in body: body=body[:body.index('\n## Teaching note')]
    out.append(f"## Episode {num}: {title}")
    first=re.search(r'^### PANEL 1\n(.*?)\n\n', body, re.S|re.M)
    if first: out.append(f"**Setting:** {flat(first.group(1))}")
    if concept: out.append(f"**Concept:** {flat(concept.group(1))}")
    if reg: out.append(f"**Register:** {flat(reg.group(1))}")
    out.append("")
    for chunk in re.split(r'\n(?=## PAGE |### PANEL )', body):
        m=re.match(r'## PAGE (\w+)', chunk)
        if m:
            out.append(f"**Page {words.get(m.group(1), m.group(1).title())}**"); out.append(""); continue
        m=re.match(r'### PANEL (\d+)\n', chunk)
        if not m: continue
        rest=chunk[m.end():]
        cut=rest.find('**GEMINI PROMPT:**')
        seg=rest[:cut] if cut>=0 else rest
        di=seg.find('> **')
        desc, dial = (seg[:di], seg[di:]) if di>=0 else (seg, '')
        out.append(f"*Panel {m.group(1)}. {flat(desc)}*")
        if dial:
            parts=re.split(r'\n(?=> \*\*)', dial.strip())
            for part in parts:
                sm=re.match(r'> \*\*(.+?):\*\*\s*(.*)', part, re.S)
                if sm: out.append(f"- **{sm.group(1)}:** {flat(sm.group(2).replace('> ',''))}")
        out.append("")
    out.append("---"); out.append("")
open('story_review.md','w').write("\n".join(out))
print("regenerated")
