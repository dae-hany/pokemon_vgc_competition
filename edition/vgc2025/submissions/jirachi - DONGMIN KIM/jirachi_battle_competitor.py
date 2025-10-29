"""
Enhanced Jirachi AI Battle Track Competitor - VGC2 호환성 최적화
Import 안정성 강화 + 기존 구조 완전 유지
"""

import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# VGC2 imports with enhanced stability
try:
    from vgc2.agent import BattlePolicy, SelectionPolicy
    from vgc2.competition import Competitor
except ImportError as e:
    print(f"Critical VGC2 import error: {e}")
    print("Please ensure VGC2 is properly installed")
    sys.exit(1)

# Import Jirachi policies with enhanced compatibility
try:
    from .jirachi_core_policies import AlwaysSmartBeamSearchPolicy, MaxFirepowerSelectionPolicy
except ImportError:
    try:
        from jirachi_core_policies import AlwaysSmartBeamSearchPolicy, MaxFirepowerSelectionPolicy
    except ImportError as e:
        print(f"Jirachi policies import error: {e}")
        print("Please ensure jirachi_core_policies.py exists in the same directory")
        sys.exit(1)


class SmartJirachiBattleCompetitor(Competitor):
    """Enhanced Smart Beam Search + Max Firepower Selection 지라치 배틀 경쟁자"""

    def __init__(self, name: str = "Smart_Jirachi_Battle_AI",
                 time_limit_ms: int = 90):
        self.__name = name

        # 🧠 Always Smart Beam Search 정책 (내부적으로 점진적 확장)
        try:
            self.__battle_policy = AlwaysSmartBeamSearchPolicy(
                time_limit_ms=time_limit_ms,
                is_championship=False
            )
        except Exception as e:
            print(f"❌ Battle policy initialization failed: {e}")
            raise

        # 🎯 Max Firepower Selection 정책
        try:
            self.__selection_policy = MaxFirepowerSelectionPolicy()
        except Exception as e:
            print(f"❌ Selection policy initialization failed: {e}")
            raise

        # ✅ 대회 제출용이므로 team_build_policy는 None이 올바름
        self.__team_build_policy = None

        print(f"🔥 Enhanced Jirachi Battle AI: {name}")
        print("🎯 Always Smart Beam Search + Max Firepower Selection")
        print(f"⏰ Time Budget: {time_limit_ms}ms")
        print("🌦️ 8개 환경 완전 지원 (날씨 4개 + 지형 4개)")
        print("✅ Battle Track: team_build_policy = None (올바른 설정)")

    @property
    def name(self) -> str:
        return self.__name

    @property
    def battlepolicy(self) -> BattlePolicy:
        return self.__battle_policy

    @property
    def selectionpolicy(self) -> SelectionPolicy:
        return self.__selection_policy

    @property
    def teambuildpolicy(self):
        return self.__team_build_policy


# 기존 호환성을 위한 별칭들
class JirachiBattleCompetitor(SmartJirachiBattleCompetitor):
    """기존 호환성을 위한 별칭"""
    pass


class EnhancedJirachiBattleCompetitor(SmartJirachiBattleCompetitor):
    """Enhanced 버전 별칭"""
    pass


if __name__ == "__main__":
    import argparse

    try:
        from vgc2.net.server import RemoteCompetitorManager, BASE_PORT
    except ImportError:
        print("Could not import RemoteCompetitorManager")
        print("Running in test mode...")

        competitor = SmartJirachiBattleCompetitor("Test_Smart_Jirachi")
        print(f"✅ Smart Jirachi competitor: {competitor.name}")

        print("\n🔥 Enhanced Jirachi Features:")
        print("• 🎯 Always Smart Beam Search: 매번 최고 품질 결정")
        print("• 🔥 Max Firepower Selection: 화력 극대화 우선순위")
        print("• 🌦️ 8개 환경 완전 지원: 날씨 4개 + 지형 4개")
        print("• ⚡ 이중 평가 시스템: 내 관점 + 상대방 관점")
        print("• 🕐 시간 예산 관리: 70ms 내 최적 성능")
        print("• 🎲 적응형 전략: 상황별 알고리즘 선택")
        print("• ✅ Battle Track 최적화: team_build_policy = None")
        sys.exit(0)

    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=int, default=0)
    parser.add_argument('--time_limit', type=int, default=90,
                        help='Time limit in ms (50-90)')
    parser.add_argument('--name', type=str, default='Smart_Jirachi',
                        help='Competitor name')
    args = parser.parse_args()

    print(f"🚀 Starting Smart Jirachi Battle competitor with ID {args.id}")
    print(f"⚙️ Time Limit: {args.time_limit}ms")

    competitor = SmartJirachiBattleCompetitor(
        name=f"{args.name}_{args.id}",
        time_limit_ms=args.time_limit
    )

    server = RemoteCompetitorManager(
        competitor,
        port=BASE_PORT + args.id,
        authkey=f'Smart_Jirachi_{args.id}'.encode('utf-8')
    )

    print(f"🌟 Server starting on port {BASE_PORT + args.id}")
    print("🔥 SMART JIRACHI AI READY FOR BATTLE!")
    print("=" * 50)
    print("🆕 Enhanced AI Advantages:")
    print("• 🎯 Always Smart: 매번 스마트 빔 서치")
    print("• 🔥 Max Firepower: 화력 극대화 선택")
    print("• 🌦️ Full Environment: 8개 환경 완전 지원")
    print("• ⚡ Dual Evaluation: 내+상대방 이중 평가")
    print("• 🕐 Time Optimal: 시간 예산 완벽 관리")
    print("• 🎲 Adaptive: 상황별 최적 알고리즘")
    print("• 💎 Contest Ready: 대회 제출 최적화")
    print("• ✅ Import Safety: 향상된 호환성")
    print("=" * 50)
    server.run()
