#!/usr/bin/env python
"""SKA Korea 홈페이지 빌더.

두 갈래의 원고를 하나의 사이트로 합친다.
  · content/**/*.md   — 관리자가 쓰는 본문 (Markdown + YAML frontmatter)
  · ../harvest/html/  — LOC가 Google Sites에서 관리하는 미팅 본문 (수확기 산출물)

출력은 순수 정적 HTML. 실행:
    python build.py            # _site/ 로 빌드
    python build.py --serve    # 빌드 후 로컬 미리보기 서버
"""

import argparse
import hashlib
import http.server
import json
import re
import shutil
import socketserver
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import markdown
import yaml

import meetingfmt
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

ROOT = Path(__file__).resolve().parent
HARVEST = ROOT / "harvest"
OUT = ROOT / "_site"

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# 한글 종결어미 뒤의 마침표에서만 자른다.
# '15.4 GHz'나 'Dr. Kim'처럼 마침표가 문장 끝이 아닌 경우를 건드리지 않기 위함.
SENTENCE_SPLIT = re.compile(r"(?<=[가-힣][.!?])\s+")


def sentences(text) -> Markup:
    """문장마다 <span>에 담아, 줄이 바뀐다면 문장 사이에서 바뀌게 한다.

    한 문장이 통째로 움직이므로 '아래 순서로 / 읽으면'처럼 구절 한가운데서
    끊기지 않는다. 문장이 한 줄보다 길면 그 안에서는 평소대로 줄을 바꾼다.
    짧은 리드·부제에만 쓴다 — 긴 본문에 쓰면 줄 끝이 크게 비어 되레 지저분해진다.
    """
    if not text:
        return Markup("")
    parts = [p for p in SENTENCE_SPLIT.split(str(text).strip()) if p]
    if len(parts) < 2:
        return Markup(escape(text))
    return Markup(" ".join(f'<span class="sent">{escape(p)}</span>' for p in parts))


# 우리 사이트로 취급할 호스트. 맞춤 도메인으로 옮긴 뒤에도 그대로 두면
# 예전 주소로 걸린 링크가 '외부'로 잘못 잡히지 않는다.
SELF_HOSTS = {"ska-korea.github.io", "ska.kasi.re.kr", "www.ska.kasi.re.kr"}
# 같은 사이트에 있어도 '문서'는 새 창으로 연다 — 눌렀다고 보던 페이지가
# 사라지면 곤란하고, 뒤로 가기로 돌아오는 것도 뷰어에 따라 어색하다.
DOC_EXT = (".pdf", ".pptx", ".ppt", ".key", ".zip", ".xlsx", ".docx", ".hwp", ".hwpx")

A_TAG = re.compile(r"<a\b([^>]*)>", re.I)
HREF = re.compile(r'href\s*=\s*"([^"]*)"', re.I)
TARGET = re.compile(r'\s*target\s*=\s*"[^"]*"', re.I)
REL = re.compile(r'\s*rel\s*=\s*"([^"]*)"', re.I)


def link_targets(html: str) -> str:
    """내부 링크는 제자리에서, 외부 링크는 새 창에서 열리게 맞춘다.

    템플릿이 아니라 완성된 HTML에 한 번 적용한다. 그래야 우리가 쓴 원고뿐 아니라
    조직위원회가 Google Sites에서 쓴 미팅 본문까지 빠짐없이 같은 규칙을 따른다.
    """
    def fix(m):
        attrs = m.group(1)
        href_m = HREF.search(attrs)
        if not href_m:
            return m.group(0)
        href = href_m.group(1).strip()

        if href.lower().startswith(("mailto:", "tel:")):
            # 메일·전화는 새 창을 열 일이 아니다. Google Sites가 붙여 보낸
            # target="_blank"는 빈 탭만 만들었다 사라지므로 걷어낸다.
            return f"<a{TARGET.sub('', attrs)}>"
        if href.lower().startswith("javascript:"):
            return m.group(0)

        if re.match(r"https?://", href, re.I):
            host = (urlparse(href).hostname or "").lower()
            external = host not in SELF_HOSTS
        else:
            # /경로 · #앵커 · 상대경로 = 우리 사이트
            external = False

        new_tab = external or href.lower().split("?")[0].endswith(DOC_EXT)

        attrs = TARGET.sub("", attrs)
        rel_m = REL.search(attrs)
        rel = set((rel_m.group(1) if rel_m else "").split())
        attrs = REL.sub("", attrs)

        if new_tab:
            rel |= {"noopener", "noreferrer"}
            attrs = attrs.rstrip() + ' target="_blank"'
        else:
            rel -= {"noopener", "noreferrer"}

        if rel:
            attrs += f' rel="{" ".join(sorted(rel))}"'
        return f"<a{attrs}>"

    return A_TAG.sub(fix, html)


def mark_dropbox_ignored(path: Path) -> None:
    """이 폴더를 Dropbox가 동기화하지 않게 표시한다(macOS).

    빌드는 _site를 통째로 지웠다 다시 만든다. 그 폴더가 Dropbox 안에 있으면
    동기화와 부딪혀 '충돌된 사본'이 생기고, 원래 index.html이 밀려나 페이지가
    사라지기도 한다. 빌드 산출물은 언제든 다시 만들 수 있으니 동기화 대상이 아니다.
    폴더를 지우면 속성도 사라지므로 빌드할 때마다 다시 붙인다.
    CI(리눅스)나 Dropbox 밖에서는 아무 일도 하지 않는다.
    """
    if sys.platform != "darwin" or "CloudStorage/Dropbox" not in str(path):
        return
    try:
        subprocess.run(["xattr", "-w", "com.dropbox.ignored", "1", str(path)],
                       check=True, capture_output=True, timeout=10)
    except Exception:
        pass  # 표시에 실패해도 빌드는 계속한다


def image_map() -> dict[str, str]:
    """수확한 이미지의 키(확장자 없음) → 실제 파일명."""
    d = HARVEST / "images"
    return {f.stem: f.name for f in d.iterdir() if f.is_file()} if d.exists() else {}


def fix_images(html: str, imgs: dict[str, str]) -> str:
    """수확 원고의 images/KEY 참조를 배포 경로로 바꾼다. 없는 이미지는 통째로 지운다."""
    def sub(m):
        name = imgs.get(m.group(1))
        return f'"/img/{name}"' if name else '""'
    html = re.sub(r'"images/([\w.-]+)"', sub, html)
    # 마크다운 이미지 ![](images/KEY) 와 CSS background-image: url(images/KEY)
    html = re.sub(r'\(images/([\w.-]+)\)',
                  lambda m: f'(/img/{imgs[m.group(1)]})' if m.group(1) in imgs else '()', html)
    # 내려받지 못한 이미지는 빈 태그로 남기지 않는다
    return re.sub(r'<img[^>]*src=""[^>]*>', "", html)


BANNER_DIR = "/static/img/banners/"


def banner_for(path: str, meta: dict, conf: dict) -> tuple[str | None, str | None]:
    """본문 페이지 배너에 깔 사진을 고른다. (주소, 자를 위치)를 돌려준다.

    원고의 frontmatter `banner:`가 있으면 그것을 쓰고(빈 값이면 사진 없이 네이비만),
    없으면 site.yaml의 경로 규칙에서 가장 긴 접두사가 이긴다. 그래서
    `/src` 규칙을 두면 `/src/korea-src`까지 함께 따라오고, 필요하면 그 쪽만 덮어쓴다.

    값은 파일명 하나로 적어도 되고, 자를 위치를 함께 정하려면
    `{file: 사진.jpg, at: "center 85%"}`로 적는다 — 배너는 사진의 가운데를 얇게
    베어 쓰므로, 담을 것이 아래쪽에 있는 사진은 위치를 내려 줘야 제 모습이 나온다.
    """
    def unpack(v):
        if not v:
            return None, None
        if isinstance(v, dict):
            name, at = v.get("file"), v.get("at")
        else:
            name, at = v, None
        return (name if str(name).startswith("/") else BANNER_DIR + str(name)), at

    if "banner" in meta:
        return unpack(meta["banner"])
    best, chosen = -1, conf.get("default")
    for prefix, v in (conf.get("paths") or {}).items():
        if (path == prefix or path.startswith(prefix.rstrip("/") + "/")) and len(prefix) > best:
            best, chosen = len(prefix), v
    return unpack(chosen)


def split_front(text: str) -> tuple[dict, str]:
    """--- YAML --- 본문 형태를 (메타, 본문)으로 나눈다."""
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body.lstrip("\n")
    return {}, text


def parse_title_date(title: str) -> tuple[int, int] | None:
    """'Oct 2026 SPARCS XIV' -> (2026, 10). 미팅 제목의 관례를 이용한다."""
    m = re.match(r"^([A-Za-z]{3,9})\.?\s+(\d{4})\b", title.strip())
    if not m:
        return None
    mon = MONTHS.get(m.group(1)[:3].lower())
    return (int(m.group(2)), mon) if mon else None


def build_nav(nav_cfg: list, current: str) -> list:
    """현재 경로를 표시한 내비게이션 트리."""
    out = []
    for item in nav_cfg:
        kids = item.get("children") or []
        path = item["path"]
        active = current == path or (path != "/" and current.startswith(path + "/")) \
            or any(current == k["path"] or current.startswith(k["path"] + "/") for k in kids)
        out.append({**item, "children": kids, "active": active,
                    "exact": current == path})
    return out


def collect_content(md: markdown.Markdown, banners: dict) -> list[dict]:
    """content/ 의 Markdown 원고를 페이지로 읽어들인다."""
    pages = []
    for f in sorted((ROOT / "content").rglob("*.md")):
        if f.parent.name == "talks":
            continue  # 발표는 collect_talks가 이름 규칙으로 따로 모은다
        meta, body = split_front(f.read_text(encoding="utf-8"))
        rel = f.relative_to(ROOT / "content").with_suffix("")
        path = "/" if rel.name == "index" and rel.parent == Path(".") \
            else "/" + str(rel.parent / rel.name if rel.name != "index" else rel.parent).replace("\\", "/")
        md.reset()
        p = meta.get("path", path)
        src, at = banner_for(p, meta, banners)
        pages.append({
            "path": p,
            "title": meta.get("title", f.stem),
            "sub": meta.get("sub"),
            "template": meta.get("template", "page.html"),
            "html": md.convert(body) if body.strip() else "",
            "meta": meta,
            "banner": src,
            "banner_at": at,
            "source": "content",
        })
    return pages


TALK_SLIDES = {".pdf", ".pptx", ".key"}
TALK_IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

WEEKDAYS = "월화수목금토일"
WHEN_DATE = re.compile(r"(\d{1,2})월\s*(\d{1,2})일(?:\s*\(([월화수목금토일])\))?")


def check_talk_date(filename: str, file_date: date, when: str | None) -> None:
    """파일명 날짜와 frontmatter의 `when`이 어긋나면 알린다.

    발표는 두 곳에 날짜가 적힌다 — 파일명(정렬·주소를 정한다)과 `when`(화면에 보인다).
    둘이 갈라져도 화면은 멀쩡해 보이므로 눈으로는 오래 못 잡는다. 실제로 한 건이
    파일명 6/22 · 표기 6/18로 넉 달을 그렇게 있었다. 요일까지 함께 본다.
    """
    m = WHEN_DATE.search(str(when or ""))
    if not m:
        return
    try:
        said = date(file_date.year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return
    if said != file_date:
        print(f"  ! {filename}: 파일명은 {file_date}인데 when은 {said}입니다 "
              f"— 정렬·주소는 파일명을 따릅니다", file=sys.stderr)
    elif m.group(3) and m.group(3) != WEEKDAYS[said.weekday()]:
        print(f"  ! {filename}: {said}는 {WEEKDAYS[said.weekday()]}요일인데 "
              f"({m.group(3)})로 적혀 있습니다", file=sys.stderr)


def collect_talks(md: markdown.Markdown) -> list[dict]:
    """content/talks/ 의 파일을 이름 규칙으로 묶어 발표 목록을 만든다.

    규칙: 파일명 앞부분(확장자 뺀 이름)이 같으면 한 발표다.
        2026-06-22-knollmueller-imaging.md    → 초록·정보
        2026-06-22-knollmueller-imaging.pdf   → 슬라이드
        2026-06-22-knollmueller-imaging.jpg   → 사진 (-2, -3 으로 여러 장)
    파일명 맨 앞의 YYYY-MM-DD가 날짜이자 정렬 기준이다.
    .md 없이 슬라이드만 넣어도 목록에 나온다.
    """
    d = ROOT / "content" / "talks"
    if not d.is_dir():
        return []

    talks: dict[str, dict] = {}
    for f in sorted(d.rglob("*")):
        if not f.is_file() or f.name.startswith((".", "_")) or f.name == "README.md":
            continue
        ext = f.suffix.lower()
        stem = f.stem
        if ext in TALK_IMAGES:
            stem = re.sub(r"-\d+$", "", stem)  # 사진 여러 장
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(.+)$", stem)
        if not m:
            print(f"  ! 이름 규칙에 안 맞는 파일 무시: talks/{f.name}", file=sys.stderr)
            continue

        t = talks.setdefault(stem, {
            "slug": stem, "date": date(int(m[1]), int(m[2]), int(m[3])),
            "title": m[4].replace("-", " "), "slides": None, "images": [],
            "html": "", "meta": {}, "assets": [],
        })
        if ext == ".md":
            meta, body = split_front(f.read_text(encoding="utf-8"))
            md.reset()
            t["meta"] = meta
            t["html"] = md.convert(body) if body.strip() else ""
            t["title"] = meta.get("title", t["title"])
            check_talk_date(f.name, t["date"], meta.get("when"))
        elif ext in TALK_SLIDES:
            t["slides"] = f"/talks/files/{f.name}"
            t["assets"].append(f)
        elif ext in TALK_IMAGES:
            t["images"].append(f"/talks/files/{f.name}")
            t["assets"].append(f)

    out = []
    for t in talks.values():
        t["images"].sort()
        meta = t["meta"]
        out.append({**t,
                    "path": f"/talks/{t['slug']}",
                    "template": "talk.html",
                    # 슬라이드가 파일이 아니라 외부(구글 드라이브 등)에 있을 수 있다
                    "slides": t["slides"] or meta.get("slides_url"),
                    "speaker": meta.get("speaker"),
                    "affiliation": meta.get("affiliation"),
                    "when": meta.get("when"),
                    "where": meta.get("where"),
                    "mode": meta.get("mode"),
                    "banner": None,   # main()에서 /talks 규칙으로 채운다
                    "year": t["date"].year})
    out.sort(key=lambda t: t["date"], reverse=True)
    return out


def collect_newsletters() -> list[dict]:
    """newsletters.yaml + tools/newsletters.py가 만든 파일에서 소식지 목록을 만든다.

    PDF와 표지·썸네일은 repo에 들어 있다 — 구글 드라이브가 아니라 우리 사이트에서
    받아가게 하기 위함이다. 파일이 없는 호는 목록에서 조용히 빠진다.
    """
    conf_file = ROOT / "newsletters.yaml"
    files = ROOT / "content" / "newsletters" / "files"
    if not conf_file.exists() or not files.is_dir():
        return []
    conf = load_yaml(conf_file)
    out = []
    for issue in conf.get("issues", []):
        stem = str(issue["date"])
        pdf = files / f"{stem}.pdf"
        if not pdf.exists():
            print(f"  ! 소식지 {stem}: PDF가 없어 목록에서 제외", file=sys.stderr)
            continue
        cover, thumb = files / f"{stem}.jpg", files / f"{stem}_t.jpg"
        out.append({
            "date": stem,
            "label": issue.get("label") or stem.replace("-", "년 ") + "월",
            "pdf": f"/newsletters/files/{pdf.name}",
            "cover": f"/newsletters/files/{cover.name}" if cover.exists() else None,
            "thumb": f"/newsletters/files/{thumb.name}" if thumb.exists() else None,
            "size_mb": round(pdf.stat().st_size / 1024 / 1024, 1),
        })
    out.sort(key=lambda i: i["date"], reverse=True)
    return out


def talk_index(talks: list[dict]) -> list[dict]:
    years: list[dict] = []
    for t in talks:
        if not years or years[-1]["year"] != t["year"]:
            years.append({"year": t["year"], "entries": []})
        years[-1]["entries"].append(t)
    return years


def collect_meetings(meta_cfg: dict) -> list[dict]:
    """수확기 산출물에서 미팅 페이지를 읽어들인다."""
    inv_file = HARVEST / "inventory.json"
    if not inv_file.exists():
        print("  ! harvest/inventory.json 없음 — 미팅 페이지를 건너뜁니다", file=sys.stderr)
        return []
    inv = json.loads(inv_file.read_text(encoding="utf-8"))
    pages = []
    for p in inv["pages"]:
        path = p["path"].replace("/view/ska-korea", "") or "/"
        if not path.startswith("/meetings/"):
            continue
        html_file = HARVEST / "html" / f"{p['slug']}.html"
        if not html_file.exists():
            continue
        info = meta_cfg.get(path, {})
        ym = parse_title_date(p["title"])
        pages.append({
            "path": path,
            "title": info.get("title", p["title"]),
            "template": "meeting.html",
            "html": html_file.read_text(encoding="utf-8"),
            "source": "harvest",
            "origin": p["url"],
            "depth": p["depth"],
            "parent": "/" + (p["parent"] or ""),
            "subnav": [{"path": s["path"].replace("/view/ska-korea", ""), "title": s["title"]}
                       for s in p.get("subnav", [])],
            "year": ym[0] if ym else None,
            "month": ym[1] if ym else None,
            "when": info.get("when"),
            "where": info.get("where"),
            "category": info.get("category"),
            "status": info.get("status"),
            # 수확기가 판정한 배너. 하위 탭은 대표쪽 것을 물려받는다(main 참조).
            "banner_info": p.get("banner"),
            # meetings.yaml에서 손으로 덮어쓰는 문: poster | photo | none
            "banner_style": info.get("banner"),
            "banner_at": info.get("banner_at"),
        })
    # 날짜를 적어 둔 미팅은 그 날짜를 정렬 기준으로 삼는다.
    # 제목에서 뽑은 연·월(예: 'Nov 2023 EASKA')보다 정확하다.
    for p in pages:
        m = re.match(r"(\d{4})\.(\d{1,2})", p["when"] or "")
        if m:
            p["year"], p["month"] = int(m.group(1)), int(m.group(2))
    return pages


def date_range(start, end) -> str:
    """(2026-10-19, 2026-10-23) → '2026.10.19–23'. 달이 넘으면 '2023.10.30–11.03'."""
    if not start:
        return ""
    a = f"{start.year}.{start.month:02d}.{start.day:02d}"
    if not end or end == start:
        return a
    if (start.year, start.month) == (end.year, end.month):
        return f"{a}–{end.day:02d}"
    if start.year == end.year:
        return f"{a}–{end.month:02d}.{end.day:02d}"
    return f"{a}–{end.year}.{end.month:02d}.{end.day:02d}"


def collect_authored(md: markdown.Markdown, today: date) -> list[dict]:
    """meetings-src/ 의 새 형식 원고를 미팅 페이지로 읽어들인다.

    수확본과 달리 조판을 우리가 소유한다 — 단 배치·지도·PDF·일정표가 그래서 가능하다.
    (수확 방식과 당분간 나란히 돈다. 옮긴 미팅만 이쪽을 쓴다.)
    """
    root = ROOT / "meetings-src"
    if not root.is_dir():
        return []
    out = []
    for f in sorted(root.glob("*/meeting.md")):
        slug = f.parent.name
        meta, body = split_front(f.read_text(encoding="utf-8"))
        start, end = None, None
        if meta.get("dates"):
            got = re.findall(r"\d{4}-\d{2}-\d{2}", str(meta["dates"]))
            if got:
                start = date.fromisoformat(got[0])
                end = date.fromisoformat(got[-1])
        phase = ("past" if end and end < today else
                 "running" if start and end and start <= today <= end else "upcoming")
        ctx = {"today": today, "phase": phase, "slug": slug,
               # 미팅 페이지 기본 언어는 영어. 국내 워크숍만 lang: ko
               "lang": (meta.get("lang") or "en").lower()}

        def render_md(text, _md=md):
            _md.reset()
            return _md.convert(text)

        pages = meetingfmt.render(meetingfmt.parse(body), render_md, ctx)
        base = f"/meetings/{slug}"
        subnav = [{"path": base if i == 0 else f"{base}/{slugify(p['title'])}",
                   "title": p["title"]} for i, p in enumerate(pages)]
        for i, p in enumerate(pages):
            # 원고 안의 상대 경로(files/…)를 배포 경로로
            html_ = re.sub(r'((?:src|href)=")files/', rf'\1{base}/files/', p["html"])
            # 탭 간 상대 링크([Registration](registration))는 미팅 주소 기준으로.
            # 하위 탭은 /<slug>/<탭>/ 아래에 배포되므로 그대로 두면 한 층 더 파고든다.
            # `&`은 마크다운이 이메일 주소를 엔티티로 난독화한 것(&#109;… = mailto:…)이다.
            html_ = re.sub(r'(href=")(?!https?:|/|#|\.|&|mailto:|tel:)', rf'\1{base}/', html_)
            out.append({
                # 대표쪽은 미팅 이름을 제목으로 — 목록·<title>에 서는 것은 탭 이름('Home')이 아니다
                "path": subnav[i]["path"],
                "title": meta.get("title", slug) if i == 0 else p["title"],
                "template": "authored.html",
                "html": html_, "source": "authored", "depth": 2 if i == 0 else 3,
                "subnav": subnav, "meeting_title": meta.get("title", slug),
                "meeting_path": base, "meeting_sub": meta.get("subtitle"),
                "banner": f"{base}/files/{meta['banner']}" if meta.get("banner") else None,
                # 대문 그림(poster)이 기본. 조직위가 글자 없는 사진을 골랐으면
                # banner_style: photo — 사진은 얇은 띠로 깔고 제목은 우리 조판으로 그린다.
                "poster": bool(meta.get("banner")) and meta.get("banner_style") != "photo",
                "banner_at": meta.get("banner_at"),
                "when": date_range(start, end) or meta.get("dates"), "where": meta.get("venue"),
                "phase": phase, "start": start, "end": end,
                # meetings 목록에 세울지. 시험용 사본은 list: false 로 빼 둔다.
                "year": start.year if start else None,
                "month": start.month if start else None,
                "category": meta.get("category"), "status": None,
                "listed": meta.get("list", True),
                "assets": f.parent / "files", "meta": meta,
                "stats": ctx.get("stats"), "lang": ctx["lang"],
            })
        # Google Sites 시절의 하위 페이지 주소 → 새 탭 주소. 이미 배포된 링크를 깨뜨리지 않는다.
        # meeting.md frontmatter:  redirects: {옛-slug: 새-탭-slug}
        tabs = {slugify(s["title"]): s["path"] for s in subnav}
        for old, tab in (meta.get("redirects") or {}).items():
            out.append({"path": f"{base}/{old}", "title": meta.get("title", slug),
                        "template": "redirect.html", "target": tabs.get(str(tab)) or base,
                        "source": "authored", "depth": 4, "subnav": [],
                        "meeting_path": base, "listed": False, "year": None, "month": None})
    return out


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "page"


def parse_when(when: str | None, year: int, month: int) -> tuple[date, date]:
    """meetings.yaml의 'YYYY.MM.DD–DD' 같은 표기를 (시작일, 종료일)로.

    날짜가 적혀 있지 않으면 그 달 전체를 기간으로 본다.
    """
    default = (date(year, month or 1, 1), date(year, month or 1, 28))
    if not when:
        return default
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})\s*(?:[–~-]\s*(?:(\d{1,2})\.)?(\d{1,2}))?", when)
    if not m:
        return default
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        start = date(y, mo, d)
        end = date(y, int(m.group(4) or mo), int(m.group(5))) if m.group(5) else start
    except ValueError:
        return default
    return start, (end if end >= start else start)


def meeting_index(meetings: list[dict], today: date) -> dict:
    """미팅 목록을 연도별 역순으로 정리하고, 다가오는 일정을 뽑는다."""
    tops = [m for m in meetings if m["depth"] == 2 and m["year"]
            and m.get("listed", True)]
    tops.sort(key=lambda m: (m["year"], m["month"] or 0), reverse=True)

    upcoming = []
    for m in tops:
        start, end = parse_when(m.get("when"), m["year"], m["month"] or 1)
        if end >= today:
            m["upcoming"] = True
            m["dday"] = (start - today).days
            m["running"] = start <= today <= end
            upcoming.append(m)
    upcoming.sort(key=lambda m: (m["year"], m["month"] or 0))

    years: list[dict] = []
    for m in tops:
        if not years or years[-1]["year"] != m["year"]:
            years.append({"year": m["year"], "entries": []})
        years[-1]["entries"].append(m)
    return {"years": years, "upcoming": upcoming[:3], "count": len(tops)}


def render(env, pages, nav_cfg, site, extra=None):
    for p in pages:
        tpl = env.get_template(p["template"])
        nav = build_nav(nav_cfg, p["path"])
        html = link_targets(tpl.render(page=p, nav=nav, site=site, **(extra or {})))
        dest = OUT / (p["path"].strip("/") or ".") / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    cfg = load_yaml(ROOT / "site.yaml")
    site = cfg["site"]
    nav_cfg = cfg["nav"]
    meet_cfg = load_yaml(ROOT / "meetings.yaml") if (ROOT / "meetings.yaml").exists() else {}
    today = date.today()
    site["built"] = today.isoformat()
    # 스타일시트 주소에 내용 해시를 붙인다. 고치면 주소가 바뀌므로 방문자가
    # 옛 CSS를 붙들고 있는 일이 없다(GitHub Pages는 10분간 캐시하라고 응답한다).
    css = ROOT / "static" / "css" / "site.css"
    site["css_v"] = hashlib.sha1(css.read_bytes()).hexdigest()[:8] if css.exists() else ""

    md = markdown.Markdown(extensions=["extra", "attr_list", "toc", "sane_lists", "footnotes"])
    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.filters["sentences"] = sentences

    # _site 폴더 자체는 남기고 안의 것만 비운다.
    # 폴더를 지웠다 다시 만들면 Dropbox 무시 표시도 함께 사라져, 표시를 붙이기 전
    # 잠깐 사이에 동기화가 끼어들어 index.html이 밀려나는 일이 있었다.
    OUT.mkdir(parents=True, exist_ok=True)
    mark_dropbox_ignored(OUT)
    for child in OUT.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()

    imgs = image_map()
    banner_cfg = site.get("banners") or {}
    content = collect_content(md, banner_cfg)
    meetings = collect_meetings(meet_cfg.get("meetings", {}) if meet_cfg else {})
    authored = collect_authored(md, today)
    # 새 형식(meetings-src)으로 옮긴 미팅은 수확본을 쓰지 않는다 —
    # 같은 주소의 정본은 하나여야 한다. Google Sites 쪽은 폴백으로만 남는다.
    owned = {m["meeting_path"] for m in authored}
    meetings = [m for m in meetings
                if not any(m["path"] == b or m["path"].startswith(b + "/") for b in owned)]
    talks = collect_talks(md)
    for t in talks:
        t["banner"], t["banner_at"] = banner_for(t["path"], t["meta"], banner_cfg)
    newsletters = collect_newsletters()
    for p in content + meetings:
        p["html"] = fix_images(p["html"], imgs)
    meetings += authored
    index = meeting_index(meetings, today)

    # 미팅 하위 페이지는 상위 미팅의 서브탭을 물려받는다
    by_path = {m["path"]: m for m in meetings}
    for m in meetings:
        # 새 형식 미팅은 collect_authored가 이미 다 채워 두었다 — 수확본 뒷손질 대상이 아니다
        if m.get("source") == "authored":
            continue
        parent = by_path.get(m["parent"]) if m["depth"] == 3 else None
        if not m["subnav"] and parent:
            m["subnav"] = parent.get("subnav", [])
        # 하위 페이지 제목은 <title>보다 조직위가 붙인 탭 이름을 따른다.
        # Google Sites는 페이지를 이름만 바꿔도 주소가 그대로라 둘이 어긋나는 일이 흔하다.
        if m["depth"] == 3:
            label = next((t["title"] for t in m["subnav"] if t["path"] == m["path"]), None)
            if label:
                m["title"] = label

        # ── 배너 ────────────────────────────────────────────────
        # 그림은 대표쪽에만 내려받는다. 하위 탭은 같은 배너를 쓰므로 물려받는다.
        # 대표쪽의 날짜·장소·이름도 함께 물려받아 어느 탭에서나 같이 보이게 한다.
        head = parent or m
        info = head.get("banner_info") or {}
        key = info.get("image")
        m["banner"] = f"/img/{imgs[key]}" if key and key in imgs else None
        m["banner_at"] = m.get("banner_at") or head.get("banner_at")
        m["poster"] = bool(info.get("poster"))
        m["meeting_title"] = head["title"]
        m["meeting_path"] = head["path"]
        if parent:
            m["when"], m["where"] = m["when"] or parent["when"], m["where"] or parent["where"]

        # meetings.yaml이 있으면 그것이 이긴다 — 자동 판정이 틀렸을 때의 문
        style = m.get("banner_style") or (parent or {}).get("banner_style")
        if style == "none":
            m["banner"], m["poster"] = None, False
        elif style == "photo":
            m["poster"] = False
        elif style == "poster":
            m["poster"] = True
        if m["poster"] and not m["banner"]:
            m["poster"] = False   # 그림이 없으면 대문 배너를 만들 수 없다

    link_cfg = load_yaml(ROOT / "links.yaml") if (ROOT / "links.yaml").exists() else {}
    media_cfg = load_yaml(ROOT / "media.yaml") if (ROOT / "media.yaml").exists() else {}
    # 언론 보도는 늘 최신이 위다. yaml에 적은 순서와 무관하게 여기서 세운다.
    articles = sorted((media_cfg or {}).get("articles", []),
                      key=lambda a: str(a.get("date") or ""), reverse=True)
    shared = {"meetings": index, "talks": talks, "talk_years": talk_index(talks),
              # 가장 최근 발표는 목록 위에 초록까지 펼쳐 보여 준다(소식지 최신호와 같은 결).
              # 그래서 아래 연대기는 그것을 뺀 나머지다 — 같은 발표를 두 번 싣지 않는다.
              "talk_years_rest": talk_index(talks[1:]),
              "newsletters": newsletters,
              "linkgroups": (link_cfg or {}).get("groups", []),
              "articles": articles}
    render(env, content, nav_cfg, site, shared)
    render(env, meetings, nav_cfg, site, shared)
    render(env, talks, nav_cfg, site, shared)

    # 정적 자산
    shutil.copytree(ROOT / "static", OUT / "static", dirs_exist_ok=True)

    # 수확한 그림은 **실제로 쓰인 것만** 배포한다. harvest/images에는 지금 이 사이트가
    # 그리지 않는 쪽의 그림도 남아 있다 — 본문 페이지는 content/로 옮겨 왔지만 수확기는
    # 여전히 그 쪽들을 훑기 때문이다. 통째로 복사하면 아무도 보지 않는 25 MB가 30분마다
    # 함께 배포된다. 렌더된 HTML이 가리키는 것만 세면 빠뜨릴 일이 없다.
    src_img = HARVEST / "images"
    kept_img = skipped_img = 0
    if src_img.exists():
        used: set[str] = set()
        for f in OUT.rglob("*.html"):
            used |= set(re.findall(r"/img/([\w.-]+)", f.read_text(encoding="utf-8")))
        dest_img = OUT / "img"
        dest_img.mkdir(parents=True, exist_ok=True)
        for f in src_img.iterdir():
            if not f.is_file():
                continue
            if f.name in used:
                shutil.copy2(f, dest_img / f.name)
                kept_img += 1
            else:
                skipped_img += 1
    # 새 형식 미팅의 첨부(배너·사진·PDF)
    for m in authored:
        src = m.get("assets")
        if src and Path(src).is_dir() and m["depth"] == 2:
            shutil.copytree(src, OUT / m["meeting_path"].strip("/") / "files", dirs_exist_ok=True)

    # 발표 첨부(슬라이드·사진)를 원래 파일명 그대로 배포한다
    files = OUT / "talks" / "files"
    for t in talks:
        for src in t["assets"]:
            files.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, files / src.name)

    # 맞춤 도메인. site.yaml의 site.domain을 채우면 산출물에 CNAME이 들어간다.
    # ⚠️ 채우는 순간 그 도메인으로 배포되므로, DNS를 GitHub으로 돌린 뒤에만 채울 것.
    #    (검수 중에는 비워 둬야 ska-korea.github.io로 볼 수 있다.)
    if site.get("domain"):
        (OUT / "CNAME").write_text(site["domain"] + "\n", encoding="utf-8")
        print(f"  CNAME → {site['domain']}")

    # 소식지 PDF·표지 배포
    src_nl = ROOT / "content" / "newsletters" / "files"
    if src_nl.is_dir():
        shutil.copytree(src_nl, OUT / "newsletters" / "files", dirs_exist_ok=True)

    total = len(content) + len(meetings) + len(talks)
    print(f"빌드 완료: {total}쪽 (본문 {len(content)} · 미팅 {len(meetings)} · 발표 {len(talks)}) → {OUT}")
    print(f"  미팅 {index['count']}건 · 다가오는 일정 {len(index['upcoming'])}건 · "
          f"발표 {len(talks)}건 · 소식지 {len(newsletters)}호")
    if skipped_img:
        print(f"  수확 그림 {kept_img}개 배포 · 쓰이지 않아 뺀 것 {skipped_img}개")

    if args.serve:
        import os
        os.chdir(OUT)
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", args.port), handler) as httpd:
            print(f"\n미리보기: http://localhost:{args.port}/  (Ctrl+C로 종료)")
            httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
