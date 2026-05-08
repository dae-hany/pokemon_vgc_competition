import sys
sys.path.insert(0, 'my_submission')
from vgc2.battle_engine import State, BattleRuleParam, BattlingMove, Move, Type, Category
from vgc2.battle_engine.view import DUMMY_MOVE
print(DUMMY_MOVE.constants)
print(hasattr(DUMMY_MOVE.constants, 'pkm_type'))
