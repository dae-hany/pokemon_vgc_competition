import math


def time_score(t, t_min=60, t_max=7200, score_min=1, score_max=10):
    # clamp
    t = max(t_min, min(t, t_max))

    # log scale normalization
    norm = (math.log(t) - math.log(t_min)) / (math.log(t_max) - math.log(t_min))
    score = score_max - norm * (score_max - score_min)
    return score
