# 🏆 DaehoAI 기술 아키텍처 및 동작 원리 (최종 보고서)

본 문서는 2026년 CoG VGC AI Competition 출품작인 **`DaehoAI`**의 기술적 설계와 핵심 알고리즘을 소스 코드 기반으로 상세히 기술한 전문 설명서입니다.

과거 우승 봇들의 패턴에 과적합(Overfitting)하는 것을 지양하고, 어떤 메타나 덱(Deck)을 만나도 **수학적/전략적 최적해(General AI)**를 도출하도록 설계되었습니다.

---

## 1. 시스템 아키텍처 개요 (System Overview)

`DaehoAI`는 `DaehoCompetitor` 클래스 하나에 3개의 독립적이면서도 유기적으로 연결된 정책 모듈이 조합된 구조입니다.

```
DaehoCompetitor
├── SmartTeamBuildPolicy   → 50마리 로스터 → 6마리 엔트리 구성 (Championship Track)
├── CoverageSelectionPolicy → 6마리 엔트리 → 4마리 선발 (Championship Track)
└── EnhancedBattlePolicy   → 매 턴 최적의 행동 결정 (Battle Track + Championship Track)
```

> **트랙별 사용 모듈**
> - **Battle Track**: `EnhancedBattlePolicy`만 사용 (팀/선발은 엔진이 고정 제공)
> - **Championship Track**: 세 모듈 모두 순서대로 실행

---

## 2. Phase 1: 팀 빌딩 — `SmartTeamBuildPolicy`

> **파일**: `team_build_policy.py` | **사용 트랙**: Championship Track 전용

대회에서 주어지는 **50마리 로스터(Roster)**에서 빈틈없는 **6마리 엔트리**를 수학적으로 조립합니다.

### 2-1. 50×50 데미지 매트릭스 구축

먼저 로스터 내 **모든 포켓몬 쌍(50×50 = 2,500개 조합)**에 대해 기대 데미지 비율(Damage Ratio)을 계산하여 행렬을 구축합니다.

```
damage_matrix[i][j] = 포켓몬 i가 포켓몬 j에게 줄 수 있는 최대 데미지 / j의 최대 HP
```

데미지 계산 공식 (`_get_best_damage_ratio`):
1. 포켓몬이 보유한 모든 **공격 기술(물리/특수)**을 순회
2. 기술 위력 = `base_power + max(0, priority) * 10` (선제 기술에 보정 적용)
3. 공격 스탯: 물리 기술 → ATK, 특수 기술 → SPA
4. **STAB 보정**: 기술의 타입이 포켓몬 자신의 타입과 일치하면 `× 1.5`
5. **타입 상성**: 19×19 타입 차트 행렬(`TYPE_CHART`)로 방어 타입별 효과 계산 (복합 타입은 두 효과를 곱)
6. 레벨 50 기준 데미지 공식 적용 후, 상대 최대 HP로 나눠 비율(ratio) 산출
7. 해당 포켓몬의 모든 기술 중 **가장 높은 ratio**를 채택

### 2-2. 기본 점수(Base Score) 산출

각 포켓몬의 **종합 역량**을 3가지 축으로 수치화합니다.

| 구성 요소 | 계산 방법 | 가중치 |
|-----------|-----------|--------|
| 화력(Firepower) | `damage_matrix[i]`의 평균 (로스터 50마리 상대 평균 데미지) | `× 1.0` |
| 내구(Bulk) | `HP × DEF × SpDEF` 기저 스탯의 곱 (각 150 기준 정규화) | `× 0.5` |
| 스피드(Speed) | 기저 스피드 ÷ 150 | `× 0.3` |

```python
base_scores[i] = 1.0 * firepower + 0.5 * bulk + 0.3 * speed
```

### 2-3. 그리디 커버리지 탐색 (Greedy Coverage Search)

**Step 1**: `base_scores`가 가장 높은 에이스 포켓몬을 첫 번째로 선발. 해당 포켓몬의 데미지 행(damage_matrix row)을 초기 `coverage` 벡터로 설정.

**Step 2**: 남은 후보군에서 아래 점수가 가장 높은 포켓몬을 반복 추가 (총 6마리 채울 때까지):

```
val = 1.5 × delta_range + 1.0 × base_scores[i] - 0.2 × shared_weakness
```

- **`delta_range`** = 현재 커버리지의 `(최댓값 - 최솟값)` — 추가 후 커버리지의 `(최댓값 - 최솟값)`. 값이 클수록 약점 포켓몬 커버리지가 균형 있게 개선됨
- **`base_scores[i]`**: 후보 포켓몬 자체의 화력+내구+스피드 점수
- **`shared_weakness`**: 이미 선발된 팀원들과 공유하는 방어 약점 타입 수. 18가지 타입 전체를 순회하며 타입 효과가 `> 1.0`인 타입이 겹칠 때마다 카운트하여 **공유 약점 페널티** 부여

### 2-4. EV/성격(Nature) 최적화

선발된 6마리 각각에 대해 **기술 배치를 분석**해 물리형/특수형/쌍두형을 자동 분류하고 스탯을 배분합니다.

```
물리형 판단: Σ(물리 기술 위력 × ATK) > Σ(특수 기술 위력 × SpA) × 1.2
특수형 판단: Σ(특수 기술 위력 × SpA) > Σ(물리 기술 위력 × ATK) × 1.2
쌍두형: 위 두 조건 모두 불충족
```

| 유형 | EV 배분 (HP/ATK/DEF/SpA/SpD/SPE) | 성격 |
|------|-----------------------------------|------|
| 물리형 | 252 / 252 / 0 / 0 / 0 / 4 | ADAMANT (공격↑, 특공↓) |
| 특수형 | 252 / 0 / 0 / 252 / 0 / 4 | MODEST (특공↑, 공격↓) |
| 쌍두형 | 252 / 126 / 0 / 126 / 0 / 4 | HASTY (스피드↑, 방어↓) |

모든 개체값(IV)은 `31`로 고정.

### 2-5. 기술 선택 (`_select_best_moves`)

각 포켓몬의 기술 풀에서 **최대 `max_pkm_moves`개**를 선택합니다.

- 공격 기술: `base_power × accuracy × STAB × atk_stat / 100` 점수로 정렬. 선제 기술(`priority > 0`)은 `× 1.2` 추가 보정
- 변화 기술 우선순위: **Protect = 150점** > Tailwind = 100점 > Reflect/Light Screen = 80점 > 스탯 변화 기술 = 60점 > 기타 = 30점
- **타입 다양성 보장**: 이미 선택된 기술과 동일 타입 공격 기술은 슬롯이 남을 때까지 후순위 배정

---

## 3. Phase 2: 선발 — `CoverageSelectionPolicy`

> **파일**: `selection_policy.py` | **사용 트랙**: Championship Track 전용

VGC 규칙의 승패를 결정짓는 핵심 단계로, 아군 6마리 중 상대방 6마리를 **가장 효과적으로 공략할 수 있는 4마리**를 수학적으로 선발합니다.

### 3-1. m×k 데미지 매트릭스 구축

`damage_matrix[i][j]` = 아군 포켓몬 i가 상대 포켓몬 j에게 줄 수 있는 최대 데미지 비율.

계산 방법은 팀빌딩의 `_get_best_damage_ratio`와 동일하나, **실제 배틀 스탯**(`stats[]`)을 사용합니다 (EV/IV/Nature가 모두 반영된 최종 수치).

### 3-2. 종합 점수(Score) 산출

각 아군 포켓몬의 선발 점수 (`_score_attacker`):

```
score = 1.07 × (상대 6마리 합산 데미지 총량) + (내구 보정치)
```

내구 보정: `HP_ratio × DEF_ratio × SpDEF_ratio × 0.42`
- 각 비율의 기준값: HP=402, DEF=257, SpDEF=257 (최고 스탯 수준으로 정규화)

### 3-3. 그리디 선발 로직

**Step 1**: 종합 점수(`score_vec`)가 가장 높은 포켓몬을 첫 번째로 선발. 해당 포켓몬의 데미지 행을 초기 `coverage` 벡터로 설정.

**Step 2**: 남은 후보군에서 아래 점수가 가장 높은 포켓몬을 반복 선발 (총 `max_size`마리 채울 때까지):

```python
val = 1.25 × delta_range + 0.74 × score_vec[i]
```

- **`delta_range`** = 추가 전 커버리지 Range — 추가 후 커버리지 Range. **상대의 어떤 포켓몬에 대해서도 최소한 한 마리가 효과적으로 대응 가능**하도록 균형을 맞추는 핵심 지표
- **`score_vec[i]`**: 후보 포켓몬 자체의 화력+내구 점수

> **예시**: 상대 6마리에 대한 현재 커버리지가 `[3.0, 0.1, 2.5, 2.0, 1.5, 0.2]`라면,
> Range = 3.0 − 0.1 = 2.9 (커버리지 불균형이 심함).
> 이때 특정 포켓몬을 추가하면 `[0.1, 0.2]`에 해당하는 약점 상대의 커버리지를 크게 올려
> Range를 줄이는 포켓몬이 우선 선발됩니다.

### 3-4. Edge Case 처리

`max_size >= m` (선발 인원 ≥ 보유 포켓몬 수)인 경우, 전원 출전(`list(range(m))`)을 즉시 반환합니다.

---

## 4. Phase 3: 배틀 — `EnhancedBattlePolicy`

> **파일**: `battle_policy.py` | **사용 트랙**: Battle Track + Championship Track 모두 사용

매 턴 주어지는 **100ms(실제 제한 90ms 내 실행)** 안에서 MCTS를 수행하여 최선의 수를 찾습니다.

### 4-1. 주요 파라미터

| 파라미터 | 기본값 | 의미 |
|----------|--------|------|
| `time_limit_ms` | 90ms | 실제 탐색 제한 시간 |
| `rollout_depth` | 4턴 | 롤아웃 시뮬레이션 깊이 |
| `C` (UCB 탐험 계수) | 1.41 | MCTS 탐험-활용 균형 계수 |

### 4-2. 불완전 정보 극복: Mock State 생성 (`_deduce_moves`)

엔진에서 상대방의 **미공개 기술은 `DUMMY_MOVE`**로 표시되어 시뮬레이션 중 크래시를 유발합니다. DaehoAI는 이를 다음과 같이 처리합니다:

```python
# 상대 포켓몬의 기술 슬롯 수가 max_moves(4)보다 적으면,
# 해당 포켓몬의 종족값(species)에 등록된 기술 풀에서 랜덤으로 기술을 추론·추가
ids = [m.constants.id for m in pokemon.battling_moves]  # 이미 알고 있는 기술 제외
moves = [m for m in pokemon.constants.species.moves if m.id not in ids]
pokemon.battling_moves += [BattlingMove(m) for m in random.sample(moves, ...)]
```

> 이미 공개된 기술은 제외하고, **해당 포켓몬이 배울 수 있는 기술 중에서만 랜덤 추론**함으로써 완전 무작위보다 훨씬 현실적인 시뮬레이션을 보장합니다.

### 4-3. 행동 공간 생성 (`get_all_possible_actions`)

아군 활성 포켓몬 2마리의 가능한 모든 행동 조합을 생성합니다:

```
[포켓몬1 행동 (기술 인덱스, 타겟 인덱스)] × [포켓몬2 행동 (기술 인덱스, 타겟 인덱스)]
```

각 포켓몬의 행동은 **PP > 0이고 비활성화되지 않은 기술**에 한해, **모든 상대 타겟과의 조합**으로 생성됩니다. 유효한 행동이 없으면 `(0, 0)`을 기본 반환.

### 4-4. 상태 평가 함수 (`evaluate_state`)

MCTS의 모든 평가는 이 함수의 반환값인 `own_score - enemy_score`로 이루어집니다.

**아군/적군 각각의 점수 계산 요소:**

| 요소 | 점수 | 의미 |
|------|------|------|
| 활성 포켓몬 HP 비율 합계 | `× 50` | HP 보존율 |
| KO된 적군 포켓몬 수 | `(4 - enemy_count) × 400` | KO 가중치 (가장 큰 점수) |
| 아군 활성 포켓몬 수 | `× 300` | 수적 우위 유지 |
| 아군 예비 포켓몬 수 | `× 100` | 후속 전력 보유 |
| 상대방 상태이상 | `+ 1000` (아군 점수) | 화상/마비 등 상태이상 유발 가치 |
| 스피드 스탯 | `+ speed` | 선공 우위 평가 |
| 스탯 변화(Boost) 합계 | `× 20` | 랭크업 가치 평가 |

**게임 종반(총 생존 수 ≤ 2) 보정**: 점수를 `× 0.8`로 줄여 종반의 극단적 평가를 완화.

> **핵심 설계 철학**: KO 1개의 가치(400점)는 HP 회복 전체(최대 50점)보다 **약 8배** 높게 설정됩니다. 이를 통해 DaehoAI는 본능적으로 **수적 우위(KO 우선)**를 추구하는 전략을 학습합니다.

### 4-5. MCTS 핵심 루프

**트리 정책 (`tree_policy`)**: 루트에서 리프까지 내려가며 탐색할 노드를 선택합니다.
- 아직 시도하지 않은 행동이 있으면 → **확장(Expand)**
- 모든 행동을 시도했으면 → **UCB1 점수 최고 자식 노드 선택**

**확장 (`expand_one_child`)**: 미시도 행동 중에서 다음 규칙으로 행동을 선택합니다:
- **80% 확률**: `GreedyBattlePolicy`가 추천하는 최선 행동 선택 (활용)
- **20% 확률**: 랜덤 행동 선택 (탐험)

상대방 행동도 동일하게 `GreedyBattlePolicy`를 통해 추론 (`opp_policy`).

**롤아웃 (`rollout`)**: 리프 노드에서 `rollout_depth`(4턴)만큼 시뮬레이션:
- 현재 상태가 **불리(score < 0)**하면: **60% 랜덤, 40% Greedy** (탈출 시도)
- 현재 상태가 **유리(score ≥ 0)**하면: **20% 랜덤, 80% Greedy** (우세 유지)

**역전파 (Backpropagation)**: 롤아웃 결과 점수를 루트까지 모든 조상 노드에 누적 (`total_reward`, `visit_count`).

**UCB1 공식** (자식 노드 선택):
```
UCB1 = Q + C × √(ln(N_parent) / N)
     = (총 보상 / 방문 횟수) + 탐험 계수 × √(부모 방문 로그 / 자신 방문 횟수)
```

### 4-6. 위기 탈출 메커니즘 (Adaptive Parameters)

MCTS 루프 중 롤아웃 결과가 `-600` 이하의 극단적 불리 상태로 나오면:
```python
if reward < -600:
    self.C = 10.0          # 탐험 계수를 대폭 높여 새로운 행동 탐색 강화
    self.rollout_depth *= 2  # 롤아웃 깊이를 2배 늘려 장기적 결과 고려
else:
    self.C = 1.41          # 정상 상태 복귀
    self.rollout_depth = 4
```

> **효과**: 위기 상황에서는 탐험성을 높이고 더 깊이 시뮬레이션하여 반전 가능성을 적극적으로 탐색합니다.

### 4-7. 최종 행동 결정 (`decision`)

- **MCTS 결과 있음**: 루트의 자식 노드 중 **UCB1 점수가 가장 높은 노드의 행동** 반환
- **MCTS 결과 없음** (탐색 실패 시): `GreedyBattlePolicy` 결과를 Fallback으로 사용

---

## 5. 트랙별 동작 흐름 요약

### ⚔️ Battle Track

Battle Track은 팀과 선발이 엔진에 의해 고정 제공되므로, **`EnhancedBattlePolicy`만 실행**됩니다.

```
[엔진이 팀 제공] → 매 턴: MCTS(90ms) → 최선 행동 반환
```

각 턴의 상세 흐름:
1. `decision(state)` 호출
2. `MCTS(state, 90ms)` 시작 → 90ms × 0.9 = **81ms 이내** 반복
3. `tree_policy` → `expand` 또는 `UCB1 select` → `rollout(4턴)` → `backpropagate`
4. 시간 초과 시 루트 자식 중 최고 UCB1 노드의 행동 반환
5. 탐색 결과가 없으면 `GreedyBattlePolicy` 폴백

### 🏆 Championship Track

Championship Track은 3단계 파이프라인이 **순서대로 모두 실행**됩니다.

```
[로스터 50마리 공개]
        ↓
① SmartTeamBuildPolicy: 50×50 매트릭스 → 그리디 탐색 → 최적 6마리 + EV/성격/기술 배정
        ↓
[상대방 6마리 엔트리 공개]
        ↓
② CoverageSelectionPolicy: m×k 매트릭스 → 그리디 탐색 → 커버리지 최적 4마리 선발
        ↓
[배틀 시작]
        ↓
③ EnhancedBattlePolicy: 매 턴 MCTS(90ms) → 최선 행동 반환
```

---

## 6. 종합 요약 (Conclusion)

**`DaehoAI`**는 세 개의 정책 모듈이 유기적으로 맞물린 **데이터 기반 General AI**입니다.

| 단계 | 모듈 | 핵심 기술 | 목표 |
|------|------|-----------|------|
| 팀 빌딩 | `SmartTeamBuildPolicy` | 50×50 매트릭스 + 그리디 커버리지 + 공유 약점 페널티 | 메타 전체를 커버하는 빈틈없는 6마리 조립 |
| 선발 | `CoverageSelectionPolicy` | m×k 매트릭스 + 분산 최소화 선발 | 상대 6마리 중 어떤 포켓몬도 무조건 카운터 가능한 4마리 |
| 배틀 | `EnhancedBattlePolicy` | MCTS + Greedy Rollout + 적응형 파라미터 | 매 턴 시뮬레이션 기반 최선의 수 결정 |
