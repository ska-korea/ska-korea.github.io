---
title: Using SRCNet
path: /src/using-srcnet
sub: SKA 자료로 연구하려는 천문학자를 위한 접근·분석·협업 안내
wide: true
---

## 시작하기

<ol class="steps">
<li><b>계정 준비</b>SKA 자원에 쓰는 공통 계정으로 SRCNet에 접근합니다. 자원은 개인이 아니라 <b>프로젝트나 팀 단위</b>로 할당됩니다.</li>
<li><b>자료 검색·발견</b>과학 게이트웨이에서 좌표나 조건으로 자료를 찾습니다. 내려받지 않고 미리보기로 확인할 수 있습니다.</li>
<li><b>자료 곁에서 분석</b>노트북·컨테이너·워크플로 도구로 자료가 놓인 노드에서 바로 분석하고 시각화합니다. 표준 처리에는 워크플로 템플릿을 씁니다.</li>
<li><b>협업과 발행</b>워크플로·자료·코드를 팀과 공유하고, 최종 산출물을 저장·발행하며 DOI로 연결합니다.</li>
</ol>

<div class="callout">
<span class="eyebrow">기본 전제</span>
SRCNet은 <strong>서버에서 분석하는 방식</strong>이 기본입니다. 대용량 자료를 밖으로 내려받지 않고, 분석을 자료가 있는 곳에서 실행합니다.
</div>

## 어떤 분석을 할 수 있나

SKA 과학 사례를 바탕으로 필요한 기능이 설계되고 있습니다. 대표적인 작업들입니다.

<div class="cards">
<div class="card"><h3>이미지·큐브 시각화</h3><p>연속파와 스펙트럼선 큐브를 대화형으로 보고, 적률 지도와 위치-속도 다이어그램을 만듭니다.</p></div>
<div class="card"><h3>천체 검출</h3><p>연속파·스펙트럼선 천체를 자동으로 찾아(예: PyBDSF·SoFiA) 카탈로그를 만듭니다.</p></div>
<div class="card"><h3>편광·회전측정 분석</h3><p>회전측정(RM) 합성처럼 계산이 많이 드는 작업을 GPU 가속으로 수행합니다.</p></div>
<div class="card"><h3>카탈로그 교차 매칭</h3><p>SKA 카탈로그를 다파장 아카이브와 맞대어 보고(예: TOPCAT), VO로 연동합니다.</p></div>
<div class="card"><h3>펄서·일과성 천체</h3><p>펄서 타이밍, 분산 보정과 접기, 단일 펄스·주기 탐색 진단을 수행합니다.</p></div>
<div class="card"><h3>재이온화·우주론</h3><p>21cm 파워 스펙트럼, 2점·3점 상관함수 같은 대규모 통계 분석을 실행합니다.</p></div>
</div>

## 지금부터 연습할 수 있습니다

<div class="split">
<div class="panel">
<h3>SKA 자료가 나오기 전에</h3>
<ul>
<li><b>과학 자료 챌린지(SDC)</b>의 모의 자료로 자신의 분석 흐름을 미리 시험해 볼 수 있습니다</li>
<li>ASKAP·MeerKAT 등 <b>선행망원경</b> 자료로 준비할 수 있습니다 — 자료를 받는 곳은 <a href="/links">Links</a>에 모아 두었습니다</li>
</ul>
</div>
<div class="panel dark">
<h3>국내 사용자 지원</h3>
<ul>
<li>KRSRC가 국내 연구자를 위한 헬프데스크를 제공할 예정입니다</li>
<li>교육과 워크숍을 엽니다 — 지난 모임은 <a href="/meetings" style="color:#ff86bb">Meetings</a>에서 볼 수 있습니다</li>
<li>한글 실습 자료를 준비하고 있습니다</li>
</ul>
</div>
</div>

<div class="btnrow">
<a class="btn primary" href="/src/korea-src">한국 지역센터</a>
<a class="btn ghost" href="/src/tutorials">튜토리얼</a>
</div>
