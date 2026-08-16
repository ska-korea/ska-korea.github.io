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
import sys
from datetime import date
from pathlib import Path

import markdown
import yaml
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


def collect_content(md: markdown.Markdown) -> list[dict]:
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
        pages.append({
            "path": meta.get("path", path),
            "title": meta.get("title", f.stem),
            "sub": meta.get("sub"),
            "template": meta.get("template", "page.html"),
            "html": md.convert(body) if body.strip() else "",
            "meta": meta,
            "source": "content",
        })
    return pages


TALK_SLIDES = {".pdf", ".pptx", ".key"}
TALK_IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


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
                    "year": t["date"].year})
    out.sort(key=lambda t: t["date"], reverse=True)
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
            "status": info.get("status"),
        })
    return pages


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
    tops = [m for m in meetings if m["depth"] == 2 and m["year"]]
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
        html = tpl.render(page=p, nav=nav, site=site, **(extra or {}))
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

    md = markdown.Markdown(extensions=["extra", "attr_list", "toc", "sane_lists"])
    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.filters["sentences"] = sentences

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    imgs = image_map()
    content = collect_content(md)
    meetings = collect_meetings(meet_cfg.get("meetings", {}) if meet_cfg else {})
    talks = collect_talks(md)
    for p in content + meetings:
        p["html"] = fix_images(p["html"], imgs)
    index = meeting_index(meetings, today)

    # 미팅 하위 페이지는 상위 미팅의 서브탭을 물려받는다
    by_path = {m["path"]: m for m in meetings}
    for m in meetings:
        if not m["subnav"] and m["depth"] == 3:
            m["subnav"] = by_path.get(m["parent"], {}).get("subnav", [])
        # 하위 페이지 제목은 <title>보다 조직위가 붙인 탭 이름을 따른다.
        # Google Sites는 페이지를 이름만 바꿔도 주소가 그대로라 둘이 어긋나는 일이 흔하다.
        if m["depth"] == 3:
            label = next((t["title"] for t in m["subnav"] if t["path"] == m["path"]), None)
            if label:
                m["title"] = label

    shared = {"meetings": index, "talks": talks, "talk_years": talk_index(talks)}
    render(env, content, nav_cfg, site, shared)
    render(env, meetings, nav_cfg, site, shared)
    render(env, talks, nav_cfg, site, shared)

    # 정적 자산
    shutil.copytree(ROOT / "static", OUT / "static", dirs_exist_ok=True)
    if (HARVEST / "images").exists():
        shutil.copytree(HARVEST / "images", OUT / "img", dirs_exist_ok=True)
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

    total = len(content) + len(meetings) + len(talks)
    print(f"빌드 완료: {total}쪽 (본문 {len(content)} · 미팅 {len(meetings)} · 발표 {len(talks)}) → {OUT}")
    print(f"  미팅 {index['count']}건 · 다가오는 일정 {len(index['upcoming'])}건 · 발표 {len(talks)}건")

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
