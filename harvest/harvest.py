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
    상단 메뉴(role=navigation)·푸터는 이 컨테이너 밖이라 자연히 제외된다.
    (주의: role="banner"는 상단 검색줄이지 페이지 배너가 아니다 — 아래 참조.)

★ 첫 섹션은 배너다 (2026-08-17 실측으로 확정):
    본문 컨테이너의 첫 <section>은 언제나 '페이지 배너' — 배경 그림 위에 페이지
    제목을 얹은 구역이다. 44쪽 전수 확인 결과 예외가 없었다. 새 사이트는 제목을
    우리 조판으로 다시 그리므로 이 섹션은 본문에서 빼고, 배경 그림만 따로 거둔다.
    거두지 않으면 미팅 본문이 제목을 한 번 더 되풀이한다.
    조직위원회가 만든 대문 그림(EASKA 2023·SPARCS XIV)은 그림만 있고 글자가 없어,
    '배경 있고 글자 0자'로 자동 판별된다 → poster.

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

# 배너 판정·가공
BANNER_TEXT_MAX = 150   # 첫 섹션 글자가 이보다 많으면 배너가 아니라 본문으로 본다
BANNER_MAX_W = 1920     # 화면에서 쓰는 폭. 원본은 7008px·2.5MB짜리도 있다
BANNER_BACKDROP = (7, 0, 104)   # SKAO 네이비 #070068 — 반투명 배너를 여기에 합성한다


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


def banner_of(sec: Tag) -> dict | None:
    """첫 섹션이 페이지 배너면 그 배경 그림 주소와 제목 글자를 돌려준다.

    배너로 보는 조건 — 셋을 모두 만족해야 한다. 본문 구역을 배너로 잘못 보고
    통째로 버리는 것이 가장 큰 위험이라, 조건을 좁게 건다.
      1. 배경 그림(background-image)이 있다
      2. 글자가 BANNER_TEXT_MAX 이하다 (실측 최대 62자 — 페이지 제목뿐이다)
      3. <img>·<iframe>이 없다 (있으면 본문 구역이다)
    글자가 하나도 없으면 조직위원회가 만든 대문 그림(poster)으로 본다.
    """
    url = None
    for t in sec.find_all(style=True):
        m = re.search(r"url\(([^)]+)\)", t["style"])
        if m:
            url = m.group(1).strip("'\" ")
            break
    if not url or not url.startswith("http"):
        return None
    if sec.find("img") or sec.find("iframe"):
        return None
    text = re.sub(r"\s+", " ", sec.get_text(" ", strip=True))
    if len(text) > BANNER_TEXT_MAX:
        return None
    return {"url": url, "text": text, "poster": not text}


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

    # 배경 이미지도 내려받아 로컬 경로로 바꾼다.
    # ★ Google의 서명 URL은 같은 이미지라도 요청할 때마다 값이 달라진다. 그대로 두면
    #   내용이 하나도 안 바뀐 날에도 매 수확이 '변경'으로 잡혀 30분마다 커밋·재배포가 돈다.
    for t in node.find_all(style=True):
        def swap(m):
            url = m.group(1).strip("'\" ")
            if not url.startswith("http"):
                return m.group(0)
            key = f"{slug_of(page_path)}_bg{len(images):02d}"
            images[key] = url
            return f"url(images/{key})"
        new = re.sub(r"url\(([^)]+)\)", swap, t["style"])
        if new != t["style"]:
            t["style"] = new

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


def wants_banner_image(path: str) -> bool:
    """배너 그림을 실제로 내려받을 페이지인가.

    미팅 대표쪽(깊이 2)만 받는다. 하위 탭은 같은 배너를 쓰므로 빌드가 부모 것을
    물려받게 하고, 본문 페이지 배너는 우리가 static/img/banners/에서 고른다.
    """
    rel = path[len(SITE):].strip("/").split("/")
    return len(rel) == 2 and rel[0] == "meetings"


def harvest_page(path: str, session: requests.Session, images: dict, banners: dict,
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
    slug = slug_of(path)

    # 첫 섹션이 배너면 본문에서 뺀다. 섹션이 하나뿐인 쪽은 건드리지 않는다 —
    # 그 하나가 본문일 수 있고, 배너를 지우면 남는 게 없다.
    banner = banner_of(sections[0]) if len(sections) > 1 else None
    banner_key = None
    if banner:
        sections = sections[1:]
        if wants_banner_image(path):
            banner_key = f"{slug}_banner"
            banners[banner_key] = banner["url"]

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
        # 배너. image는 실제로 내려받은 쪽에만 있고, 하위 탭은 빌드가 부모 것을 물려받는다.
        # ★ 구글 주소는 요청마다 값이 달라지므로 절대 남기지 않는다(헛커밋의 원인).
        "banner": ({"image": banner_key, "text": banner["text"],
                    "poster": banner["poster"]} if banner else None),
    }, found)


def download_images(images: dict, session: requests.Session, refresh: bool = False) -> tuple[int, int]:
    """없는 이미지만 내려받는다.

    이미지 키는 페이지·순서에서 만들어지므로, 본문이 그대로면 키도 그대로다.
    이미 받아 둔 파일을 30분마다 다시 받을 이유가 없다.
    조직위가 같은 자리의 사진만 바꿔 끼운 경우에는 --refresh-images로 다시 받는다.
    """
    ok, skipped = 0, 0
    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
               "image/webp": ".webp", "image/svg+xml": ".svg"}
    have = {f.stem for f in IMG_DIR.iterdir() if f.is_file()} if IMG_DIR.exists() else set()
    for key, url in images.items():
        if key in have and not refresh:
            skipped += 1
            continue
        try:
            r = session.get(url, headers={"User-Agent": UA}, timeout=30)
            r.raise_for_status()
            ext = ext_map.get(r.headers.get("content-type", "").split(";")[0], ".bin")
            (IMG_DIR / f"{key}{ext}").write_bytes(r.content)
            ok += 1
        except Exception as e:
            print(f"  ! 이미지 실패 {key}: {e}", file=sys.stderr)
    return ok, skipped


def shrink(raw: bytes) -> bytes:
    """배너 그림을 화면에서 쓰는 폭으로 줄여 JPEG로 담는다.

    ★ 반투명한 배너는 네이비 위에 미리 합성한다. 새 사이트에서 배너가 놓이는 자리는
      언제나 네이비 바탕이므로(.pagehead·.posterhead) 브라우저가 할 합성을 미리 해 두는
      것일 뿐, 보이는 그림은 같다. 알파를 살리려고 PNG로 담으면 같은 그림이
      1.3 MB가 된다(실측) — JPEG로는 200 KB다.

    Pillow가 없으면 원본을 그대로 둔다 — 수확이 멈추는 것보다 낫다.
    같은 입력에 같은 출력이 나와야 한다(헛커밋 방지). Pillow의 인코딩은 결정적이다.
    """
    try:
        import io
        from PIL import Image
    except ImportError:
        return raw
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, BANNER_BACKDROP)
                bg.paste(im, mask=im.getchannel("A"))
                im = bg
            else:
                im = im.convert("RGB")
            if im.width > BANNER_MAX_W:
                im = im.resize((BANNER_MAX_W, round(im.height * BANNER_MAX_W / im.width)),
                               Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=86, optimize=True, progressive=True)
            return buf.getvalue()
    except Exception as e:
        print(f"  ! 배너 가공 실패, 원본 사용: {e}", file=sys.stderr)
        return raw


def download_banners(banners: dict, session: requests.Session) -> tuple[int, int, int]:
    """배너 그림은 매번 새로 받아, 내용이 달라졌을 때만 저장한다.

    본문 그림과 달리 '이미 있으면 건너뛰기'를 쓸 수 없다. 배너 키는 페이지마다
    고정(<slug>_banner)이라 조직위원회가 그림을 갈아 끼워도 키가 그대로다. 배너 교체는
    눈에 바로 보이는 변화라 놓치면 안 된다. 받는 쪽 수가 미팅 대표쪽뿐이라 부담도 적다.

    구글이 이따금 403을 돌려준다(연달아 같은 서명 주소를 부를 때). 한 번 쉬었다 다시
    부르고, 그래도 안 되면 **직전 파일을 그대로 둔다** — 못 받았다고 배너를 지우지 않는다.
    """
    changed, same, failed = 0, 0, 0
    for key, url in sorted(banners.items()):
        data = None
        for attempt in range(2):
            try:
                r = session.get(url, headers={"User-Agent": UA}, timeout=60)
                r.raise_for_status()
                data = shrink(r.content)
                break
            except Exception as e:
                if attempt:
                    print(f"  ! 배너 실패 {key}: {e} — 직전 그림을 그대로 둡니다",
                          file=sys.stderr)
                else:
                    time.sleep(2)
        if data is None:
            failed += 1
            continue
        dest = IMG_DIR / f"{key}.jpg"
        # 예전에 다른 확장자로 담았던 파일이 남아 있으면 치운다(같은 키가 둘로 남지 않게)
        for old in IMG_DIR.glob(f"{key}.*"):
            if old != dest:
                old.unlink()
        if dest.exists() and dest.read_bytes() == data:
            same += 1
            continue
        dest.write_bytes(data)
        changed += 1
    return changed, same, failed


def prune_images(banner_keys: set[str]) -> int:
    """어느 페이지에서도 참조하지 않는 그림 파일을 지운다.

    본문 그림의 키는 '페이지 + 등장 순서'라 원고가 바뀌면 번호가 밀린다. 치우지 않으면
    쓰이지 않는 파일이 저장소에 계속 쌓인다. 판단 기준은 인벤토리가 아니라 **디스크에
    남아 있는 html이 실제로 가리키는 것** — 갱신을 보류한 페이지가 옛 키를 쓰고 있어도
    안전하다.
    """
    used = set(banner_keys)
    for f in HTML_DIR.glob("*.html"):
        used |= set(re.findall(r"images/([\w.-]+)", f.read_text(encoding="utf-8")))
    gone = 0
    for f in IMG_DIR.iterdir():
        if f.is_file() and f.stem not in used:
            f.unlink()
            gone += 1
    return gone


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="경로에 이 문자열이 포함된 페이지만 수확")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--refresh-images", action="store_true",
                    help="이미 받아 둔 이미지도 다시 내려받는다")
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
    banners: dict[str, str] = {}
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
            info, found = harvest_page(path, session, images, banners, prev,
                                       guard=not args.no_guard)
            results.append(info)
            flag = f"  서브탭{len(info['subnav'])}" if info["subnav"] else ""
            if info["banner"] and info["banner"]["poster"]:
                flag += "  대문그림"
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
        got, skipped = download_images(images, session, args.refresh_images)
        print(f"\n이미지 {len(images)}개 — 새로 받음 {got} · 이미 있음 {skipped}")
    if not args.no_images and banners:
        ch, same, failed = download_banners(banners, session)
        print(f"배너 {len(banners)}개 — 바뀜 {ch} · 그대로 {same}"
              + (f" · 못 받음 {failed}(직전 그림 유지)" if failed else ""))

    # 페이지 수가 크게 줄면 발견 자체가 망가진 것이다 — 아무것도 덮어쓰지 않고 멈춘다.
    if prev_count and len(results) < prev_count * 0.8:
        print(f"\n✗ 중단: 발견 페이지가 {prev_count} → {len(results)}로 급감했습니다. "
              f"내비게이션 구조 변경이 의심됩니다. 기존 내용은 그대로 두었습니다.", file=sys.stderr)
        return 2

    results.sort(key=lambda r: r["path"])
    # ★ 구글 이미지 URL은 요청마다 값이 달라지므로 여기에 남기지 않는다.
    #   남기면 내용이 그대로여도 매 수확이 '변경'으로 잡혀 헛커밋이 돈다.
    #   빌드는 images/ 폴더를 직접 읽으므로 이 목록에 URL이 필요하지도 않다.
    (OUT / "inventory.json").write_text(
        json.dumps({"pages": results, "failures": failures,
                    "images": sorted(images)},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    held = [r for r in results if r["held"]]
    if not args.no_images:
        gone = prune_images(set(banners))
        if gone:
            print(f"쓰이지 않는 그림 {gone}개 정리")

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
