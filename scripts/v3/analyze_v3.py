"""Compare the frozen FINAL classifier with the v3 candidates (3 seeds).

Reads score files written by score_v3.py and applies the PRE-REGISTERED rule in
docs/v3_decision_rule.md (fixed on 11 Nov 2026, before any v3 training).

Dev mode (default) decides ACCEPT / REJECT and chooses thresholds.
Locked mode (--locked) reports the one-time locked-test results for FINAL and
the chosen candidate; it cannot change the decision.

Usage (from E:\\SecureRAG):
  python scripts\\v3\\analyze_v3.py
  python scripts\\v3\\analyze_v3.py --locked
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

SCORES = Path("data/evaluation/v3_scores")
SEEDS = ["v3-seed1", "v3-seed2", "v3-seed3"]
BOOT = 2000
RNG = np.random.default_rng(20261111)

# ---- pre-registered tolerances (see docs/v3_decision_rule.md) ----
A_DOCS_AUC_GAIN = 0.01
B_AGENTIC_AUC_TOL = 0.005
C_TPR_TOL = 0.01
C_FPR_TOL = 0.02
D_DOC_FPR_TARGET = 0.02
E_MAX_SEED_STD = 0.02
F_CUSTOM_TOL = 0.02


def load(name, kind="dev"):
    path = SCORES / f"{name}__{kind}.jsonl"
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run score_v3.py for {name} first.")
    by = {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        by.setdefault(r["set"], []).append(r)
    out = {}
    for s, rows in by.items():
        rows.sort(key=lambda r: r["id"])
        out[s] = {"id": [r["id"] for r in rows], "y": np.array([r["label"] for r in rows]),
                  "p": np.array([r["prob"] for r in rows]), "m": np.array([r["margin"] for r in rows]),
                  "type": [r.get("technique") or r.get("attack_type") for r in rows]}
    return out


def aligned(a, b):
    if a["id"] != b["id"]:
        raise SystemExit("Score files cover different items; re-score both models on the same files.")


def threshold_for_fpr(y, p, target):
    """Lowest threshold whose false-positive rate on benign items is <= target."""
    b = np.sort(p[y == 0])[::-1]
    k = int(math.floor(target * len(b)))
    if k >= len(b):
        return 0.0
    return float(np.nextafter(b[k], 1.0))


def rates(y, p, t):
    pred = p >= t
    out = {}
    if (y == 0).any():
        out["fpr"] = float(pred[y == 0].mean())
    if (y == 1).any():
        out["tpr"] = float(pred[y == 1].mean())
    if len(set(y.tolist())) == 2:
        out["f1"] = float(f1_score(y, pred))
        out["macro_f1"] = float(f1_score(y, pred, average="macro"))
    return out


def threshold_free(y, p):
    if len(set(y.tolist())) < 2:
        return {}
    out = {"roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p))}
    for target in (0.01, 0.05):
        out[f"tpr_at_{int(target * 100)}pct_fpr"] = rates(y, p, threshold_for_fpr(y, p, target)).get("tpr")
    return out


def boot_ci(fn, *arrays):
    n = len(arrays[0])
    vals = []
    for _ in range(BOOT):
        idx = RNG.integers(0, n, n)
        try:
            vals.append(fn(*[a[idx] for a in arrays]))
        except ValueError:
            continue
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def auc_diff_ci(y, p_new, p_old):
    return boot_ci(lambda yy, a, b: roc_auc_score(yy, a) - roc_auc_score(yy, b), y, p_new, p_old)


def mcnemar(y, pred_new, pred_old):
    """Exact two-sided McNemar test on items where exactly one model is correct."""
    new_ok, old_ok = pred_new == y, pred_old == y
    b = int((new_ok & ~old_ok).sum())
    c = int((~new_ok & old_ok).sum())
    n = b + c
    if n == 0:
        return {"new_only_correct": 0, "old_only_correct": 0, "p_value": 1.0}
    k = min(b, c)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return {"new_only_correct": b, "old_only_correct": c, "p_value": p}


def fit_temperature(y, m):
    """Temperature scaling on the logit margin: P(mal) = sigmoid(m / T)."""
    best = (None, float("inf"))
    for T in np.exp(np.linspace(np.log(0.2), np.log(10), 400)):
        z = np.clip(m / T, -40, 40)
        nll = float(np.mean(np.logaddexp(0, -z) * y + np.logaddexp(0, z) * (1 - y)))
        if nll < best[1]:
            best = (float(T), nll)
    return best[0]


def ece(y, p, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if mask.any():
            total += mask.mean() * abs(p[mask].mean() - y[mask].mean())
    return float(total)


def dev_mode():
    final = load("FINAL")
    seeds = {s: load(s) for s in SEEDS}
    for s in seeds.values():
        for k in ("agentic_5k", "docs_dev", "notinject", "xstest", "custom_3000"):
            aligned(final[k], s[k])

    report = {"models": {}}
    for name, sc in [("FINAL", final), *seeds.items()]:
        report["models"][name] = {k: {**threshold_free(v["y"], v["p"]), "at_0.5": rates(v["y"], v["p"], 0.5)}
                                  for k, v in sc.items()}
    sel = {s: float(np.mean([report["models"][s]["agentic_5k"]["roc_auc"], report["models"][s]["docs_dev"]["roc_auc"]]))
           for s in SEEDS}
    deploy = max(sel, key=sel.get)
    D = seeds[deploy]
    report["selection_scores"] = sel
    report["deploy_seed"] = deploy

    F = {k: report["models"]["FINAL"][k] for k in final}
    auc = lambda k: [report["models"][s][k]["roc_auc"] for s in SEEDS]  # noqa: E731
    checks = {}

    docs_gain_ci = auc_diff_ci(final["docs_dev"]["y"], D["docs_dev"]["p"], final["docs_dev"]["p"])
    checks["A_docs_dev_auc_improves"] = {
        "seed_mean": float(np.mean(auc("docs_dev"))), "FINAL": F["docs_dev"]["roc_auc"],
        "deploy_minus_FINAL_95ci": docs_gain_ci,
        "pass": bool(np.mean(auc("docs_dev")) >= F["docs_dev"]["roc_auc"] + A_DOCS_AUC_GAIN and docs_gain_ci[0] > 0)}

    checks["B_agentic_auc_not_worse"] = {
        "seed_mean": float(np.mean(auc("agentic_5k"))), "FINAL": F["agentic_5k"]["roc_auc"],
        "deploy_minus_FINAL_95ci": auc_diff_ci(final["agentic_5k"]["y"], D["agentic_5k"]["p"], final["agentic_5k"]["p"]),
        "pass": bool(np.mean(auc("agentic_5k")) >= F["agentic_5k"]["roc_auc"] - B_AGENTIC_AUC_TOL)}

    ag = D["agentic_5k"]
    t_prompt = threshold_for_fpr(ag["y"], ag["p"], F["agentic_5k"]["at_0.5"]["fpr"])
    c_ag = rates(ag["y"], ag["p"], t_prompt)
    c_ni = rates(D["notinject"]["y"], D["notinject"]["p"], t_prompt)
    c_xs = rates(D["xstest"]["y"], D["xstest"]["p"], t_prompt)
    checks["C_promptguard_operating_point"] = {
        "threshold": t_prompt,
        "agentic_tpr": c_ag["tpr"], "FINAL_agentic_tpr_at_0.5": F["agentic_5k"]["at_0.5"]["tpr"],
        "notinject_fpr": c_ni["fpr"], "FINAL_notinject_fpr_at_0.5": F["notinject"]["at_0.5"]["fpr"],
        "xstest_fpr": c_xs["fpr"], "FINAL_xstest_fpr_at_0.5": F["xstest"]["at_0.5"]["fpr"],
        "pass": bool(c_ag["tpr"] >= F["agentic_5k"]["at_0.5"]["tpr"] - C_TPR_TOL
                     and c_ni["fpr"] <= F["notinject"]["at_0.5"]["fpr"] + C_FPR_TOL
                     and c_xs["fpr"] <= F["xstest"]["at_0.5"]["fpr"] + C_FPR_TOL)}

    dd = D["docs_dev"]
    t_doc = threshold_for_fpr(dd["y"], dd["p"], D_DOC_FPR_TARGET)
    t_doc_final = threshold_for_fpr(final["docs_dev"]["y"], final["docs_dev"]["p"], D_DOC_FPR_TARGET)
    d_new = rates(dd["y"], dd["p"], t_doc)
    d_old = rates(final["docs_dev"]["y"], final["docs_dev"]["p"], t_doc_final)
    checks["D_documentguard_operating_point"] = {
        "threshold": t_doc, "docs_dev_fpr": d_new["fpr"], "docs_dev_tpr": d_new["tpr"],
        "FINAL_threshold_at_same_fpr": t_doc_final, "FINAL_docs_dev_tpr_at_same_fpr": d_old["tpr"],
        "FINAL_docs_dev_at_0.5": F["docs_dev"]["at_0.5"],
        "pass": bool(d_new["tpr"] >= d_old["tpr"])}

    stds = {"docs_dev": float(np.std(auc("docs_dev"))), "agentic_5k": float(np.std(auc("agentic_5k")))}
    checks["E_seed_stability"] = {"auc_std": stds, "pass": all(v <= E_MAX_SEED_STD for v in stds.values())}

    cu = D["custom_3000"]
    c_cu = rates(cu["y"], cu["p"], t_prompt)
    checks["F_self_built_not_worse"] = {
        "macro_f1": c_cu["macro_f1"], "FINAL_macro_f1_at_0.5": F["custom_3000"]["at_0.5"]["macro_f1"],
        "pass": bool(c_cu["macro_f1"] >= F["custom_3000"]["at_0.5"]["macro_f1"] - F_CUSTOM_TOL)}

    report["checks"] = checks
    report["verdict"] = "ACCEPT" if all(c["pass"] for c in checks.values()) else "REJECT"

    # Informational: McNemar at operating points, per-technique FPR, calibration.
    report["mcnemar_vs_FINAL_at_0.5"] = {}
    for k, t_new in (("agentic_5k", t_prompt), ("notinject", t_prompt), ("xstest", t_prompt), ("docs_dev", t_doc)):
        report["mcnemar_vs_FINAL_at_0.5"][k] = mcnemar(final[k]["y"], D[k]["p"] >= t_new, final[k]["p"] >= 0.5)
    tech = {}
    for name, sc, t in (("FINAL", final, 0.5), (deploy, D, t_prompt)):
        a = sc["agentic_5k"]
        for typ in sorted({x for x, y in zip(a["type"], a["y"]) if y == 0}):
            mask = np.array([x == typ for x in a["type"]]) & (a["y"] == 0)
            tech.setdefault(typ, {})[name] = float((a["p"][mask] >= t).mean())
    report["agentic_benign_fpr_by_technique"] = tech
    cal_y = np.concatenate([D["agentic_5k"]["y"], dd["y"]])
    cal_m = np.concatenate([D["agentic_5k"]["m"], dd["m"]])
    T = fit_temperature(cal_y, cal_m)
    raw = 1 / (1 + np.exp(-cal_m))
    scaled = 1 / (1 + np.exp(-cal_m / T))
    report["calibration"] = {"temperature": T, "ece_raw": ece(cal_y, raw), "ece_scaled": ece(cal_y, scaled),
                             "note": "Temperature scaling is monotonic: it changes probabilities, not rankings or decisions at matched thresholds."}
    report["chosen_thresholds_raw_probability"] = {"prompt_guard": t_prompt, "document_guard": t_doc}

    Path("docs").mkdir(exist_ok=True)
    Path("docs/v3_dev_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"deploy_seed": deploy, "selection_scores": sel,
                      "checks": {k: v["pass"] for k, v in checks.items()}, "verdict": report["verdict"],
                      "thresholds": report["chosen_thresholds_raw_probability"]}, indent=2))
    print("Full report: docs/v3_dev_report.json")


def locked_mode():
    dev = json.loads(Path("docs/v3_dev_report.json").read_text(encoding="utf-8"))
    deploy, th = dev["deploy_seed"], dev["chosen_thresholds_raw_probability"]
    final, cand = load("FINAL", "locked"), load(deploy, "locked")
    out = {"deploy_seed": deploy, "dev_verdict": dev["verdict"], "thresholds": th, "sets": {}}
    for k, t_new in (("locked_deepset", th["prompt_guard"]), ("locked_docs_test", th["document_guard"])):
        f, c = final[k], cand[k]
        aligned(f, c)
        out["sets"][k] = {
            "n": int(len(f["y"])),
            "FINAL": {**threshold_free(f["y"], f["p"]), "at_0.5": rates(f["y"], f["p"], 0.5)},
            deploy: {**threshold_free(c["y"], c["p"]), "at_chosen_threshold": rates(c["y"], c["p"], t_new)},
            "auc_diff_95ci": auc_diff_ci(f["y"], c["p"], f["p"]),
            "macro_f1_95ci": {"FINAL": boot_ci(lambda y, p: f1_score(y, p >= 0.5, average="macro"), f["y"], f["p"]),
                              deploy: boot_ci(lambda y, p: f1_score(y, p >= t_new, average="macro"), c["y"], c["p"])},
            "mcnemar": mcnemar(f["y"], c["p"] >= t_new, f["p"] >= 0.5)}
    Path("docs/v3_locked_test_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--locked", action="store_true")
    a = ap.parse_args()
    locked_mode() if a.locked else dev_mode()
