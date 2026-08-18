# SKA Korea 홈페이지

한국 SKA 커뮤니티 홈페이지(`ska.kasi.re.kr`)의 소스입니다.
Python으로 정적 HTML을 만들어 GitHub Pages로 배포합니다.

## 원고가 세 갈래인 이유

| 무엇 | 누가 고치나 | 어디에 있나 |
|---|---|---|
| 본문 페이지 (SKA·Science·SRC·Links…) | 관리자 | `content/**/*.md` |
| **미팅 페이지 (새 형식)** | **각 모임 조직위원회(LOC)** | 별도 저장소 [`ska-korea/meetings`](https://github.com/ska-korea/meetings) — CI가 `meetings-src/`로 받아온다 |
| 미팅 페이지 (아직 안 옮긴 것) | 각 모임 조직위원회(LOC) | **Google Sites** → `harvest/`로 자동 수확 |

새 형식으로 옮긴 미팅(SPARCS XIV · 2026 SKA Korea Summer Workshop)은
`ska-korea/meetings` 저장소의 원고가 정본이며,
**같은 주소의 수확본은 빌드에서 자동으로 빠집니다**(저장소에서 폴더를 빼면 수확본으로 되돌아옵니다).
원고를 별도 저장소에 두는 이유는 LOC가 매번 바뀌므로 **권한을 사이트 코드와 떼어 놓기** 위함입니다.
쓰는 방법은 그 저장소의 README(5분 안내서)에 있습니다.

아직 안 옮긴 미팅은 지금까지처럼 조직위원회가 [Google Sites](https://sites.google.com/view/ska-korea)에서
직접 만들고 고칩니다. 30분마다 자동으로 본문만 가져와 이 사이트의 머리·꼬리를 입혀 보여줍니다.
어느 쪽이든 반영까지 최대 1시간으로 안내하세요.

Google Sites의 상단 메뉴·푸터는 가져오지 않습니다. 본문과 **배너 그림**만 옮겨옵니다.

**배너 그림도 조직위원회가 정합니다.** Google Sites 페이지 맨 위에 깔아 둔 그림을 그대로 가져옵니다.
글자 없이 그림만 있는 배너(조직위원회가 만든 대문 그림)는 그 그림이 페이지 머리가 되고,
그 아래 하위 탭, 다시 그 아래에 제목이 놓입니다. 사진 위에 제목을 글자로 얹은 배너는
사진만 배경으로 쓰고 제목은 이 사이트 조판으로 다시 그립니다.
자동 판정이 어긋나면 `meetings.yaml`에 `banner: poster` 또는 `photo`, `none`으로 적으세요.
새 형식 원고에서는 `meeting.md`의 frontmatter에 `banner_style: photo`로 적습니다.

## 폴더

```
build.py            빌드 — content/ + harvest/ → _site/
harvest/harvest.py  수확 — Google Sites에서 미팅 본문 가져오기
import_content.py   기존 홈페이지 본문을 content/로 옮기는 1회성 도구

site.yaml           사이트 제목·내비게이션·자료 창구·수치·배너·**문의처**
meetings.yaml       미팅 목록에 쓰는 날짜·장소
links.yaml          자료 창구(Links) 목록 — 갈래·사진·링크
media.yaml          언론 보도 목록 — 날짜·언론사·제목·기사 주소·사진
content/            본문 원고 (Markdown)
content/talks/      발표 — 파일명 규칙으로 자동 구성 (README 참조)
templates/          Jinja2 템플릿
static/             CSS·이미지
static/img/banners/ 본문 페이지 배너 사진 (어느 쪽에 무엇을 쓰는지는 site.yaml, 출처는 그 폴더 README)
harvest/            수확 결과 (자동 생성, 커밋됨)
```

## 자주 하는 일

**문의처를 늘리려면** `site.yaml`의 `site.contacts`에 항목을 더하세요. 템플릿·CSS는 손댈 필요 없습니다.

```yaml
- topic: 새 사안 이름
  what: 한 줄 설명.
  people:
    - {name: 이름, email: 주소@kasi.re.kr}
  # 메일 말고 다른 창구가 있을 때만
  # actions: [{label: 버튼 이름, url: "https://…", note: 곁들일 설명}]
```

**자료 창구를 늘리려면** `links.yaml`에 항목을 더하세요. 갈래를 새로 만들면 사진은
`static/img/links/`에 넣습니다(가로 1400px 이하). 링크는 **줄 전체**가 눌리고 주소는
화면에 나오지 않으므로, `label`만 보고도 어디로 가는지 알 수 있게 적으세요.

**언론 보도를 추가하려면** `media.yaml`에 다섯 줄을 더하고, 대표 사진을
`static/img/media/`에 넣으세요(가로 720px 정도, 파일명은 `날짜-언론사.jpg`).
카드는 **날짜 역순으로 자동 정렬**되므로 적는 위치는 상관없습니다. 사진이 없으면
`image:`를 빼면 됩니다 — 언론사 이름이 들어간 판으로 대신 나옵니다.

홈페이지 수정 요청 양식은 `.github/ISSUE_TEMPLATE/homepage-request.yml`입니다.

## 로컬에서 작업하기

```bash
pip install -r requirements.txt

# 미팅 원고는 별도 저장소 — 한 번만 받아 두면 된다 (없으면 수확본만으로 빌드된다)
git clone git@github.com:ska-korea/meetings.git meetings-src

python build.py --serve      # http://localhost:8000 에서 미리보기
python build.py              # _site/ 로 빌드만
```

미팅 내용까지 새로 받아오려면:

```bash
cd harvest && python harvest.py
```

## 배포

`main`에 push하면 GitHub Actions가 빌드해서 배포합니다.
30분마다 같은 워크플로가 미팅을 수확하고, 바뀐 게 있으면 커밋한 뒤 다시 배포합니다.

### 수확 안전장치

Google이 Sites 마크업을 바꾸면 추출이 조용히 망가질 수 있습니다. 그래서:

- 어떤 페이지의 본문이 **직전의 절반 아래로 줄면** 갱신을 보류하고 **직전 내용을 그대로 둡니다.**
- 발견한 페이지 수가 **직전의 80% 아래로 떨어지면** 아무것도 덮어쓰지 않고 멈춥니다.
- 두 경우 모두 Actions 로그에 경고가 남습니다. **빈 페이지가 게시되는 일은 없습니다.**

조직위원회가 실제로 내용을 지운 경우라면 보류가 잘못된 것이므로, 한 번만 이렇게 돌립니다:

```bash
cd harvest && python harvest.py --no-guard
```

### 수확은 결정적이어야 합니다

내용이 안 바뀌었으면 수확 결과도 한 글자도 바뀌지 않아야 합니다. 그래야 헛커밋과 헛배포가 돌지 않습니다.
Google이 이미지에 붙이는 주소는 요청할 때마다 값이 달라지므로, 이미지는 모두 내려받아
로컬 경로로 고정하고 그 주소를 기록에 남기지 않습니다.

**수확기를 손댔다면 반드시 이 시험을 하세요** — 두 번 돌려서 결과가 같아야 합니다.

```bash
cd harvest
python harvest.py && cp -R html /tmp/h1 && cp inventory.json /tmp/inv1.json
python harvest.py
diff -rq /tmp/h1 html && diff -q /tmp/inv1.json inventory.json && echo OK
```

이미 받아 둔 이미지는 다시 받지 않습니다. 조직위가 같은 자리의 사진만 바꿔 끼웠다면:

```bash
cd harvest && python harvest.py --refresh-images
```

### 알아둘 것

- **예약 실행은 저장소가 60일간 조용하면 GitHub이 자동으로 끕니다.** 오래 손대지 않았다면
  Actions 탭에서 다시 켜세요. (봇 커밋은 활동으로 쳐주지 않을 수 있습니다.)
- 맞춤 도메인(`ska.kasi.re.kr`)은 **DNS를 GitHub으로 돌린 뒤에** `site.yaml`의 `site.domain`을 채웁니다.
  먼저 채우면 아직 Google을 가리키는 주소로 배포되어 검수를 할 수 없습니다.

## 라이선스

정해지지 않았습니다. 이미지 일부는 SKAO·CSIRO·SARAO·CARTA 등 제3자 자료이며 각 출처의 조건을 따릅니다.
