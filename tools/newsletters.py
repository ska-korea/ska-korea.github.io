#!/usr/bin/env python
"""소식지 PDF를 내려받고 표지·썸네일 이미지를 만든다.

newsletters.yaml에 호를 적고 이것을 한 번 돌리면 끝난다.
산출물은 repo에 커밋해서 GitHub에서 직접 받아가게 한다(구글 드라이브 의존 제거).

    content/newsletters/files/2026-04.pdf     내려받은 원본
    content/newsletters/files/2026-04.jpg     첫 쪽 전체 (최신호 표지용)
    content/newsletters/files/2026-04_t.jpg   썸네일 (지난호 목록용)

썸네일은 첫 쪽에서 **가장 큰 사진**을 찾아 그 부분을 잘라낸다.
첫 쪽을 통째로 줄이면 글씨만 빽빽해 무엇에 관한 호인지 알아볼 수 없기 때문이다.
자동으로 고른 자리가 마음에 안 들면 newsletters.yaml의 crop에 좌표를 적으면 된다.

사용법:
    python tools/newsletters.py            # 없는 것만 처리
    python tools/newsletters.py --force    # 전부 다시
"""

import argparse
import io
import sys
from pathlib import Path

import fitz  # PyMuPDF
import requests
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "content" / "newsletters" / "files"
CONF = ROOT / "newsletters.yaml"

COVER_W = 1000      # 최신호 표지 가로 픽셀
THUMB_W = 720       # 썸네일 가로 픽셀
THUMB_RATIO = 4 / 3  # 썸네일 가로:세로


def download(file_id: str, dest: Path, session: requests.Session) -> None:
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    r = session.get(url, timeout=120)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise RuntimeError("PDF가 아님 — 공유 설정이 '링크가 있는 모든 사용자'인지 확인")
    dest.write_bytes(r.content)


def main_photo_rect(page: fitz.Page) -> fitz.Rect | None:
    """첫 쪽에서 가장 큰 사진의 위치. 너무 작으면 None."""
    best = None
    for img in page.get_images(full=True):
        for rect in page.get_image_rects(img[0]):
            if best is None or rect.get_area() > best.get_area():
                best = rect
    if best is None:
        return None
    # 쪽 넓이의 5%도 안 되는 것은 로고·아이콘이다
    if best.get_area() < page.rect.get_area() * 0.05:
        return None
    return best


def thumb_box(page: fitz.Page, crop) -> fitz.Rect:
    """썸네일로 쓸 영역을 정한다."""
    if crop:
        return fitz.Rect(*crop)
    box = main_photo_rect(page)
    if box is None:
        # 사진을 못 찾으면 제호가 있는 윗부분을 쓴다
        box = fitz.Rect(page.rect.x0, page.rect.y0,
                        page.rect.x1, page.rect.y0 + page.rect.height * 0.42)
    # 가로:세로를 맞추되 쪽 밖으로 나가지 않게 한다
    cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
    w = max(box.width, box.height * THUMB_RATIO)
    w = min(w, page.rect.width)
    h = min(w / THUMB_RATIO, page.rect.height)
    w = h * THUMB_RATIO
    x0 = min(max(page.rect.x0, cx - w / 2), page.rect.x1 - w)
    y0 = min(max(page.rect.y0, cy - h / 2), page.rect.y1 - h)
    return fitz.Rect(x0, y0, x0 + w, y0 + h)


def render(page: fitz.Page, dest: Path, width: int, clip: fitz.Rect | None = None) -> None:
    src = clip or page.rect
    zoom = width / src.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    img.save(dest, "JPEG", quality=82, optimize=True, progressive=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="이미 있는 것도 다시 처리")
    args = ap.parse_args()

    conf = yaml.safe_load(CONF.read_text(encoding="utf-8"))
    issues = sorted(conf["issues"], key=lambda i: str(i["date"]), reverse=True)
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    for n, issue in enumerate(issues):
        stem = str(issue["date"])
        pdf, cover, thumb = OUT / f"{stem}.pdf", OUT / f"{stem}.jpg", OUT / f"{stem}_t.jpg"
        try:
            if not issue.get("id"):
                if not pdf.exists():
                    raise RuntimeError(f"id가 없는데 {pdf.name} 도 없다 — 파일을 넣어 둘 것")
            elif args.force or not pdf.exists():
                download(issue["id"], pdf, session)
            if args.force or not cover.exists() or not thumb.exists():
                with fitz.open(pdf) as doc:
                    page = doc[0]
                    render(page, cover, COVER_W)
                    render(page, thumb, THUMB_W, thumb_box(page, issue.get("crop")))
            mark = "최신호" if n == 0 else ""
            print(f"  {stem}  {issue['label']:<14} "
                  f"{pdf.stat().st_size // 1024:>6} KB  {mark}")
        except Exception as e:
            print(f"  ! {stem} 실패: {e}", file=sys.stderr)

    total = sum(f.stat().st_size for f in OUT.iterdir()) // 1024 // 1024
    print(f"\n{len(issues)}호 · {total} MB → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
