# Re-import needed packages after code reset
import json
from pathlib import Path
from statistics import mean
import numpy as np
from sklearn.metrics import cohen_kappa_score

# Define quadratic kappa
def quadratic_weighted_kappa(y_true, y_pred, min_rating=-5, max_rating=5):
    labels = list(range(min_rating, max_rating + 1))
    return cohen_kappa_score(y_true, y_pred, weights="quadratic", labels=labels)

# 🔹 NEW: Distribution-Free Quadratic Kappa (DFK)
def distribution_free_kappa(y_true, y_pred, min_rating=-5, max_rating=5):
    """
    Distribution-Free Quadratic Kappa (DFK)

    This metric compares observed disagreement (O) to disagreement expected under a uniform baseline.

    - Treats each label as equally likely, avoiding distortion from uneven score distributions.
    - Appropriate for scenarios where labels are independently and idiosyncratically assigned (e.g., by LLMs).

    Mathematical formula:
        DFK = 1 - (∑ W_ij * O_ij) / (∑ W_ij * E_ij)

    Where:
    - O_ij is the observed frequency of true rating i and predicted rating j (normalized)
    - E_ij is a uniform expected frequency = 1 / (N_labels^2)
    - W_ij is the quadratic weight matrix: ((i - j)^2 / (N_labels - 1)^2)
    """
    labels = list(range(min_rating, max_rating + 1))
    n = len(labels)
    W = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            W[i, j] = ((i - j) ** 2) / ((n - 1) ** 2)

    O = np.zeros((n, n))
    for t, p in zip(y_true, y_pred):
        O[t - min_rating, p - min_rating] += 1
    O /= O.sum()

    E_uniform = np.full((n, n), 1 / (n * n))

    numerator = np.sum(W * O)
    denominator = np.sum(W * E_uniform)

    return 1 - (numerator / denominator)



# File Paths
OUTPUT_DIR = Path(__file__).parent / "data_output"

GOLDEN_FILE_PATH = Path(__file__).parent.parent / "data/demographic_golden_set_custom_demos.json"

OUTPUT_COMPARE_PATH_HAIKU = Path(__file__).parent.parent / "data_output/bill_impact_analysis_haiku.json"

OUTPUT_COMPARE_PATH_OPUS = Path(__file__).parent.parent / "data_output/bill_impact_analysis_opus.json"



def compare_demographics_scores(golden_scores, analyzer_output, hit_margin=1):
    results = []

    for bill_key, gold_data in golden_scores.items():

        predicted_section = analyzer_output.get(bill_key, {}).get("matched_demographics", {})

        # Ensure it's a dict and contains actual demographic predictions
        if isinstance(predicted_section, dict) and all(isinstance(v, dict) and "impact_score" in v for v in predicted_section.values()):
            predicted = {
                k.strip(): v["impact_score"] for k, v in predicted_section.items()
            }
        else:
            predicted = {}  # fallback to empty if structure is invalid


        predicted = {
            k.strip(): v["impact_score"] for k, v in predicted_section.items()
        }

        # Normalize known common mismatch between Race and Ethnicity
        if "Race - Hispanic or Latino" in predicted:
            predicted["Ethnicity - Hispanic or Latino"] = predicted.pop("Race - Hispanic or Latino")
            #predicted["Ethnicity - Not Hispanic or Latino"] = predicted.pop("Race - Not Hispanic or Latino")

        gold_scores = {
            f"{row['category']} - {row['subcategory']}": row["score"]
            for row in gold_data
        }

        predicted_scores = {
            group: score for group, score in predicted.items()
            if group in gold_scores
        }


        matches = len(predicted_scores)
        if matches == 0:
            results.append({
                "bill_key": bill_key,
                "predicted_groups": 0,
                "mae": None,
                "hit@0": 0,
                f"hit@{hit_margin}": 0,
                "quadratic_kappa": None,
                "df_kappa": None,
            })
            continue

        gold_list = [gold_scores[group] for group in predicted_scores]
        pred_list = [predicted_scores[group] for group in predicted_scores]

        total_abs_error = sum(abs(predicted_scores[group] - gold_scores[group]) for group in predicted_scores)
        exact_matches = sum(1 for group in predicted_scores if predicted_scores[group] == gold_scores[group])
        close_matches = sum(1 for group in predicted_scores if abs(predicted_scores[group] - gold_scores[group]) <= hit_margin)

        mae = total_abs_error / matches
        hit_at_0 = exact_matches / matches
        hit_at_k = close_matches / matches
        kappa = quadratic_weighted_kappa(gold_list, pred_list)
        df_kappa = distribution_free_kappa(gold_list, pred_list)

        results.append({
            "bill_key": bill_key,
            "predicted_groups": matches,
            "mae": mae,
            "hit@0": hit_at_0,
            f"hit@{hit_margin}": hit_at_k,
            "quadratic_kappa": kappa,
            "df_kappa": df_kappa,
        })

    return results

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(GOLDEN_FILE_PATH, "r") as f:
        golden = json.load(f)

    with open(OUTPUT_COMPARE_PATH_OPUS, "r") as f:
        output = json.load(f)

    results = compare_demographics_scores(golden, output, hit_margin=1)
    
    print("\nBill Comparison Results:")
    for res in results:
        print(json.dumps(res, indent=2))

    # Add average metrics as a special entry
    valid_results = [r for r in results if r["mae"] is not None]

    if valid_results:
        avg_mae = mean(r["mae"] for r in valid_results)
        avg_hit0 = mean(r["hit@0"] for r in valid_results)
        avg_hitk = mean(r[f"hit@{1}"] for r in valid_results)
        avg_kappa = mean(r["quadratic_kappa"] for r in valid_results)
        avg_df_kappa = mean(r["df_kappa"] for r in valid_results)


        average_entry = {
            "bill_key": "AVERAGE_METRICS",
            "predicted_groups": sum(r["predicted_groups"] for r in valid_results),
            "df_kappa": avg_df_kappa,
            "quadratic_kappa": avg_kappa,
            "mae": avg_mae,
            "hit@0": avg_hit0,
            f"hit@{1}": avg_hitk,
        }

        results.append(average_entry)

        print("\nAverage Metrics Across All Bills:")
        print(f"Distribution Free Kappa: {avg_df_kappa:.3f}")
        print(f"Cohen's Quadratic Kappa: {avg_kappa:.3f}")
        print(f"Average MAE: {avg_mae:.3f}")
        print(f"Average Hit@0: {avg_hit0:.3f}")
        print(f"Average Hit@1: {avg_hitk:.3f}")
    else:
        print("\nNo valid predictions to compute averages.")

    # Save results to JSON
    results_path = OUTPUT_DIR / "comparison_results_opus.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
   

    print(f"\nResults saved to: {results_path}")

