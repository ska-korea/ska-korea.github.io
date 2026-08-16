#!/usr/bin/env python
"""수확한 기존 홈페이지 본문을 content/ 원고로 한 번에 옮긴다 (1회성 이관 도구).

미팅 페이지는 계속 Google Sites에서 관리하므로 제외한다.
옮긴 뒤에는 content/ 의 마크다운이 정본이며, 사람이 손으로 다듬는다.

사용법:
    python import_content.py           # 없는 파일만 생성
    python import_content.py --force   # 기존 원고를 덮어씀
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
HARVEST = ROOT / "harvest"
CONTENT = ROOT / "content"

# 페이지별 부제 — 목록·머리에 쓰인다. 비워두면 부제 없이 렌더된다.
SUBS = {
    "/ska-korea/ska": "하나의 관측소, 두 대의 망원경, 세 대륙",
    "/ska-korea/ska-korea": "한국의 SKA 참여를 잇는 연구자 모임",
    "/ska-korea/ska-in-korean-media": "국내 언론에 소개된 SKA",
    "/science": "SKA로 무엇을 밝힐 수 있는가",
    "/science/ska-science-working-groups": "주제별 국제 연구 모임과 국내 참여",
    "/science/data-archives": "선행망원경 관측 자료를 받는 곳",
    "/src": "SKA 자료가 연구자에게 닿는 길",
    "/src/srcnet-overview": "지역센터 네트워크는 어떻게 작동하는가",
    "/src/data-resources": "쓸 수 있는 자료와 자원",
    "/src/using-srcnet": "접속부터 분석까지",
    "/src/korea-src": "한국 SKA 지역센터(KRSRC)",
    "/src/tutorials": "한글 실습 자료",
    "/newsletters": "SKA Korea 소식지",
    "/talks": "지난 모임의 발표 자료",
    "/links": "자주 쓰는 자료 창구",
    "/contacts": "문의처",
}


def clean(md: str) -> str:
    lines, out = md.split("\n"), []
    for ln in lines:
        if ln.startswith("<!-- 원본:"):
            continue
        # Google Sites 목록이 남긴 과도한 들여쓰기
        ln = re.sub(r"^\s{4,}([-*]|\d+\.)\s", r"\1 ", ln)
        out.append(ln.rstrip())
    text = "\n".join(out)
    # 첫 제목 두 개(파일 제목 + 페이지 안 제목)는 머리말이 대신하므로 뺀다
    text = re.sub(r"\A(\s*#\s+.*\n+){1,2}", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    inv = json.loads((HARVEST / "inventory.json").read_text(encoding="utf-8"))
    made, skipped = 0, 0

    for p in inv["pages"]:
        path = p["path"].replace("/view/ska-korea", "") or "/"
        if path.startswith("/meetings") or path == "/home":
            continue
        src = HARVEST / "text" / f"{p['slug']}.md"
        if not src.exists():
            continue

        dest = CONTENT / (path.strip("/") + ".md")
        if dest.exists() and not args.force:
            skipped += 1
            continue

        body = clean(src.read_text(encoding="utf-8"))
        meta = {"title": p["title"], "path": path}
        if SUBS.get(path):
            meta["sub"] = SUBS[path]
        front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()

        dest.parent.mkdir(parents=True, exist_ok=True)
        note = "" if body else "\n<!-- 원본이 비어 있습니다. 내용을 새로 씁니다. -->\n"
        dest.write_text(f"---\n{front}\n---\n\n{body}{note}\n", encoding="utf-8")
        made += 1
        print(f"  {path:<44} {len(body):>6}자")

    print(f"\n이관 완료: 생성 {made} · 건너뜀 {skipped}")
    if skipped:
        print("  (이미 있는 원고는 두었습니다. 덮어쓰려면 --force)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
