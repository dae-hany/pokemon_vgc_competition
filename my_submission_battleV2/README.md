# DaehoV2 — VGC AI 제출물 (battle / championship track)

VGC AI Competition의 **battle track**과 **championship track** 양쪽에 참여하는 에이전트.
세 개의 정책(team build / selection / battle)을 `competitor.py`가 하나로 묶는다.

> 본 문서는 제출물의 **전략과 설계 의사결정**을 설명한다. 줄 단위 상세 구현은 [`DESIGN.md`](DESIGN.md)를 함께 참고.

---

## 0. 한눈에 보기

| 정책 | 클래스 / 파일 | 핵심 전략 | 적용 트랙 |
|---|---|---|---|
| **Team Build** | `SmartTeamBuildPolicy` (`team_build_policy.py`) | **내구 우선(bulk-first)** + 커버리지 그리디 + 공유약점 패널티 | championship |
| **Selection** | `StrategySelectionPolicy` (`selection_policy.py`) | **전략 감지**(TR/날씨/HO/밸런스) + 방어 인지 스코어링 | battle, championship |
| **Battle** | `StrategyBattlePolicy` (`battle_policy.py`) | 턴 단위 휴리스틱(solo-KO / protect / 생존 교체 / 듀오 배분) | battle, championship |

세 정책을 관통하는 설계 원리는 **"많이 때리고, 적게 맞는다"** — 팀빌드는 화력+내구(bulk)로,
선발은 화력−피격(방어 인지)으로, 배틀은 생존 교체·보호로 각 계층에서 이를 구현한다.

---

## 1. 아키텍처

```
my_submission_battleV2/
├── competitor.py          # DaehoV2Competitor — 세 정책을 묶는 진입점
├── main.py                # RemoteCompetitorManager 서버 (championship 원격 대전)
├── team_build_policy.py   # SmartTeamBuildPolicy
├── selection_policy.py    # StrategySelectionPolicy
├── battle_policy.py       # StrategyBattlePolicy
├── strategy.py            # identify_strategy() · _score_attacker() 등 선발 공통 모듈
├── DESIGN.md              # 상세 설계/구현 문서
└── README.md              # (이 문서) 전략 개요
```

### 1-1. 계층 분리 — 가장 중요한 설계 결정

이 제출물의 핵심 자산은 **"어느 계층을 건드려야 안전한가"**에 대한 실험적 통찰이다.

- **선발(selection) / 팀빌드(team build) 계층 = 안전한 개선 레버.**
  배틀 시작 *전에* 한 번 실행되며, 우리의 턴 단위 행동 패턴을 바꾸지 않는다.
- **배틀(battle) 계층 = 구조적으로 위험.**
  Yamabuki 같은 상대는 **MCTS로 우리를 greedy로 가정하고 예측**한다.
  배틀 로직을 "더 똑똑하게" 바꾸면 행동이 더 규칙적·예측가능해져 **오히려 역이용당한다**
  (실측: 1v2 교체/보호/시뮬레이션 도입 P18–P20에서 Yamabuki 일관 하락).

> 따라서 본 제출물의 고도화는 **선발·팀빌드 계층에 집중**한다. 배틀 계층은 검증된 휴리스틱을 유지한다.

### 1-2. `_plan_holder` — 정직한 메모

`competitor.py`는 `_plan_holder = [None]` 리스트를 선발·배틀 정책에 공유 주입한다.
이는 *"선발이 감지한 전략을 배틀에 전달"*하려던 통신 채널이지만, **현재 코드에서는 사용되지 않는다**
(선발이 쓰지 않고 배틀이 읽지 않음). 두 계층은 **독립적으로** 동작한다 — 선발은 전략적 팀 구성을,
배틀은 매 턴 국소 최적 행동을 담당한다. 향후 두 계층을 잇는 확장 지점(hook)으로 남겨둔 상태다.

---

## 2. 정책 1 — Team Build (`SmartTeamBuildPolicy`)

**역할:** 50마리 로스터에서 6마리를 선택하고 각 포켓몬의 EV/Nature/기술을 배정한다 (championship track).

설계 철학은 **bulk-first**: 한 방에 무너지지 않는 내구를 확보한 뒤 화력과 커버리지를 더한다.
대회 환경(50마리 풀, 4마리 선발 더블배틀)에서 "맞고도 버티는" 포켓몬이 행동 횟수를 확보해 가치가 높다는 가설.

### 2-1. 50×50 데미지 매트릭스 (`team_build_policy.py:163`)

```
damage_matrix[i][j] = roster[i]가 roster[j]에게 입히는 최대 데미지 비율
```

- 모든 기술을 순회해 `STAB × 타입상성 × (공격스탯/방어스탯)` 기반 데미지 비율 계산 (`_get_best_damage_ratio`)
- 변화기(비공격기) 제외, 선공기(priority>0)는 `base_power + priority×10` 보정
- 이 행렬이 화력(행 평균)과 커버리지(열) 계산의 단일 출처

### 2-2. 기본 점수 — bulk-first (`team_build_policy.py:171`)

```
base_score[i] = 1.0·firepower + 1.0·bulk + 0.5·hp_score
```

| 항목 | 계산식 | 의미 |
|---|---|---|
| `firepower` | `mean(damage_matrix[i])` | 로스터 전체에 대한 평균 화력 |
| `bulk` | `(HP/150)·(DEF/150)·(SpD/150)` | 3축 내구 곱 |
| `hp_score` | `HP/150` | 생존성 가산(고HP 보너스) |

- 화력과 내구를 **동일 가중**으로 두고 HP를 추가 가산 — "맞고도 버티는" 포켓몬을 선호하는 bulk-first 철학.
- 속도는 **의도적으로 제외** — 팀 선택 기준은 내구·화력, 속도는 선발 계층에서 처리.

> **실험 메모(방어 패널티):** 선발 계층에서 검증된 방어 인지(3-3, P21)를 팀빌드에도 이식하고자
> `− λ·mean(damage_matrix[:, i])` 항(λ=0.5)을 추가해 paired A/B로 검증했으나, 800매치 합산
> **51.1%(중립)**으로 baseline을 신뢰성 있게 넘지 못해 **미채택**(6-2). 근본 설계는 baseline을 유지한다.

### 2-3. 그리디 팀 선택 + 공유 약점 패널티 (`team_build_policy.py:117`)

`base_score` 최고 포켓몬을 시작점으로, 남은 슬롯을 그리디로 채운다.

```
val(i) = 1.5·(커버리지 범위 감소량) + 1.0·base_score[i] − 0.2·shared_weakness
```

- **커버리지 범위 감소량:** 후보 추가 시 `max(coverage)−min(coverage)`가 줄어드는 양 →
  특정 상대에게만 강한 편중을 막고 *전 로스터에 고르게* 데미지가 들어가도록 평탄화.
- **공유 약점(`shared_weakness`):** 이미 뽑힌 팀원과 후보가 *같은 공격 타입에 함께 약점*인 경우 수.
  → 타입 편중으로 상대의 한 커버리지 기술에 동시에 쓸리는 것을 방지.

### 2-4. 로컬 스왑 개선 (`team_build_policy.py:182`)

그리디 결과에서 멤버 1명을 미선발 후보와 교체했을 때 종합 점수가 오르면 교체를 반복(수렴까지).

```
composite(team) = mean_coverage(team) + 0.5·mean_base_score(team)
```

### 2-5. EV / Nature / 기술 배정 (`team_build_policy.py:206`)

기술 구성으로 물리/특수 성향을 판정(`_determine_orientation`, 1.2배 우세 기준)해 스프레드를 결정.

| 성향 | EV | Nature |
|---|---|---|
| physical | HP 252 / Atk 252 / Spe 4 | ADAMANT |
| special | HP 252 / SpA 252 / Spe 4 | MODEST |
| mixed | HP 252 / Atk 126 / SpA 126 / Spe 4 | HASTY |

기술 선택(`_select_best_moves`)은 `base_power·accuracy·STAB·공격스탯/100` 점수 순. 선공기 ×1.2,
변화기는 Protect 150 / Tailwind 100 / Reflect·LightScreen 80 / 능력변화 60점. 타입 다양성을 우선해 중복 공격 타입을 배제.

---

## 3. 정책 2 — Selection (`StrategySelectionPolicy` + `identify_strategy`)

**역할:** 6마리 중 4마리를 골라 선발 순서를 정한다. 핵심은 `strategy.py`의 `identify_strategy()`.

### 3-1. 전략 감지 우선순위 (`strategy.py:134`)

내 팀 구성에서 다음 순서로 전략을 판별하고, 그에 맞는 리드 2마리를 구성한다.

| 순위 | 전략 | 감지 조건 | 리드 구성 |
|---|---|---|---|
| 1 | **TRICK_ROOM** | 트릭룸 기술 보유 + 속도<70 공격수 존재 | [TR 설정자, 최고점수 느린 공격수] |
| 2 | **WEATHER** | 날씨 기술 보유 | RAIN→[setter, 최고 Water]·SUN→[setter, 최고 Fire]·SAND/SNOW→[setter, 최고 공격수] |
| 3 | **HYPER_OFFENSE** | 속도≥100 포켓몬 2마리 이상 | 속도 상위 2마리 |
| 4 | **BALANCED** (fallback) | 그 외 전부 | `_pick_best_n`으로 커버리지 최적 4마리 |

> 트릭룸/날씨 같은 **팀 시너지 전략을 자동 인식**해, 단순 화력 그리디가 놓치는
> "설정자+수혜자" 조합을 의도적으로 함께 내보내는 것이 선발 계층의 차별점이다.

### 3-2. 공격 점수 `_score_attacker` (`strategy.py:92`)

리드·후보 선정에 쓰는 포켓몬 가치 함수.

```
score = 1.07·total_damage − 0.50·def_penalty + 0.30·(HP_r·DEF_r) + 0.55·SPD_r
```

| 항목 | 의미 |
|---|---|
| `total_damage` | 상대 팀 전체에 입히는 데미지 비율 합 (화력) |
| `def_penalty` | 상대 팀이 나에게 주는 평균 데미지 (**방어 인지**) |
| `HP_r·DEF_r` | 내구 곱 |
| `SPD_r` | 속도 — 선발 단계에선 선공 우위에 직결되므로 독립 항으로 반영 |

### 3-3. 방어 인지 — 검증된 핵심 (P21)

`−0.50·def_penalty` 항은 **"상대에게 많이 맞는 포켓몬"을 감점**한다.
순수 화력만 보던 기존 스코어에 방어 인지를 더한 변경(P21)으로, 외부봇 가중 평균 **+4%대**를 확인했다.
이 원리가 충분히 일반적이어서, 같은 아이디어를 팀빌드(2-2)로 확장했다.

### 3-4. `_pick_best_n` — 커버리지 그리디 (`strategy.py:103`)

1. 점수 최고 포켓몬을 첫 번째로 선택
2. `1.25·(커버리지 범위 감소) + 0.74·점수` 가중으로 나머지를 채움
   → 반환 리스트의 앞 2 = 리드, 뒤 = 후보. **이 순서가 커버리지 다양성을 보장**하므로 임의 재정렬 금지.

---

## 4. 정책 3 — Battle (`StrategyBattlePolicy`)

**역할:** 매 턴 각 포켓몬의 행동(기술/교체/보호)을 결정한다. 더블배틀(2v2) 기준.

### 4-1. 턴 의사결정 순서 (`battle_policy.py:350`)

```
각 슬롯 slot ∈ {0,1}:
    solo KO 가능?        → 공격 위임 (자유 슬롯으로 남김)
    else Protect 조건?   → Protect
    else 생존/타입 교체?  → 교체

자유 슬롯 2개 → _best_assignment() (듀오 동시 배분)
자유 슬롯 1개 → _best_move()       (개별 최적 기술)
```

모든 데미지는 엔진의 정확한 `calculate_damage()`로 계산한다(휴리스틱 추정이 아님).

### 4-2. `_try_protect` — 보호막 (`battle_policy.py:291`)

내 슬롯이 파트너보다 큰 입사 위협을 받을 때만 검토.

| 시나리오 | 조건 | 보호 생략 예외 |
|---|---|---|
| **생존 Protect** | 총 입사 데미지 ≥ 현재 HP (한 방 KO) | 파트너가 그 주 위협을 직접 KO 가능 |
| **전술 Protect** | 최강 상대 공격이 최대 HP 50%↑ AND 파트너가 그 상대 KO 가능 | — |

> 핵심: **Protect로 한 턴 벌어 파트너에게 KO를 맡긴다.** 파트너가 이미 처리 가능하면 Protect는 손해.

### 4-3. `_try_survival_switch` — 생존/타입 교체 (P1) (`battle_policy.py:43`)

세 발동 조건(OR): ① HP<25% & 입사≥HP, ② 4배 약점 & HP≤75%, ③ 2배 약점 & HP≤50%.
(예외: solo KO 가능 / 연속 Protect 직후 / 살아있는 후보 없음 → 교체 안 함.)

교체 후보 선별: 교체 즉시 KO당할 후보 제외 → 공격력 합산 최대 선택 →
상대 최강기 저항(×0.5↓) 후보 **×1.3**, 교체 후보가 즉시 KO 가능하면 **+15000**(P7).

### 4-4. `_best_assignment` — 듀오 행동 배분 (`battle_policy.py:140`)

- **단계 1 (Solo KO Split):** 한 쪽이 상대 1마리를 solo KO 가능하면 파트너를 다른 타겟으로 리다이렉트.
- **단계 2 (Focus-fire):** solo KO가 없으면 두 포켓몬이 같은 타겟을 집중. 점수에 KO 보너스
  (빠르면 +13000, 느리면 +10000), priority solo KO +20000, **위협도 보정**(상대 화력×0.001)을 가산해
  *단순 데미지가 아닌 "위협 제거" 가치*를 반영.

### 4-5. 보조 — `_best_move` / `_effective_speed`

- `_best_move`: 단일 슬롯용. priority 기술 solo KO면 즉시 반환, 아니면 최대 데미지.
- `_effective_speed`: `기본속도 × 부스트배율 × 0.5(마비) × −1(트릭룸)`. 트릭룸 중 음수화로 느린 쪽을 "빠르게" 취급.

---

## 5. 설계 원칙 & 검증 방법론

### 5-1. 원리적(principled) 개선만 채택

수강생 간 friends 대전이 최종 성적이지만, **보유한 친구 코드는 전체도 아니고 최신 제출본이라는 보장도 없다.**
따라서 특정 상대에 맞춘 튜닝(예: 선발 카운터피킹 P5 → 대폭 하락)은 *보이지 않는/갱신된* 상대에게 전이되지 않아 위험하다.
대신 **방어 인지·타입 커버리지·EV 효율 같은 근본 의사결정 품질** 개선만 채택한다 — 이런 변경은 어떤 상대에게도 일반화된다.

### 5-2. 검증 기준

| 대상 | 1차 검증 | 특징 |
|---|---|---|
| 선발 계층 변경 | `battle_benchmark.py --loop` (Greedy/JJJ/Yamabuki, 외부봇) | 고정·재현 가능. 단, 랜덤 팀 기반이라 분산 큼(특히 Yamabuki 100판 ±5%) |
| 팀빌드 변경 | **paired A/B**: 동일 로스터에서 팀빌드만 바꿔 직접 head-to-head 대결 | 분산이 작아 미세 효과 검출에 적합 |
| 최종 점검 | friends_benchmark 1회 (게이트가 아닌 방향성 확인) | 과적합 회피 |

> keep/revert는 가중 평균(0.35·Greedy + 0.35·JJJ + 0.30·Yamabuki)과 단일 상대 하락 가드로 결정하며,
> 경계값이면 재실행 후 평균(`improve_loop.py`). **불확실하면 baseline 유지**가 기본값.

---

## 6. 성능

### 6-1. Battle Track (외부봇, 변동성 유의)

| 상대 | 승률(근사) | 비고 |
|---|---|---|
| Greedy | ~57–62% | 400판, ±2.5% |
| JJJ | ~57–64% | 400판, ±2.5% |
| Yamabuki | ~46–62% | 100판, ±5% (고분산) |

> 단일 측정은 분산이 크다. 절대 수치보다 **방어 인지 도입(P21)이 가중 평균을 끌어올린 방향성**이 핵심.

### 6-2. Championship Track — Team-build 방어 패널티 A/B (미채택)

방어 패널티(λ=0.5) 팀빌드 vs baseline(λ=0)을 **동일 로스터 head-to-head**(선발·배틀 고정)로 검증:

| seed | E3승 | BASE승 | E3 승률 |
|---|---|---|---|
| 0 | 215 | 185 | 53.8% |
| 1 | 194 | 206 | 48.5% |
| **합산** | **409** | **391** | **51.1%** |

두 시드가 방향까지 엇갈리고 합산 51.1%(SE≈1.8%)는 50%와 통계적으로 구분되지 않는다 → **중립, 미채택**.
다만 이 paired A/B 방식 자체가 외부봇 battle_benchmark보다 분산이 작아, 팀빌드 검증의 올바른 도구임을 확인했다.

---

## 7. 한계 & 향후 과제

- **배틀 계층 상단(上限) 제약:** Yamabuki MCTS 취약점 때문에 배틀 로직 고도화는 구조적으로 어렵다(1-1).
  현재의 검증된 휴리스틱 유지가 최선.
- **벤치마크 분산:** 외부봇 battle_benchmark는 랜덤 팀·소표본(Yamabuki 100판)으로 단일 측정 신뢰도가 낮다.
  팀빌드는 paired A/B로 보완하지만, 선발 계층은 다회 측정·재실행 평균에 의존.
- **`meta` 미활용:** 팀빌드의 `meta`(사용률) 파라미터를 아직 쓰지 않는다. 단, 빌드 시점의 usage가
  비어/균등할 수 있어 효용은 조건부.
- **`_plan_holder` 미사용(1-2)**, **TYPE_CHART/데미지 공식 3개 파일 중복** — 정리 대상(기능 영향 없음).
- **알려진 엔진 버그:** `damage_calculator.calculate_modifier()`가 스크린(Reflect/Light Screen) 보정 시
  *공격 측* 조건을 참조 → 스크린이 실효 없음. 이를 수동 보정하려는 시도(P3)는 AI에 허상의 안전감을 주어 역효과(롤백).

---

*상세 구현·실험 이력은 [`DESIGN.md`](DESIGN.md) 참고.*
