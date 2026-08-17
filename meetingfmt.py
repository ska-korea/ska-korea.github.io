#!/usr/bin/env python
"""미팅 원고 형식 — 조판을 우리가 소유하기 위한 최소 문법.

Google Sites에서 HTML을 긁어오던 방식의 한계(지도·PDF·설문이 원본에 아예 없고,
단 구성은 난독화 클래스라 재현 불가)를 벗어나려면 원고를 우리 형식으로 가져야 한다.

구조는 LaTeX와 같다 — 파일 하나가 미팅 하나다.

    ---                     ← frontmatter (제목·날짜·장소·배너)
    ---
    # Home                  ← 하위 탭
    ## Scientific Rationale  ← 단락
    ### 세부                  ← 소제목

    ::: split 2:1           ← 블록. 여는 줄에 이름과 인자, 닫는 줄은 :::
    왼쪽
    ---                     ← 단 구분
    오른쪽
    :::

블록은 여덟 가지뿐이다(split·program·people·deadlines·map·pdf·form·logos).
미팅 27쪽을 전수 조사해 실제로 쓰이는 요소가 그만큼이었다.
"""

import html
import re
from datetime import date, datetime, timedelta
from urllib.parse import quote

BLOCK_OPEN = re.compile(r"^:::\s*(\w+)\s*(.*)$")
BLOCK_CLOSE = re.compile(r"^:::\s*$")
HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")


# ── 파싱 ────────────────────────────────────────────────────────────

def split_front(text):
    """--- YAML --- 본문 → (앞머리 문자열, 본문)"""
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return fm, body.lstrip("\n")
    return "", text


def scan(lines):
    """줄 목록 → 노드 목록. [("md", 글) | ("block", 이름, 인자, 안쪽 줄들)]

    ★ 블록은 중첩된다. `::: split` 안에 `::: people`을 넣는 것이 이 형식의 핵심
      쓰임이므로, 닫는 `:::`를 만나면 무조건 닫지 말고 **깊이를 세어** 짝을 맞춘다.
      (짝을 안 맞추면 안쪽 블록이 통째로 글자로 새어 나온다.)
    """
    nodes, buf, i = [], [], 0

    def flush():
        nonlocal buf
        if any(l.strip() for l in buf):
            nodes.append(("md", "\n".join(buf)))
        buf = []

    while i < len(lines):
        m = BLOCK_OPEN.match(lines[i])
        if m:
            depth, j, inner = 1, i + 1, []
            while j < len(lines):
                if BLOCK_OPEN.match(lines[j]):
                    depth += 1
                elif BLOCK_CLOSE.match(lines[j]):
                    depth -= 1
                    if depth == 0:
                        break
                inner.append(lines[j])
                j += 1
            flush()
            nodes.append(("block", m.group(1), m.group(2).strip(), inner))
            i = j + 1
            continue
        buf.append(lines[i])
        i += 1
    flush()
    return nodes


def parse(body):
    """본문을 하위 탭 목록으로 나눈다. `#` 하나가 탭 하나.

    블록 안의 `#`은 탭 구분으로 보지 않는다 — 깊이를 세면서 자른다.
    맨 앞에 `#` 없이 시작하는 글은 첫 탭(Home)에 담는다.
    """
    pages, cur, buf, depth = [], None, [], 0

    def close():
        if cur is not None:
            cur["nodes"] = scan(buf)

    for line in body.splitlines():
        h = HEADING.match(line)
        if depth == 0 and h and len(h.group(1)) == 1:
            close()
            cur = {"title": h.group(2)}
            pages.append(cur)
            buf = []
            continue
        if cur is None:
            cur = {"title": "Home"}
            pages.append(cur)
            buf = []
        buf.append(line)
        if BLOCK_OPEN.match(line):
            depth += 1
        elif BLOCK_CLOSE.match(line) and depth:
            depth -= 1
    close()
    return pages


def columns(lines):
    """`---` 로 단을 나눈다. 안쪽 블록의 `---`은 세지 않는다."""
    parts, cur, depth = [], [], 0
    for l in lines:
        if BLOCK_OPEN.match(l):
            depth += 1
        elif BLOCK_CLOSE.match(l) and depth:
            depth -= 1
        elif depth == 0 and l.strip() == "---":
            parts.append(cur)
            cur = []
            continue
        cur.append(l)
    parts.append(cur)
    return parts


# ── 잔손질 ───────────────────────────────────────────────────────────

def cells(line, n=None):
    """`가 | 나 | 다` → ['가','나','다']. n을 주면 그 길이로 맞춘다."""
    out = [c.strip() for c in line.split("|")]
    if n is not None:
        out += [""] * (n - len(out))
    return out


def kv(parts):
    """['slides=a.pdf', 'lang=ko'] → {'slides': 'a.pdf', 'lang': 'ko'}"""
    d = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def e(s):
    return html.escape(str(s or ""), quote=True)


def parse_args(arg):
    """`2:1 gap=large` → (['2:1'], {'gap': 'large'})"""
    pos, opt = [], {}
    for tok in arg.split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            opt[k] = v
        elif tok:
            pos.append(tok)
    return pos, opt


# ── 블록 ────────────────────────────────────────────────────────────

def blk_split(lines, arg, ctx, md):
    """단 배치. `::: split 2:1`, 단 사이는 `---`.

    각 단의 내용을 다시 통째로 해석하므로 안에 다른 블록을 넣을 수 있다
    (예: 왼쪽에 초청연사 `people`, 오른쪽에 SOC `people`).
    """
    pos, _ = parse_args(arg)
    ratio = pos[0] if pos else "1:1"
    fr = " ".join(f"{n}fr" for n in ratio.split(":"))
    cols = "".join(f'<div class="mx-col">{render_nodes(scan(p), md, ctx)}</div>'
                   for p in columns(lines))
    return f'<div class="mx-split" style="--cols:{e(fr)}">{cols}</div>'


def blk_program(lines, arg, ctx, md):
    """일정표. 날짜줄에 시작시각을 한 번 적으면 나머지는 소요시간만 적는다.

        2026-10-19  09:30
          session Session 1 | chair 강혜성
          10 | 손봉원 | KASI | Opening
          break 15

    → 09:30–09:40, 휴식, … 를 스스로 계산한다. 가운데 하나만 고쳐도 뒤가 따라온다.
    이것이 이 형식을 쓰는 가장 큰 이유다 — 스프레드시트로 도망갈 이유가 없어진다.
    """
    days, cur, clock = [], None, None
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        d = re.match(r"^(\d{4}-\d{2}-\d{2})\s*(?:\|\s*)?(\d{1,2}:\d{2})?\s*(?:\|\s*)?(.*)$", s)
        if d:
            cur = {"date": d.group(1), "note": d.group(3).strip(), "rows": []}
            days.append(cur)
            clock = datetime.strptime(d.group(2) or "09:00", "%H:%M")
            continue
        if cur is None:
            continue
        if s.lower().startswith("session"):
            parts = cells(s)
            title = re.sub(r"^session\s*", "", parts[0], flags=re.I).strip()
            chair = next((p.split(None, 1)[1] for p in parts[1:]
                          if p.lower().startswith("chair")), "")
            cur["rows"].append({"kind": "session", "title": title, "chair": chair})
            continue
        if s.lower().startswith("break"):
            m = re.match(r"break\s+(\d+)\s*(?:\|\s*(.*))?$", s, re.I)
            mins = int(m.group(1)) if m else 0
            label = (m.group(2) if m and m.group(2) else "휴식")
            start = clock
            clock = clock + timedelta(minutes=mins)
            cur["rows"].append({"kind": "break", "label": label, "mins": mins,
                                "from": start.strftime("%H:%M"), "to": clock.strftime("%H:%M")})
            continue
        # 일반 항목: 소요시간 | 발표자 | 소속 | 제목 | 옵션…
        parts = cells(s)
        head = parts[0]
        fixed = re.match(r"^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$", head)
        if fixed:
            start, end = fixed.group(1), fixed.group(2)
            clock = datetime.strptime(end, "%H:%M")
        else:
            mins = int(re.sub(r"\D", "", head) or 0)
            start = clock.strftime("%H:%M")
            clock = clock + timedelta(minutes=mins)
            end = clock.strftime("%H:%M")
        opt = kv(parts[4:])
        cur["rows"].append({"kind": "talk", "from": start, "to": end,
                            "speaker": parts[1] if len(parts) > 1 else "",
                            "affil": parts[2] if len(parts) > 2 else "",
                            "title": parts[3] if len(parts) > 3 else "",
                            "slides": opt.get("slides", ""), "lang": opt.get("lang", ""),
                            "swg": opt.get("swg", "")})
    ctx.setdefault("program", []).extend(days)

    out = ['<div class="mx-program">']
    for d in days:
        try:
            dt = date.fromisoformat(d["date"])
            head = f'{dt.year}.{dt.month:02d}.{dt.day:02d} ({"월화수목금토일"[dt.weekday()]})'
        except ValueError:
            head = d["date"]
        out.append(f'<div class="mx-day"><span>{e(head)}</span>'
                   + (f'<em>{e(d["note"])}</em>' if d["note"] else "") + "</div>")
        for r in d["rows"]:
            if r["kind"] == "session":
                chair = f' <span class="mx-chair">좌장 {e(r["chair"])}</span>' if r["chair"] else ""
                out.append(f'<div class="mx-session">{e(r["title"])}{chair}</div>')
            elif r["kind"] == "break":
                out.append(f'<div class="mx-row mx-break"><span class="mx-time">'
                           f'{r["from"]}–{r["to"]}</span><span class="mx-what">{e(r["label"])}</span></div>')
            else:
                who = " · ".join(x for x in (r["speaker"], r["affil"]) if x)
                slides = (f'<a class="mx-slides" href="{e(r["slides"])}">슬라이드</a>'
                          if r["slides"] and ctx.get("phase") == "past" else "")
                lang = f'<span class="mx-lang">{e(r["lang"])}</span>' if r["lang"] else ""
                out.append(
                    f'<div class="mx-row"><span class="mx-time">{r["from"]}–{r["to"]}</span>'
                    f'<span class="mx-what"><b>{e(r["title"])}</b>'
                    + (f'<span class="mx-who">{e(who)}</span>' if who else "")
                    + f'</span><span class="mx-mark">{lang}{slides}</span></div>')
    out.append("</div>")
    return "".join(out)


ROLE_ORDER = {"chair": 0, "speaker": 1, "": 2}

# 셋째 칸에 적는 꼬리표. 역할(발표자·좌장)과 직급을 함께 적을 수 있다.
#   Bong Won Sohn | KASI | speaker staff
# 직급은 네 갈래로만 센다 — 실제로는 이 이상 구분되지 않는 경우가 대부분이다(사용자 확인).
ROLES = {"speaker", "chair"}
POSITIONS = {
    "student": "학생", "학생": "학생", "grad": "학생", "phd": "학생", "ms": "학생",
    "postdoc": "포닥", "포닥": "포닥", "pd": "포닥",
    "staff": "교수·연구원", "faculty": "교수·연구원", "prof": "교수·연구원",
    "professor": "교수·연구원", "researcher": "교수·연구원",
    "other": "기타", "기타": "기타",
}


def blk_people(lines, arg, ctx, md):
    """사람 목록. `이름 | 소속 | 꼬리표…`.

    sort=speaker,name 이면 발표자를 앞에 두고 이름 오름차순.
    LOC가 손으로 정렬하던 일을 없앤다.
    꼬리표는 역할(speaker·chair)과 직급(student·postdoc·staff·other)을 섞어 적을 수 있다.
    """
    _, opt = parse_args(arg)
    rows = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        c = cells(s, 3)
        tags = [t.strip().lower() for t in re.split(r"[,\s]+", c[2]) if t.strip()]
        rows.append({"name": c[0], "affil": c[1],
                     "role": next((t for t in tags if t in ROLES), ""),
                     "position": next((POSITIONS[t] for t in tags if t in POSITIONS), "")})
    keys = [k.strip() for k in opt.get("sort", "name").split(",")]

    def keyf(r):
        return tuple(ROLE_ORDER.get(r["role"], 3) if k == "speaker" else
                     r.get(k, "").lower() for k in keys)
    rows.sort(key=keyf)
    # 통계는 '참가자' 명단에서만 뽑는다. SOC·LOC·초청연사 목록까지 세면 중복이 된다.
    # 그래서 세고 싶은 목록에만 stats=yes 를 단다.
    if opt.get("stats") == "yes":
        ctx["people_stat"] = list(rows)

    cls = "mx-people" + (" grid" if opt.get("as", "grid") == "grid" else " list")
    out = [f'<ul class="{cls}">']
    for r in rows:
        mark = f'<span class="mx-role">{e(r["role"])}</span>' if r["role"] else ""
        out.append(f'<li><span class="mx-name">{e(r["name"])}</span>'
                   + (f'<span class="mx-affil">{e(r["affil"])}</span>' if r["affil"] else "")
                   + mark + "</li>")
    out.append("</ul>")
    if opt.get("count", "yes") != "no":
        out.append(f'<p class="mx-count">모두 {len(rows)}명</p>')
    return "".join(out)


def blk_deadlines(lines, arg, ctx, md):
    """마감일. `2026-04-15 | 초록 접수 시작`.

    지난 것은 스스로 물러나고 다음 것이 강조된다 — LOC가 색을 손으로 바꾸던 일을 없앤다.
    """
    today = ctx.get("today") or date.today()
    rows = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        c = cells(s, 2)
        try:
            d = date.fromisoformat(c[0])
        except ValueError:
            continue
        rows.append((d, c[1]))
    rows.sort()
    nxt = next((d for d, _ in rows if d >= today), None)
    out = ['<ul class="mx-deadlines">']
    for d, what in rows:
        state = "past" if d < today else ("next" if d == nxt else "future")
        out.append(f'<li class="{state}"><span class="mx-date mono">'
                   f'{d.year}.{d.month:02d}.{d.day:02d}</span>'
                   f'<span>{e(what)}</span></li>')
    out.append("</ul>")
    return "".join(out)


def blk_map(lines, arg, ctx, md):
    """지도. 주소만 적으면 된다(Google 지도, API 키 없이 삽입 가능함을 실측 확인)."""
    _, opt = parse_args(arg)
    addr = " ".join(l.strip() for l in lines if l.strip()) or opt.get("q", "")
    if not addr:
        return ""
    src = f"https://www.google.com/maps?q={quote(addr)}&hl=ko&z={opt.get('zoom', '16')}&output=embed"
    return (f'<div class="mx-map"><iframe src="{e(src)}" loading="lazy" '
            f'referrerpolicy="no-referrer-when-downgrade" title="{e(addr)} 지도"></iframe>'
            f'<p class="mx-cap"><a href="https://www.google.com/maps?q={quote(addr)}" '
            f'rel="noopener">{e(addr)}</a></p></div>')


def blk_pdf(lines, arg, ctx, md):
    """PDF를 그 자리에서 펼친다. repo에 둔 파일이라 브라우저가 그대로 띄운다
       (Google Drive 삽입은 우리 쪽에서 재현할 수 없다)."""
    pos, opt = parse_args(arg)
    src = pos[0] if pos else ""
    label = opt.get("label") or (lines[0].strip() if lines and lines[0].strip() else "PDF")
    if not src:
        return ""
    return (f'<div class="mx-pdf"><iframe src="{e(src)}#view=FitH" loading="lazy" '
            f'title="{e(label)}"></iframe>'
            f'<p class="mx-cap"><a href="{e(src)}">{e(label)} 내려받기</a></p></div>')


def blk_form(lines, arg, ctx, md):
    """등록 폼. 미팅이 끝나면 스스로 접힌다 — 끝난 모임에 등록창이 열려 있으면 안 된다."""
    pos, opt = parse_args(arg)
    src = pos[0] if pos else ""
    if not src:
        return ""
    if ctx.get("phase") == "past":
        return ('<div class="mx-closed"><b>등록이 마감되었습니다.</b> '
                '이 모임은 이미 끝났습니다.</div>')
    sep = "&" if "?" in src else "?"
    return (f'<div class="mx-form"><iframe src="{e(src + sep)}embedded=true" loading="lazy" '
            f'title="등록 양식" height="{e(opt.get("height", "900"))}"></iframe></div>')


def blk_logos(lines, arg, ctx, md):
    """후원·주관 기관 로고 줄. 높이를 맞춰 한 줄에 세운다."""
    out = ['<div class="mx-logos">']
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        c = cells(s, 3)
        img = f'<img src="{e(c[1])}" alt="{e(c[0])}" loading="lazy">'
        out.append(f'<a href="{e(c[2])}" rel="noopener">{img}</a>' if c[2] else
                   f"<span>{img}</span>")
    out.append("</div>")
    return "".join(out)


def blk_gallery(lines, arg, ctx, md):
    """사진첩. `파일명 | 캡션`. 캡션은 없어도 된다 — 그때는 사진만 보인다.

    미팅이 끝난 뒤 LOC가 사진만 올리면 되도록, 캡션을 따로 관리하지 않고
    원고 안에서 함께 적는다.
    """
    _, opt = parse_args(arg)
    out = [f'<div class="mx-gallery" style="--min:{e(opt.get("size", "240px"))}">']
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        c = cells(s, 2)
        cap = f'<figcaption>{e(c[1])}</figcaption>' if c[1] else ""
        out.append(f'<figure><a href="{e(c[0])}"><img src="{e(c[0])}" alt="{e(c[1])}" '
                   f'loading="lazy"></a>{cap}</figure>')
    out.append("</div>")
    return "".join(out)


def bars(title, counts, total, note=""):
    if not counts:
        return ""
    rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    out = [f'<div class="mx-stat"><h4>{e(title)}</h4><ul>']
    for k, n in rows:
        pct = round(n / total * 100) if total else 0
        out.append(f'<li><span class="k">{e(k)}</span>'
                   f'<span class="bar"><i style="width:{pct}%"></i></span>'
                   f'<span class="n">{n}<small>{pct}%</small></span></li>')
    out.append("</ul>" + (f'<p class="mx-note">{e(note)}</p>' if note else "") + "</div>")
    return "".join(out)


def blk_stats(lines, arg, ctx, md):
    """참가자·프로그램 자료에서 구성을 스스로 뽑는다. LOC가 따로 세지 않아도 된다.

    ★ 발표 주제는 **적어 둔 꼬리표(swg=)만** 센다. 제목을 보고 분야를 추정하지 않는다 —
      그것은 사실을 지어내는 일이다. 꼬리표를 안 단 발표는 '미분류'로 남긴다.
      분류 어휘를 코드에 박아 두지도 않는다. 무엇으로 정하든 그대로 집계된다.
    """
    from collections import Counter
    people = ctx.get("people_stat") or []
    talks = [r for d in (ctx.get("program") or []) for r in d["rows"]
             if r["kind"] == "talk" and (r["title"] or r["speaker"])]
    out = ['<div class="mx-stats">']
    if people:
        out.append(bars("소속", Counter(p["affil"] or "미기재" for p in people), len(people)))
        pos = Counter(p["position"] or "미기재" for p in people)
        out.append(bars("구성", pos, len(people)))
    if talks:
        tagged = [t["swg"] for t in talks if t["swg"]]
        c = Counter(tagged)
        if tagged:
            c["미분류"] = len(talks) - len(tagged)
            out.append(bars("발표 주제", {k: v for k, v in c.items() if v}, len(talks),
                            "주제 꼬리표(swg=)를 단 발표만 셉니다."))
    out.append("</div>")
    body = "".join(out)
    return body if (people or talks) else (
        '<p class="mx-note">참가자 명단이나 일정표가 채워지면 여기에 구성이 나옵니다.</p>')


BLOCKS = {"split": blk_split, "program": blk_program, "people": blk_people,
          "deadlines": blk_deadlines, "map": blk_map, "pdf": blk_pdf,
          "form": blk_form, "logos": blk_logos, "gallery": blk_gallery,
          "stats": blk_stats}


def render_nodes(nodes, md, ctx):
    """노드 목록 → HTML. 블록 안에서 다시 불려 중첩을 만든다."""
    out = []
    for node in nodes:
        if node[0] == "md":
            out.append(md(node[1]))
        else:
            _, name, arg, lines = node
            fn = BLOCKS.get(name)
            out.append(fn(lines, arg, ctx, md) if fn else
                       f'<p class="mx-unknown">알 수 없는 블록: {e(name)}</p>')
    return "\n".join(out)


def render(pages, md, ctx):
    """파싱한 하위 탭들을 HTML로. md는 마크다운 → HTML 함수.

    ★ 두 번 그린다. `::: stats`는 참가자 명단과 일정표에서 값을 뽑는데, 그것들은
      다른 하위 탭에 있다. 한 번만 그리면 탭 순서에 따라 통계가 비어 나온다.
      첫 번째는 자료를 모으는 회차이고, 두 번째 결과만 쓴다.
    """
    for _ in range(2):
        # 회차마다 비우고 다시 모은다 — 안 그러면 일정표가 두 배로 세어진다
        ctx.pop("program", None); ctx.pop("people_stat", None)
        for p in pages:
            p["html"] = render_nodes(p["nodes"], md, ctx)
    return pages
