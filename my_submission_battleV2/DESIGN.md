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

### 1-3. Greedy 팀 선택

1. `base_score` 최고 포켓몬을 시작점으로 고정
2. 남은 슬롯을 greedy하게 채움: 추가했을 때 전체 커버리지 범위(max−min)를 가장 많이 줄이는 포켓몬 우선

```
val(i) = 1.5 × (범위 감소량) + 1.0 × base_score[i]
```

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
```

- `total_damage_ratio`: 내 포켓몬이 상대 팀 전체에 입히는 데미지 비율 합
- 속도(SPD_r)를 독립 항으로 포함 — 선발 단계에서는 속도가 선공 우위에 직결되므로 반영

### `_pick_best_n` (커버리지 greedy)

1. 점수 최고 포켓몬을 첫 번째로 선택
2. 커버리지 범위 감소 × 1.25 + 점수 × 0.74 가중치로 나머지 슬롯을 채움

---

## 4. 배틀 — `StrategyBattlePolicy`

**역할:** 매 턴 각 포켓몬의 행동(기술/교체)을 결정한다.

### 턴 처리 순서

```
for slot in [0, 1]:
    if 이 슬롯이 solo KO 가능:   → 그냥 공격 (자유 슬롯으로 남김)
    elif Protect 조건 충족:       → Protect
    elif 생존 교체 조건 충족:     → 교체

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

### 4-2. `_try_survival_switch()` — 생존 교체

**발동 조건**:
1. 현재 HP < 최대 HP × 25%
2. 상대 전체가 이번 턴 이 포켓몬을 KO할 수 있음 (예상 총 데미지 ≥ 현재 HP)
3. 교체 후보가 살아 있음

**교체 후보 선별**:
- 교체 직후 즉시 KO당할 후보 제외 (switch-in threat ≥ HP이면 스킵)
- 남은 후보 중 상대 전체에 대한 공격력 합계 최대인 포켓몬 선택

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

한 슬롯만 자유로울 때 사용. Priority 기술로 KO 가능하면 즉시 반환, 아니면 데미지 최대 기술 선택.

---

### 4-5. `_effective_speed()` — 유효 속도

```
유효 속도 = 기본 속도 × 스탯 부스트 배율
           × 0.5 (마비 시)
           × -1  (트릭룸 활성 시)
```

트릭룸 중에는 음수로 변환하여 느린 포켓몬이 "더 빠르게" 취급되도록 처리.

---

## 5. 성능 (championship_benchmark, 2026-05-26 기준)

| 순위 | 참가자 | ELO |
|---|---|---|
| **1** | **DaehoV2** | **1859.5** |
| 2 | Minimon | 1176.1 |
| 3 | Jirachi | 1163.4 |
| 4 | Yamabuki | 1162.3 |
| 5 | Caaaden | 1162.1 |
| 6 | JJJ | 1159.6 |
| 7 | StocKarpador | 1145.8 |
| 8 | Greedy | 1137.6 |
| 9 | Botzilla | 1114.9 |
| 10 | Peach | 1063.6 |
| 11 | Laze | 1055.2 |

benchmark 설정: 50마리 roster, build-6 / select-4, N_EPOCHS=30, N_BATTLES=3, ELO_PAIRING

---

## 6. 다음 개선 후보

1. **Priority 기술 우선 선택 강화** — `_best_move`에서 priority 기술이 KO 가능하면 항상 최우선 (현재는 `_best_assignment` focus-fire에서만 보너스)
2. **교체 임계값 조정** — HP 25% 임계값을 낮추거나 조건 추가 (순수 공격 AI 상대로 교체가 손해인 경우 많음)
