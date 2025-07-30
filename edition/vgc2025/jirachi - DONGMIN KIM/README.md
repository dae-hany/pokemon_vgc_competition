# 🌟 Smart Jirachi AI - VGC2 Competition Suite

## 🎯 Overview

Smart Jirachi AI는 VGC2 competiton을 위한 AI 시스템입니다. Thunder(青木栄太) 선수의 혁신적인 알고리즘을 참고하였습니다.
Always Smart Beam Search와 Max Firepower 전략을 핵심으로 합니다.

🧠 Core Philosophy: "지라치의 철학"
⚡ 핵심 원칙

1턴킬 > 모든 것: 상대를 즉시 처치할 수 있다면 최우선
스피드 = 생명: 선공권 확보가 승리의 열쇠
고위험 고보상: 확률이 낮더라도 고위력 기술 선호
환경 마스터: 날씨와 지형 완전 정복

🚀 Key Features
🧠 Always Smart Beam Search

매번 스마트 탐색: 모든 턴에서 빔 서치 적용
점진적 확장: beam_width [2→3→4→5], depth [1→2→3] 자동 탐색
Greedy 기본선: 5ms 내 안전한 기본 결과 확보
시간 예산 관리: 90% 시간 소모시 자동 중단

🔥 Max Firepower Strategy

화력 극대화 팀: 1설치자 + 3공격자 + 2카운터 = 6인
서포터 완전 제거: 불확실한 지원보다 확실한 화력
화력 극대화 선택: 1턴킬 기회 절대 우선 포착
이중 평가 시스템: 내 관점 + 상대방 관점 종합 판단

🌦️ 8개 환경 완전 지원
날씨 4개:

RAIN: 물, 전기 타입 부스트
SUN: 불꽃, 풀 타입 부스트
SAND: 바위, 땅, 강철 타입 부스트
SNOW: 얼음 타입 부스트

지형 4개:

ELECTRIC_TERRAIN: 전기 타입 부스트
GRASSY_TERRAIN: 풀 타입 부스트
MISTY_TERRAIN: 페어리 타입 부스트
PSYCHIC_TERRAIN: 에스퍼 타입 부스트

📁 File Structure
new/
├── jirachi_core_policies.py # Always Smart + Max Firepower Selection
├── jirachi_team_builder.py # Max Firepower Team Builder
├── jirachi_battle_competitor.py # Battle Track 경쟁자
├── jirachi_championship_competitor.py # Championship Track 경쟁자
└── README.md # 이 파일
🎯 Algorithm Details
🔍 Always Smart Beam Search Process

Greedy 기본선 확보 (5ms)
pythoncurrent_best = greedy_analysis(state)  # 안전한 기본 결과

점진적 빔 서치 확장 (최대 65ms)
pythonfor beam_width in [2, 3, 4, 5]:
for depth in [1, 2, 3]:
if time_remaining < 10ms:
break
beam_result = beam_search(state, beam_width, depth)
if beam_result.score > current_best.score:
current_best = beam_result

시간 예산 관리

90% 시간 소모시 조기 종료
남은 시간 10ms 미만시 탐색 중단

🔥 Max Firepower Team Strategy
팀 구성 (6명):
pythonteam_composition = {
'main_setter': 1, # 환경 설치자 (최고속)
'main_attackers': 2, # 환경 부스트 어태커  
'flex_attacker': 1, # 환경 독립 어태커
'counters': 2 # 카운터 전문
}
환경 부스트 계산:

기본 부스트: 날씨 1.5배 or 지형 1.3배
STAB 적용: 1.5배 추가
최대 배수: 1.5 × 1.3 × 1.5 = 2.925배 (날씨+지형+STAB)

🏆 Competition Advantages
⚡ 속도 우위

70ms 완전 활용: 시간 예산 동적 관리
매번 고품질: Always Smart로 일관된 결정 품질
적응형 탐색: 상황별 최적 깊이 자동 선택

🔥 화력 우위

압도적 화력: 공격자 3명으로 화력 집중
환경 마스터: 8개 환경 완전 활용
듀얼 시너지: 날씨+지형 동시 부스트

🎮 Usage
Battle Track
bashpython jirachi_battle_competitor.py --id 0 --time_limit 70
Championship Track
bashpython jirachi_championship_competitor.py --id 0 --time_limit 70
📝 Technical Specs

Language: Python 3.8+
Framework: VGC2 Competition Engine
Time Limit: 70ms per decision
Memory: Optimized with caching system
Algorithm: Always Smart Beam Search + Max Firepower

🌟 "지라치의 소원 - 매번 스마트하게, 화력으로 승부!" 🌟

## 🙏 Acknowledgments

### Thunder (青木栄太) Algorithm Reference

이 프로젝트는 Thunder 선수의 혁신적인 MCTS(Monte Carlo Tree Search) 알고리즘과 전략적 사고를 참고하여 개발되었습니다:

- **MCTS Foundation**: Thunder의 기본 트리 서치 구조
- **Risk Assessment**: 위험도 기반 의사결정 시스템
- **Meta Analysis**: 메타게임 데이터 활용 방법론
- **Time Management**: 제한된 시간 내 최적화 기법

## 📝 License & Contact

- **Author**: Jirachi AI Development Team
- **Based on**: Thunder (青木栄太) Algorithm Framework
- **License**: VGC2 Competition License
- **Version**: 1.0.0 (Smart Beam Search + Dual Environment)


