# DaehoV2 — 설계 문서

VGC AI Competition의 **battle track** 및 **championship track** 양쪽에 참여하는 AI 에이전트.  
세 개의 policy(`TeamBuildPolicy`, `SelectionPolicy`, `BattlePolicy`)가 서로 공유된 전략 감지 로직으로 연결된다.

---

## 파일 구조

```
my_submission_battleV2/
├── competitor.py          # DaehoV2Competitor — 세 policy를 하나로 묶는 진입점
├── main.py                # RemoteCompetitorManager 서버 (championship track)
├── team_build_policy.py   # SmartTeamBuildPolicy
├── selection_policy.py    # StrategySelectionPolicy
├── battle_policy.py       # StrategyBattlePolicy
└── strategy.py            # identify_strategy() — 전략 감지 공통 모듈
```

---

## 1. 팀빌딩 — `SmartTeamBuildPolicy`

**역할:** 50마리 roster에서 6마리를 선택하고 EV/Nature/기술을 배정한다.

### 1-1. 50×50 데미지 매트릭스

```
damage_matrix[i][j] = roster[i]가 roster[j]에게 입히는 최대 데미지 비율 (0.0~∞)
```

- 모든 기술을 순회하여 STAB × 타입 상성 × 공격/방어 스탯 비율로 계산
- 비전투 기술(변화기)은 제외
- 선공 기술(priority > 0)은 base_power에 +10 보정

### 1-2. 기본 점수 (bulk-first)

```
base_score[i] = 1.0 × firepower + 1.0 × bulk + 0.5 × hp_score
```

| 항목 | 계산식 | 의미 |
|---|---|---|
| `firepower` | `mean(damage_matrix[i])` | 전체 roster 평균 공격력 |
| `bulk` | `(HP/150) × (DEF/150) × (SpD/150)` | 3축 내구력 곱 |
| `hp_score` | `HP / 150` | HP 단독 보정 (고HP 보너스) |

속도(Speed)는 의도적으로 제외 — 팀 선택 기준은 내구 + 화력, 속도는 선발에서 처리.

### 1-3. Greedy 팀 선택 + 공유 약점 패널티 (P4)

1. `base_score` 최고 포켓몬을 시작점으로 고정
2. 남은 슬롯을 greedy하게 채움: 커버리지 범위 감소 + 점수 - 공유 약점 패널티

```
val(i) = 1.5 × (범위 감소량) + 1.0 × base_score[i] - 0.2 × shared_weakness
```

**공유 약점(shared_weakness):** 이미 선발된 팀원과 후보 포켓몬이 같은 공격 타입에 모두 약점(×1.0 초과)을 갖는 경우의 수.  
→ 타입 편중 팀 구성을 억제해 상대 coverage 기술에 한꺼번에 쓸리는 상황을 방지.

### 1-4. 로컬 스왑 개선

greedy 결과를 출발점으로, 멤버 1명을 교체했을 때 composite score가 향상되면 교체를 반복한다.

```
composite(team) = mean_coverage(team) + 0.5 × mean_base_score(team)
```

수렴(개선 없음)까지 반복 → 지역 최적 보장.

### 1-5. EV/Nature/기술 배정

| 성향 | 판단 기준 | EV 배분 | Nature |
|---|---|---|---|
| physical | 물리기술 총합이 특수 × 1.2 초과 | HP 252 / Atk 252 / Spe 4 | ADAMANT |
| special | 특수기술 총합이 물리 × 1.2 초과 | HP 252 / SpA 252 / Spe 4 | MODEST |
| mixed | 그 외 | HP 252 / Atk 126 / SpA 126 / Spe 4 | HASTY |

기술 선택 (`_select_best_moves`):
- 공격기: `base_power × accuracy × STAB × 공격 스탯 / 100` 점수 순 정렬
- 선공기(priority > 0): 점수에 ×1.2 보정
- 변화기: Protect 150점, Tailwind 100점, Reflect/LightScreen 80점, 능력 변화 60점
- 타입이 중복되는 공격기는 가급적 배제 (타입 다양성 우선)

---

## 2. 선발 — `StrategySelectionPolicy`

**역할:** 팀빌딩으로 구성된 6마리 중 4마리를 골라 출전 순서를 결정한다.

`identify_strategy()`를 호출해 전략 유형을 판별한 뒤, 전략에 맞는 선발 순서를 반환한다.

```python
ordered = plan.lead_idxs + plan.reserve_idxs   # 전략이 정한 선발 2 + 후보 2
# 나머지 멤버가 있으면 뒤에 붙임 (max_size까지 슬라이스)
```

---

## 3. 전략 감지 — `identify_strategy()` (`strategy.py`)

**입력:** 내 팀 멤버 리스트, 상대 팀 멤버 리스트  
**출력:** `StrategyPlan(strategy, setter_idx, lead_idxs, reserve_idxs)`

### 전략 판별 우선순위

#### TRICK_ROOM
- TR 기술 보유 포켓몬이 있고 + 속도 < 70인 공격수가 있으면
- Lead: [TR 설정자, 최고 점수 느린 공격수]

#### WEATHER (RAIN / SUN / SAND / SNOW)
- 날씨 기술 보유 포켓몬이 있으면
- RAIN: Water 타입 수혜자가 있으면 [setter, 최고 Water 공격수]
- SUN: Fire 타입 수혜자가 있으면 [setter, 최고 Fire 공격수]
- SAND/SNOW: 수혜 타입 불문, [setter, 최고 공격 점수 파트너]

#### HYPER_OFFENSE
- 속도 ≥ 100인 포켓몬이 2마리 이상
- Lead: 속도 상위 2마리

#### BALANCED (fallback)
- 위 어디에도 해당 없으면
- `_pick_best_n()`으로 커버리지 최적 4마리를 선택해 선발

### 공격 점수 `_score_attacker`

```
score = 1.07 × total_damage_ratio + 0.30 × (HP_r × DEF_r) + 0.55 × SPD_r
        - 0.50 × def_penalty
```

- `total_damage_ratio`: 내 포켓몬이 상대 팀 전체에 입히는 데미지 비율 합
- `HP_r = HP/402`, `DEF_r = DEF/257`, `SPD_r = SPEED/257` (정규화 상수)
- 속도(SPD_r)를 독립 항으로 포함 — 선발 단계에서는 속도가 선공 우위에 직결되므로 반영
- `def_penalty`(P21): 상대 팀이 이 포켓몬에게 입히는 **평균 입사 데미지 비율**. 잘 버티는(맞는 피해가 적은) 포켓몬을 선발에서 우대하기 위해 −0.50 가중으로 차감

### `_pick_best_n` (커버리지 greedy)

1. 점수 최고 포켓몬을 첫 번째로 선택
2. 커버리지 범위 감소 × 1.25 + 점수 × 0.74 가중치로 나머지 슬롯을 채움

---

## 4. 배틀 — `StrategyBattlePolicy`

**역할:** 매 턴 각 포켓몬의 행동(기술/교체)을 결정한다.

### 턴 처리 순서

```
active가 1마리뿐이면 → _greedy_single() (단일 최대 데미지 기술)

for slot in [0, 1]:
    if 이 슬롯이 solo KO 가능:   → 그냥 공격 (자유 슬롯으로 남김)
    elif Protect 조건 충족:       → Protect
    elif 생존/타입 교체 조건 충족: → 교체

자유 슬롯이 2개 모두 남아 있으면 → _best_assignment() (듀오 최적 배분)
자유 슬롯이 1개이면              → _best_move() (개별 최적 기술)
```

---

### 4-1. `_try_protect()` — Protect 판단

**발동 조건 (AND)**:
1. 연속 Protect 미사용 (`_consecutive_protect == 0`)
2. Protect 기술 보유 및 PP > 0
3. 내 슬롯이 파트너보다 더 큰 입사 데미지 위협을 받음

**두 가지 Protect 시나리오**:

| 시나리오 | 조건 | 예외 (Protect 생략) |
|---|---|---|
| **생존 Protect** | 총 입사 데미지 ≥ 현재 HP (1방에 KO될 때) | 파트너가 주 위협 상대를 solo KO 가능 |
| **전술 Protect** | 가장 강한 상대의 공격이 최대 HP의 50% 이상 & 파트너가 그 상대를 KO 가능 | — |

> Protect를 써서 파트너에게 KO를 맡기는 것이 핵심. 파트너가 이미 처리할 수 있으면 Protect는 손해.

---

### 4-2. `_try_survival_switch()` — 생존/타입 교체 (P1)

**세 가지 발동 조건 (OR)**:

| 조건 | 내용 |
|---|---|
| **생존 교체** | HP < 25% AND 상대 총 입사 데미지 ≥ 현재 HP |
| **4배 약점 교체** | 상대 최강 기술이 4배 유효 AND HP ≤ 75% |
| **2배 약점 교체** | 상대 최강 기술이 2배 유효 AND HP ≤ 50% |

**공통 예외 (교체 안 함)**:
- 현재 포켓몬이 solo KO 가능한 경우
- 연속 Protect 직후
- 교체 가능한 살아 있는 후보가 없는 경우

**교체 후보 선별**:
1. 교체 직후 즉시 KO당할 후보 제외 (switch-in 예상 피해 ≥ HP이면 스킵)
2. 남은 후보 중 공격력 합산 최대 포켓몬 선택
3. 상대 최강 기술에 저항(×0.5 이하)하는 후보에 score ×1.3 보너스
4. 교체 후보가 상대를 즉시 KO 가능하면 score +15,000 보너스 (P7)

> 타입 불리 상황에서 무작정 버티지 않고 저항 가능한 포켓몬으로 포지션을 교체해 전선을 유리하게 재편.

---

### 4-3. `_best_assignment()` — 듀오 행동 배분

두 포켓몬의 행동을 동시에 결정하는 핵심 로직. 두 단계로 작동한다.

#### 단계 1: Solo KO Split (우선)

한 쪽 포켓몬이 상대 1마리를 solo KO 가능하면, 파트너를 다른 상대로 리다이렉트한다.

```
score = (solo_ko_dmg + 10000) / opp_A_max_hp
      + (partner_dmg + 파트너 KO 보너스) / opp_B_max_hp
```

Split score > Focus-fire score이면 split 채택.

#### 단계 2: Focus-fire (fallback)

Solo KO가 없을 때, 두 포켓몬이 동일 타겟을 집중 공격하는 모든 조합을 평가한다.

```
score = (dmg1 + dmg2 + KO보너스 + priority보너스) / max_hp + 위협도 보정
```

| 보너스 항목 | 값 |
|---|---|
| KO 보너스 (아군이 상대보다 빠를 때) | +13,000 |
| KO 보너스 (속도 불리) | +10,000 |
| Priority 기술 solo KO | +20,000 (per 기술) |
| 위협도 보정 | 상대의 아군 최대 공격력 × 0.001 |

> 위협적인 상대를 먼저 KO하면 위협도 보정이 붙어, 단순 데미지가 아닌 "위협 제거" 가치를 반영한다.

---

### 4-4. `_best_move()` — 단일 최적 기술

한 슬롯만 자유로울 때 사용. Priority 기술로 solo KO 가능하면 즉시 반환, 아니면 데미지 최대 기술 선택.

---

### 4-5. `_effective_speed()` — 유효 속도

```
유효 속도 = 기본 속도 × 스탯 부스트 배율
           × 0.5 (마비 시)
           × -1  (트릭룸 활성 시)
```

트릭룸 중에는 음수로 변환하여 느린 포켓몬이 "더 빠르게" 취급되도록 처리.

---

## 5. 성능 기록

### 5-1. Battle Benchmark (fast mode, ~1000 매치)

| 시점 | Greedy | JJJ | Yamabuki | 비고 |
|---|---|---|---|---|
| 원본 (76ed01f) | 58.5% | 54.9% | 44.5% | 베이스라인 |
| P1 적용 후 | 56.5% | 55.8% | **49.5%** | 타입 교체 도입 |

### 5-2. Friends Benchmark (battle, 200 매치)

| 시점 | Luciner | PokemonMaster | Wonyoung | 평균 |
|---|---|---|---|---|
| 원본 (76ed01f) | ~46% | ~52% | ~42% | ~46.7% |
| P1 적용 후 | ~42%* | ~49%* | ~61%* | **~50.5%** |

> \* 200회 기준 개별 매치업은 분산이 크므로 (±5%) 평균 추세로 해석.

### 5-3. Friends Championship Benchmark (50 매치)

| 시점 | Luciner | PokemonMaster | Wonyoung | 평균 |
|---|---|---|---|---|
| 원본 (76ed01f) | 74.0% | 40.0% | 84.0% | 66.0% |
| P1 적용 후 | 80.0% | 38.0% | 96.0% | **71.3%** |

### 5-4. Championship ELO (N_EPOCHS=30)

| 시점 | DaehoV2 ELO | 순위 | 비고 |
|---|---|---|---|
| 원본 (76ed01f) | ~1147.6 | #1 | 실측값; 이전 기록 1859.5는 고점 노이즈 |
| P1+P4 적용 후 | ~1170.7 | #1 | P2 제거, P4(공유약점) 적용 상태 추정 |

---

## 6. 개선 이력 (Changelog)

| ID | 대상 파일 | 내용 | 결과 | 상태 |
|---|---|---|---|---|
| **P1** | `battle_policy.py` | 타입 불리 조기 교체 (2x@50% / 4x@75%) + 저항 후보 보너스 | Battle Yamabuki +5%, Championship +5.3% | ✅ 적용 |
| P2-v1 | `battle_policy.py` | STATUS 기술 직접 score 경쟁 | Yamabuki -3% 등 net 손실 | ❌ 롤백 |
| P2-v2 | `battle_policy.py` | STATUS 기술 데미지 플랜B (데미지 <20% 시만) | Greedy +3.7%, Championship -4% — net 부정적 | ❌ 롤백 |
| P3 | `battle_policy.py` | 스크린 incoming 데미지 수동 보정 | 엔진 버그로 오히려 AI 오판 유발 (-3.3%) | ❌ 롤백 |
| **P4** | `team_build_policy.py` | 공유 약점 패널티 복구 (-0.2 × shared_weakness) | Championship +23 ELO | ✅ 적용 |
| P5 | `selection_policy.py` | 선발 카운터피킹 — 적 전략 감지 후 속도/내구 기준 리드 재정렬 | Championship friends -23.6% — 적 팀 전체로 전략 추정 시 오판 多 | ❌ 롤백 |
| P6 | `battle_policy.py` | 위협도 상시 반영 (`danger_bonus` 조건 제거) | Greedy +4.4%, JJJ -4.1%, Yamabuki -1.0% — net 부정적 | ❌ 롤백 |
| **P7** | `battle_policy.py` | 교체 후보 즉시 KO 가능 시 score +15000 보너스 | Friends Battle +0%, Championship -4% (Yamabuki -6%) — friends 기준 채택 | ✅ 적용 |
| **P21** | `strategy.py` | 선발 `_score_attacker`에 방어 패널티 추가 (−0.50 × 상대 평균 입사 데미지) | baseline(5fc2ca0) 유지 — KEEP 채택 | ✅ 적용 |

### 교훈

- **P2**: STATUS 기술은 "공격력이 아예 없을 때 최후 수단"으로만 쓸 때도 championship에서 턴 낭비 패널티 발생. VGC 환경에서 상태이상 기술의 가치는 상대방의 적응 수준에 크게 좌우됨.
- **P3**: 엔진의 `calculate_modifier()`가 스크린을 공격 측 조건으로 잘못 읽음 → 배틀 중 실제 피해는 스크린 적용 안 됨. AI가 "스크린 있으니 안전"으로 오판하면 오히려 손해.
- **P5**: `identify_strategy(enemy_team, my_team)` 역호출로 적 전략을 추정했으나, 상대 6마리 전체를 보고 판단하면 실제 선발 4마리와 괴리가 커 오히려 아군 시너지를 파괴.
- **P6/P7**: 공격 타겟팅·교체 후보 변경은 Greedy/JJJ엔 유효하지만 Yamabuki처럼 강한 상대는 행동 변화를 역이용. 단순 스코어 튜닝의 한계.

---

## 7. 알려진 엔진 버그

`vgc2/battle_engine/damage_calculator.py`의 `calculate_modifier()`가 스크린(Reflect/Light Screen) 보정 시 **공격 측** 조건을 참조하는 버그가 있음.

```python
# 실제 코드 (버그)
modifier *= light_screen_modifier(params, move, state.sides[attacking_side].conditions.lightscreen)
modifier *= reflect_modifier(params, move, state.sides[attacking_side].conditions.reflect)
# 수비 측(1 - attacking_side)의 conditions를 읽어야 정확함
```

이로 인해 스크린은 실제 배틀에서 피해 경감 효과가 없음. 이를 우리 코드에서 수동으로 "보정"하려 하면 AI가 허상의 안전감을 갖고 교체/Protect를 놓침.

---

## 8. 다음 개선 후보

### Battle Track

| 우선순위 | 개선 내용 | 예상 효과 |
|---|---|---|
| 🔴 High (미시도) | 교체 후 공격 우선순위 — switch-in 첫 턴에 priority 기술 우선 탐색 | 교체 이득 극대화 |
| 🔴 High (미시도) | HP 잔량 기반 공격 강도 조절 — HP 우위 시 보존, 열세 시 공격적으로 | 전반적 승률 |
| ~~🔴 High~~ | ~~`_best_assignment` 위협도 가중치 정밀화~~ | ~~P6로 시도 → 역효과~~ |
| ~~🔴 High~~ | ~~P5: 선발 카운터피킹~~ | ~~시도 → Championship 대폭 하락~~ |
| 🟢 Low | 상태이상 기술 재설계 — "타입 면역 또는 moves exhausted" 상황에서만 사용 | Greedy 회복 |

### Championship Track

| 우선순위 | 개선 내용 | 예상 효과 |
|---|---|---|
| 🟡 Medium | `_score_attacker` 가중치 재조정 (현재 SPD_r 0.55가 과도할 수 있음) | 팀 밸런스 개선 |
