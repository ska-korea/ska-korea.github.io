# SKA Korea 홈페이지

한국 SKA 커뮤니티 홈페이지(`ska.kasi.re.kr`)의 소스입니다.
Python으로 정적 HTML을 만들어 GitHub Pages로 배포합니다.

## 원고가 두 갈래인 이유

| 무엇 | 누가 고치나 | 어디에 있나 |
|---|---|---|
| 본문 페이지 (SKA·Science·SRC·Links…) | 관리자 | `content/**/*.md` |
| **미팅 페이지** | **각 모임 조직위원회(LOC)** | **Google Sites** → `harvest/`로 자동 수확 |

미팅 홈페이지는 지금까지처럼 조직위원회가 [Google Sites](https://sites.google.com/view/ska-korea)에서
직접 만들고 고칩니다. 30분마다 자동으로 본문만 가져와 이 사이트의 머리·꼬리를 입혀 보여줍니다.
**조직위원회는 아무것도 새로 배울 필요가 없습니다.** 반영까지 최대 1시간으로 안내하세요.

Google Sites의 상단 메뉴·배너·푸터는 가져오지 않습니다. 본문만 옮겨옵니다.

## 폴더

```
build.py            빌드 — content/ + harvest/ → _site/
harvest/harvest.py  수확 — Google Sites에서 미팅 본문 가져오기
import_content.py   기존 홈페이지 본문을 content/로 옮기는 1회성 도구

site.yaml           사이트 제목·내비게이션·자료 창구·수치
meetings.yaml       미팅 목록에 쓰는 날짜·장소
content/            본문 원고 (Markdown)
content/talks/      발표 — 파일명 규칙으로 자동 구성 (README 참조)
templates/          Jinja2 템플릿
static/             CSS·이미지
harvest/            수확 결과 (자동 생성, 커밋됨)
```

## 로컬에서 작업하기

```bash
pip install -r requirements.txt

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

### 알아둘 것

- **예약 실행은 저장소가 60일간 조용하면 GitHub이 자동으로 끕니다.** 오래 손대지 않았다면
  Actions 탭에서 다시 켜세요. (봇 커밋은 활동으로 쳐주지 않을 수 있습니다.)
- 맞춤 도메인(`ska.kasi.re.kr`)은 **DNS를 GitHub으로 돌린 뒤에** `site.yaml`의 `site.domain`을 채웁니다.
  먼저 채우면 아직 Google을 가리키는 주소로 배포되어 검수를 할 수 없습니다.

## 라이선스

정해지지 않았습니다. 이미지 일부는 SKAO·CSIRO·SARAO·CARTA 등 제3자 자료이며 각 출처의 조건을 따릅니다.
