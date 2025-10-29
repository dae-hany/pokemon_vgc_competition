"""
Smart Jirachi Championship AI - VGC2 호환성 최적화
Import 안정성 강화 + Exception 처리 구체화 + 기존 구조 완전 유지
"""

import os
import sys
from typing import List, Dict

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# VGC2 imports with enhanced stability
try:
    from vgc2.agent import BattlePolicy, SelectionPolicy, TeamBuildPolicy
    from vgc2.competition import Competitor
except ImportError as e:
    print(f"Critical VGC2 import error: {e}")
    print("Please ensure VGC2 is properly installed")
    sys.exit(1)

# Import Jirachi policies with enhanced compatibility
try:
    from .jirachi_core_policies import AlwaysSmartBeamSearchPolicy, MaxFirepowerSelectionPolicy
    from .jirachi_team_builder import MaxFirepowerTeamBuildPolicy
except ImportError:
    try:
        from jirachi_core_policies import AlwaysSmartBeamSearchPolicy, MaxFirepowerSelectionPolicy
        from jirachi_team_builder import MaxFirepowerTeamBuildPolicy
    except ImportError as e:
        print(f"Jirachi modules import error: {e}")
        print("Please ensure all jirachi modules exist in the same directory")
        sys.exit(1)


class SmartJirachiChampionshipCompetitor(Competitor):
    """Always Smart Beam Search + Max Firepower 전략의 챔피언십 경쟁자"""

    def __init__(self, name: str = "Smart_Jirachi_Championship_AI",
                 time_limit_ms: int = 90):
        self.__name = name

        # 🧠 Always Smart Beam Search 정책 (Championship 모드)
        try:
            self.__battle_policy = AlwaysSmartBeamSearchPolicy(
                time_limit_ms=time_limit_ms,
                is_championship=True
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

        # 🏗️ Max Firepower Team Build 정책 (구체적 Exception 처리)
        try:
            self.__team_build_policy = MaxFirepowerTeamBuildPolicy(time_limit=60)
            print("✅ TeamBuildPolicy initialized with time_limit=60")
        except TypeError as e:
            print(f"⚠️ time_limit 파라미터 미지원: {e}")
            try:
                self.__team_build_policy = MaxFirepowerTeamBuildPolicy()
                print("✅ TeamBuildPolicy initialized without time_limit")
            except Exception as fallback_error:
                print(f"❌ TeamBuildPolicy fallback initialization failed: {fallback_error}")
                raise
        except Exception as e:
            print(f"❌ TeamBuildPolicy 초기화 실패: {e}")
            raise

        # 팀빌더와 선택 정책 연계
        self._link_team_builder_with_selection_policy()

        print(f"🏆 Smart Jirachi Championship AI: {name}")
        print("🔥 Always Smart + Max Firepower Team + Max Firepower Selection")
        print(f"⏰ Time Budget: {time_limit_ms}ms")
        print("🎯 1설치자 + 3공격자 + 2카운터 = 6인 (서포터 제거)")
        print("🌦️ 8개 환경 완전 지원 (날씨 4개 + 지형 4개)")

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
    def teambuildpolicy(self) -> TeamBuildPolicy:
        return self.__team_build_policy

    def _link_team_builder_with_selection_policy(self):
        """팀빌더와 선택 정책 연계 설정"""
        try:
            # 팀빌더의 환경 선택 결과를 Selection Policy에 전달
            if hasattr(self.__team_build_policy, 'get_environment_selections'):
                if hasattr(self.__team_build_policy, 'set_selection_callback'):
                    self.__team_build_policy.set_selection_callback(
                        lambda selections: self.__selection_policy.set_team_builder_selections(selections)
                    )
                    print("🔗 Team builder and selection policy linked successfully!")
                else:
                    print("⚠️ TeamBuildPolicy does not support selection callback")
            else:
                print("⚠️ TeamBuildPolicy does not provide environment selections")
        except Exception as e:
            print(f"⚠️ Policy linking warning: {e}")
            print("🔄 Continuing without advanced linking...")

    def update_team_builder_selections(self, selections: List[int]):
        """외부에서 팀빌더 선택 결과를 업데이트"""
        try:
            if hasattr(self.__selection_policy, 'set_team_builder_selections'):
                self.__selection_policy.set_team_builder_selections(selections)
                print(f"🏗️ Updated team builder selections: {selections}")
            else:
                print("⚠️ Selection policy does not support team builder selections")
        except Exception as e:
            print(f"⚠️ Failed to update selections: {e}")

    def get_team_strategy_info(self) -> Dict:
        """팀 전략 정보 반환"""
        return {
            'strategy': 'max_firepower',
            'composition': '1설치자 + 3공격자 + 2카운터',
            'environment_support': '8개 완전 지원 (날씨 4개 + 지형 4개)',
            'philosophy': '화력 극대화 + 환경 마스터',
            'features': [
                'Always Smart Beam Search',
                'Max Firepower Team Building',
                'Max Firepower Selection',
                '듀얼 환경 시너지',
                '환경 독립적 카운터'
            ]
        }


# 기존 호환성을 위한 별칭들
class JirachiChampionshipCompetitor(SmartJirachiChampionshipCompetitor):
    """기존 호환성을 위한 별칭"""
    pass


class EnhancedJirachiChampionshipCompetitor(SmartJirachiChampionshipCompetitor):
    """Enhanced 버전 별칭"""
    pass


if __name__ == "__main__":
    import argparse

    try:
        from vgc2.net.server import RemoteCompetitorManager, BASE_PORT
    except ImportError:
        print("Could not import RemoteCompetitorManager")
        print("Running in test mode...")

        competitor = SmartJirachiChampionshipCompetitor("Test_Championship")
        print(f"✅ Smart Championship competitor: {competitor.name}")

        # 팀 전략 정보 출력
        strategy_info = competitor.get_team_strategy_info()
        print(f"\n📊 Team Strategy: {strategy_info['strategy']}")
        print(f"📋 Composition: {strategy_info['composition']}")
        print(f"🌦️ Environment: {strategy_info['environment_support']}")

        print("\n🔥 Enhanced Championship Features:")
        print("• 🎯 Always Smart Beam Search: 매번 최고 품질 결정")
        print("• 🔥 Max Firepower Team: 1설치자+3공격자+2카운터")
        print("• 🌦️ 8개 환경 마스터: 날씨 4개 + 지형 4개 완전 지원")
        print("• ⚡ 화력 극대화 선택: 1턴킬 절대 우선")
        print("• 🕐 시간 예산 관리: 70ms 내 최적 성능")
        print("• 🔗 완벽 연계: 팀빌더-선택정책 통합")
        print("• ✅ Import Safety: 향상된 호환성")
        sys.exit(0)

    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=int, default=0)
    parser.add_argument('--time_limit', type=int, default=90
                        ,
                        help='Time limit in ms (50-90)')
    parser.add_argument('--name', type=str, default='Smart_Jirachi_Championship',
                        help='Competitor name')
    args = parser.parse_args()

    print(f"🚀 Starting Smart Jirachi Championship competitor with ID {args.id}")
    print(f"⚙️ Time Limit: {args.time_limit}ms")

    competitor = SmartJirachiChampionshipCompetitor(
        name=f"{args.name}_{args.id}",
        time_limit_ms=args.time_limit
    )

    server = RemoteCompetitorManager(
        competitor,
        port=BASE_PORT + args.id,
        authkey=f'Smart_Jirachi_Championship_{args.id}'.encode('utf-8')
    )

    print(f"🌟 Server starting on port {BASE_PORT + args.id}")
    print("🏆 SMART JIRACHI CHAMPIONSHIP AI READY!")
    print("=" * 60)
    print("🆕 Enhanced Championship AI:")
    print("• 🎯 Always Smart: 매번 스마트 빔 서치")
    print("• 🔥 Max Firepower: 화력 극대화 팀 구성")
    print("• 🌦️ 8개 환경 마스터: 완전한 환경 지원")
    print("• ⚡ 1턴킬 우선: 절대적 화력 우선순위")
    print("• 🕐 Time Optimal: 시간 예산 완벽 관리")
    print("• 🔗 Perfect Link: 팀빌더-선택 완벽 연계")
    print("• 💎 Contest Ready: 대회 제출 최적화")
    print("• 🏆 Championship: 장기전 메타 적응력")
    print("• ✅ Import Safety: 향상된 호환성")
    print("=" * 60)
    server.run()
