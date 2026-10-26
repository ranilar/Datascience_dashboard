import math
from decimal import ROUND_HALF_UP, Decimal

from .reference import COHORTS, PARAM_SPECS, SPECS_BY_ID


def js_round(x):
    return math.floor(x + 0.5)


def to_fixed(x, digits):
    return float(Decimal(x).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def normal_cdf(z):
    t = 1 / (1 + 0.2316419 * abs(z))
    d = 0.3989423 * math.exp(-z * z / 2)
    prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    return (1 - prob) * 100 if z > 0 else prob * 100


def hydration_target(sex):
    if sex == "M":
        return {"target": 3.7, "low": 3.4, "high": 4.1, "label": "3.7 L (Male Target)"}
    if sex == "F":
        return {"target": 2.7, "low": 2.4, "high": 3.1, "label": "2.7 L (Female Target)"}
    return {"target": 3.1, "low": 2.7, "high": 3.5, "label": "3.1 L (Dataset Norm)"}


def sub_score(param_id, val, sex):
    if param_id == "sleep_hours":
        if 7.0 <= val <= 9.0:
            return 100.0
        if val < 7.0:
            return max(0.0, 100 - math.pow((7.0 - val) / 1.5, 1.4) * 45)
        return max(0.0, 100 - math.pow((val - 9.0) / 1.5, 1.4) * 50)

    if param_id == "stress_level":
        if 2.0 <= val <= 3.0:
            return 100.0
        if val < 2.0:
            return 95.0
        return max(5.0, 100 - ((val - 3.0) / 7.0) * 92)

    if param_id == "daily_steps":
        if 7000 <= val <= 10000:
            return 100.0
        if val < 7000:
            return max(15.0, 100 - math.pow((7000 - val) / 5000, 1.25) * 78)
        return max(82.0, 100 - ((val - 10000) / 12000) * 16)

    if param_id == "heart_rate":
        if val <= 60:
            return 100.0
        return max(10.0, 100 - math.pow((val - 60) / 5.5, 1.2) * 8.5)

    if param_id == "endurance_level":
        if val >= 18.0:
            return 100.0
        if val <= 4.0:
            return 15.0
        return max(15.0, 15 + math.pow((val - 4.0) / 14.0, 1.05) * 85)

    if param_id == "bmi":
        if 22.0 <= val <= 25.0:
            return 100.0
        if val > 25.0:
            return 25.0 + (75.0 / (1.0 + math.pow((val - 25.0) / 8.0, 1.7)))
        deficit = 22.0 - val
        if val < 18.0:
            return max(15.0, 100 - (deficit / 4.0) * 65)
        return max(65.0, 100 - (deficit / 4.0) * 35)

    if param_id == "hydration_level":
        target = hydration_target(sex)
        if target["low"] <= val <= target["high"]:
            return 100.0
        if val < target["low"]:
            deficit = (target["low"] - val) / 1.5
            return max(10.0, 100 * math.exp(-0.45 * math.pow(deficit, 1.6)))
        excess = (val - target["high"]) / 1.5
        return max(35.0, 100 * math.exp(-0.35 * math.pow(excess, 1.5)))

    return 50.0


def synergies(vals):
    alerts = []
    total = 0.0

    if vals["bmi"] < 18.0:
        deduction = 4.0
        total += deduction
        alerts.append({
            "type": "danger",
            "title": "Underweight Clinical Concern",
            "description": f"BMI of {to_fixed(vals['bmi'], 1):.1f} kg/m² is below 18.0, flagged as a potential health concern for nutrient deficiency and bone density loss.",
            "deduction": deduction,
        })
    elif vals["bmi"] > 30.0:
        deduction = min(10, 3.5 + (vals["bmi"] - 30.0) * 0.35)
        total += deduction
        alerts.append({
            "type": "danger",
            "title": "Obesity Class Health Concern",
            "description": f"BMI of {to_fixed(vals['bmi'], 1):.1f} kg/m² exceeds 30.0, flagged as a potential health concern for elevated cardiometabolic risk.",
            "deduction": deduction,
        })

    if vals["daily_steps"] >= 20000:
        deduction = 2.0
        total += deduction
        alerts.append({
            "type": "warning",
            "title": "Physical Overexertion Warning",
            "description": f"Daily step volume exceeds 20,000 steps ({js_round(vals['daily_steps']):,}). Sustained high volume poses musculoskeletal fatigue.",
            "deduction": deduction,
        })

    if vals["sleep_hours"] < 6.0 or vals["sleep_hours"] > 10.0:
        short = vals["sleep_hours"] < 6.0
        deduction = 4.0 if short else 3.0
        total += deduction
        alerts.append({
            "type": "warning",
            "title": "Sleep Deprivation Alert" if short else "Hypersomnia Warning",
            "description": f"Logged sleep of {to_fixed(vals['sleep_hours'], 1):.1f} hrs falls outside the safe 6.0–10.0 hr recovery window.",
            "deduction": deduction,
        })

    if vals["sleep_hours"] < 6.2 and vals["stress_level"] > 6.0:
        sleep_severity = (6.2 - vals["sleep_hours"]) / 1.6
        stress_severity = (vals["stress_level"] - 6.0) / 4.0
        deduction = min(15, (sleep_severity * stress_severity * 12) + 3.5)
        total += deduction
        alerts.append({
            "type": "danger",
            "title": "Allostatic Burnout & Sleep Debt",
            "description": f"Short sleep ({to_fixed(vals['sleep_hours'], 1):.1f}h) paired with elevated stress ({to_fixed(vals['stress_level'], 1):.1f}/10) exhausts autonomic recovery.",
            "deduction": deduction,
        })

    return total, alerts


def verdict(score):
    if score >= 90:
        return {"tier": "emerald", "title": "Peak Vitality & High Resilience",
                "description": "Optimal physiological conditioning, low allostatic wear, and restorative recovery."}
    if score >= 75:
        return {"tier": "emerald", "title": "Robust Health Equilibrium",
                "description": "Consistent cardiorespiratory metrics with mild opportunities for habit optimization."}
    if score >= 60:
        return {"tier": "sky", "title": "Moderate Physiological State",
                "description": "Aligned with dataset averages. Regular activity sustains stability."}
    if score >= 45:
        return {"tier": "amber", "title": "Elevated Physiological Strain",
                "description": "Moderate allostatic stress detected across autonomic sleep or cardiometabolic markers."}
    return {"tier": "rose", "title": "Compounded Allostatic Load",
            "description": "Systemic strain detected. Chronic sleep restriction, elevated stress, or deconditioning."}


def _weighted_base(vals, sex):
    return sum(sub_score(p["id"], vals[p["id"]], sex) * p["weight"] for p in PARAM_SPECS)


ROI_CANDIDATES = [
    {"id": "sleep_hours", "delta": 1.0, "label": "sleeping 1 hour more"},
    {"id": "sleep_hours", "delta": -1.0, "label": "sleeping 1 hour less"},
    {"id": "stress_level", "delta": 1.0, "label": "raising stress by 1 point"},
    {"id": "stress_level", "delta": -1.0, "label": "lowering stress by 1 point"},
    {"id": "daily_steps", "delta": 2000, "label": "walking 2,000 more steps a day"},
    {"id": "daily_steps", "delta": -2000, "label": "walking 2,000 fewer steps a day"},
    {"id": "hydration_level", "delta": 0.5, "label": "drinking 0.5 L more water a day"},
    {"id": "hydration_level", "delta": -0.5, "label": "drinking 0.5 L less water a day"},
    {"id": "heart_rate", "delta": 5, "label": "raising resting heart rate by 5 bpm"},
    {"id": "heart_rate", "delta": -5, "label": "lowering resting heart rate by 5 bpm"},
    {"id": "endurance_level", "delta": 2.0, "label": "improving aerobic endurance by 2 points"},
    {"id": "endurance_level", "delta": -2.0, "label": "lowering aerobic endurance by 2 points"},
    {"id": "bmi", "delta": 1.0, "label": "raising BMI by 1 point"},
    {"id": "bmi", "delta": -1.0, "label": "lowering BMI by 1 point"},
]


def behavioral_roi(vals, sex, current_total):
    best = None
    max_gain = -999.0
    for cand in ROI_CANDIDATES:
        test_vals = dict(vals)
        spec = SPECS_BY_ID[cand["id"]]
        test_vals[cand["id"]] = max(spec["min"], min(spec["max"], test_vals[cand["id"]] + cand["delta"]))

        deduction, _ = synergies(test_vals)
        hypo_score = max(0.0, min(100.0, _weighted_base(test_vals, sex) - deduction))
        gain = hypo_score - current_total
        if gain > max_gain:
            max_gain = gain
            best = {"id": cand["id"], "label": cand["label"], "gain": gain}

    return best if best and best["gain"] > 0.4 else None


def evaluate(values, *, cohort, sex):
    vals = dict(values)

    stats = COHORTS[cohort]["stats"]
    sub_scores = {}
    percentiles = {}
    for p in PARAM_SPECS:
        pid = p["id"]
        val = vals[pid]
        sub_scores[pid] = sub_score(pid, val, sex)
        stat = stats[pid]
        z = (val - stat["mean"]) / stat["std"]
        pct = normal_cdf(-z) if pid in ("heart_rate", "stress_level") else normal_cdf(z)
        percentiles[pid] = {"z": z, "pct": pct, "mean": stat["mean"]}

    total_deduction, alerts = synergies(vals)
    weighted = sum(sub_scores[p["id"]] * p["weight"] for p in PARAM_SPECS)
    score = max(0.0, min(100.0, weighted - total_deduction))

    return {
        "score": score,
        "total_deduction": total_deduction,
        "verdict": verdict(score),
        "values": vals,
        "sub_scores": sub_scores,
        "percentiles": percentiles,
        "alerts": alerts,
        "roi": behavioral_roi(vals, sex, score),
        "hydration_target": hydration_target(sex),
    }
