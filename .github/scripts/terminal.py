import base64
import datetime as dt
import html
import json
import os
import urllib.request
from pathlib import Path

LOGIN = "BrunoPolaski"
LINKEDIN = "https://www.linkedin.com/in/bruno-polaski-27a97b255"
PORTFOLIO = "https://brunopolaski.github.io"
ASSETS = Path(__file__).resolve().parents[2] / "assets"
SLICES = ["json", "linkedin", "portfolio", "stats", "cursor"]

PROFILE_QUERY = """query($login: String!) {
  user(login: $login) {
    createdAt
    pullRequests { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10) { edges { size node { name color } } }
      }
    }
  }
}"""

CALENDAR_QUERY = """query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""

JSON_LINES = [
    [("p", "{")],
    [("p", "  "), ("k", '"name"'), ("p", ": "), ("s", '"Bruno Polaski"'), ("p", ",")],
    [("p", "  "), ("k", '"role"'), ("p", ": "), ("s", '"Full-stack & mobile developer"'), ("p", ",")],
    [("p", "  "), ("k", '"company"'), ("p", ": "), ("s", '"@BairesDev"'), ("p", ",")],
    [("p", "  "), ("k", '"experience"'), ("p", ": "), ("s", '"3 years"'), ("p", ",")],
    [("p", "  "), ("k", '"location"'), ("p", ": "), ("s", '"Santa Catarina, Brazil"'), ("p", ",")],
    [("p", "  "), ("k", '"education"'), ("p", ": {")],
    [("p", "    "), ("k", '"degree"'), ("p", ": "), ("s", '"Software Engineering (undergrad)"'), ("p", ",")],
    [("p", "    "), ("k", '"school"'), ("p", ": "), ("s", '"Universidade do Contestado"')],
    [("p", "  },")],
    [("p", "  "), ("k", '"stack"'), ("p", ": {")],
    [("p", "    "), ("k", '"frontend"'), ("p", ": ["), ("s", '"TypeScript"'), ("p", ", "), ("s", '"Vue"'), ("p", ", "), ("s", '"Angular"'), ("p", ", "), ("s", '"React"'), ("p", ", "), ("s", '"Flutter"'), ("p", "],")],
    [("p", "    "), ("k", '"backend"'), ("p", ": ["), ("s", '"Go"'), ("p", ", "), ("s", '"PHP"'), ("p", ", "), ("s", '".NET"'), ("p", ", "), ("s", '"Node.js"'), ("p", "],")],
    [("p", "    "), ("k", '"devops"'), ("p", ": ["), ("s", '"Terraform"'), ("p", ", "), ("s", '"AWS"'), ("p", ", "), ("s", '"Serverless Framework"'), ("p", ", "), ("s", '"GitHub Actions"'), ("p", "]")],
    [("p", "  },")],
    [("p", "  "), ("k", '"learning"'), ("p", ": ["), ("s", '"Harness engineering"'), ("p", "],")],
    [("p", "  "), ("k", '"open_to_chat"'), ("p", ": "), ("b", "true")],
    [("p", "}")],
]


def graphql(query, **variables):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    )
    with urllib.request.urlopen(request) as response:
        body = json.load(response)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]["user"]


def contribution_days(created_at, now):
    days = {}
    start = created_at
    while start < now:
        end = min(start + dt.timedelta(days=365), now)
        user = graphql(CALENDAR_QUERY, login=LOGIN, **{"from": start.isoformat(), "to": end.isoformat()})
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                days[dt.date.fromisoformat(day["date"])] = day["contributionCount"]
        start = end
    return days


def streaks(days, today):
    first = last = None
    longest = 0
    for day in sorted(days):
        if days[day]:
            first = first or day
            last = day
            longest = max(longest, (last - first).days + 1)
        elif day.weekday() < 5 and day != today:
            first = last = None
    current = (last - first).days + 1 if first else 0
    return current, longest


def top_languages(repos, count=4):
    sizes, colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b85a8"
    total = sum(sizes.values()) or 1
    ranked = sorted(sizes, key=sizes.get, reverse=True)[:count]
    return [(name, sizes[name] / total, colors[name]) for name in ranked]


def collect_stats():
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    user = graphql(PROFILE_QUERY, login=LOGIN)
    created_at = dt.datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))
    days = contribution_days(created_at, now)
    current, longest = streaks(days, now.date())
    repos = user["repositories"]["nodes"]
    return {
        "contributions": sum(days.values()),
        "current": current,
        "longest": longest,
        "pull_requests": user["pullRequests"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "stars": sum(repo["stargazerCount"] for repo in repos),
        "languages": top_languages(repos),
    }


class Terminal:
    width, x, line_height, gap, photo_height = 800, 28, 24, 10, 450
    prompt = [("u", "bruno@github"), ("c", ":"), ("d", "~"), ("c", "$ ")]

    def __init__(self):
        self.y, self.t, self.body, self.clips, self.cuts = 58, 0.2, [], [], [0]

    @staticmethod
    def spans(parts):
        return "".join(f'<tspan class="{c}">{html.escape(text, quote=False)}</tspan>' for c, text in parts)

    def reveal(self, inner):
        self.body.append(f'<g class="l" style="animation-delay:{self.t:.2f}s">{inner}</g>')
        self.t += 0.08

    def command(self, cmd):
        self.y += self.line_height
        n = len(cmd)
        duration = 0.2 + 0.04 * n
        clip = f"c{len(self.clips)}"
        width = (16 + n) * 9.5
        self.clips.append(
            f'<clipPath id="{clip}"><rect class="type" x="{self.x}" y="{self.y - 18}" width="{width}" height="24" '
            f'style="animation:type {duration:.2f}s steps({n + 16}) {self.t:.2f}s forwards"/></clipPath>'
        )
        self.body.append(f'<text x="{self.x}" y="{self.y}" clip-path="url(#{clip})">{self.spans(self.prompt + [("c", cmd)])}</text>')
        self.t += duration + 0.25

    def line(self, parts):
        self.y += self.line_height
        self.reveal(f'<text x="{self.x}" y="{self.y}">{self.spans(parts)}</text>')

    def columns(self, cells):
        self.y += self.line_height
        inner = "".join(f'<text x="{self.x + 16 + i * 392}" y="{self.y}">{self.spans(parts)}</text>' for i, parts in enumerate(cells))
        self.reveal(inner)

    def bars(self, languages):
        self.y += self.line_height
        inner = ""
        for i, (name, share, color) in enumerate(languages):
            x = self.x + 16 + i * 392
            inner += (
                f'<text x="{x}" y="{self.y}" class="k">{html.escape(name)}</text>'
                f'<rect x="{x + 120}" y="{self.y - 10}" width="160" height="8" rx="4" fill="#ffffff" fill-opacity="0.08"/>'
                f'<rect x="{x + 120}" y="{self.y - 10}" width="{max(share * 160, 3):.1f}" height="8" rx="4" fill="{color}"/>'
                f'<text x="{x + 292}" y="{self.y}" class="b">{share * 100:.1f}%</text>'
            )
        self.reveal(inner)

    def cut(self):
        self.cuts.append(self.y + 8)

    def space(self):
        self.y += self.gap

    def cursor(self):
        self.y += self.line_height
        self.reveal(f'<text x="{self.x}" y="{self.y}">{self.spans(self.prompt)}<tspan class="k cur">█</tspan></text>')

    def slices(self, background):
        bounds = self.cuts + [self.y + 28]
        return [self.svg(background, top, bottom) for top, bottom in zip(bounds, bounds[1:])]

    def svg(self, background, top, bottom):
        w, h = self.width, self.y + 28
        photo = ""
        if top < self.photo_height:
            photo = (
                f'<image href="data:image/jpeg;base64,{background}" width="{w}" height="{self.photo_height}" '
                f'preserveAspectRatio="xMidYMin slice" opacity="0.22" mask="url(#photo)"/>'
            )
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{bottom - top}" viewBox="0 {top} {w} {bottom - top}">
<style>
text{{font:15px "Fira Code","JetBrains Mono",Consolas,"DejaVu Sans Mono",monospace;white-space:pre}}
.k{{fill:#b39cff}} .s{{fill:#9ece6a}} .p{{fill:#c0caf5}} .b{{fill:#ff9e64}} .m{{fill:#8b85a8}}
.u{{fill:#8B6FDC}} .d{{fill:#7aa2f7}} .c{{fill:#c0caf5}}
.l{{opacity:0;animation:in .25s ease-out forwards}}
.type{{transform:scaleX(0);transform-box:fill-box;transform-origin:0 0}}
.cur{{animation:blink 1s step-end infinite}}
@keyframes in{{to{{opacity:1}}}}
@keyframes type{{to{{transform:scaleX(1)}}}}
@keyframes blink{{50%{{opacity:0}}}}
</style>
<defs>
<clipPath id="win"><rect width="{w}" height="{h}" rx="12"/></clipPath>
<linearGradient id="base" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="{h}">
<stop offset="0" stop-color="#0d0b1a"/><stop offset="0.55" stop-color="#11102a"/><stop offset="1" stop-color="#1c1233"/>
</linearGradient>
<radialGradient id="wine" gradientUnits="userSpaceOnUse" cx="{w * 0.82}" cy="{h}" r="460">
<stop offset="0" stop-color="#783356" stop-opacity="0.45"/><stop offset="1" stop-color="#783356" stop-opacity="0"/>
</radialGradient>
<radialGradient id="violet" gradientUnits="userSpaceOnUse" cx="{w * 0.12}" cy="{h * 0.72}" r="380">
<stop offset="0" stop-color="#452460" stop-opacity="0.4"/><stop offset="1" stop-color="#452460" stop-opacity="0"/>
</radialGradient>
<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
<stop offset="0.6" stop-color="#fff"/><stop offset="1" stop-color="#000"/>
</linearGradient>
<mask id="photo"><rect width="{w}" height="{self.photo_height}" fill="url(#fade)"/></mask>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" fill-opacity="0.025"/></pattern>
{chr(10).join(self.clips)}
</defs>
<g clip-path="url(#win)">
<rect width="{w}" height="{h}" fill="url(#base)"/>
<rect width="{w}" height="{h}" fill="url(#violet)"/>
<rect width="{w}" height="{h}" fill="url(#wine)"/>
{photo}
<rect width="{w}" height="{h}" fill="url(#scan)"/>
<rect width="{w}" height="36" fill="#1a1530" fill-opacity="0.9"/>
<circle cx="22" cy="18" r="6" fill="#ff5f57"/><circle cx="42" cy="18" r="6" fill="#febc2e"/><circle cx="62" cy="18" r="6" fill="#28c840"/>
<text x="{w / 2}" y="23" text-anchor="middle" style="font-size:13px" fill="#8b85a8">bruno@github: ~</text>
{chr(10).join(self.body)}
</g>
<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="none" stroke="#8B6FDC" stroke-opacity="0.5"/>
</svg>
'''


def render(stats):
    term = Terminal()
    term.command("cat bruno.json")
    for parts in JSON_LINES:
        term.line(parts)
    term.cut()
    term.space()
    term.command("open linkedin")
    term.line([("m", "Opening "), ("d", LINKEDIN)])
    term.cut()
    term.space()
    term.command("open portfolio")
    term.line([("m", "Opening "), ("d", PORTFOLIO)])
    term.cut()
    term.space()
    term.command("gh stats")
    term.columns([
        [("k", "contributions   "), ("b", f"{stats['contributions']:,}")],
        [("k", "current streak  "), ("b", f"{stats['current']}"), ("m", " days")],
    ])
    term.columns([
        [("k", "pull requests   "), ("b", f"{stats['pull_requests']:,}")],
        [("k", "longest streak  "), ("b", f"{stats['longest']}"), ("m", " days")],
    ])
    term.columns([
        [("k", "public repos    "), ("b", f"{stats['repos']}")],
        [("k", "stars           "), ("b", f"{stats['stars']}")],
    ])
    term.space()
    languages = stats["languages"]
    for i in range(0, len(languages), 2):
        term.bars(languages[i:i + 2])
    term.cut()
    term.space()
    term.cursor()
    background = base64.b64encode((ASSETS / "coding.jpg").read_bytes()).decode()
    return dict(zip(SLICES, term.slices(background)))


if __name__ == "__main__":
    for name, svg in render(collect_stats()).items():
        (ASSETS / f"terminal-{name}.svg").write_text(svg)
