import time
import random
from vgc2.battle_engine import State, BattleRuleParam
from vgc2.util.generator import gen_team
from vgc2.battle_engine.game_state import get_battle_teams
import sys
import os
sys.path.insert(0, os.getcwd())

from my_submission.battle_policy import EnhancedBattlePolicy

def measure_time(rollout_depth=4, time_limit_ms=90, n_trials=50):
    policy = EnhancedBattlePolicy(time_limit_ms=time_limit_ms)
    policy.rollout_depth = rollout_depth
    params = BattleRuleParam()
    policy.set_params(params)

    times = []
    iterations = []
    
    for i in range(n_trials):
        # Generate a random state
        team0 = gen_team(4, 4)
        team1 = gen_team(4, 4)
        state = State(get_battle_teams((team0, team1), 2))
        
        # We need to simulate some turns to get to a non-trivial state if needed, 
        # but act() should work on the initial state too.
        
        start = time.perf_counter()
        # Mocking MCTS to track iterations
        # We'll wrap the MCTS method to count iterations if possible, 
        # but let's just measure time first.
        policy.decision(state)
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000.0
        times.append(elapsed_ms)
        
        if (i+1) % 10 == 0:
            print(f"Trial {i+1}/{n_trials} done...")

    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)
    
    print(f"\n--- Results for rollout_depth={rollout_depth}, time_limit={time_limit_ms}ms ---")
    print(f"Average Time: {avg_time:.2f} ms")
    print(f"Max Time:     {max_time:.2f} ms")
    print(f"Min Time:     {min_time:.2f} ms")
    print(f"Over 100ms:   {sum(1 for t in times if t > 100)} trials")
    print("--------------------------------------------------")

if __name__ == "__main__":
    print("Measuring performance for rollout_depth = 4...")
    measure_time(rollout_depth=4, time_limit_ms=90, n_trials=100)
    
    print("\nMeasuring performance for rollout_depth = 10 (as a comparison)...")
    measure_time(rollout_depth=10, time_limit_ms=90, n_trials=50)
