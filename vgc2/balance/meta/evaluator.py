from typing import Callable

from vgc2.balance.meta import Meta, Roster

MetaEvaluator = Callable[[Meta], float]


def evaluate_meta(meta: Meta, roster: Roster) -> float:
    n = meta.n_pkm()
    if n == 0:
        return 0.

    # 1. Get usages in ID order (assuming roster is sorted by ID)
    usages = [meta.usage_rate_pokemon(p) for p in roster]

    # 2. Define the split point for the first 30%
    # We use round or int depending on how you want to handle mid-points
    split_idx = max(1, int(n * 0.30))

    # 3. Sum the actual usage for both segments
    actual_top_30_usage = sum(usages[:split_idx])
    actual_bottom_70_usage = sum(usages[split_idx:])

    # 4. Calculate distance from targets (0.7 and 0.3)
    # We take the absolute difference for both parts
    # Lower result = closer to your "Ideal Meta"
    dist_top = abs(0.7 - actual_top_30_usage)
    dist_bottom = abs(0.3 - actual_bottom_70_usage)

    return dist_top + dist_bottom
