# 미팅 홈페이지 만들기

조직위원회(LOC)가 미팅 홈페이지를 만드는 방법입니다. **5분이면 다 읽습니다.**

미팅 하나가 **파일 하나**입니다. 글은 평범한 글로 쓰고, 표·지도·사진첩처럼 손이 많이 가는
것만 정해진 표시를 씁니다. 나머지 조판은 저희가 맡습니다.

```
meetings-src/
  2026-10-sparcs-xiv/
    meeting.md      ← 여기에 다 씁니다
    files/          ← 사진·PDF·로고를 넣습니다
```

---

## 1. 맨 위에 미팅 정보

```yaml
---
title:    SPARCS XIV
subtitle: The SKAO Awakens
dates:    2026-10-19 ~ 2026-10-23
venue:    Seoul MICE Plaza, Seoul, South Korea
banner:   banner.jpg
---
```

`dates`만 정확히 적으면 **끝난 뒤 모습으로 저절로 바뀝니다.** 등록 폼이 닫히고, 지난 마감일이
회색이 되고, 상단에 "이 모임은 …에 끝났습니다"가 붙습니다. 끝나고 아무것도 안 하셔도 됩니다.

## 2. 제목으로 쪽을 나눕니다

| 표시 | 뜻 |
|---|---|
| `# Program` | **하위 탭**이 하나 생깁니다 (Home · Program · Registration …) |
| `## 등록비` | 그 쪽 안의 단락 제목 |
| `### 세부` | 소제목 |

글은 그냥 쓰시면 됩니다. `**굵게**`, `- 목록`, `[링크](주소)` 정도만 아시면 충분합니다.

## 3. 손이 많이 가는 것들

표시는 `::: 이름` 으로 열고 `:::` 로 닫습니다.

### 일정표 — 시각은 저절로 계산됩니다

```
::: program
2026-10-19 | 09:30 | Day 1
  session Session 1 | chair 강혜성
  10 | 손봉원 | KASI | Opening
  25 | Tessa Vernstrom | CSIRO | SPARCS: where we stand
  break 20
  20 | Alec Thomson | SKAO | SKA continuum surveys | slides=thomson.pdf
:::
```

**날짜줄에 시작시각을 한 번 적고, 나머지는 걸리는 시간(분)만 적습니다.**
`09:30–09:40`, `09:40–10:05`, 휴식, `10:25–10:45` … 를 저희가 계산합니다.
가운데 발표 하나가 길어져도 **그 줄의 숫자만 고치면 뒤가 전부 따라옵니다.**

- 시각을 직접 박고 싶으면 `10:00-10:30 | …` 처럼 적어도 됩니다.
- `slides=파일명` 을 적어 두면 **미팅이 끝난 뒤에** 슬라이드 링크가 나타납니다.
- `swg=…` 로 발표 주제를 달아 두면 통계에 잡힙니다(선택).

### 사람 목록 — 정렬은 저희가 합니다

```
::: people sort=speaker,name as=grid stats=yes
Bong Won Sohn | KASI | speaker staff
Wonki Lee | Yonsei | postdoc
Minji Kim | KASI | student
Dahee Lee | Chosun
:::
```

- 순서대로 안 적으셔도 됩니다. `sort=name`(이름순) · `sort=speaker,name`(발표자 먼저).
- 셋째 칸은 선택입니다. 역할(`speaker` `chair`)과 직급(`student` `postdoc` `staff` `other`)을
  함께 적을 수 있습니다.
- `as=grid`(여러 단) / `as=list`(한 줄씩). 인원수는 저절로 붙습니다.
- **참가자 명단에만** `stats=yes` 를 다세요 — 아래 구성 통계가 그 목록에서 나옵니다.

### 마감일 — 지난 것은 저절로 물러납니다

```
::: deadlines
2026-05-31 | Abstract submission closes
2026-08-31 | Registration & payment deadline
:::
```

상자에 담기고 **Important Dates** 제목이 저절로 붙습니다.
제목을 바꾸려면 `::: deadlines title=주요_일정` (빈칸은 `_`), 없애려면 `title=none`.

### 상자로 묶어 강조

```
::: card title=Confirmed_Invited_Speakers accent=yes
::: people sort=name as=grid count=no
Alec Thomson | SKAO
:::
:::
```

`accent=yes` 를 빼면 수수한 상자가 됩니다. 참석 여부를 좌우하는 정보(초청연사 같은)를
눈에 띄게 둘 때 쓰세요.

### 지도 · PDF · 등록 폼

```
::: map
Seoul MICE Plaza, 143 Magokjungang-ro, Gangseo-gu, Seoul, Korea
:::

::: pdf files/programme.pdf | label=프로그램
:::

::: form https://docs.google.com/forms/d/e/…/viewform
:::
```

주소만 적으면 지도가 뜹니다. PDF는 `files/`에 넣으면 그 자리에서 펼쳐집니다.
**등록 폼은 미팅이 끝나면 저절로 닫힙니다.**

### 후원 기관 로고

```
::: logos
KASI | files/logo-kasi.png | https://www.kasi.re.kr
KAIST | files/logo-kaist.png
:::
```

높이를 맞춰 한 줄에 세웁니다. 크기를 맞추실 필요 없습니다.

### 사진첩 — 미팅이 끝난 뒤

```
::: gallery
files/photo-01.jpg | 개회사
files/photo-02.jpg
:::
```

캡션은 안 쓰셔도 됩니다. 그러면 사진만 나옵니다.

### 구성 통계

```
::: stats
:::
```

이 한 줄이면 참가자 명단과 일정표에서 **소속별·직급별 구성**을 스스로 뽑습니다.
따로 세지 않으셔도 됩니다.

## 4. 화면을 두세 단으로

```
::: split 2:1
왼쪽에 들어갈 글 (2칸)
---
![캡션](files/사진.jpg)
:::
```

`2:1`, `1:1`, `1:1:1` 처럼 비율을 적습니다. `---` 가 단을 나눕니다.
좁은 화면에서는 저절로 한 단으로 접힙니다.

**안에 다른 표시를 넣어도 됩니다** — 왼쪽에 초청연사 `people`, 오른쪽에 SOC `people` 처럼.

---

## 자주 걸리는 것

- **목록 안에 목록을 두 단계 이상 넣지 마세요.** 문단이 엉겨 붙습니다.
  `###` 소제목으로 나누는 편이 낫습니다.
- 사진·PDF는 반드시 `files/` 안에 두고 `files/이름.jpg` 로 가리키세요.
- `:::` 를 닫는 것을 잊지 마세요. 안에 다른 `:::` 가 있으면 그것도 각각 닫아야 합니다.
- 잘 모르겠으면 **`test-sparcs-xiv/meeting.md` 를 통째로 복사해** 고쳐 쓰세요.

막히면 [연락처](https://ska.kasi.re.kr/contacts)로 물어보세요.
