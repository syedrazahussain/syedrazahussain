#!/usr/bin/env python3
"""Generates all profile cards (stats, languages, streak, trophies, activity, 3D contributions)
as self-contained SVG files using only the GitHub API. No third-party services needed.

Usage:  GH_TOKEN=... GH_USER=... python scripts/generate_cards.py
Test :  python scripts/generate_cards.py --mock
"""
import os, sys, json, math, random, datetime, urllib.request, urllib.error
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "assets", "generated"))
FONT = "Segoe UI, Helvetica, Arial, sans-serif"
PURPLE, CYAN, PINK, AMBER, GREEN = "#7C4DFF", "#22D3EE", "#FF4081", "#FBBF24", "#4ADE80"
TXT, MUTED = "#F1F5F9", "#94A3B8"
FALLBACK_COLORS = ["#7C4DFF", "#22D3EE", "#FF4081", "#FBBF24", "#4ADE80", "#FB923C", "#A78BFA"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    name login
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount } }
      }
    }
  }
}
"""

# ---------------------------------------------------------------- data
def gql(token, query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": "bearer " + token, "Content-Type": "application/json", "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    if not d.get("data") or not d["data"].get("user"):
        raise RuntimeError("GitHub API error: " + json.dumps(d.get("errors", d))[:500])
    return d["data"]["user"]

def normalize(u):
    langs, stars = {}, 0
    for repo in u["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            size, color = langs.get(n, (0, e["node"]["color"]))
            langs[n] = (size + e["size"], color or color)
    cc = u["contributionsCollection"]
    weeks = [[(d["weekday"], d["contributionCount"], d["date"]) for d in w["contributionDays"]]
             for w in cc["contributionCalendar"]["weeks"]]
    return {
        "name": u["name"] or u["login"], "login": u["login"],
        "followers": u["followers"]["totalCount"], "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"], "repos": u["repositories"]["totalCount"],
        "stars": stars, "commits": cc["totalCommitContributions"],
        "total": cc["contributionCalendar"]["totalContributions"], "weeks": weeks, "langs": langs,
    }

def mock():
    random.seed(7)
    end = datetime.date.today()
    start = end - datetime.timedelta(days=364)
    start -= datetime.timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    weeks, d = [], start
    while d <= end:
        wk = []
        for _ in range(7):
            if d <= end:
                c = 0 if random.random() < 0.35 else random.choice([1, 2, 3, 5, 8, 12, 20])
                wk.append(((d.weekday() + 1) % 7, c, d.isoformat()))
            d += datetime.timedelta(days=1)
        weeks.append(wk)
    total = sum(c for w in weeks for _, c, _ in w)
    return {"name": "Syed Raza Hussain", "login": "syedrazahussain", "followers": 12, "prs": 18, "issues": 4,
            "repos": 14, "stars": 9, "commits": 410, "total": total, "weeks": weeks,
            "langs": {"JavaScript": (52000, "#f1e05a"), "TypeScript": (21000, "#3178c6"), "PHP": (9000, "#4F5D95"),
                      "Python": (7000, "#3572A5"), "CSS": (6000, "#563d7c"), "HTML": (4000, "#e34c26")}}

# ---------------------------------------------------------------- helpers
def days_flat(data):
    return [(date, c) for w in data["weeks"] for _, c, date in w]

def streaks(data):
    days = days_flat(data)
    longest, run, run_start, best = 0, 0, None, (None, None)
    for i, (dt, c) in enumerate(days):
        if c > 0:
            if run == 0: run_start = dt
            run += 1
            if run > longest: longest, best = run, (run_start, dt)
        else:
            run = 0
    # current streak: walk back from the last day (skip today if empty)
    idx = len(days) - 1
    if idx >= 0 and days[idx][1] == 0: idx -= 1
    cur, cur_end = 0, (days[idx][0] if idx >= 0 else None)
    while idx >= 0 and days[idx][1] > 0:
        cur += 1; cur_start = days[idx][0]; idx -= 1
    return cur, (cur_start, cur_end) if cur else (None, None), longest, best

def short(dt):
    if not dt: return ""
    d = datetime.date.fromisoformat(dt)
    return f"{d.strftime('%b')} {d.day}"

def shade(hex_color, f):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % (min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)))

def svg(w, h, body, extra_defs=""):
    return f'''<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" xmlns="http://www.w3.org/2000/svg">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="{w}" y2="{h}" gradientUnits="userSpaceOnUse"><stop stop-color="#0B0F1A"/><stop offset="1" stop-color="#17113D"/></linearGradient>
<linearGradient id="edge" x1="0" y1="0" x2="{w}" y2="{h}" gradientUnits="userSpaceOnUse"><stop stop-color="{PURPLE}"/><stop offset=".6" stop-color="{CYAN}" stop-opacity=".5"/><stop offset="1" stop-color="{PINK}" stop-opacity=".8"/></linearGradient>
{extra_defs}</defs>
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="url(#bg)" stroke="url(#edge)" stroke-width="1.5"/>
{body}
</svg>'''

def text(x, y, s, size=14, fill=TXT, weight=400, anchor="start", extra=""):
    return f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" {extra}>{escape(str(s))}</text>'

def fmt(n):
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 10000 else f"{n:,}"

# ---------------------------------------------------------------- cards
def card_stats(d):
    days = days_flat(d)
    active = sum(1 for _, c in days if c > 0)
    rows = [("Total Stars Earned", d["stars"], AMBER), ("Commits (last year)", d["commits"], PURPLE),
            ("Pull Requests", d["prs"], CYAN), ("Issues", d["issues"], PINK),
            ("Public Repos", d["repos"], GREEN), ("Followers", d["followers"], "#FB923C")]
    body = text(28, 38, f"{d['name']}'s GitHub Stats", 18, TXT, 700)
    for i, (label, val, col) in enumerate(rows):
        y = 74 + i * 22
        body += f'<circle cx="34" cy="{y-5}" r="4" fill="{col}"/>'
        body += text(48, y, label, 14, "#CBD5E1")
        body += text(300, y, fmt(val), 14, TXT, 700, "end")
    r = 46; circ = 2 * math.pi * r; prog = min(1, active / 365)
    body += f'<circle cx="400" cy="112" r="{r}" stroke="#ffffff" stroke-opacity=".08" stroke-width="9"/>'
    body += (f'<circle cx="400" cy="112" r="{r}" stroke="url(#ring)" stroke-width="9" stroke-linecap="round" '
             f'stroke-dasharray="{circ*prog:.1f} {circ:.1f}" transform="rotate(-90 400 112)"/>')
    body += text(400, 118, active, 28, TXT, 800, "middle")
    body += text(400, 136, "active days", 12, MUTED, 400, "middle")
    ring = f'<linearGradient id="ring" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{PURPLE}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>'
    return svg(495, 200, body, ring)

def card_langs(d):
    langs = sorted(d["langs"].items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(s for _, (s, _) in langs) or 1
    body = text(28, 38, "Most Used Languages", 18, TXT, 700)
    bx, bw = 28, 439
    clip = f'<clipPath id="bar"><rect x="{bx}" y="54" width="{bw}" height="12" rx="6"/></clipPath>'
    body += '<g clip-path="url(#bar)">'
    x = bx
    for i, (n, (s, c)) in enumerate(langs):
        w = bw * s / total
        body += f'<rect x="{x:.1f}" y="54" width="{w+0.5:.1f}" height="12" fill="{c or FALLBACK_COLORS[i % 7]}"/>'
        x += w
    body += "</g>"
    for i, (n, (s, c)) in enumerate(langs):
        col, row = i // 3, i % 3
        px, py = 32 + col * 225, 96 + row * 25
        body += f'<circle cx="{px}" cy="{py-5}" r="5" fill="{c or FALLBACK_COLORS[i % 7]}"/>'
        body += text(px + 14, py, n, 14, "#CBD5E1")
        body += text(px + 190, py, f"{100*s/total:.1f}%", 13, MUTED, 600, "end")
    return svg(495, 170, body, clip)

def card_streak(d):
    cur, (cs, ce), longest, (ls, le) = streaks(d)
    days = days_flat(d)
    body = ""
    for x in (165, 330):
        body += f'<line x1="{x}" y1="28" x2="{x}" y2="142" stroke="#fff" stroke-opacity=".1"/>'
    body += text(82, 86, fmt(d["total"]), 32, CYAN, 800, "middle")
    body += text(82, 116, "Total Contributions", 13, "#CBD5E1", 600, "middle")
    body += text(82, 134, "last 12 months", 11.5, MUTED, 400, "middle")
    r = 40; circ = 2 * math.pi * r; prog = min(1, cur / 30)
    body += f'<circle cx="247" cy="72" r="{r}" stroke="#fff" stroke-opacity=".08" stroke-width="7"/>'
    body += (f'<circle cx="247" cy="72" r="{r}" stroke="url(#fire)" stroke-width="7" stroke-linecap="round" '
             f'stroke-dasharray="{circ*prog:.1f} {circ:.1f}" transform="rotate(-90 247 72)"/>')
    body += text(247, 82, cur, 32, TXT, 800, "middle")
    body += text(247, 130, "Current Streak", 13, AMBER, 700, "middle")
    body += text(247, 148, f"{short(cs)} – {short(ce)}" if cur else "no active streak", 11.5, MUTED, 400, "middle")
    body += text(412, 86, longest, 32, PINK, 800, "middle")
    body += text(412, 116, "Longest Streak", 13, "#CBD5E1", 600, "middle")
    body += text(412, 134, f"{short(ls)} – {short(le)}" if longest else "-", 11.5, MUTED, 400, "middle")
    fire = f'<linearGradient id="fire" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{AMBER}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>'
    return svg(495, 170, body, fire)

TIERS = [("#475569", "-"), ("#CD7F32", "C"), ("#C0C7D1", "B"), (AMBER, "A"), (CYAN, "S")]
def tier(v, th):
    return sum(1 for t in th if v >= t)

def card_trophies(d):
    _, _, longest, _ = streaks(d)
    items = [("Stars", d["stars"], [1, 10, 50, 200]), ("Commits", d["commits"], [50, 300, 1000, 3000]),
             ("Pull Requests", d["prs"], [1, 10, 50, 200]), ("Issues", d["issues"], [1, 10, 50, 200]),
             ("Followers", d["followers"], [1, 10, 50, 200]), ("Repos", d["repos"], [1, 10, 30, 80]),
             ("Best Streak", longest, [3, 10, 30, 100])]
    body = ""
    for i, (label, val, th) in enumerate(items):
        x = 8 + i * 118
        col, letter = TIERS[tier(val, th)]
        body += f'<g transform="translate({x} 6)">'
        body += f'<rect width="108" height="120" rx="14" fill="#0F1424" stroke="{col}" stroke-opacity=".6"/>'
        body += f'<rect width="108" height="4" rx="2" fill="{col}"/>'
        body += f'<g transform="translate(54 50)" fill="{col}">'
        body += '<path d="M-14,-26 h28 v12 a14,14 0 0 1 -28,0 z"/>'
        body += f'<path d="M-14,-22 q-13,0 -10,10 q2,7 11,7 M14,-22 q13,0 10,10 q-2,7 -11,7" stroke="{col}" stroke-width="3" fill="none"/>'
        body += '<rect x="-3" y="0" width="6" height="9"/><rect x="-13" y="9" width="26" height="5" rx="2"/>'
        body += f'<text y="-8" text-anchor="middle" font-family="{FONT}" font-size="13" font-weight="800" fill="#0B0F1A">{letter}</text>'
        body += "</g>"
        body += text(54, 90, fmt(val), 19, TXT, 800, "middle")
        body += text(54, 109, label, 11.5, MUTED, 400, "middle")
        body += "</g>"
    w, h = 8 + 7 * 118, 132
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" xmlns="http://www.w3.org/2000/svg">{body}</svg>'

def card_activity(d):
    days = days_flat(d)[-90:]
    W, H = 1200, 300
    x0, x1, y0, y1 = 70, 1160, 80, 250
    mx = max(1, max(c for _, c in days))
    top = math.ceil(mx / 4) * 4 or 4
    pts = [(x0 + (x1 - x0) * i / (len(days) - 1), y1 - (y1 - y0) * c / top) for i, (_, c) in enumerate(days)]
    body = text(32, 40, "Contribution Activity", 22, TXT, 700) + text(32, 62, "last 90 days", 13, MUTED)
    for k in range(5):
        y = y1 - (y1 - y0) * k / 4
        body += f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="#fff" stroke-opacity=".07"/>'
        body += text(x0 - 12, y + 4, int(top * k / 4), 12, MUTED, 400, "end")
    path = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for a, b in zip(pts, pts[1:]):
        m = (a[0] + b[0]) / 2
        path += f" C{m:.1f},{a[1]:.1f} {m:.1f},{b[1]:.1f} {b[0]:.1f},{b[1]:.1f}"
    area = path + f" L{pts[-1][0]:.1f},{y1} L{pts[0][0]:.1f},{y1} Z"
    body += f'<path d="{area}" fill="url(#area)"/>'
    body += f'<path d="{path}" stroke="url(#line)" stroke-width="3" stroke-linejoin="round"/>'
    peak = max(range(len(days)), key=lambda i: days[i][1])
    for i, (px, py) in enumerate(pts):
        if days[i][1] > 0:
            body += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{4.5 if i==peak else 2.4}" fill="{"#fff" if i==peak else CYAN}"/>'
    body += text(pts[peak][0], pts[peak][1] - 12, f"{days[peak][1]} on {short(days[peak][0])}", 12, "#fff", 600, "middle")
    for i in range(0, len(days), 15):
        body += text(pts[i][0], 276, short(days[i][0]), 12, MUTED, 400, "middle")
    defs = (f'<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="{PURPLE}" stop-opacity=".55"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></linearGradient>'
            f'<linearGradient id="line" x1="{x0}" y1="0" x2="{x1}" y2="0" gradientUnits="userSpaceOnUse"><stop stop-color="{PURPLE}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>')
    return svg(W, H, body, defs)

def card_3d(d):
    W, H = 1200, 340
    weeks = d["weeks"]
    mx = max([c for w in weeks for _, c, _ in w] + [1])
    palette = ["#1E2233", "#3B2F7F", "#5B3FD0", PURPLE, CYAN]
    def level(c):
        if c == 0: return 0
        r = c / mx
        return 1 if r <= .25 else 2 if r <= .5 else 3 if r <= .75 else 4
    ux, vx, vy = 20, -8, 10          # grid steps
    bu, bvx, bvy = 17, -6.8, 8.5     # bar footprint
    X0, Y0, HMAX = 80, 196, 125
    cells = {}
    for i, w in enumerate(weeks):
        for wd, c, _ in w:
            cells[(i, wd)] = c
    body = text(30, 36, f"{fmt(d['total'])} contributions in the last year", 20, TXT, 700)
    body += text(30, 58, "3D view · taller bars = more activity", 13, MUTED)
    for j in range(7):
        for i in range(len(weeks)):
            if (i, j) not in cells: continue
            c = cells[(i, j)]
            h = 1.5 if c == 0 else 6 + HMAX * c / mx
            col = palette[level(c)]
            px, py = X0 + i * ux + j * vx, Y0 + j * vy
            A = (px, py); B = (px + bu, py); C = (px + bu + bvx, py + bvy); D = (px + bvx, py + bvy)
            up = lambda p: (p[0], p[1] - h)
            def poly(pts, fill):
                return '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f'" fill="{fill}"/>'
            body += poly([up(A), up(B), up(C), up(D)], col)
            body += poly([D, C, up(C), up(D)], shade(col, .72))
            body += poly([B, C, up(C), up(B)], shade(col, .52))
    lx = 880
    body += text(lx - 12, 322, "Less", 12, MUTED, 400, "end")
    for k, c in enumerate(palette):
        body += f'<rect x="{lx + k*22}" y="311" width="16" height="16" rx="4" fill="{c}"/>'
    body += text(lx + 5 * 22 + 6, 323, "More", 12, MUTED)
    return svg(W, H, body)

# ---------------------------------------------------------------- main
def main():
    if "--mock" in sys.argv:
        data = mock()
    else:
        token, user = os.environ.get("GH_TOKEN"), os.environ.get("GH_USER")
        if not token or not user:
            sys.exit("GH_TOKEN and GH_USER are required (or use --mock)")
        last = None
        for attempt in range(3):
            try:
                data = normalize(gql(token, QUERY, {"login": user})); break
            except (urllib.error.URLError, RuntimeError) as e:
                last = e; print("retry:", e)
        else:
            sys.exit(f"Failed after retries: {last}")
    os.makedirs(OUT, exist_ok=True)
    for name, fn in [("stats", card_stats), ("top-langs", card_langs), ("streak", card_streak),
                     ("trophies", card_trophies), ("activity", card_activity), ("3d-contrib", card_3d)]:
        path = os.path.join(OUT, name + ".svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(fn(data))
        print("wrote", path, os.path.getsize(path), "bytes")

if __name__ == "__main__":
    main()
