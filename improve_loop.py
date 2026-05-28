"""
Pokemon VGC AI 자동 성능 고도화 루프.

Usage:
    C:\\Users\\daeho\\anaconda3\\envs\\pokemonai\\python.exe improve_loop.py [--baseline]

--baseline: baseline 측정 모드 (실험 실행 없이 현재 성능만 측정)
인수 없이 실행: 다음 실험을 queue에서 꺼내 적용 → 벤치마크 → 결정
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime

PYTHON = r"C:\Users\daeho\anaconda3\envs\pokemonai\python.exe"
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(REPO_ROOT, "loop_state.json")
BATTLE_RESULTS = os.path.join(REPO_ROOT, "battle_results.csv")

# ── 실험 정의 ──────────────────────────────────────────────────────────────────

_BATTLE_POLICY = os.path.join(REPO_ROOT, "my_submission_battleV2", "battle_policy.py")
_STRATEGY = os.path.join(REPO_ROOT, "my_submission_battleV2", "strategy.py")
_TEAM_BUILD = os.path.join(REPO_ROOT, "my_submission_battleV2", "team_build_policy.py")

EXPERIMENTS = {
    "P8": {
        "description": "_best_move: non-KO priority move 1.5x score",
        "file": _BATTLE_POLICY,
        "old": (
            "            dmg = calculate_damage(params, 0, bm.constants, state, pkm, d)\n"
            "            if bm.constants.priority > 0 and dmg >= d.hp:\n"
            "                return (mi, di)\n"
            "            if dmg > best_dmg:\n"
            "                best_dmg, best_cmd = dmg, (mi, di)"
        ),
        "new": (
            "            dmg = calculate_damage(params, 0, bm.constants, state, pkm, d)\n"
            "            if bm.constants.priority > 0:\n"
            "                if dmg >= d.hp:\n"
            "                    return (mi, di)\n"
            "                dmg_effective = dmg * 1.5\n"
            "            else:\n"
            "                dmg_effective = dmg\n"
            "            if dmg_effective > best_dmg:\n"
            "                best_dmg, best_cmd = dmg_effective, (mi, di)"
        ),
    },
    "P9": {
        "description": "_try_survival_switch: dynamic 2x threshold based on incoming/hp ratio",
        "file": _BATTLE_POLICY,
        "old": (
            "    cond_survival = (ratio < 0.25) and (total_incoming >= pkm.hp)\n"
            "    cond_4x = (max_eff >= 4.0) and (ratio <= 0.75)\n"
            "    cond_2x = (max_eff >= 2.0) and (ratio <= 0.50)"
        ),
        "new": (
            "    cond_survival = (ratio < 0.25) and (total_incoming >= pkm.hp)\n"
            "    cond_4x = (max_eff >= 4.0) and (ratio <= 0.75)\n"
            "    incoming_ratio = total_incoming / max(pkm.hp, 1)\n"
            "    threshold_2x = min(0.70, 0.50 + max(0.0, incoming_ratio - 1.0) * 0.20)\n"
            "    cond_2x = (max_eff >= 2.0) and (ratio <= threshold_2x)"
        ),
    },
    "P10": {
        "description": "_score_attacker: speed coefficient 0.55 -> 0.35",
        "file": _STRATEGY,
        "old": "    return 1.07 * total + 0.30 * (hp_r * def_r) + 0.55 * spd_r",
        "new": "    return 1.07 * total + 0.30 * (hp_r * def_r) + 0.35 * spd_r",
    },
    "P11": {
        "description": "_score_bulk: HP component sqrt (soften multiplicative penalty)",
        "file": _TEAM_BUILD,
        "old": (
            "def _score_bulk(species) -> float:\n"
            "    hp_ratio = max(species.base_stats[Stat.MAX_HP], 1) / 150\n"
            "    def_ratio = max(species.base_stats[Stat.DEFENSE], 1) / 150\n"
            "    spd_ratio = max(species.base_stats[Stat.SPECIAL_DEFENSE], 1) / 150\n"
            "    return hp_ratio * def_ratio * spd_ratio"
        ),
        "new": (
            "def _score_bulk(species) -> float:\n"
            "    hp_ratio  = (max(species.base_stats[Stat.MAX_HP], 1) / 150) ** 0.5\n"
            "    def_ratio = max(species.base_stats[Stat.DEFENSE], 1) / 150\n"
            "    spd_ratio = max(species.base_stats[Stat.SPECIAL_DEFENSE], 1) / 150\n"
            "    return hp_ratio * def_ratio * spd_ratio"
        ),
    },
    "P12": {
        "description": "_try_protect: tactical protect vs current HP (not max HP)",
        "file": _BATTLE_POLICY,
        "old": (
            "    # Tactical protect: primary threat deals ≥50% HP and partner can KO that same threat\n"
            "    if (incoming_by_opp[primary_di] >= 0.5 * max_hp and\n"
            "            _partner_can_ko_specific(params, state, slot, primary_di)):\n"
            "        return (protect_idx, 0)"
        ),
        "new": (
            "    # Tactical protect: primary threat deals ≥40% current HP and ≥30% max HP\n"
            "    if (incoming_by_opp[primary_di] >= 0.40 * pkm.hp and\n"
            "            incoming_by_opp[primary_di] >= 0.30 * max_hp and\n"
            "            _partner_can_ko_specific(params, state, slot, primary_di)):\n"
            "        return (protect_idx, 0)"
        ),
    },
}

# ── 유틸 ───────────────────────────────────────────────────────────────────────

def read_state():
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def write_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def apply_patch(exp_id):
    exp = EXPERIMENTS[exp_id]
    content = open(exp["file"], encoding="utf-8").read()
    assert exp["old"] in content, (
        f"[ERROR] {exp_id}: patch target not found in {os.path.basename(exp['file'])}.\n"
        f"Expected:\n{exp['old']}"
    )
    new_content = content.replace(exp["old"], exp["new"], 1)
    open(exp["file"], "w", encoding="utf-8").write(new_content)
    print(f"  Applied patch to {os.path.basename(exp['file'])}")


def revert_patch(exp_id):
    exp = EXPERIMENTS[exp_id]
    rel_path = os.path.relpath(exp["file"], REPO_ROOT).replace("\\", "/")
    result = subprocess.run(
        ["git", "checkout", "HEAD", "--", rel_path],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  [WARN] git checkout failed: {result.stderr}")
    else:
        print(f"  Reverted {os.path.basename(exp['file'])}")


def commit_change(exp_id, description):
    exp = EXPERIMENTS[exp_id]
    rel_path = os.path.relpath(exp["file"], REPO_ROOT).replace("\\", "/")
    subprocess.run(["git", "add", rel_path], cwd=REPO_ROOT)
    msg = f"battleV2 {exp_id}: {description}"
    subprocess.run(["git", "commit", "-m", msg], cwd=REPO_ROOT)
    print(f"  Committed: {msg}")


def run_benchmark():
    print("  Running benchmark (--fast --loop)...")
    result = subprocess.run(
        [PYTHON, "battle_benchmark.py", "--fast", "--loop", "--submission", "battleV2"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
    )
    if result.stdout:
        for line in result.stdout.splitlines():
            if any(k in line for k in ["WR:", ">>> Battle", "SUMMARY", "=====", "-----",
                                        "Opponent", "Greedy", "JJJ", "Yamabuki", "ERROR"]):
                print(" ", line)
    if result.returncode != 0 and result.stderr:
        print("  [STDERR]", result.stderr[:400])
    return result.returncode


def parse_latest_results():
    if not os.path.exists(BATTLE_RESULTS):
        return None
    rows = []
    with open(BATTLE_RESULTS, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    if not rows:
        return None
    latest_ts = rows[-1]["Timestamp"]
    results = {}
    for r in rows:
        if r["Timestamp"] == latest_ts:
            wr_str = r["WinRate"].replace("%", "").strip()
            try:
                results[r["Opponent"]] = float(wr_str)
            except ValueError:
                pass
    return results if results else None


def compute_weighted_delta(current, baseline):
    dg = current.get("Greedy", baseline["greedy"]) - baseline["greedy"]
    dj = current.get("JJJ",    baseline["jjj"])    - baseline["jjj"]
    dy = current.get("Yamabuki", baseline["yamabuki"]) - baseline["yamabuki"]
    weighted = 0.35 * dg + 0.35 * dj + 0.30 * dy
    min_drop = min(dg, dj, dy)
    return weighted, dg, dj, dy, min_drop


def decide(current, baseline, run_count):
    weighted, dg, dj, dy, min_drop = compute_weighted_delta(current, baseline)
    print(f"\n  Δgreedy={dg:+.1f}%  ΔJJJ={dj:+.1f}%  ΔYamabuki={dy:+.1f}%")
    print(f"  weighted_delta={weighted:+.2f}%  min_single_drop={min_drop:+.1f}%")

    if weighted < -1.0 or min_drop < -6.0:
        return "revert"
    elif weighted >= 1.0 and min_drop >= -4.0:
        return "keep"
    else:
        if run_count < 2:
            return "rerun"
        # After 2 runs with borderline result, decide by weighted sign
        return "keep" if weighted >= 0 else "revert"


def print_summary(state):
    sep = "=" * 65
    print(f"\n{sep}")
    print(" IMPROVEMENT LOOP — FINAL SUMMARY")
    print(sep)
    print(f" Baseline: Greedy={state['baseline']['greedy']}%  JJJ={state['baseline']['jjj']}%  Yamabuki={state['baseline']['yamabuki']}%")
    print()
    for h in state["history"]:
        status = h["status"].upper()
        r = h.get("results", {}) or {}
        g = r.get("Greedy", "?")
        j = r.get("JJJ", "?")
        y = r.get("Yamabuki", "?")
        print(f" [{status:6}] {h['id']}: {h['description']}")
        print(f"          Greedy={g}%  JJJ={j}%  Yamabuki={y}%")
    print(sep)
    remaining = state.get("queue", [])
    if remaining:
        print(f" Remaining queue: {remaining}")
    else:
        print(" Queue exhausted.")
    print(sep + "\n")


# ── 메인 로직 ──────────────────────────────────────────────────────────────────

def run_baseline():
    print("\n[BASELINE] Running baseline benchmark...")
    rc = run_benchmark()
    if rc != 0:
        print("[ERROR] Benchmark failed.")
        sys.exit(1)
    results = parse_latest_results()
    if not results:
        print("[ERROR] Could not parse results.")
        sys.exit(1)
    state = read_state()
    state["baseline"]["greedy"]   = results.get("Greedy", state["baseline"]["greedy"])
    state["baseline"]["jjj"]      = results.get("JJJ",    state["baseline"]["jjj"])
    state["baseline"]["yamabuki"] = results.get("Yamabuki", state["baseline"]["yamabuki"])
    state["phase"] = "pending"
    write_state(state)
    print(f"\n[BASELINE] Greedy={state['baseline']['greedy']}%  JJJ={state['baseline']['jjj']}%  Yamabuki={state['baseline']['yamabuki']}%")
    print("[BASELINE] Saved to loop_state.json. Ready to run experiments.")


def run_next_experiment():
    state = read_state()

    if state["phase"] == "baseline":
        print("[INFO] Baseline not yet measured. Run with --baseline first.")
        sys.exit(0)

    if state["phase"] != "pending":
        print(f"[INFO] Unexpected phase '{state['phase']}'. Resetting to pending.")
        state["phase"] = "pending"
        write_state(state)

    if not state["queue"]:
        print("\n[DONE] All experiments completed!")
        print_summary(state)
        sys.exit(0)

    exp_id = state["queue"][0]
    exp = EXPERIMENTS[exp_id]
    state["iteration"] += 1

    sep = "=" * 65
    print(f"\n{sep}")
    print(f" Iteration {state['iteration']}: Experiment {exp_id}")
    print(f" {exp['description']}")
    print(sep)

    # 1. Apply patch
    try:
        apply_patch(exp_id)
    except AssertionError as e:
        print(f"[ERROR] {e}")
        state["history"].append({
            "id": exp_id, "description": exp["description"],
            "status": "error", "results": None
        })
        state["queue"].pop(0)
        write_state(state)
        sys.exit(1)

    # 2. Run benchmark (possibly twice if borderline)
    run_count = 0
    accumulated = None
    decision = "rerun"

    while decision == "rerun":
        run_count += 1
        print(f"\n  [Run {run_count}]")
        rc = run_benchmark()
        if rc != 0:
            print("[ERROR] Benchmark failed — reverting.")
            revert_patch(exp_id)
            state["history"].append({
                "id": exp_id, "description": exp["description"],
                "status": "error", "results": None
            })
            state["queue"].pop(0)
            write_state(state)
            sys.exit(1)

        current = parse_latest_results()
        if not current:
            print("[ERROR] Could not parse results — reverting.")
            revert_patch(exp_id)
            state["history"].append({
                "id": exp_id, "description": exp["description"],
                "status": "error", "results": None
            })
            state["queue"].pop(0)
            write_state(state)
            sys.exit(1)

        if accumulated is None:
            accumulated = current
        else:
            # Average two runs
            accumulated = {
                k: (accumulated.get(k, 0) + current.get(k, 0)) / 2
                for k in set(accumulated) | set(current)
            }

        decision = decide(accumulated, state["baseline"], run_count)

    # 3. Keep or revert
    print(f"\n  Decision: {decision.upper()}")

    if decision == "keep":
        state["baseline"]["greedy"]   = accumulated.get("Greedy",   state["baseline"]["greedy"])
        state["baseline"]["jjj"]      = accumulated.get("JJJ",      state["baseline"]["jjj"])
        state["baseline"]["yamabuki"] = accumulated.get("Yamabuki", state["baseline"]["yamabuki"])
        commit_change(exp_id, exp["description"])
        print(f"  New baseline: Greedy={state['baseline']['greedy']:.1f}%  JJJ={state['baseline']['jjj']:.1f}%  Yamabuki={state['baseline']['yamabuki']:.1f}%")
    else:
        revert_patch(exp_id)

    # 4. Update state
    state["history"].append({
        "id": exp_id,
        "description": exp["description"],
        "status": decision,
        "results": {k: round(v, 1) for k, v in accumulated.items()},
    })
    state["queue"].pop(0)
    state["phase"] = "pending"
    write_state(state)

    print(f"\n  Remaining queue: {state['queue']}")

    if not state["queue"]:
        print("\n[DONE] All experiments completed!")
        print_summary(state)
    else:
        print(f"  Next: {state['queue'][0]} — {EXPERIMENTS[state['queue'][0]]['description']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VGC AI Improvement Loop")
    parser.add_argument("--baseline", action="store_true",
                        help="Measure baseline performance and save to loop_state.json")
    args = parser.parse_args()

    if args.baseline:
        run_baseline()
    else:
        run_next_experiment()
