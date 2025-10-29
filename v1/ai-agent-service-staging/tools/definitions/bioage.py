import os
import pickle
import math
from typing import Dict

import numpy as np

from tools import tool


MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools_config"))


# The bio-age report tool accepts a flexible mapping of feature names to values.
# A strict JSON schema would disallow arbitrary feature keys and trigger errors
# when registering the tool with OpenAI. Relax the schema to permit additional
# properties so the tool can be invoked via function calling.
@tool(strict_schema=False)
def full_bioage_report(inputs: dict, bio_age: float, minimum_needed: int = 6) -> Dict:
    """Generate a full bio-age report.

    Args:
        inputs: Mapping of feature name to value.
        bio_age: The individual's actual age.
        minimum_needed: Minimum required features to proceed (default: 6).

    Returns:
        Dictionary with status, prediction details, top drivers, and text report.
    """

    # ---- helper: missing checker ----
    def is_missing(x):
        return x is None or (isinstance(x, float) and math.isnan(x)) \
               or (isinstance(x, np.floating) and np.isnan(x))

    # Required features
    required_features = [
        "LBXGH", "BMXWAIST", "LBDHDD", "BMXWT", "LBXGLU",
        "BMXBMI", "LBDTRSI", "LBDLDL", "BMXHT", "RIAGENDR"
    ]

    present_required = {k: v for k, v in inputs.items() if (k in required_features and not is_missing(v))}
    missing = [k for k in required_features if (k not in inputs or is_missing(inputs[k]))]

    if len(present_required) < minimum_needed:
        return {"status": "insufficient", "missing": missing}

    status = "all_inputs" if len(missing) == 0 else "minimum_inputs"

    # ---- prediction part ----
    model_paths = sorted([
        os.path.join(MODELS_DIR, f) for f in os.listdir(MODELS_DIR) if f.endswith(".pkl")
    ])
    if not model_paths:
        raise FileNotFoundError(f"No .pkl models found in: {MODELS_DIR}")

    per_model_preds = []
    for path in model_paths:
        with open(path, "rb") as f:
            bundle = pickle.load(f)  # expects: model, scaler, feature_names
        features_required = bundle["feature_names"]
        row = np.array([[float(inputs.get(f, np.nan)) for f in features_required]])
        X_scaled = bundle["scaler"].transform(row)
        pred = bundle["model"].predict(X_scaled)
        per_model_preds.append(float(pred))

    predicted_age = float(np.mean(per_model_preds))
    age_diff = predicted_age - float(bio_age)

    non_empty = {k: v for k, v in inputs.items() if not is_missing(v)}
    sex = non_empty.get("RIAGENDR", None)

    # ---- out-of-range evaluators ----
    def eval_LBXGH(v):
        if v < 5.7:
            return None
        if 5.7 <= v <= 6.4:
            return ("Prediabetes", "5.7–6.4%")
        return ("Diabetes-range", "≥6.5%")

    def eval_BMXWAIST(v):
        if sex == 1:
            if v > 102:
                return ("High cardiometabolic risk", "men >102cm")
            if v > 94:
                return ("Increased risk", "men >94cm")
        elif sex == 2:
            if v > 88:
                return ("High cardiometabolic risk", "women >88cm")
            if v > 80:
                return ("Increased risk", "women >80cm")
        else:
            if v > 88:
                return ("Potential increased risk", "sex unknown; >88cm")
        return None

    def eval_LBDHDD(v):
        if sex == 1:
            if v < 40:
                return ("Low HDL", "<40 mg/dL (male)")
        elif sex == 2:
            if v < 50:
                return ("Low HDL", "<50 mg/dL (female)")
        else:
            if v < 40:
                return ("Low HDL", "<40 mg/dL")
        return None

    def eval_LBXGLU(v):
        if v < 100:
            return None
        if 100 <= v <= 125:
            return ("Prediabetes-range", "100–125 mg/dL")
        return ("Diabetes-range", "≥126 mg/dL")

    def eval_SMQ040(v):
        if v and v != 0:
            return ("Smoker", "Any current smoking increases risk")
        return None

    def eval_BMXBMI(v):
        if 18.5 <= v <= 24.9:
            return None
        if 25.0 <= v <= 29.9:
            return ("Overweight", "25.0–29.9")
        if v >= 30.0:
            return ("Obesity", "≥30.0")
        if v < 18.5:
            return ("Underweight", "<18.5")
        return None

    def eval_LBDTRSI(v):
        if v < 1.7:
            return None
        if 1.7 <= v <= 2.2:
            return ("Borderline high TG", "1.7–2.2 mmol/L")
        if 2.3 <= v <= 5.6:
            return ("High TG", "2.3–5.6 mmol/L")
        return ("Very high TG", "≥5.7 mmol/L")

    def eval_LBDLDL(v):
        if v < 100:
            return None
        return ("Above optimal LDL", "≥100 mg/dL")

    def eval_LBXHSCRP(v):
        if v < 1.0:
            return None
        if 1.0 <= v <= 3.0:
            return ("Average CV risk", "1.0–3.0 mg/L")
        return ("High CV risk", ">3.0 mg/L")

    evaluators = {
        "LBXGH": eval_LBXGH,
        "BMXWAIST": eval_BMXWAIST,
        "LBDHDD": eval_LBDHDD,
        "LBXGLU": eval_LBXGLU,
        "SMQ040": eval_SMQ040,
        "BMXBMI": eval_BMXBMI,
        "LBDTRSI": eval_LBDTRSI,
        "LBDLDL": eval_LBDLDL,
        "LBXHSCRP": eval_LBXHSCRP,
    }

    out_of_range = {}
    for feat, fn in evaluators.items():
        if feat in non_empty:
            res = fn(non_empty[feat])
            if res is not None:
                status_flag, details = res
                out_of_range[feat] = {
                    "value": float(non_empty[feat]),
                    "status": status_flag,
                    "details": details,
                }

    # ---- top 4 selection ----
    hierarchy = [
        "LBXGH",
        "LBXGLU",
        "BMXBMI",
        "BMXWAIST",
        "LBDLDL",
        "LBDTRSI",
        "LBXHSCRP",
        "LBDHDD",
        "SMQ040",
        "BMXWT",
        "BMXHT",
        "RIAGENDR",
        "ALQ130",
        "SMD650",
    ]
    oor_ordered = [f for f in hierarchy if f in out_of_range]
    if len(oor_ordered) >= 4:
        top4 = oor_ordered[:4]
    else:
        present_ordered = [f for f in hierarchy if f in non_empty and f not in oor_ordered]
        combined = oor_ordered + present_ordered
        if len(combined) < 4:
            others = [k for k in non_empty if k not in combined]
            combined += others
        top4 = combined[:4]

    # ---- table-style formatters ----
    def fmt_waist():
        v = non_empty.get("BMXWAIST")
        if v is None:
            return None
        if sex == 1:
            optimal = "<102 cm (40 in) for most men"
        elif sex == 2:
            optimal = "<88 cm (35 in) for most women"
        else:
            optimal = "<88 cm (35 in) for most women; <102 cm (40 in) for most men"
        return (
            f"Waist size: {v:.1f} cm\n"
            "What it is: Larger waist may mean more visceral fat, stressing heart/metabolism.\n"
            "Try this: more fiber, strength train, cut sugary drinks.\n"
            f"Optimal: {optimal}"
        )

    def fmt_bmi():
        v = non_empty.get("BMXBMI")
        if v is None:
            return None
        return (
            f"BMI: {v:.1f} kg/m²\n"
            "What it is: Estimates body fat.\n"
            "Try this: cardio + strength, 7–9k steps/day, whole foods.\n"
            "Optimal: 18.5–24.9"
        )

    def fmt_hdl():
        v = non_empty.get("LBDHDD")
        if v is None:
            return None
        if sex == 2:
            optimal = ">50 mg/dL (women); ≥60 protective"
        elif sex == 1:
            optimal = ">40 mg/dL (men); ≥60 protective"
        else:
            optimal = ">50 (women), >40 (men); ≥60 protective"
        return (
            f"HDL: {v:.0f} mg/dL\n"
            "What it is: Helps clear bad cholesterol.\n"
            "Try this: healthy fats, exercise, avoid smoking.\n"
            f"Optimal: {optimal}"
        )

    def fmt_triglycerides():
        v_mmol = non_empty.get("LBDTRSI")
        if v_mmol is None:
            return None
        v_mg = v_mmol * 88.57
        return (
            f"Triglycerides: {v_mg:.0f} mg/dL ({v_mmol:.2f} mmol/L)\n"
            "What it is: High with too much sugar, carbs, alcohol.\n"
            "Try this: cut sugar, limit alcohol, eat omega‑3.\n"
            "Optimal: <150 normal; 150–199 borderline; ≥200 high"
        )

    def fmt_ldl():
        v = non_empty.get("LBDLDL")
        if v is None:
            return None
        return (
            f"LDL: {v:.0f} mg/dL\n"
            "What it is: Can build up in arteries.\n"
            "Try this: swap saturated for unsaturated fats, add fiber.\n"
            "Optimal: <100 optimal; 100–129 near‑optimal; 130–159 borderline high; ≥160 high"
        )

    def fmt_glucose():
        v = non_empty.get("LBXGLU")
        if v is None:
            return None
        return (
            f"Glucose: {v:.0f} mg/dL\n"
            "What it is: High indicates possible insulin resistance.\n"
            "Try this: protein/veg first, less night starch, walk after meals.\n"
            "Optimal: 70–99 normal; 100–125 prediabetes; ≥126 diabetes"
        )

    def fmt_hba1c():
        v = non_empty.get("LBXGH")
        if v is None:
            return None
        return (
            f"HbA1c: {v:.1f}%\n"
            "What it is: Average blood sugar over 3 months.\n"
            "Try this: regular meals, resistance training.\n"
            "Optimal: <5.7 normal; 5.7–6.4 prediabetes; ≥6.5 diabetes"
        )

    def fmt_hscrp():
        v = non_empty.get("LBXHSCRP")
        if v is None:
            return None
        return (
            f"hs‑CRP: {v:.2f} mg/L\n"
            "What it is: Marker of inflammation.\n"
            "Try this: sleep, stress mgmt, anti‑inflammatory foods.\n"
            "Optimal: <1 low; 1–3 average; >3 high"
        )

    all_metrics_order = [
        ("BMXWAIST", fmt_waist),
        ("BMXBMI", fmt_bmi),
        ("LBDHDD", fmt_hdl),
        ("LBDTRSI", fmt_triglycerides),
        ("LBDLDL", fmt_ldl),
        ("LBXGLU", fmt_glucose),
        ("LBXGH", fmt_hba1c),
        ("LBXHSCRP", fmt_hscrp),
    ]

    # ---- build report ----
    gap_sign = "+" if age_diff >= 0 else "-"
    gap_abs = abs(age_diff)
    header = [
        f"Actual age: {bio_age:.1f}",
        f"Predicted age: {predicted_age:.1f}",
        f"Age gap: {gap_sign}{gap_abs:.1f} years ({'older' if age_diff >= 0 else 'younger'})",
        "",
    ]

    # Top 4
    top4_lines = ["Top 4 drivers:"]
    for f in top4:
        label = f
        if f == "BMXWAIST":
            label = "Waist size"
        elif f == "BMXBMI":
            label = "BMI"
        elif f == "LBDHDD":
            label = "HDL cholesterol"
        elif f == "LBDTRSI":
            label = "Triglycerides"
        elif f == "LBDLDL":
            label = "LDL cholesterol"
        elif f == "LBXGLU":
            label = "Fasting glucose"
        elif f == "LBXGH":
            label = "HbA1c"
        elif f == "LBXHSCRP":
            label = "hs‑CRP"
        elif f == "SMQ040":
            label = "Smoking status"
        status_note = ""
        if f in out_of_range:
            st = out_of_range[f]["status"]
            det = out_of_range[f]["details"]
            status_note = f" — out-of-range: {st} ({det})"
        elif f in non_empty:
            status_note = " — within reference"
        top4_lines.append(f"- {label}{status_note}")
    top4_lines.append("")

    # All metrics
    all_lines = ["All metrics:"]
    for code, formatter in all_metrics_order:
        block = formatter()
        if block:
            formatted_block = block.replace("\n", "\n  ")
            all_lines.append(f"- {formatted_block}")
    if status != "all_inputs" and missing:
        all_lines += ["", "Missing required:", "- " + ", ".join(missing)]

    report = "\n".join(header + top4_lines + all_lines)

    return {
        "status": status,
        "missing": missing,
        "bio_age": float(bio_age),
        "predicted_age": predicted_age,
        "age_gap": age_diff,
        "top_4": top4,
        "out_of_range": out_of_range,
        "report": report,
    }
