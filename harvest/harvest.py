#!/usr/bin/env python
"""SKA Korea Google Sites 수확기.

게시된 Google Sites를 재귀 순회하며 각 페이지의 본문만 추출해
(1) 정제된 HTML, (2) 검토용 마크다운, (3) 인벤토리 JSON으로 저장한다.

본문 추출 앵커 (2026-08-16 실측으로 확정):
    Google Sites 페이지 본문은 <section> 여러 개로 나뉘고, 그 전체를 감싸는
    컨테이너 div 하나가 있다. role="main"은 '첫 섹션'에만 붙으므로 그것만
    가져오면 본문 대부분을 잃는다. 따라서
        role="main"  →  상위 <section>  →  그 부모(=본문 컨테이너)
    를 앵커로 삼고 그 안의 <section>을 순서대로 모은다.
    이 규칙은 표준 속성·태그만 쓰므로 난독화된 클래스명(UtePc 등)에 의존하지 않는다.
    상단 메뉴(role=navigation)·배너(role=banner)·푸터는 이 컨테이너 밖이라 자연히 제외된다.

사용법:
    python harvest.py                  # 전체 수확
    python harvest.py --only meetings  # 경로에 'meetings'가 든 페이지만
"""

import argparse
import json
import re
import sys
import time
from collections import deque
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

BASE = "https://sites.google.com"
SITE = "/view/ska-korea"
HOME = f"{BASE}{SITE}/home"

OUT = Path(__file__).resolve().parent
HTML_DIR = OUT / "html"
MD_DIR = OUT / "text"
IMG_DIR = OUT / "images"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 남길 속성. class는 Google 난독화 클래스라 버리고, style은 정렬·글꼴을 담고 있어 살린다.
KEEP_ATTRS = {"href", "src", "alt", "title", "style", "colspan", "rowspan",
              "target", "rel", "id", "width", "height"}


def fetch(url: str, session: requests.Session) -> str:
    r = session.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text


def norm(href: str) -> str | None:
    """사이트 내부 링크면 정규화된 경로를, 아니면 None을 반환."""
    href = href.split("?")[0].split("#")[0].rstrip("/")
    if href.startswith(BASE + SITE):
        href = href[len(BASE):]
    if href == SITE or href.startswith(SITE + "/"):
        return href
    return None


def slug_of(path: str) -> str:
    """/view/ska-korea/meetings/oct-2026-sparcs-xiv -> meetings__oct-2026-sparcs-xiv"""
    rel = path[len(SITE):].strip("/")
    return rel.replace("/", "__") or "home"


def body_container(soup: BeautifulSoup) -> Tag | None:
    main = soup.find(attrs={"role": "main"})
    if main is None:
        return None
    sec = main.find_parent("section")
    if sec is None:
        return main.parent
    return sec.parent


def is_sibling_subnav(sec: Tag, page_path: str) -> list[dict] | None:
    """미팅 하위 탭처럼 '형제 페이지 링크만으로 이루어진' 섹션이면 그 링크 목록을 반환.

    새 사이트는 페이지 계층에서 서브탭을 직접 생성하므로 이런 섹션은 중복이다.
    오탐을 막기 위해 '모든 링크가 같은 부모 경로 아래'일 때만 서브내비로 본다.
    """
    links = sec.find_all("a", href=True)
    if len(links) < 2:
        return None
    parent = page_path.rsplit("/", 1)[0]
    items = []
    for a in links:
        p = norm(a["href"])
        if p is None or not (p.startswith(parent + "/") or p == parent):
            return None
        items.append({"path": p, "title": a.get_text(strip=True)})
    # 링크 밖 텍스트가 거의 없어야 한다
    link_text = sum(len(a.get_text(strip=True)) for a in links)
    all_text = len(sec.get_text(strip=True))
    if all_text and link_text / all_text < 0.8:
        return None
    return items


def clean(node: Tag, page_path: str, images: dict) -> None:
    """Google Sites 마크업을 새 사이트에 이식 가능한 형태로 정제한다(제자리 수정)."""
    for t in node.find_all(["script", "style", "noscript"]):
        t.decompose()
    # 제목 옆 '링크 복사' 버튼 등 내용 없는 UI 위젯
    for t in node.find_all(attrs={"jscontroller": True}):
        if not t.get_text(strip=True) and not t.find("img"):
            t.decompose()

    for t in node.find_all(True):
        for attr in list(t.attrs):
            if attr in KEEP_ATTRS or attr.startswith("aria-"):
                continue
            del t[attr]

    # Google Sites 원고에는 Arial·Roboto·Lato 같은 글꼴이 인라인으로 박혀 온다.
    # 이 사이트의 글꼴은 Noto Sans KR 하나이므로 글꼴 지정만 걷어낸다.
    # (정렬·굵기 등 나머지 인라인 스타일은 원고의 뜻이므로 그대로 둔다.)
    for t in node.find_all(style=True):
        st = re.sub(r"font-family\s*:[^;]*;?", "", t["style"]).strip().strip(";").strip()
        if st:
            t["style"] = st
        else:
            del t["style"]

    for img in node.find_all("img", src=True):
        src = img["src"]
        if src.startswith("//"):
            src = "https:" + src
        if not src.startswith("http"):
            continue
        key = f"{slug_of(page_path)}_{len(images):02d}"
        images[key] = src
        img["src"] = f"images/{key}"
        img["loading"] = "lazy"

    for a in node.find_all("a", href=True):
        p = norm(a["href"])
        if p is not None:
            a["href"] = "/" + p[len(SITE):].strip("/")


def to_markdown(node: Tag) -> str:
    """검토용 마크다운. 완벽한 변환이 아니라 '내용을 읽고 판단'하기 위한 것."""
    out: list[str] = []

    def inline(n) -> str:
        if isinstance(n, NavigableString):
            return re.sub(r"\s+", " ", str(n))
        if not isinstance(n, Tag):
            return ""
        inner = "".join(inline(c) for c in n.children)
        if n.name in ("b", "strong"):
            return f"**{inner.strip()}**" if inner.strip() else ""
        if n.name in ("i", "em"):
            return f"*{inner.strip()}*" if inner.strip() else ""
        if n.name == "a":
            return f"[{inner.strip()}]({n.get('href','')})" if inner.strip() else ""
        if n.name == "img":
            return f"![{n.get('alt','')}]({n.get('src','')})"
        if n.name == "br":
            return "\n"
        return inner

    def walk(n, depth=0):
        if isinstance(n, NavigableString):
            txt = re.sub(r"\s+", " ", str(n)).strip()
            if txt:
                out.append(txt)
            return
        if not isinstance(n, Tag):
            return
        name = n.name
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            out.append(f"\n{'#' * int(name[1])} {inline(n).strip()}\n")
        elif name == "p":
            txt = inline(n).strip()
            if txt:
                out.append(txt + "\n")
        elif name in ("ul", "ol"):
            for i, li in enumerate(n.find_all("li", recursive=False), 1):
                bullet = "-" if name == "ul" else f"{i}."
                out.append(f"{'  ' * depth}{bullet} {inline(li).strip()}")
            out.append("")
        elif name == "table":
            for tr in n.find_all("tr"):
                cells = [inline(td).strip() for td in tr.find_all(["td", "th"])]
                out.append("| " + " | ".join(cells) + " |")
            out.append("")
        elif name == "img":
            out.append(f"![{n.get('alt','')}]({n.get('src','')})")
        elif name == "iframe":
            out.append(f"[EMBED] {n.get('src','')}")
        elif name == "hr":
            out.append("\n---\n")
        else:
            for c in n.children:
                walk(c, depth + 1)

    for c in node.children:
        walk(c)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def harvest_page(path: str, session: requests.Session, images: dict,
                 prev: dict[str, int], guard: bool = True) -> tuple[dict, list[str]]:
    url = BASE + path
    soup = BeautifulSoup(fetch(url, session), "lxml")

    tt = soup.find("title")
    full = tt.get_text(strip=True) if tt else ""
    title = full.split(" - ", 1)[1] if " - " in full else full

    # 이 페이지에서 새로 발견되는 내부 링크 (하위 페이지는 부모 페이지에서만 노출된다)
    found = []
    for a in soup.find_all("a", href=True):
        p = norm(a["href"])
        if p:
            found.append(p)

    cont = body_container(soup)
    if cont is None:
        raise RuntimeError("role='main'을 찾지 못함 — Google Sites 마크업 변경 의심")

    sections = cont.find_all("section", recursive=False) or [cont]
    subnav: list[dict] = []
    kept: list[Tag] = []
    for sec in sections:
        nav = is_sibling_subnav(sec, path)
        if nav:
            subnav = nav
            continue
        if not sec.get_text(strip=True) and not sec.find("img") and not sec.find("iframe"):
            continue  # 여백용 빈 섹션
        kept.append(sec)

    for sec in kept:
        clean(sec, path, images)

    body_html = "\n".join(f'<section class="gs-section">{s.decode_contents()}</section>'
                          for s in kept)
    body_md = "\n\n".join(to_markdown(s) for s in kept)
    text_chars = sum(len(re.sub(r"\s+", " ", s.get_text(" ", strip=True))) for s in kept)

    slug = slug_of(path)

    # ── 안전장치 ────────────────────────────────────────────────
    # Google이 마크업을 바꾸면 추출이 조용히 망가질 수 있다. 그때 빈 페이지를
    # 게시하는 대신 직전 스냅샷을 그대로 둔다. 사람이 내용을 지운 경우라면
    # --no-guard로 한 번 돌리면 반영된다.
    was = prev.get(path, 0)
    shrunk = guard and was > 200 and text_chars < was * 0.5
    if shrunk:
        print(f"  ⚠ 본문 급감으로 갱신 보류: {path} ({was}자 → {text_chars}자)", file=sys.stderr)
    else:
        (HTML_DIR / f"{slug}.html").write_text(body_html, encoding="utf-8")
        (MD_DIR / f"{slug}.md").write_text(
            f"# {title}\n\n<!-- 원본: {url} -->\n\n{body_md}\n", encoding="utf-8")

    rel = path[len(SITE):].strip("/")
    return ({
        "path": path, "url": url, "slug": slug, "title": title,
        "held": shrunk, "prev_chars": was,
        "depth": len(rel.split("/")) if rel else 0,
        "parent": "/".join(rel.split("/")[:-1]) or None,
        "sections": len(kept),
        # 보류했으면 디스크에 남은 건 옛 내용이다. 그 값을 기록해야 다음 회차에도
        # 같은 기준으로 비교된다(망가진 값을 새 기준으로 삼지 않는다).
        "text_chars": was if shrunk else text_chars,
        "fetched_chars": text_chars,
        "html_bytes": len(body_html), "subnav": subnav,
    }, found)


def download_images(images: dict, session: requests.Session) -> int:
    ok = 0
    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
               "image/webp": ".webp", "image/svg+xml": ".svg"}
    for key, url in images.items():
        try:
            r = session.get(url, headers={"User-Agent": UA}, timeout=30)
            r.raise_for_status()
            ext = ext_map.get(r.headers.get("content-type", "").split(";")[0], ".bin")
            (IMG_DIR / f"{key}{ext}").write_bytes(r.content)
            ok += 1
        except Exception as e:
            print(f"  ! 이미지 실패 {key}: {e}", file=sys.stderr)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="경로에 이 문자열이 포함된 페이지만 수확")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--no-guard", action="store_true",
                    help="본문이 줄어도 그대로 반영(원본에서 실제로 지운 경우)")
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()

    for d in (HTML_DIR, MD_DIR, IMG_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # 직전 회차 기록 — 안전장치의 비교 기준
    prev: dict[str, int] = {}
    prev_count = 0
    inv_file = OUT / "inventory.json"
    if inv_file.exists():
        old = json.loads(inv_file.read_text(encoding="utf-8"))
        prev = {p["path"]: p.get("text_chars", 0) for p in old.get("pages", [])}
        prev_count = len(old.get("pages", []))

    session = requests.Session()
    images: dict[str, str] = {}
    results, failures = [], []
    seen = {norm(HOME)}
    queue = deque(seen)

    while queue:
        path = queue.popleft()
        if args.only and args.only not in path:
            # 순회는 계속하되 저장은 건너뛴다
            try:
                soup = BeautifulSoup(fetch(BASE + path, session), "lxml")
                for a in soup.find_all("a", href=True):
                    p = norm(a["href"])
                    if p and p not in seen:
                        seen.add(p); queue.append(p)
            except Exception:
                pass
            time.sleep(args.delay)
            continue
        try:
            info, found = harvest_page(path, session, images, prev, guard=not args.no_guard)
            results.append(info)
            flag = f"  서브탭{len(info['subnav'])}" if info["subnav"] else ""
            if info["held"]:
                flag += "  ⚠보류"
            print(f"  [{len(results):2d}] {info['title'][:42]:<42} "
                  f"{info['sections']:>2}섹션 {info['fetched_chars']:>6}자{flag}")
            for p in found:
                if p not in seen:
                    seen.add(p); queue.append(p)
        except Exception as e:
            failures.append({"page": path, "error": str(e)})
            print(f"  [!!] 실패 {path}: {e}", file=sys.stderr)
        time.sleep(args.delay)

    if not args.no_images and images:
        print(f"\n이미지 {len(images)}개 내려받는 중...")
        print(f"  성공 {download_images(images, session)}/{len(images)}")

    # 페이지 수가 크게 줄면 발견 자체가 망가진 것이다 — 아무것도 덮어쓰지 않고 멈춘다.
    if prev_count and len(results) < prev_count * 0.8:
        print(f"\n✗ 중단: 발견 페이지가 {prev_count} → {len(results)}로 급감했습니다. "
              f"내비게이션 구조 변경이 의심됩니다. 기존 내용은 그대로 두었습니다.", file=sys.stderr)
        return 2

    results.sort(key=lambda r: r["path"])
    (OUT / "inventory.json").write_text(
        json.dumps({"pages": results, "failures": failures, "images": images},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    held = [r for r in results if r["held"]]
    total = sum(r["text_chars"] for r in results)
    print(f"\n완료: 성공 {len(results)} / 실패 {len(failures)} / 본문 총 {total:,}자")
    if held:
        print(f"⚠ 본문 급감으로 갱신을 보류한 페이지 {len(held)}건 "
              f"— 원본에서 실제로 지운 것이라면 --no-guard로 다시 실행하세요:", file=sys.stderr)
        for r in held:
            print(f"    {r['path']}  {r['prev_chars']}자 → {r['fetched_chars']}자", file=sys.stderr)
    return 1 if (failures or held) else 0


if __name__ == "__main__":
    sys.exit(main())
