import json
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from tools import tool

from tools.services.digbi_service import get_user_cgm_stats, get_user_meal_history_chunked

@tool
async def cgm_meals_summary(
        user_token: str,
        start_date: date,
        end_date: date,
        k: Optional[float] = None,
        min_trust: float = 0.45,
        alpha: float = 0.5,
):
    """
      - filters to entries with cgmDataAvailable
      - compiles per-day stats (counts, % good responses, ND scores)
      - selects champion/challenge days
      - summarizes by meal type (avg ND, typical time, consistency)
      - surfaces best/least helpful meals and response patterns
    """

    # Fetch meals day-by-day via the chunked fetcher
    input_json: List[Dict[str, Any]] = await get_user_meal_history_chunked(
        user_token=user_token,
        start_date=start_date,
        end_date=end_date
    )

    rows = []
    for item in input_json or []:
        fbs = item.get("feedbacks")
        if not (isinstance(fbs, list) and fbs and fbs[0].get("cgmDataAvailable") is True):
            continue

        fb = fbs[0]
        impactors = fb.get("infractionTitlesToScores", {}) or {}
        ingredients = fb.get("ingredients") or []
        if not ingredients:
            desc = (item.get("foodDescription") or "").strip()
            ingredients = [desc] if desc else ["Meal details not available"]

        peak_score = impactors.get("Poor CGM Peak")
        rec_score = impactors.get("Poor CGM 2hr Recovery")
        good_peak = peak_score is None
        good_recovery = rec_score is None
        poor_peak = peak_score in (-1, -2)
        poor_recovery = rec_score in (-1, -2)

        rows.append(
            {
                "date": pd.to_datetime(item["postedDate"]).date(),
                "time": item.get("postedTime", ""),
                "meal_type": (item.get("mealType") or "").replace("_", " ").title(),
                "description": (item.get("foodDescription") or "").strip(),
                "nd_score": fb.get("totalScore", np.nan),
                "nd_score_impactors": impactors,
                "ingredients": ingredients,
                "meal_feedback": fb.get("message", ""),
                "good_peak": good_peak,
                "good_recovery": good_recovery,
                "good_peak_good_recovery": bool(good_peak and good_recovery),
                "poor_peak_poor_recovery": bool(poor_peak and poor_recovery),
                "good_peak_poor_recovery": bool(good_peak and poor_recovery),
                "poor_peak_good_recovery": bool(poor_peak and good_recovery),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return json.dumps(
            {
                "champion_day": None,
                "challenge_day": None,
                "meal_type_summary": [],
                "best_performing_meals": [],
                "least_helpful_meals": [],
                "meal_glucose_response_patterns": [],
            },
            indent=2,
            default=str,
        )

    # ---------- Per-day rollup ----------
    day = (
        df.groupby("date")
        .agg(
            total_meals=("date", "size"),
            good_peak_good_recovery_count=("good_peak_good_recovery", "sum"),
            median_nd_score=("nd_score", "median"),
            average_nd_score=("nd_score", "mean"),
        )
        .reset_index()
    )
    day["poor_peak_poor_recovery_count"] = day["total_meals"] - day["good_peak_good_recovery_count"]
    day["pct_good_peak_good_recovery"] = (100 * day["good_peak_good_recovery_count"] / day["total_meals"]).round(2)

    # ---------- Trusted days & composite ----------
    if k is None:
        k = float(day["total_meals"].median())
    day = day.copy()
    day["weight"] = day["total_meals"] / (day["total_meals"] + k)
    trusted = day[day["weight"] >= min_trust]
    if trusted.empty:
        trusted = day.copy()

    trusted["pct_frac"] = trusted["pct_good_peak_good_recovery"] / 100.0
    trusted["nd"] = trusted["average_nd_score"]
    nd_min, nd_max = float(trusted["nd"].min()), float(trusted["nd"].max())
    trusted["norm_nd"] = (trusted["nd"] - nd_min) / (nd_max - nd_min) if nd_max > nd_min else 1.0
    trusted["composite_score"] = alpha * trusted["pct_frac"] + (1 - alpha) * trusted["norm_nd"]

    trusted_sorted = trusted.sort_values(
        ["composite_score", "average_nd_score", "pct_frac", "total_meals", "date"],
        ascending=[False, False, False, False, False],
    )

    # Champion
    champion_row = trusted_sorted.iloc[0] if not trusted_sorted.empty else day.sort_values(
        ["average_nd_score", "pct_good_peak_good_recovery", "total_meals", "date"],
        ascending=[False, False, False, True],
    ).iloc[0]

    # Challenge (pick a lower ND than champion; otherwise None)
    pool = trusted_sorted[trusted_sorted["date"] != champion_row["date"]]
    candidates = pool[pool["average_nd_score"] < champion_row["average_nd_score"]]

    if not candidates.empty:
        # prefer lowest composite/ND first among trusted pool
        challenge_row = candidates.sort_values(
            by=["composite_score", "average_nd_score", "pct_frac", "total_meals", "date"],
            ascending=[True, True, False, False, True],
        ).iloc[0]
    else:
        # FALLBACK: search the full day summary for any lower-ND day
        fallback = day[
            (day["date"] != champion_row["date"]) &
            (day["average_nd_score"] < champion_row["average_nd_score"])
            ]
        if not fallback.empty:
            challenge_row = fallback.sort_values(
                by=["average_nd_score", "pct_good_peak_good_recovery", "total_meals", "date"],
                ascending=[True, False, False, True],
            )   .iloc[0]
        else:
            challenge_row = None

    # Enforce ND contrast just in case
    if challenge_row is not None and float(challenge_row["average_nd_score"]) >= float(champion_row["average_nd_score"]):
        challenge_row = None

    # Business-rule fallback (unchanged)
    if challenge_row is None and float(champion_row["average_nd_score"]) < 12:
        # Use champion as challenge; drop champion
        challenge_row, champion_row = champion_row, None

    # ---------- Meal type summary ----------
    # Parse times (assume HH:MM; add seconds if missing)
    times = df["time"].fillna("").astype(str)
    df["parsed_time"] = pd.to_timedelta(df["time"] + ":00", errors="coerce")
    df["time_numeric"] = df["parsed_time"].dt.total_seconds()

    total_meals = len(df)

    def _iqr_minutes(x: pd.Series) -> float:
        if len(x) == 0 or x.isna().all():
            return np.nan
        p75, p25 = np.percentile(x.dropna(), [75, 25])
        return round(float((p75 - p25) / 60.0), 2)

    def _consistency(iqr_min: float) -> str:
        if pd.isna(iqr_min): return "Inconsistent"
        if iqr_min <= 30:    return "Consistent"
        if iqr_min <= 90:    return "Fairly Consistent"
        return "Inconsistent"

    mts = (
        df.groupby("meal_type")
        .agg(
            average_nd_score=("nd_score", lambda x: round(float(np.mean(x)), 2)),
            median_seconds=("time_numeric", "median"),
            iqr_minutes=("time_numeric", _iqr_minutes),
            count=("meal_type", "size"),
        )
        .reset_index()
    )
    mts["pct_of_meals"] = (mts["count"] / total_meals * 100).round(1) if total_meals else 0.0
    mts["typical_time"] = pd.to_datetime(mts["median_seconds"], unit="s", errors="coerce").dt.strftime("%H:%M")
    mts["consistency"] = mts["iqr_minutes"].apply(_consistency)
    meal_type_summary = mts[["meal_type", "average_nd_score", "pct_of_meals", "typical_time", "consistency"]].to_dict(
        orient="records"
    )

    # ---------- Best / Least helpful meals ----------
    df["nd_score"] = pd.to_numeric(df["nd_score"], errors="coerce")
    df["flat_ingredients"] = df["ingredients"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x or ""))

    # Initial best: 1 per meal_type among good-both; fallback: top 3 among (good_peak OR good_recovery)
    initial_best = (
        df[df["good_peak"] & df["good_recovery"]]
        .groupby("meal_type", group_keys=False)
        .apply(lambda x: x.nlargest(1, "nd_score"))
        .reset_index(drop=True)
    )
    if len(initial_best) < 3:
        initial_best = df[(df["good_peak"] | df["good_recovery"])].nlargest(3, "nd_score")

    # Initial worst: 1 per meal_type among poor-both; fallback: absolute 3 lowest overall
    initial_worst = (
        df[~df["good_peak"] & ~df["good_recovery"]]
        .groupby("meal_type", group_keys=False)
        .apply(lambda x: x.nsmallest(1, "nd_score"))
        .reset_index(drop=True)
    )
    if len(initial_worst) < 3:
        initial_worst = df.nsmallest(3, "nd_score")

    # Conflict resolution: same meal in both -> keep in best if ND >= 12, else keep in worst
    def _key(r):
        return (str(r["date"]), str(r["time"]), r["flat_ingredients"].strip().lower())

    best_keys = set(initial_best.apply(_key, axis=1))
    worst_keys = set(initial_worst.apply(_key, axis=1))
    conflicts = best_keys & worst_keys

    final_best_rows = []
    for _, r in initial_best.iterrows():
        if _key(r) in conflicts and float(r["nd_score"]) < 12:
            continue
        final_best_rows.append(r)

    final_worst_rows = []
    for _, r in initial_worst.iterrows():
        if _key(r) in conflicts and float(r["nd_score"]) >= 12:
            continue
        final_worst_rows.append(r)

    # Ensure we still have 3 in worst by filling from absolute lowest (excluding best/dups)
    if len(final_worst_rows) < 3:
        used = { _key(r) for r in final_worst_rows }
        abs_low = df.nsmallest(10, "nd_score")  # small buffer
        for _, r in abs_low.iterrows():
            k_ = _key(r)
            if k_ in used or k_ in best_keys:
                continue
            final_worst_rows.append(r)
            used.add(k_)
            if len(final_worst_rows) == 3:
                break

    best_meals_df = pd.DataFrame(final_best_rows)
    worst_meals_df = pd.DataFrame(final_worst_rows).sort_values(
        ["nd_score", "date", "time"], ascending=[True, True, True], kind="mergesort"
    )

    def _format_pick(table: pd.DataFrame) -> List[Dict[str, Any]]:
        if table.empty:
            return []
        sub = table[["meal_type", "date", "time", "nd_score", "flat_ingredients"]].copy()
        sub = sub.rename(columns={"flat_ingredients": "ingredients"})
        sub["date"] = sub["date"].astype(str)
        return sub.to_dict(orient="records")

    best_meals = _format_pick(best_meals_df)
    least_helpful_meals = _format_pick(worst_meals_df)

    # ---------- Response patterns ----------
    def _response_type(row):
        if row["good_peak_good_recovery"]:
            return "Good Peak & Good Recovery"
        if row["good_peak_poor_recovery"]:
            return "Good Peak & Poor Recovery"
        if row["poor_peak_good_recovery"]:
            return "Poor Peak & Good Recovery"
        if row["poor_peak_poor_recovery"]:
            return "Poor Peak & Poor Recovery"
        return None

    df["response_type"] = df.apply(_response_type, axis=1)
    df["flat_deductors"] = df["nd_score_impactors"].apply(
        lambda d: ", ".join([k for k, v in (d or {}).items() if v in (-1, -2)])
    )
    df["ingredients_str"] = df["ingredients"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x or ""))

    with_patterns = df[df["response_type"].notna()]
    rp = (
        with_patterns.groupby("response_type")
        .agg(
            pct_of_meals=("response_type", lambda x: round(100 * len(x) / total_meals, 1)),
            average_nd_score=("nd_score", lambda x: round(float(np.mean(x)), 2)),
            common_issues=("flat_deductors", lambda x: ", ".join([t for t in x if t])),
            meal_ingredients=("ingredients_str", lambda x: ", ".join([t for t in x if t])),
        )
        .reset_index()
        .sort_values("pct_of_meals", ascending=False)
        .to_dict(orient="records")
    )

    # ---------- Assemble champion/challenge day details ----------
    def _assemble_day(sel) -> Dict[str, Any]:
        sel_date = pd.to_datetime(sel["date"]).date()
        meals = df[df["date"] == sel_date].copy()
        # Sort: champion -> high ND first; challenge -> low ND first
        ascending = sel is challenge_row
        meals = meals.sort_values(["good_peak_good_recovery", "nd_score"], ascending=[ascending, ascending])
        meal_list = [
            {
                "date": str(r["date"]),
                "time": str(r.get("time", "")),
                "description": r.get("description", ""),
                "meal_type": r.get("meal_type", ""),
                "nd_score": round(float(r.get("nd_score", 0) or 0), 2),
                "ingredients": r["flat_ingredients"],
                "meal_feedback": r.get("meal_feedback", ""),
            }
            for _, r in meals.iterrows()
        ]
        return {
            "date": str(sel_date),
            "average_nd_score": round(float(sel.get("average_nd_score", sel.get("nd", 0))), 2),
            "no_of_meals": int(sel.get("total_meals", len(meal_list))),
            "meals": meal_list,
        }

    champion_day = _assemble_day(champion_row) if champion_row is not None else None
    challenge_day = _assemble_day(challenge_row) if challenge_row is not None else None

    # ---------- Output ----------
    out = {
        "champion_day": champion_day,
        "challenge_day": challenge_day,
        "meal_type_summary": meal_type_summary,
        "best_performing_meals": best_meals,
        "least_helpful_meals": least_helpful_meals,
        "meal_glucose_response_patterns": rp,
    }
    return json.dumps(out, indent=2, default=str)


@tool
async def cgm_glucose_summary(
        user_token: str,
        start_date: date,
        end_date: date,
) -> str:

    """
    Generate a JSON-formatted CGM glucose summary for a user over a given date range,
    including key metrics, time-in-range percentages, and time-of-day glucose patterns.
    """

    api_json = await get_user_cgm_stats(
        user_token,
        start_date,
        end_date,
    )
    readings = (
        api_json.get("result", {}).get("readings")
        if isinstance(api_json.get("result"), dict)
        else api_json.get("readings")
    )
    if not isinstance(readings, list) or not readings:
        return json.dumps({"error": "No valid readings found"}, indent=2)

    df = pd.DataFrame(readings)
    if "reading" not in df.columns or "date" not in df.columns:
        return json.dumps({"error": "Missing required fields: 'reading' or 'date'"}, indent=2)

    # Normalize columns & types
    df = df.rename(columns={"reading": "blood_glucose_level"})
    df["blood_glucose_level"] = pd.to_numeric(df["blood_glucose_level"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["blood_glucose_level", "timestamp"]).reset_index(drop=True)
    if df.empty:
        return json.dumps({"error": "No valid readings found"}, indent=2)

    s = df["blood_glucose_level"].astype(float)

    # ---- Vectorized range categorization ----
    conditions = [
        s <= 54,
        (s > 54) & (s < 70),
        (s >= 70) & (s <= 180),
        (s > 180) & (s <= 250),
        s > 250,
        ]
    choices = ["Very Low", "Low", "Target", "High", "Very High"]
    # np.select requires an object-friendly default to avoid dtype promotion errors on
    # newer NumPy versions when combining string choices with a float fallback. Using
    # ``None`` keeps the result as an object array so unmatched entries become missing
    # values once converted to a categorical series.
    range_values = np.select(conditions, choices, default=None)
    df["range"] = pd.Categorical(range_values, categories=choices, ordered=True)

    # ---- Time-block assignment (vectorized) ----
    hours = df["timestamp"].dt.hour
    # bins: [-inf,6), [6,12), [12,18), [18,inf)
    block_labels = ["Midnight", "Morning", "Afternoon", "Evening"]
    df["time_block"] = pd.Categorical(
        pd.cut(hours, bins=[-1, 5, 11, 17, 23], labels=block_labels, include_lowest=True),
        categories=block_labels,
        ordered=True,
    )

    total_readings = len(df)

    # ---- Summary metrics ----
    mean_glucose = float(s.mean())
    std_glucose = float(s.std(ddof=0))  # population std to stabilize CV
    cv = round((std_glucose / mean_glucose) * 100, 1) if mean_glucose > 0 else None
    summary_metrics = {
        "min_glucose": float(s.min()),
        "max_glucose": float(s.max()),
        "gmi": round(3.31 + 0.02392 * mean_glucose, 2),
        "coefficient_variation": cv,
    }

    # ---- Range percentages ----
    range_pct = df["range"].value_counts(normalize=True).reindex(choices, fill_value=0.0) * 100
    range_percentages = {
        "time_in_range_percent": round(float(range_pct["Target"]), 1),
        "time_in_low_percent": round(float(range_pct["Low"]), 1),
        "time_very_low_percent": round(float(range_pct["Very Low"]), 1),
        "time_in_high_percent": round(float(range_pct["High"]), 1),
        "time_in_very_high_percent": round(float(range_pct["Very High"]), 1),
    }

    # ---- Time block patterns ----
    # Precompute boolean flags once; means of booleans == percentages after *100
    is_high = (df["range"] == "High").astype(float)
    is_vhigh = (df["range"] == "Very High").astype(float)
    is_low = (df["range"] == "Low").astype(float)
    is_vlow = (df["range"] == "Very Low").astype(float)

    block = (
        df.assign(is_high=is_high, is_vhigh=is_vhigh, is_low=is_low, is_vlow=is_vlow)
        .groupby("time_block", observed=True)
        .agg(
            mean_glucose=("blood_glucose_level", "mean"),
            percent_high=("is_high", lambda x: round(x.mean() * 100, 1)),
            percent_very_high=("is_vhigh", lambda x: round(x.mean() * 100, 1)),
            percent_low=("is_low", lambda x: round(x.mean() * 100, 1)),
            percent_very_low=("is_vlow", lambda x: round(x.mean() * 100, 1)),
        )
        .reset_index()
    )
    block["mean_glucose"] = block["mean_glucose"].round(1)
    # Ensure chronological order of blocks
    block["time_block"] = pd.Categorical(block["time_block"], categories=block_labels, ordered=True)
    block = block.sort_values("time_block")
    time_block_patterns = block.to_dict(orient="records")

    # ---- Output ----
    def _serialize_date(value: Any) -> str:
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    result = {
        "cgm_start_date": _serialize_date(start_date),
        "cgm_end_date": _serialize_date(end_date),
        "glucose_total_readings": total_readings,
        "glucose_summary_metrics": summary_metrics,
        "glucose_range_percentages": range_percentages,
        "time_block_patterns": time_block_patterns,
    }
    return json.dumps(result, indent=2)

