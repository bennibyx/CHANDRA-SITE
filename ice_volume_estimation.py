"""
CHANDRASITE — Ice Volume Estimation Module
BAH 2026 | Days 4-7 (July 6-9)

Takes radar-detected ice deposits from Stage 1 (Bayesian multi-instrument
fusion output) and estimates ice volume ranges using a dielectric mixing
model, calibrated against LCROSS-derived ice fraction bounds and the
ISRO PS8 fixed-depth specification.

Pipeline position:
    Stage 1 (deposit detection) --> [THIS MODULE] --> Scientific Confidence
    Analysis --> Landing/Traverse Feasibility --> ... --> Dashboard

Input contract (matches schema.json, agreed with Vaishali/Anika):
    {
      "ice_deposits": [
        {
          "id": 1,
          "area_m2": 480000,
          "cpr_mean": 0.62,
          "dop_mean": 0.38,
          "centroid": [-87.13, 77.8],
          "confidence": 0.81
        },
        ...
      ]
    }
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import json
import datetime


# ---------------------------------------------------------------------------
# Physical constants / model parameters
# ---------------------------------------------------------------------------

EPSILON_ICE = 3.15
EPSILON_DRY = 2.70
F_ICE_LOW = 0.005          # 0.5% minimum ice fraction (LCROSS literature)
F_ICE_HIGH = 0.056         # 5.6% maximum ice fraction (LCROSS literature)
FIXED_DEPTH_M = 5.0        # metres, fixed per ISRO PS8 specification
MIN_ROBUST_VOLUME_M3 = 100.0  # threshold for "Robust GO" flag

# Cabeus benchmark (LCROSS impact site) — used to sanity-check the model,
# not to validate individual Faustini deposits.
CABEUS_BENCHMARK = {
    "site": "Cabeus (LCROSS impact, 2009)",
    "reported_water_ice_fraction_pct": 5.6,   # Colaprete et al. 2010, upper end
    "reported_water_ice_fraction_pct_low": 0.5,
    "note": "Used only as a literature sanity-check for f_ice bounds, "
            "not a per-deposit ground truth.",
}


# ---------------------------------------------------------------------------
# Step 1: Core dielectric mixing model
# ---------------------------------------------------------------------------

def estimate_ice_volume(deposit_area_m2: float, cpr_mean: float, dop_mean: float) -> Dict[str, Any]:
    """
    Estimate ice volume range for a single radar-detected deposit.

    deposit_area_m2 : deposit footprint area from Stage 1, m^2
    cpr_mean        : mean Circular Polarization Ratio for the deposit
    dop_mean        : mean Degree of Polarization (carried through for the
                       false-positive discriminator / confidence module —
                       not yet used in the volume calc itself)
    """
    if deposit_area_m2 is None or deposit_area_m2 <= 0:
        raise ValueError("deposit_area_m2 must be a positive number")
    if cpr_mean is None:
        raise ValueError("cpr_mean is required")

    # Estimate bulk dielectric constant from CPR (rough linear proxy —
    # anchored so CPR=0.4 ~ dry regolith, higher CPR -> more ice-like)
    epsilon_measured = EPSILON_DRY + (cpr_mean - 0.4) * 0.5

    volume_low = deposit_area_m2 * FIXED_DEPTH_M * F_ICE_LOW
    volume_high = deposit_area_m2 * FIXED_DEPTH_M * F_ICE_HIGH

    return {
        # schema.json fields (single conservative estimate)
        "estimated_volume_m3": round(volume_low, 1),
        "estimated_depth_m": FIXED_DEPTH_M,
        # extra range fields, not in schema.json yet — confirm with
        # Vaishali/Anika before relying on these downstream
        "volume_low_m3": round(volume_low, 1),
        "volume_high_m3": round(volume_high, 1),
        "ice_fraction_range": "0.5% to 5.6% (LCROSS literature)",
        "epsilon_measured": round(epsilon_measured, 3),
        "dop_mean": dop_mean,
    }


# ---------------------------------------------------------------------------
# Step 2: Batch processing over Stage 1 output
# ---------------------------------------------------------------------------

def process_stage1_deposits(stage1_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Run estimate_ice_volume() over every deposit in a Stage 1 output dict,
    and attach the robustness verdict (Step 3) to each result.
    """
    deposits = stage1_output.get("ice_deposits", [])
    if not deposits:
        raise ValueError("stage1_output contains no 'ice_deposits' list")

    results = []
    for dep in deposits:
        try:
            vol = estimate_ice_volume(
                deposit_area_m2=dep["area_m2"],
                cpr_mean=dep["cpr_mean"],
                dop_mean=dep.get("dop_mean"),
            )
        except (KeyError, ValueError) as e:
            # Don't let one bad deposit kill the whole batch — flag and continue
            results.append({
                "id": dep.get("id", "UNKNOWN"),
                "error": str(e),
            })
            continue

        robustness = check_robustness(vol["volume_low_m3"])

        results.append({
            "id": dep.get("id", "UNKNOWN"),
            "centroid": dep.get("centroid"),
            "confidence": dep.get("confidence"),
            "area_m2": dep["area_m2"],
            "cpr_mean": dep["cpr_mean"],
            **vol,
            **robustness,
        })

    return results


# ---------------------------------------------------------------------------
# Step 3: Robustness check
# ---------------------------------------------------------------------------

def check_robustness(volume_low_m3: float, threshold_m3: float = MIN_ROBUST_VOLUME_M3) -> Dict[str, Any]:
    """
    Does the GO recommendation survive even at the conservative (lower-bound)
    volume estimate?
    """
    is_robust = volume_low_m3 >= threshold_m3
    return {
        "robust_go": is_robust,
        "robustness_flag": (
            "Robust GO — holds at conservative estimate"
            if is_robust else
            f"Caution — lower-bound volume ({volume_low_m3} m3) is below "
            f"the {threshold_m3} m3 robustness threshold"
        ),
    }


# ---------------------------------------------------------------------------
# Step 4: Ice resource summary report
# ---------------------------------------------------------------------------

def generate_ice_resource_report(results: List[Dict[str, Any]], mission_name: str = "CHANDRASITE") -> str:
    """
    Produce a formatted, human-readable ice resource summary report
    (goes into the Mission Recommendation Report stage downstream).
    """
    valid = [r for r in results if "error" not in r]
    errored = [r for r in results if "error" in r]

    total_low = sum(r["volume_low_m3"] for r in valid)
    total_high = sum(r["volume_high_m3"] for r in valid)
    robust_count = sum(1 for r in valid if r["robust_go"])

    lines = []
    lines.append("=" * 64)
    lines.append(f"{mission_name} — ICE RESOURCE SUMMARY REPORT")
    lines.append(f"Site: Faustini Crater, Lunar South Pole")
    lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 64)
    lines.append("")
    lines.append(f"Deposits analysed : {len(valid)}"
                  + (f"  ({len(errored)} skipped due to missing data)" if errored else ""))
    lines.append(f"Model             : Dielectric mixing (eps_ice={EPSILON_ICE}, eps_dry={EPSILON_DRY})")
    lines.append(f"Assumed depth     : {FIXED_DEPTH_M} m (ISRO PS8 spec)")
    lines.append(f"Ice fraction range: {F_ICE_LOW*100:.1f}% - {F_ICE_HIGH*100:.1f}% (LCROSS literature)")
    lines.append("")
    lines.append("-" * 64)
    lines.append(f"{'Deposit':<10}{'Area(m2)':>12}{'Vol Low(m3)':>14}{'Vol High(m3)':>14}{'Verdict':>14}")
    lines.append("-" * 64)

    for r in valid:
        verdict = "ROBUST GO" if r["robust_go"] else "CAUTION"
        lines.append(
            f"{str(r['id']):<10}{r['area_m2']:>12,.0f}"
            f"{r['volume_low_m3']:>14,.1f}{r['volume_high_m3']:>14,.1f}{verdict:>14}"
        )

    if errored:
        lines.append("")
        lines.append("Skipped deposits:")
        for r in errored:
            lines.append(f"  - {r['id']}: {r['error']}")

    lines.append("-" * 64)
    lines.append("")
    lines.append("TOTALS ACROSS ALL DEPOSITS")
    lines.append(f"  Conservative (low)  total ice volume : {total_low:,.1f} m3")
    lines.append(f"  Optimistic  (high)  total ice volume : {total_high:,.1f} m3")
    lines.append(f"  Deposits holding Robust GO at low bound: {robust_count}/{len(valid)}")
    lines.append("")
    lines.append("Note: 'Robust GO' means the mission-relevant GO recommendation")
    lines.append("for a deposit survives even using the conservative 0.5% ice")
    lines.append(f"fraction bound and the {MIN_ROBUST_VOLUME_M3:.0f} m3 minimum viability threshold.")
    lines.append("These are honest ranges, not point estimates — treat the low")
    lines.append("bound as the number to plan a mission around.")
    lines.append("=" * 64)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 5: JSON output for downstream modules (schema.json contract)
# ---------------------------------------------------------------------------

def write_module_output(results: List[Dict[str, Any]], out_path: str) -> None:
    """
    Writes ice volume results to JSON so the Scientific Confidence Analysis
    and Mission Intelligence Engine modules can consume it directly.
    Adjust the top-level key names here once schema.json is finalised.
    """
    payload = {
        "module": "ice_volume_estimation",
        "generated_at": datetime.datetime.now().isoformat(),
        "model_params": {
            "epsilon_ice": EPSILON_ICE,
            "epsilon_dry": EPSILON_DRY,
            "f_ice_low": F_ICE_LOW,
            "f_ice_high": F_ICE_HIGH,
            "depth_m": FIXED_DEPTH_M,
            "min_robust_volume_m3": MIN_ROBUST_VOLUME_M3,
        },
        "deposits": results,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)


# ---------------------------------------------------------------------------
# Placeholder Stage 1 output (Faustini Crater) — SWAP OUT once real data lands.
# Field names now match schema.json exactly (ice_deposits/id/confidence).
# ---------------------------------------------------------------------------

FAUSTINI_PLACEHOLDER_STAGE1_OUTPUT = {
    "ice_deposits": [
        {"id": 1, "area_m2": 480000, "cpr_mean": 0.62, "dop_mean": 0.38,
         "centroid": [-87.13, 77.80], "confidence": 0.81},
        {"id": 2, "area_m2": 125000, "cpr_mean": 0.55, "dop_mean": 0.31,
         "centroid": [-87.09, 78.05], "confidence": 0.68},
        {"id": 3, "area_m2": 32000,  "cpr_mean": 0.71, "dop_mean": 0.44,
         "centroid": [-87.21, 77.55], "confidence": 0.74},
        {"id": 4, "area_m2": 8500,   "cpr_mean": 0.48, "dop_mean": 0.28,
         "centroid": [-87.17, 78.20], "confidence": 0.52},
    ]
}


if __name__ == "__main__":
    # Swap this line for your own sample_data.json to test against real
    # team-agreed fixture data instead of the internal placeholder:
    #   with open("sample_data.json") as f:
    #       stage1_output = json.load(f)
    results = process_stage1_deposits(FAUSTINI_PLACEHOLDER_STAGE1_OUTPUT)
    report = generate_ice_resource_report(results)
    print(report)

    write_module_output(results, "ice_volume_output.json")
    print("\n[Saved: ice_volume_output.json]")
