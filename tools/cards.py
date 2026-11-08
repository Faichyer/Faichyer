"""Cyberpunk GitHub cards for the profile README (cybercore-style magenta + green: clipped corners, scanlines, glitch).

    python tools/cards.py --user Faichyer --out dist              # stats, contrib, vitals (needs GITHUB_TOKEN)
    python tools/cards.py --static assets                        # neural map, ID card, quests, timeline (no token)

Standard library only. Fonts (Rajdhani, JetBrains Mono, SIL OFL) are subset from Google Fonts and embedded,
because GitHub shows README SVGs as images, which cannot load anything external.
"""
import argparse, base64, datetime as dt, json, os, re, sys, urllib.parse, urllib.request
from pathlib import Path

# cybercore-css palette: magenta main, neon green secondary, void backgrounds
MAG, MAG_D, MAG_DD = "#ff2a6d", "#5e1033", "#1c0d18"
GRN, GRN_D = "#05ffa1", "#015331"
BG, PANEL, TEXT, DIM = "#0d0e14", "#12141d", "#f0f1f5", "#939ab0"
HEAT = ["#181a25", "#4a1030", "#8a1745", "#c81e5a", "#ff2a6d"]
W = 900
CUT = 22

DISPLAY = "Rajdhani,Bahnschrift,'Arial Narrow',sans-serif"
MONO = "'JetBrains Mono',Consolas,Menlo,monospace"
CHARS = "".join(chr(c) for c in range(32, 127)) + "·—■◀▶→“”"


# ----------------------------------------------------------------------------------------------- fonts
def _get(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def font_css():
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
    out = []
    for fam, spec in [("Rajdhani", "Rajdhani:wght@600;700"), ("JetBrains Mono", "JetBrains+Mono:wght@500")]:
        try:
            css = _get(f"https://fonts.googleapis.com/css2?family={spec}&text={urllib.parse.quote(CHARS)}", ua).decode()
            for weight, url in re.findall(r"font-weight:\s*(\d+);.*?src:\s*url\((.*?)\)", css, re.S):
                b64 = base64.b64encode(_get(url, ua)).decode()
                out.append(f"@font-face{{font-family:'{fam}';font-weight:{weight};src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
        except Exception as e:  # fall back to system fonts
            print(f"font {fam}: {e}", file=sys.stderr)
    return "".join(out)


# ----------------------------------------------------------------------------------------------- data
def gql(query, token):
    body = json.dumps({"query": query}).encode()
    res = json.loads(_get("https://api.github.com/graphql", {"Authorization": f"bearer {token}",
                                                             "Content-Type": "application/json",
                                                             "User-Agent": "profile-cards"}, body))
    if res.get("errors"):
        raise SystemExit(f"GraphQL: {res['errors']}")
    return res["data"]


def fetch(user, token):
    d = gql(f"""{{ user(login:"{user}") {{ createdAt followers {{ totalCount }}
      repositories(ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC) {{ totalCount }}
      contributionsCollection {{ contributionYears contributionCalendar {{ totalContributions
        weeks {{ contributionDays {{ date contributionCount weekday }} }} }} }} }} }}""", token)["user"]
    years = d["contributionsCollection"]["contributionYears"]
    parts = " ".join(f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y}-12-31T23:59:59Z")'
                     f"{{ contributionCalendar {{ totalContributions }} }}" for y in years)
    per_year = gql(f'{{ user(login:"{user}") {{ {parts} }} }}', token)["user"]
    d["allTime"] = sum(v["contributionCalendar"]["totalContributions"] for v in per_year.values())
    return d


def summarize(d):
    cal = d["contributionsCollection"]["contributionCalendar"]
    days = [x for w in cal["weeks"] for x in w["contributionDays"]]
    counts = [x["contributionCount"] for x in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    i = len(counts) - 1
    if counts[i] == 0:  # today not done yet: the streak still counts from yesterday
        i -= 1
    current = 0
    while i >= 0 and counts[i]:
        current += 1
        i -= 1
    peak = max(days, key=lambda x: x["contributionCount"])
    since = int(d["createdAt"][:4])
    return {
        "year": cal["totalContributions"], "all": d["allTime"], "current": current, "longest": longest,
        "active": sum(1 for c in counts if c), "years": dt.date.today().year - since, "since": since,
        "repos": d["repositories"]["totalCount"], "followers": d["followers"]["totalCount"],
        "peak": peak["contributionCount"], "peak_date": peak["date"], "weeks": cal["weeks"],
    }


# ----------------------------------------------------------------------------------------------- svg kit
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def clipped(x, y, w, h, c=CUT):
    return f"{x},{y} {x + w - c},{y} {x + w},{y + c} {x + w},{y + h} {x + c},{y + h} {x},{y + h - c}"


def card(h, tag, right, body, extra_css="", label="", w=W, barcode=True):
    ul = min(120, w // 4)
    css = f"""
    .mono{{font-family:{MONO};font-weight:500}} .disp{{font-family:{DISPLAY};font-weight:700}}
    .tag{{font-size:12px;letter-spacing:3px;fill:{MAG}}} .lab{{font-size:11px;letter-spacing:2px;fill:{DIM}}}
    .dot{{animation:dot 1.4s steps(1) infinite}} @keyframes dot{{50%{{opacity:.15}}}}
    .sweep{{animation:sweep 5s linear infinite}} @keyframes sweep{{from{{transform:translateX(-160px)}}to{{transform:translateX({w + 160}px)}}}}
    .flick{{animation:flick 7s infinite}} @keyframes flick{{0%,93%,100%{{opacity:1}}94%{{opacity:.4}}95%{{opacity:1}}96%{{opacity:.6}}}}
    {extra_css}"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(label)}">
  <defs>
    <style>{FONTS}{css}</style>
    <clipPath id="shape"><polygon points="{clipped(0, 0, w, h)}"/></clipPath>
    <linearGradient id="bgg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PANEL}"/><stop offset="1" stop-color="{BG}"/></linearGradient>
    <linearGradient id="sw" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{MAG}" stop-opacity="0"/><stop offset=".8" stop-color="{MAG}" stop-opacity=".10"/><stop offset="1" stop-color="{MAG}" stop-opacity=".35"/></linearGradient>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".28"/></pattern>
    <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="{MAG}" stroke-opacity=".05"/></pattern>
  </defs>
  <g clip-path="url(#shape)">
    <rect width="{w}" height="{h}" fill="url(#bgg)"/><rect width="{w}" height="{h}" fill="url(#grid)"/>
    <rect x="0" y="0" width="{w}" height="44" fill="{MAG_DD}"/>
    <rect x="0" y="44" width="{w}" height="1" fill="{MAG}" opacity=".5"/><rect x="24" y="43" width="{ul}" height="3" fill="{MAG}"/><rect x="{ul + 28}" y="43" width="18" height="3" fill="{GRN}"/>
    <text class="mono tag" x="24" y="28">◢ {esc(tag)}</text>
    <text class="mono lab" x="{w - 48}" y="28" text-anchor="end">{esc(right)}</text>
    <circle class="dot" cx="{w - 34}" cy="24" r="4" fill="{GRN}"/>
    {body}
    <rect class="sweep" x="0" y="45" width="160" height="{h - 45}" fill="url(#sw)"/>
    <rect width="{w}" height="{h}" fill="url(#scan)"/>
  </g>
  <polygon points="{clipped(1, 1, w - 2, h - 2, CUT - 1)}" fill="none" stroke="{MAG}" stroke-opacity=".75" stroke-width="1.5"/>
  <path d="M{w - 26} {h - 8}h18v-18" fill="none" stroke="{GRN}" stroke-width="3"/>
  <g fill="{GRN}" opacity=".7">{''.join(f'<rect x="{w - 140 + i * 6}" y="{h - 14}" width="{(i * 7) % 3 + 1}" height="6"/>' for i in range(14)) if barcode else ''}</g>
</svg>
"""


def num(n):
    return f"{n:,}"


# ----------------------------------------------------------------------------------------------- cards
def stats_card(s, user):
    h = 250
    big = num(s["year"])
    cells = [("CURRENT STREAK", f"{s['current']}", "DAYS"), ("LONGEST STREAK", f"{s['longest']}", "DAYS"),
             ("ACTIVE DAYS", f"{s['active']}", "/ 365"), ("YEARS ONLINE", f"{s['years']}", f"SINCE {s['since']}"),
             ("PUBLIC REPOS", f"{s['repos']}", ""), ("FOLLOWERS", f"{s['followers']}", "")]
    out = []
    for i, (lab, val, unit) in enumerate(cells):
        x, y = 370 + (i % 3) * 172, 66 + (i // 3) * 86
        live = ' class="live"' if i == 0 and s["current"] else ""
        out.append(f"""<g transform="translate({x} {y})">
      <polygon points="{clipped(0, 0, 160, 74, 12)}" fill="{MAG_DD}" stroke="{MAG_D}"/>
      <rect x="0" y="12" width="3" height="50" fill="{GRN if i == 0 else MAG}"{live}/>
      <text class="mono lab" x="14" y="22">{lab}</text>
      <text class="disp" x="14" y="60" font-size="36" fill="{TEXT}">{val}<tspan class="mono" font-size="12" fill="{DIM}" dx="6">{unit}</tspan></text>
    </g>""")
    body = f"""
    <text class="mono lab" x="24" y="80">CONTRIBUTIONS // LAST 365 DAYS</text>
    <g class="g1"><text class="disp" x="20" y="166" font-size="104" fill="{MAG}">{big}</text></g>
    <g class="g2"><text class="disp" x="20" y="166" font-size="104" fill="{GRN}" opacity=".7">{big}</text></g>
    <text class="disp flick" x="20" y="166" font-size="104" fill="{TEXT}">{big}</text>
    <text class="mono lab" x="24" y="198">ALL TIME <tspan fill="{TEXT}">{num(s['all'])}</tspan> · PEAK <tspan fill="{TEXT}">{s['peak']}</tspan> ON {s['peak_date']}</text>
    <rect x="24" y="214" width="{min(300, 300 * s['active'] / 365):.0f}" height="4" fill="{GRN}"/><rect x="24" y="214" width="300" height="4" fill="{GRN}" opacity=".15"/>
    {''.join(out)}"""
    css = """.g1{animation:g1 6s infinite}.g2{animation:g2 6s infinite}
    @keyframes g1{0%,90%,100%{transform:translate(0,0)}91%{transform:translate(-5px,2px)}93%{transform:translate(4px,-1px)}95%{transform:translate(-2px,0)}}
    @keyframes g2{0%,90%,100%{transform:translate(0,0)}91%{transform:translate(5px,-2px)}93%{transform:translate(-4px,1px)}95%{transform:translate(2px,0)}}
    .live{animation:live 1.6s ease-in-out infinite alternate}@keyframes live{from{opacity:.3}to{opacity:1}}"""
    return card(h, "SYS.STATS // RUNNER PROFILE", f"{user.upper()} · LINK STABLE", body, css,
                f"{user}: {s['year']} contributions in the last year, current streak {s['current']} days, "
                f"longest {s['longest']} days")


def contrib_card(s, user):
    h, x0, y0, p, c = 226, 64, 84, 15, 12
    weeks = s["weeks"]
    nz = sorted(x["contributionCount"] for w in weeks for x in w["contributionDays"] if x["contributionCount"])
    q = [nz[int(len(nz) * f)] for f in (.25, .5, .75)] if nz else [1, 2, 3]

    def lvl(n):
        return 0 if n == 0 else 1 + sum(n > t for t in q)

    peak_ring = f' stroke="{GRN}" stroke-width="2"'
    cols, months, last = [], [], None
    for i, w in enumerate(weeks):
        cells = "".join(
            f'<rect x="0" y="{x["weekday"] * p}" width="{c}" height="{c}" fill="{HEAT[lvl(x["contributionCount"])]}"'
            f'{peak_ring if x["date"] == s["peak_date"] else ""}>'
            f'<title>{x["date"]}: {x["contributionCount"]}</title></rect>'
            for x in w["contributionDays"])
        cols.append(f'<g class="col" transform="translate({x0 + i * p} {y0})" style="animation-delay:{i * .018:.3f}s">{cells}</g>')
        m = w["contributionDays"][0]["date"][5:7]
        if m != last and i < len(weeks) - 2:
            months.append(f'<text class="mono lab" x="{x0 + i * p}" y="{y0 - 10}">'
                          f'{dt.date(2000, int(m), 1).strftime("%b").upper()}</text>')
            last = m
    days = "".join(f'<text class="mono lab" x="{x0 - 10}" y="{y0 + d * p + 10}" text-anchor="end">{n}</text>'
                   for d, n in [(1, "MON"), (3, "WED"), (5, "FRI")])
    legend = "".join(f'<rect x="{W - 150 + k * 16}" y="{h - 30}" width="12" height="12" fill="{col}"/>'
                     for k, col in enumerate(HEAT))
    body = f"""{''.join(months)}{days}{''.join(cols)}
    <text class="mono lab" x="{x0}" y="{h - 20}"><tspan fill="{TEXT}">{num(s['year'])}</tspan> CONTRIBUTIONS IN THE LAST YEAR · <tspan fill="{GRN}">■</tspan> PEAK DAY</text>
    <text class="mono lab" x="{W - 160}" y="{h - 20}" text-anchor="end">LOW</text>{legend}
    <text class="mono lab" x="{W - 64}" y="{h - 20}">HIGH</text>"""
    css = ".col{animation:in .4s ease-out backwards}@keyframes in{from{opacity:0}to{opacity:1}}"
    return card(h, "NET.ACTIVITY // CONTRIBUTION GRID", f"{user.upper()} · {weeks[-1]['contributionDays'][-1]['date']}",
                body, css, f"{user}: contribution grid, {s['year']} contributions in the last year")


def wrap(text, size, width):
    """Greedy word wrap using Rajdhani's average glyph width (~0.43em)."""
    per = max(8, int(width / (size * .43)))
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > per:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + [cur]


def rich(s):
    """*word* renders in magenta (no italic face is embedded)."""
    parts = esc(s).split("*")
    return "".join(f'<tspan fill="{MAG}">{p}</tspan>' if i % 2 else p for i, p in enumerate(parts))


# ----------------------------------------------------------------------------------------------- one-off layouts
# Each block below has its own composition (picked from the Claude Design proposals); they only share the
# clipped outline, the scanlines and the palette, so the README no longer reads as a stack of identical panels.
INK_SOFT, MAG_MID = "#d1d4de", "#c81e5a"


def shell(w, h, body, extra_css="", label="", cut=CUT, defs="", fill=BG):
    css = f"""
    .mono{{font-family:{MONO};font-weight:500}} .disp{{font-family:{DISPLAY};font-weight:700}} .semi{{font-family:{DISPLAY};font-weight:600}}
    .blink{{animation:blink 1.4s steps(1) infinite}} @keyframes blink{{50%{{opacity:.2}}}}
    {extra_css}"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(label)}">
  <defs>
    <style>{FONTS}{css}</style>
    <clipPath id="shape"><polygon points="{clipped(0, 0, w, h, cut)}"/></clipPath>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".22"/></pattern>
    {defs}
  </defs>
  <g clip-path="url(#shape)">
    <rect width="{w}" height="{h}" fill="{fill}"/>
    {body}
    <rect width="{w}" height="{h}" fill="url(#scan)"/>
  </g>
  <polygon points="{clipped(.75, .75, w - 1.5, h - 1.5, cut - .5)}" fill="none" stroke="{MAG}" stroke-opacity=".7" stroke-width="1.5"/>
</svg>
"""


def mono(x, y, s, size=10, fill=DIM, ls=2, anchor="start", cls="mono"):
    a = "" if anchor == "start" else f' text-anchor="{anchor}"'
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{size}" letter-spacing="{ls}" fill="{fill}"{a}>{s}</text>'


def mono_w(s, size, ls):
    """JetBrains Mono advance is 0.6em, plus letter-spacing after every glyph."""
    return len(s) * (size * .6 + ls)


# ------------------------------------------------------------------ vitals monitor (live, replaces the snake)
def vitals_card(s):
    w, h, lw, base, x0, x1 = W, 240, 660, 176, 24, 636
    weeks = s["weeks"]
    tot = [sum(x["contributionCount"] for x in wk["contributionDays"]) for wk in weeks]
    peak_i = max(range(len(tot)), key=tot.__getitem__)
    k = 116 / (tot[peak_i] ** .5 or 1)
    step = (x1 - x0) / len(tot)
    pts, length, prev = [(x0, base)], 0.0, (x0, base)
    for i, n in enumerate(tot):
        x, amp = x0 + i * step, n ** .5 * k
        pts += [(x + step * .3, base), (x + step * .5, base - amp), (x + step * .65, base + amp * .25), (x + step * .8, base)]
    pts.append((x1, base))
    for p in pts[1:]:
        length += ((p[0] - prev[0]) ** 2 + (p[1] - prev[1]) ** 2) ** .5
        prev = p
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    L = int(length) + 10
    px, py = x0 + peak_i * step + step * .5, base - tot[peak_i] ** .5 * k
    when = dt.date.fromisoformat(weeks[peak_i]["contributionDays"][0]["date"]).strftime("%b %d").upper()
    peak_lab = f"{tot[peak_i]} · WEEK OF {when}"
    if px + 12 + mono_w("◀ " + peak_lab, 10, 1.5) < lw - 12:
        peak = mono(px + 12, py + 4, "◀ " + peak_lab, 10, GRN, 1.5)
    else:
        peak = mono(px - 12, py + 4, peak_lab + " ▶", 10, GRN, 1.5, "end")

    marks = []
    for j, i in enumerate(round(f * (len(weeks) - 1)) for f in (0, .25, .5, .75, 1)):
        d = dt.date.fromisoformat(weeks[i]["contributionDays"][0]["date"])
        lab = d.strftime("%b").upper() + (d.strftime(" %y") if j in (0, 4) else "")
        marks.append(mono(x0 + i * step if j < 4 else x1, h - 18, lab, 10, DIM, 1.5,
                          "start" if j == 0 else "end" if j == 4 else "middle"))

    avg = round(s["year"] / len(weeks))
    live = s["current"] > 0
    rx = lw + 24
    body = f"""
    <rect width="{lw}" height="{h}" fill="url(#vgrid)"/>
    {mono(24, 30, f"VITALS · CONTRIBUTIONS PER WEEK · {len(weeks)} WEEKS", 11, MAG, 3)}
    <line x1="{x0}" y1="{base}" x2="{x1}" y2="{base}" stroke="{MAG_D}"/>
    <polyline points="{poly}" fill="none" stroke="{MAG}" stroke-width="5" stroke-opacity=".25" stroke-linejoin="round"/>
    <polyline class="trace" points="{poly}" fill="none" stroke="{MAG}" stroke-width="2" stroke-linejoin="round" stroke-dasharray="{L}"/>
    <circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="none" stroke="{GRN}" stroke-width="2"/>
    {peak}{''.join(marks)}
    <rect x="{lw}" width="{w - lw}" height="{h}" fill="{PANEL}"/><rect x="{lw}" width="1" height="{h}" fill="{MAG_D}"/>
    <rect class="beat" x="{rx}" y="22" width="8" height="8" fill="{GRN if live else MAG}"/>
    {mono(rx + 16, 30, "SIGNAL STABLE" if live else "FLATLINE", 11, GRN if live else MAG, 2)}
    {mono(rx, 96, "AVG / WEEK", 10, DIM, 2)}
    <text class="disp" x="{rx}" y="148" font-size="56" fill="{TEXT}">{avg}<tspan font-size="18" fill="{MAG}"> CPW</tspan></text>
    {mono(rx, 190, "STREAK", 10, DIM, 1.5)}{mono(rx + 101, 190, "ACTIVE", 10, DIM, 1.5)}
    <text class="disp" x="{rx}" y="216" font-size="24" fill="{TEXT}">{s['current']} D</text>
    <text class="disp" x="{rx + 101}" y="216" font-size="24" fill="{TEXT}">{s['active']} D</text>"""
    defs = (f'<pattern id="vgrid" width="24" height="24" patternUnits="userSpaceOnUse">'
            f'<path d="M24 0H0V24" fill="none" stroke="{MAG}" stroke-opacity=".08"/></pattern>')
    css = (f".trace{{animation:draw 7s linear infinite}}"
           f"@keyframes draw{{0%{{stroke-dashoffset:{L}}}75%,100%{{stroke-dashoffset:0}}}}"
           f".beat{{animation:beat .9s ease-in-out infinite}}@keyframes beat{{50%{{opacity:.25}}}}")
    return shell(w, h, body, css, f"Vitals: {s['year']} contributions in {len(weeks)} weeks, about {avg} a week, "
                 f"peak {peak_lab.lower()}", defs=defs)


# ------------------------------------------------------------------ neural map (stack)
NEURAL = [  # name, tag, x, y (left hemisphere = web, right = mobile, data, AI; the last two hang under the core)
    ("TYPESCRIPT", "LANG", 56, 60), ("REACT", "UI", 36, 130), ("NEXT.JS", "FRAME", 36, 200), ("TAILWIND", "STYLE", 56, 270),
    ("FLUTTER", "UI", 688, 60), ("DART", "LANG", 708, 130), ("SUPABASE", "DATA", 708, 200), ("FIREBASE", "DATA", 688, 270),
    ("NODE.JS", "RUNTIME", 230, 280), ("AI AGENTS", "AUG", 514, 280),
]


def neural_card():
    w, h, nw, nh = W, 340, 156, 34
    core = (370, 140, 160, 70)
    cx, cy = 450, 175
    links, nodes = [], []
    for name, tag, x, y in NEURAL:
        ai = name == "AI AGENTS"
        col = GRN if ai else MAG
        if y > 260 and 200 < x < 600:  # under the core: rise from the top of the node
            ax = x + nw / 2
            ex = cx - 40 if ax < cx else cx + 40
            d = f"M{ax:.0f},{y} V245 H{ex} V{core[1] + core[3]}"
        else:
            left = x < cx
            ax, ay = (x + nw if left else x), y + nh / 2
            ex, ey = (core[0] if left else core[0] + core[2]), cy + (ay - cy) * .16
            mx = (ax + ex) / 2
            d = f"M{ax},{ay:.0f} H{mx:.0f} V{ey:.0f} H{ex}"
        links.append(f'<path class="flow" d="{d}" fill="none" stroke="{col}" stroke-width="1.5" stroke-dasharray="4 8"/>')
        nodes.append(f'<g transform="translate({x} {y})"><polygon points="{clipped(0, 0, nw, nh, 8)}" fill="{PANEL}" stroke="{GRN if ai else MAG_D}"/>'
                     f'<rect x="10" y="14" width="6" height="6" fill="{col}"/>'
                     f'<text class="disp" x="24" y="23" font-size="17" fill="{TEXT}">{esc(name)}</text>'
                     f'{mono(nw - 10, 21, tag, 9, DIM, 1.5, "end")}</g>')
    x, y, cw, ch = core
    body = f"""
    <rect width="{w}" height="{h}" fill="url(#dots)"/>
    {mono(24, 30, "NEURAL MAP · INSTALLED AUGMENTS", 11, MAG, 3)}
    {mono(w - 24, 30, f"{len(NEURAL)} LINKS · 0 REJECTIONS", 10, DIM, 2, "end")}
    {''.join(links)}
    <polygon class="pulse" points="{clipped(x, y, cw, ch, 14)}" fill="none" stroke="{MAG}" stroke-width="2"/>
    <polygon points="{clipped(x, y, cw, ch, 14)}" fill="{MAG_DD}" stroke="{MAG}" stroke-width="2"/>
    <text class="disp" x="{cx}" y="{cy + 4}" font-size="28" fill="{TEXT}" text-anchor="middle">MY STACKS</text>
    {mono(cx, cy + 22, f"{len(NEURAL)} AUGMENTS", 9, GRN, 2, "middle")}
    {''.join(nodes)}
    {mono(24, h - 14, "LEFT HEMISPHERE · WEB", 9, DIM, 2)}
    {mono(w - 24, h - 14, "RIGHT HEMISPHERE · MOBILE + DATA + AI", 9, DIM, 2, "end")}"""
    defs = (f'<pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse">'
            f'<circle cx="9" cy="9" r="1" fill="{MAG}" fill-opacity=".14"/></pattern>')
    css = (".flow{animation:flow 1.2s linear infinite}@keyframes flow{to{stroke-dashoffset:-24}}"
           ".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2.4s ease-out infinite}"
           "@keyframes pulse{from{transform:scale(1);opacity:.7}to{transform:scale(1.18,1.35);opacity:0}}")
    return shell(w, h, body, css, "My stacks: TypeScript, React, Next.js, Tailwind, Node.js, Flutter, Dart, Supabase, Firebase, AI agents",
                 defs=defs)


# ------------------------------------------------------------------ runner ID card (character sheet)
ID_FIELDS = [  # label, value, column (0, 1, or None for full width)
    ("CLASS", "Developer: web, mobile, AI", 0),
    ("LEVEL", "10+ years. Spawned 2016 with Pong in C#, never logged off", 1),
    ("MAIN BUILD", "Next.js · Flutter · Supabase", 0),
    ("COMPANION", "Capri, a construct who teleports around my screen and reports on my agents", 1),
    ("SPECIAL MOVE", "Building interesting, amazing and *very* silly projects", None),
]
MRZ = ["P<NCTFAICHYER<<MIKI<NAMSRAI<<<<<<<<<<<<<<<<<<<", "DEV2016<0WEB<MOBILE<AI<<CAPRI<*NEVERLOGGEDOFF*<<"]


def id_card(level=10):
    w, h, cut = W, 400, 28
    px, py = 28, 62                     # portrait
    fx, fw, gap = 206, 528, 28          # field area
    colw = (fw - gap) / 2
    size, lh = 17, 21

    fields, y = [], 124
    i = 0
    while i < len(ID_FIELDS):
        row = [ID_FIELDS[i]] if ID_FIELDS[i][2] is None else ID_FIELDS[i:i + 2]
        tallest = 0
        for lab, val, col in row:
            fx0 = fx if not col else fx + colw + gap
            width = fw if col is None else colw
            lines = wrap(val, size, width - 12)
            fh = 14 + lh * len(lines)
            tallest = max(tallest, fh)
            txt = "".join(f'<tspan x="{fx0 + 12:.0f}" y="{y + 14 + 16 + k * lh}">{rich(l)}</tspan>' for k, l in enumerate(lines))
            fields.append(f'<rect x="{fx0:.0f}" y="{y}" width="2" height="{fh + 2}" fill="{GRN if lab == "SPECIAL MOVE" else MAG_D}"/>'
                          f'{mono(fx0 + 12, y + 9, lab, 9, DIM, 2)}'
                          f'<text class="semi" font-size="{size}" fill="{TEXT}">{txt}</text>')
        y += tallest + 14
        i += len(row)

    bars = "".join(f'<rect x="{px + k * 8}" y="{py + 190}" width="2" height="22"/><rect x="{px + k * 8 + 4}" y="{py + 190}" width="1" height="22"/>'
                   for k in range(19))
    photo = Path(__file__).with_name("portrait.jpg")
    if photo.exists():
        b64 = base64.b64encode(photo.read_bytes()).decode()
        silhouette = (f'<image x="{px}" y="{py}" width="150" height="180" preserveAspectRatio="xMidYMid slice" '
                      f'href="data:image/jpeg;base64,{b64}"/>'
                      f'<rect x="{px}" y="{py}" width="150" height="180" fill="url(#scan)"/>')
    else:
        silhouette = (f'<g fill="{MAG_D}" opacity=".9"><circle cx="{px + 75}" cy="{py + 74}" r="30"/>'
                      f'<path d="M{px + 20} {py + 180} C{px + 20} {py + 128} {px + 46} {py + 112} {px + 75} {py + 112} '
                      f'C{px + 104} {py + 112} {px + 130} {py + 128} {px + 130} {py + 180}Z"/></g>')
    mrz = "".join(f'<text class="mono" x="28" y="{h - 41 + k * 20}" font-size="15" letter-spacing="3.2" fill="{INK_SOFT}">{rich(l)}</text>'
                  for k, l in enumerate(MRZ))
    scx, scy = w - 28 - 48, py + 48
    body = f"""
    <rect width="{w}" height="{h}" fill="url(#idbg)"/>
    <g class="holo" opacity=".85"><rect x="-240" width="{w + 240}" height="6" fill="url(#holo)"/></g>
    <text class="disp" x="28" y="40" font-size="18" letter-spacing="4" fill="{MAG}">NIGHT CITY · RUNNER IDENTIFICATION</text>
    <text class="mono" x="{w - 28}" y="38" font-size="10" letter-spacing="2" fill="{DIM}" text-anchor="end">DOC NO. <tspan fill="{TEXT}">NC-2016-0001</tspan></text>
    <g clip-path="url(#portrait)"><rect x="{px}" y="{py}" width="150" height="180" fill="url(#hatch)"/>{silhouette}
      <rect class="scanline" x="{px}" y="{py}" width="150" height="2" fill="{GRN}" opacity=".7"/></g>
    <rect x="{px + .5}" y="{py + .5}" width="149" height="179" fill="none" stroke="{MAG_D}"/>
    <g fill="{TEXT}" opacity=".8">{bars}</g>
    {mono(fx, 70, "SURNAME / GIVEN NAMES · HANDLE", 9, DIM, 2)}
    <text class="disp" x="{fx}" y="108" font-size="40" fill="{TEXT}">NAMSRAI, MIKI <tspan fill="{MAG}">“FAICHYER”</tspan></text>
    {''.join(fields)}
    <g transform="rotate(-12 {scx} {scy})" opacity=".9">
      <circle cx="{scx}" cy="{scy}" r="47" fill="none" stroke="{GRN}" stroke-width="2"/>
      <circle cx="{scx}" cy="{scy}" r="41" fill="none" stroke="{GRN}" stroke-opacity=".4"/>
      {mono(scx, scy - 15, "CLEARANCE", 8, GRN, 1.5, "middle")}
      <text class="disp" x="{scx}" y="{scy + 9}" font-size="26" fill="{GRN}" text-anchor="middle">LVL {level}</text>
      {mono(scx, scy + 24, "VERIFIED", 8, GRN, 1.5, "middle")}
    </g>
    <rect y="{h - 66}" width="{w}" height="66" fill="#0a0b10"/>
    <line x1="0" y1="{h - 65.5}" x2="{w}" y2="{h - 65.5}" stroke="{MAG_D}" stroke-dasharray="4 3"/>
    {mrz}"""
    defs = (f'<linearGradient id="idbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PANEL}"/><stop offset=".7" stop-color="{BG}"/></linearGradient>'
            f'<pattern id="holo" width="240" height="6" patternUnits="userSpaceOnUse"><rect width="60" height="6" fill="{MAG}"/>'
            f'<rect x="60" width="20" height="6" fill="{GRN}"/><rect x="80" width="60" height="6" fill="{MAG_MID}"/><rect x="140" width="100" height="6" fill="{MAG}"/></pattern>'
            f'<pattern id="hatch" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<rect width="12" height="12" fill="{PANEL}"/><rect width="6" height="12" fill="{MAG_DD}"/></pattern>'
            f'<pattern id="scan" width="4" height="3" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000" opacity=".28"/></pattern>'
            f'<clipPath id="portrait"><rect x="{px}" y="{py}" width="150" height="180"/></clipPath>')
    css = (".holo{animation:holo 6s linear infinite}@keyframes holo{to{transform:translateX(240px)}}"
           ".scanline{animation:scanline 3s linear infinite}@keyframes scanline{to{transform:translateY(178px)}}")
    return shell(w, h, body, css, "Runner ID: Namsrai, Miki “Faichyer”. " + " ".join(f"{l.title()}: {v.replace('*', '')}." for l, v, _ in ID_FIELDS),
                 cut=cut, defs=defs)


# ------------------------------------------------------------------ quest tracker (active gigs)
QUESTS = [
    ("GIG.01", "NOMYN", "Build the study companion every student wishes they had.",
     ["Scan notes with OCR + AI", "Turn them into spaced-repetition flashcards", "Plan the study sessions"],
     ["NEXT.JS", "SUPABASE", "FLUTTER"]),
    ("GIG.02", "YALNA", "Make keeping a trading journal feel like a game.",
     ["Journal every trade", "Track watchlists", "Backtest setups", "Level up with the progression system"],
     ["NEXT.JS", "REACT 19", "TAILWIND"]),
]


def quest_card():
    w, top, colw, cgap = W, 54, 406, 40
    tx = 34                                    # text column offset inside a quest
    goal_lines = [wrap(q[2], 15, colw - tx) for q in QUESTS]
    obj_top = [top + 52 + 20 * len(g) + 14 for g in goal_lines]
    gear_y = max(t + 25 * len(q[3]) for t, q in zip(obj_top, QUESTS)) + 10
    h = gear_y + 64

    cols = []
    for c, ((gig, name, goal, objs, gear), lines, oy) in enumerate(zip(QUESTS, goal_lines, obj_top)):
        x0 = 24 + c * (colw + cgap)
        tx0 = x0 + tx
        goal_t = "".join(f'<tspan x="{tx0}" y="{top + 72 + k * 20}">{esc(l)}</tspan>' for k, l in enumerate(lines))
        objs_t = "".join(f'<rect x="{tx0 + .5}" y="{oy + k * 25 + .5}" width="9" height="9" fill="none" stroke="{MAG}"/>'
                         f'<text class="semi" x="{tx0 + 20}" y="{oy + k * 25 + 10}" font-size="15" fill="{TEXT}">{esc(o)}</text>'
                         for k, o in enumerate(objs))
        gx = tx0 + mono_w("REQUIRED GEAR", 9, 2) + 8
        chips_t = []
        for g in gear:
            cw = mono_w(g, 10, 1.5) + 12.5
            chips_t.append(f'<polygon points="{clipped(gx, gear_y - 13, cw, 18, 5)}" fill="{MAG}"/>'
                           f'{mono(gx + 7, gear_y, g, 10, BG, 1.5)}')
            gx += cw + 8
        mx, my = x0 + 9, top + 17
        cols.append(f"""
    <g transform="rotate(45 {mx} {my})"><rect x="{mx - 7}" y="{my - 7}" width="14" height="14" fill="{MAG}"/>
      <rect class="ping" x="{mx - 7}" y="{my - 7}" width="14" height="14" fill="none" stroke="{MAG}"/></g>
    <rect x="{mx - .5}" y="{my + 17}" width="1" height="{gear_y - my - 17}" fill="url(#stem)"/>
    {mono(tx0, top + 9, f"MAIN JOB · {gig}", 9, GRN, 2)}
    <text class="disp" x="{tx0}" y="{top + 44}" font-size="34" fill="{TEXT}">{name}</text>
    <text class="semi" font-size="15" fill="{INK_SOFT}">{goal_t}</text>
    {objs_t}
    {mono(tx0, gear_y - 1, "REQUIRED GEAR", 9, DIM, 2)}{''.join(chips_t)}""")

    foot = ["[J] OPEN JOURNAL", "[M] MAP", "[T] TRACK JOB", "REWARD · STREET CRED"]
    free = (w - 48 - sum(mono_w(f, 9, 2) - 2 for f in foot)) / (len(foot) - 1)
    fx, feet = 24, []
    for k, f in enumerate(foot):
        feet.append(mono(fx, h - 18, esc(f), 9, MAG if k == len(foot) - 1 else DIM, 2))
        fx += mono_w(f, 9, 2) - 2 + free
    jw = mono_w("JOURNAL", 11, 3)
    body = f"""
    <rect width="{w}" height="{h}" fill="url(#qbg)"/>
    {mono(24, 32, "JOURNAL", 11, MAG, 3)}<rect x="{24 + jw + 7}" y="27.5" width="40" height="1" fill="{MAG}"/>
    {mono(24 + jw + 57, 32, "2 ACTIVE JOBS", 11, TEXT, 3)}
    {mono(w - 40, 31, "TRACKING", 10, DIM, 2, "end")}<rect class="blink" x="{w - 33}" y="23" width="8" height="8" fill="{GRN}"/>
    {''.join(cols)}
    <rect x="24" y="{h - 38}" width="{w - 48}" height="1" fill="{MAG}" opacity=".15"/>
    {''.join(feet)}"""
    defs = (f'<linearGradient id="qbg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{BG}"/><stop offset="1" stop-color="{PANEL}"/></linearGradient>'
            f'<linearGradient id="stem" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{MAG}"/><stop offset="1" stop-color="{MAG}" stop-opacity="0"/></linearGradient>')
    css = (".ping{transform-box:fill-box;transform-origin:center;animation:ping 2s ease-out infinite}"
           "@keyframes ping{from{transform:scale(1);opacity:.8}to{transform:scale(2.4);opacity:0}}")
    return shell(w, h, body, css, "Active jobs. " + " ".join(
        f"{n.title()}: {g} {'; '.join(o)}. Built with {', '.join(t)}." for _, n, g, o, t in QUESTS), defs=defs)


# ------------------------------------------------------------------ archive timeline
TIMELINE = [  # repo, language, position on the axis (year + fraction), above or below the axis
    ("Pong-en-C-Sharp", "C#", 2016.1, "up"), ("Melyr", "DART", 2020.2, "up"),
    ("spotify-react", "TYPESCRIPT", 2020.6, "down"), ("Motdle", "TYPESCRIPT", 2023, "up"),
]


def timeline_card():
    w, h, x0, x1, axis = W, 220, 40, 860, 118
    y0, y1 = 2016, 2023

    def xof(y):
        return x0 + (y - y0) / (y1 - y0) * (x1 - x0)

    ticks = "".join(f'<rect x="{x0 + k * 25.5:.1f}" y="{axis - 6}" width="1" height="14" fill="{MAG_D}"/>'
                    for k in range(int((x1 - x0) / 25.5) + 1))
    years = "".join(mono(xof(y), axis + 23, str(y), 9, TEXT if y in (y0, 2020, y1) else DIM, 1, "middle")
                    for y in range(y0, y1 + 1))
    items = []
    for name, lang, when, side in TIMELINE:
        x = xof(when)
        right = when > y1 - .5                     # last item hangs to the left of its stem
        sub = f"{lang} · {int(when)}"
        bw = max(len(name) * 9.6, mono_w(sub, 9, 1.5)) + 23
        bh = 46
        if side == "up":
            by, stem = axis - 22 - bh, (axis - 22, axis)
        else:
            by, stem = axis + 42, (axis + 2, axis + 42)
        bx = x - bw if right else x
        edge = bx + bw - 3 if right else bx
        tx, anchor = (bx + bw - 13, "end") if right else (bx + 13, "start")
        items.append(f'<rect x="{x - .5:.1f}" y="{stem[0]}" width="1" height="{stem[1] - stem[0]}" fill="{MAG}"/>'
                     f'<rect x="{bx:.1f}" y="{by}" width="{bw:.1f}" height="{bh}" fill="{PANEL}"/>'
                     f'<rect x="{edge:.1f}" y="{by}" width="3" height="{bh}" fill="{MAG}"/>'
                     f'<text class="disp" x="{tx:.1f}" y="{by + 24}" font-size="20" fill="{TEXT}" text-anchor="{anchor}">{esc(name)}</text>'
                     f'{mono(tx, by + 38, sub, 9, MAG, 1.5, anchor)}')
    lab = f"PLAYBACK {y0} → {y1}"
    body = f"""
    {mono(24, 30, "ARCHIVE · REWIND", 11, MAG, 3)}
    {mono(w - 24, 30, lab, 10, DIM, 2, "end")}
    {mono(w - 24 - mono_w(lab, 10, 2) - 8, 30, "◀◀", 10, GRN, 0, "end", "mono blink")}
    {ticks}<rect x="{x0}" y="{axis}" width="{x1 - x0}" height="2" fill="{MAG}"/>
    {years}
    <g class="rewind"><rect x="{x1 - 7}" y="{axis - 6}" width="14" height="14" fill="none" stroke="{GRN}" stroke-width="2"
       transform="rotate(45 {x1} {axis + 1})" opacity=".9"/></g>
    {''.join(items)}"""
    css = f".rewind{{animation:rewind 8s linear infinite}}@keyframes rewind{{to{{transform:translateX(-{x1 - x0}px)}}}}"
    return shell(w, h, body, css, "Archive timeline: " + ", ".join(f"{n} ({l.title()}, {int(y)})" for n, l, y, _ in TIMELINE))


def write_static(d):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    files = {"neural.svg": neural_card(), "id.svg": id_card(), "quests.svg": quest_card(), "timeline.svg": timeline_card()}
    for n, s in files.items():
        (d / n).write_text(s, encoding="utf-8")
    print("wrote", ", ".join(files))


# ----------------------------------------------------------------------------------------------- main
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user")
    ap.add_argument("--out")
    ap.add_argument("--static", help="write the static cards (neural, id, quests, timeline) to this folder")
    ap.add_argument("--data", help="read the GitHub data from this JSON instead of the API (preview)")
    a = ap.parse_args()
    FONTS = font_css()
    if a.static:
        write_static(a.static)
    if a.out:
        if a.data:
            d = json.loads(Path(a.data).read_text(encoding="utf-8"))
        else:
            token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN is not set")
            d = fetch(a.user, token)
        s = summarize(d)
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "stats.svg").write_text(stats_card(s, a.user), encoding="utf-8")
        (out / "contrib.svg").write_text(contrib_card(s, a.user), encoding="utf-8")
        (out / "vitals.svg").write_text(vitals_card(s), encoding="utf-8")
        print("wrote stats.svg, contrib.svg, vitals.svg in", out, {k: v for k, v in s.items() if k != "weeks"})
