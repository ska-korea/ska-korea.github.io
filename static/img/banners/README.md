# 페이지 배너 배경 사진

본문 페이지(미팅이 아닌 쪽)의 상단 배너에 까는 사진. 어느 쪽에 어느 사진을 쓰는지는
`site.yaml`의 `site.banners`에서 정하고, 개별 원고의 frontmatter `banner:`로 덮어쓸 수 있다.

## 출처

대부분은 **이용조건이 확인된 SKAO 배경 모음**에서 가져왔다. 원본은 repo 밖의
`~/Dropbox/Works/SKA/4-ska-korea/homepage/confirmed-background-images/`에 있다.

| 파일 | 내용 | 쓰이는 곳 | 원본 |
|---|---|---|---|
| `sunset-array.jpg` | SKA-Low 안테나와 SKA-Mid 접시의 노을 실루엣 | 첫 화면 | `TOP_BANNER.jpg` |
| `ska-site-day.jpg` | SKA 관측소 전경(주간) | 기본값 — Links·Contacts 등 | `Ska_landscape_day_v1.jpg` |
| `two-telescopes.jpg` | 두 망원경을 한 장에 담은 드론 합성 | `/ska-korea/*` | `MID_LOW_DRONE_COMPOSITE_2.jpg` |
| `science-goals.jpg` | SKAO 과학목표 배너 | `/science/*` | `SCI_GOALS_BANNER_1.png` |
| `global-network.jpg` | 지구와 연결망 | `/src/*` | `BACKGROUND_IMAGE_FLAT_v3.jpg` |
| `ska-korea-workshop.jpg` | 2025 SKA-Korea Fall Workshop 단체사진 | `/meetings` | `IMG_6907.JPG` |

아래 둘은 **기존 홈페이지(`ska.kasi.re.kr`)가 그 페이지 배너로 쓰던 사진**을 그대로 옮긴
것이다. 같은 사이트의 새 판이라 이용조건이 새로 생기지 않는다. 확인된 모음에 이 자리에
맞는 사진이 없어 남겨 두었다 — 대체할 사진이 생기면 바꾸면 된다.

| 파일 | 내용 | 쓰이는 곳 |
|---|---|---|
| `talks-hall.jpg` | 발표장 | `/talks` |
| `newsletter-group.jpg` | 2024 Winter 워크숍 단체사진 | `/newsletters` |

### 확인된 모음에서 쓰지 않은 것

| 파일 | 쓰지 않은 이유 |
|---|---|
| `eso0932a.jpeg` | 평균 휘도 0.012로 너무 어두워 네이비 덮개 아래에서 단색과 구별되지 않는다. CC BY 4.0이라 **크레딧(ESO/S. Brunier)을 화면에 띄워야** 하는 것도 배너에는 부담 |
| `Maria_Grazia_SKALow.png` | 인물이 크게 식별되고 1000px로 작다. 얇게 베면 몸통만 남아 조판이 어색하다 |
| `SKA-Low_construction_camp.jpg` | 쓸 만하나 지금 마땅한 자리가 없다. 필요하면 바로 쓸 수 있다 |

## 가공

가로 최대 1920px로 축소, JPEG 품질 82 · progressive. 원본은 최대 9883px·22 MB였다.

## 미팅 페이지는 여기를 쓰지 않는다

미팅 배너는 조직위원회가 Google Sites에서 고른 그림을 **수확기가 자동으로 가져온다**
(`harvest/images/<slug>_banner.jpg`). 조직위가 배너를 갈아 끼우면 새 사이트도 따라 바뀐다.

## 새 사진을 넣을 때

- 가로 1920px 이하, 300KB 안팎으로 줄여서 넣는다.
- 배너는 네이비 그라디언트를 덮어 글자를 얹으므로 **어둡고 대비가 낮은 사진**이 잘 맞는다.
  덮개는 흰 하늘(휘도 1.0)까지 감당하도록 계산해 두었으니 밝아도 글자는 읽히지만,
  **너무 어두운 사진은 덮개에 먹혀 단색 네이비와 구별되지 않는다**(평균 휘도 0.03 이하면 위험).
- 배너는 사진의 **가운데를 얇게 베어** 쓴다. 담을 것이 아래쪽에 있으면
  `{file: …, at: "center 70%"}`로 벨 자리를 내린다.
- 출처와 이용조건을 위 표에 함께 적는다. 조건이 확인되지 않은 사진은 넣지 않는다.
