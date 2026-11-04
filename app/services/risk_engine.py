LEVELS = ((17, "Critical"), (10, "High"), (5, "Medium"), (1, "Low"))


def calculate_score(likelihood, impact):
    if not 1 <= likelihood <= 5 or not 1 <= impact <= 5:
        raise ValueError("Likelihood and impact must be between 1 and 5.")
    return likelihood * impact


def score_level(score):
    if not 1 <= score <= 25:
        raise ValueError("Score must be between 1 and 25.")
    return next(level for minimum, level in LEVELS if score >= minimum)


def assess_risk(likelihood, impact):
    score = calculate_score(likelihood, impact)
    return {"score": score, "level": score_level(score)}


def is_appetite_breach(residual_score, threshold):
    return residual_score > threshold
