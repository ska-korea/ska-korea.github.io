# 발표(Talks) 추가하는 법

이 폴더에 **파일명 규칙에 맞게 파일을 넣기만 하면** 목록과 개별 페이지가 자동으로 만들어집니다.
빌드 스크립트를 고칠 필요도, 목록에 등록할 필요도 없습니다.

## 파일명 규칙

```
YYYY-MM-DD-발표자-주제.확장자
```

**앞부분(확장자 뺀 이름)이 같은 파일은 한 발표로 묶입니다.**

```
2026-06-18-knollmueller-imaging-to-inference.md     ← 초록 + 발표 정보
2026-06-18-knollmueller-imaging-to-inference.pdf    ← 슬라이드
2026-06-18-knollmueller-imaging-to-inference.jpg    ← 사진
2026-06-18-knollmueller-imaging-to-inference-2.jpg  ← 사진 둘째 장
2026-06-18-knollmueller-imaging-to-inference-3.jpg  ← 셋째 장 …
```

- 맨 앞 `YYYY-MM-DD`가 **날짜이자 정렬 기준**입니다. 목록은 최신순으로 자동 정렬됩니다.
- 발표자·주제 부분은 영문 소문자와 하이픈을 쓰세요. **주소(URL)가 되기 때문입니다.**
  위 예시는 `ska.kasi.re.kr/talks/2026-06-18-knollmueller-imaging-to-inference`가 됩니다.
- 확장자가 역할을 정합니다:
  `.md` 초록 · `.pdf` `.pptx` `.key` 슬라이드 · `.jpg` `.png` `.webp` `.gif` 사진
- 규칙에 안 맞는 파일은 무시되고, 빌드할 때 경고가 뜹니다.
- ★ **파일명 날짜와 아래 `when`이 어긋나면 빌드가 알려 줍니다.** 날짜가 두 곳에 적히는데
  (파일명은 정렬·주소를, `when`은 화면에 보이는 값을 정합니다) 갈라져도 화면은 멀쩡해
  보이기 때문입니다. 요일이 틀린 것도 함께 잡습니다.

## .md 파일 쓰는 법

맨 위 `---` 사이가 발표 정보이고, 그 아래가 초록입니다.

```markdown
---
title: "From Imaging to Inference: Probabilistic Reconstruction of Physical Systems"
speaker: Jakob Knollmüller
affiliation: Max Planck Institute for Astrophysics
when: "6월 18일(화) 오후 4시"
where: 장영실홀 331-2
mode: offline
---

초록을 여기에 씁니다. 문단은 빈 줄로 나눕니다.
**굵게**, *기울임*, [링크](https://example.com) 모두 됩니다.
```

| 항목 | 필수 | 설명 |
|---|---|---|
| `title` | 권장 | 없으면 파일명에서 만들어 씁니다. **콜론(`:`)이 들어가면 반드시 따옴표로 감싸세요.** |
| `speaker` | | 발표자 이름 |
| `affiliation` | | 소속 |
| `when` | | 실제 일시. 없으면 파일명의 날짜를 씁니다 |
| `where` | | 장소 |
| `mode` | | `offline` · `online` · `hybrid` |
| `slides_url` | | 슬라이드가 파일이 아니라 **구글 드라이브 등 외부**에 있을 때 |

## 최소한으로 넣기

슬라이드 하나만 넣어도 목록에는 나옵니다. 제목은 파일명에서 만들어 쓰니
나중에 `.md`를 추가해 초록을 채우면 됩니다.

```
2026-09-10-hong-src-tutorial.pdf
```

## 확인

```
python build.py --serve
```

`http://localhost:8000/talks` 에서 결과를 봅니다.
