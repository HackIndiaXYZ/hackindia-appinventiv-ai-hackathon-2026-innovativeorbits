#!/usr/bin/env python3
"""Offscript evaluation harness.

Loads every transcript in data/transcripts, runs a single pluggable predict()
function over each one, and prints a markdown metrics table to stdout.

Standard library only. No network calls. No model calls.

Three properties this harness guarantees, and why each one matters:

1. Truncation happens here, not on disk.
   Scam transcripts are stored complete through stage 5. For each one the
   harness slices turns at truncate_at_turn, hands predict() only that prefix,
   and scores the held out remainder. So next stage prediction accuracy is
   measured on every scam record, not only on the few that happen to be cut
   short in the source data.

2. predict() never sees anything it could cheat with.
   It receives an opaque id, the language, the channel and the truncated
   turns. Never the filename, the script id, the stage labels, the ground
   truth or the notes. Descriptive filenames like scam_digital_arrest_03.json
   stay descriptive for humans without leaking the answer to the model.

3. Every metric is printed with its sample count.
   A number without its denominator is not a result. If a judge asks "on how
   many samples", the answer is already on the slide.

On hackathon day the only thing that changes in this file is the body of
predict(). Everything below it is the scoring contract and should stay fixed,
because the numbers on the final slide have to come from an unchanged scorer.

Usage:
    python eval/run_eval.py
    python eval/run_eval.py --per-item      # add a per transcript breakdown
"""

import argparse
import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSCRIPT_DIR = os.path.join(REPO_ROOT, "data", "transcripts")

SCRIPT_IDS = [
    "digital_arrest",
    "kyc_expiry",
    "fake_support",
    "loan_app",
    "task_scam",
]

# Claim kinds a deterministic offline check can actually resolve: look the
# value up in data/allowlists/, compare a registrable domain, or check a
# structural format.
#
# Everything else is excluded ON PURPOSE. legal_claim, officer_identity,
# institution_identity, payment_promise and bank_account are settled in the
# dataset by reasoning and background knowledge, not by a check we can run with
# no network. Counting them as coverage would claim a capability we do not
# have. sender_header is excluded too, because the TRAI DLT registry is not
# publicly queryable.
#
# This is why coverage is reported as two numbers. The lower one is the honest
# one, and it is the one that goes on the slide.
MACHINE_RESOLVABLE_KINDS = {
    "upi_handle",
    "shortcode",
    "helpline",
    "domain",
    "case_number",
}


# ---------------------------------------------------------------------------
# The pluggable prediction function. This is the ONLY part that changes.
# ---------------------------------------------------------------------------

def predict(transcript):
    """Return Offscript's verdict for one transcript.

    Args:
        transcript: a dict with exactly four keys, nothing else.
            id       an opaque 8 character hash, useless for inference
            language one of telugu hindi english hinglish tenglish
            channel  one of call sms whatsapp telegram
            turns    the conversation prefix, list of {speaker, text}

    Returns a dict with:
        is_scam:      bool
        script:       one of SCRIPT_IDS, or None
        final_stage:  int 0 to 5, the highest stage reached WITHIN the prefix
                      that was handed in, not the highest the script could
                      eventually reach
        next_stage:   int 1 to 5, the stage of the next manipulative move that
                      has not happened yet, or None if the script is finished
        stage_labels: optional list[int], one per turn in the prefix. If
                      present, a per turn stage accuracy is reported too.

    Current implementation is a hardcoded stub so the harness runs end to end
    before any model exists. It always says "not a scam", which by design
    scores recall 0.00 and false positive rate 0.00.
    """
    return {
        "is_scam": False,
        "script": None,
        "final_stage": 0,
        "next_stage": None,
    }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def opaque_id(relative_path):
    """First 8 hex characters of the sha1 of the repo relative file path.

    Repo relative, not absolute, so the same transcript hashes identically on
    every machine and the numbers are reproducible across the team.
    """
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()
    return digest[:8]


def load_transcripts(directory):
    if not os.path.isdir(directory):
        sys.exit("error: transcript directory not found: %s" % directory)

    records = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        # utf-8-sig tolerates the BOM that Windows editors tend to add.
        with open(path, "r", encoding="utf-8-sig") as handle:
            try:
                record = json.load(handle)
            except ValueError as exc:
                sys.exit("error: %s is not valid JSON: %s" % (name, exc))
        relative = os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")
        record["_file"] = name
        record["_opaque_id"] = opaque_id(relative)
        records.append(record)

    if not records:
        sys.exit("error: no transcripts found in %s" % directory)
    return records


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

def derived_next_stage(stage_labels, cut):
    """The stage of the first manipulative turn after the truncation point.

    Kept identical to the copy in validate.py on purpose. Both files are meant
    to run standalone with no shared import, so this is duplicated rather than
    factored out. If you change one, change the other.
    """
    for label in stage_labels[cut + 1:]:
        if label > 0:
            return label
    return None


def split_record(record):
    """Return (prefix_turns, expected_final_stage, expected_next_stage).

    Legitimate records are evaluated whole. Scam records are cut at
    truncate_at_turn, which validate.py guarantees is present, in range, and
    positioned before any stage 5 turn.
    """
    turns = record["turns"]
    labels = record["stage_labels"]
    cut = record.get("truncate_at_turn")

    if cut is None:
        return turns, (max(labels) if labels else 0), None

    prefix = turns[:cut + 1]
    return prefix, max(labels[:cut + 1]), derived_next_stage(labels, cut)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def safe_div(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / float(denominator)


def fmt(value):
    if value is None:
        return "n/a"
    return "%.2f" % value


def score(records):
    """Run predict() over every record and return a results dict."""
    tp = fp = tn = fn = 0
    script_correct = script_total = 0
    stage_correct = stage_total = 0
    turn_correct = turn_total = 0
    next_correct = next_total = 0
    settled_claims = resolvable_claims = total_claims = 0
    per_item = []

    for record in records:
        truth = record["ground_truth"]
        prefix, expected_final, expected_next = split_record(record)

        # predict() gets exactly these four keys. Nothing that identifies the
        # file, the script, or any label.
        observable = {
            "id": record["_opaque_id"],
            "language": record["language"],
            "channel": record["channel"],
            "turns": prefix,
        }
        prediction = predict(observable)

        pred_scam = bool(prediction.get("is_scam", False))
        true_scam = bool(truth["is_scam"])

        if true_scam and pred_scam:
            tp += 1
        elif true_scam and not pred_scam:
            fn += 1
        elif not true_scam and pred_scam:
            fp += 1
        else:
            tn += 1

        # Script identification, scam records only.
        if true_scam:
            script_total += 1
            if prediction.get("script") == truth["script"]:
                script_correct += 1

        # Headline stage accuracy: exact match on the highest stage present in
        # the prefix that predict() actually saw, scored on scam records only.
        # Legitimate records are always stage 0 and would inflate this number.
        if true_scam:
            stage_total += 1
            if prediction.get("final_stage") == expected_final:
                stage_correct += 1

        # Optional per turn stage accuracy, over the prefix, every record.
        pred_labels = prediction.get("stage_labels")
        if isinstance(pred_labels, list):
            true_labels = record["stage_labels"][:len(prefix)]
            for index, true_label in enumerate(true_labels):
                turn_total += 1
                if index < len(pred_labels) and pred_labels[index] == true_label:
                    turn_correct += 1

        # Next stage prediction, only where a next stage actually exists.
        if expected_next is not None:
            next_total += 1
            if prediction.get("next_stage") == expected_next:
                next_correct += 1

        # Verifier coverage, two numbers, both corpus level statistics rather
        # than predictions.
        #
        # "In principle" is every claim the dataset settles either way. It is
        # the optimistic number and it overstates what the Verifier can do,
        # because some of those verdicts rest on background knowledge.
        #
        # "Machine resolvable" is the subset a deterministic offline check
        # actually handles. That is the number that belongs on the slide.
        for entry in record["hard_claims"]:
            total_claims += 1
            if entry["expected_verdict"] != "unverifiable":
                settled_claims += 1
                if entry["kind"] in MACHINE_RESOLVABLE_KINDS:
                    resolvable_claims += 1

        per_item.append({
            "file": record["_file"],
            "opaque": record["_opaque_id"],
            "type": record["type"],
            "turns_seen": len(prefix),
            "turns_total": len(record["turns"]),
            "true_script": truth["script"],
            "pred_script": prediction.get("script"),
            "true_stage": expected_final,
            "pred_stage": prediction.get("final_stage"),
            "true_next": expected_next,
            "pred_next": prediction.get("next_stage"),
            "correct_scam_call": pred_scam == true_scam,
        })

    return {
        "counts": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "n_total": len(records),
        "n_scam": tp + fn,
        "n_legit": tn + fp,
        "precision": (safe_div(tp, tp + fp), tp + fp),
        "recall": (safe_div(tp, tp + fn), tp + fn),
        "false_positive_rate": (safe_div(fp, fp + tn), fp + tn),
        "script_accuracy": (safe_div(script_correct, script_total), script_total),
        "stage_accuracy": (safe_div(stage_correct, stage_total), stage_total),
        "turn_stage_accuracy": (safe_div(turn_correct, turn_total), turn_total),
        "next_stage_accuracy": (safe_div(next_correct, next_total), next_total),
        "coverage_in_principle": (safe_div(settled_claims, total_claims), total_claims),
        "coverage_machine": (safe_div(resolvable_claims, total_claims), total_claims),
        "per_item": per_item,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

# Targets are copied from PROJECT.md. Each entry is
# (label, results key, target text, comparison, threshold).
TARGETS = [
    ("Recall on scam", "recall", "above 0.90", "gte", 0.90),
    ("False positive rate on legitimate", "false_positive_rate", "below 0.10", "lte", 0.10),
    ("Stage accuracy", "stage_accuracy", "above 0.70", "gte", 0.70),
    ("Next stage prediction accuracy", "next_stage_accuracy", "above 0.60", "gte", 0.60),
]


def verdict(value, comparison, threshold):
    if value is None:
        return "n/a"
    if comparison == "gte":
        return "pass" if value >= threshold else "MISS"
    return "pass" if value <= threshold else "MISS"


def report(results, show_per_item):
    counts = results["counts"]

    print("# Offscript eval results")
    print()
    print("Dataset: %d transcripts, %d scam, %d legitimate."
          % (results["n_total"], results["n_scam"], results["n_legit"]))
    print("Confusion: tp %d, fp %d, tn %d, fn %d."
          % (counts["tp"], counts["fp"], counts["tn"], counts["fn"]))
    print()
    print("| metric | target | measured | n | verdict |")
    print("|--------|--------|----------|---|---------|")
    for label, key, target_text, comparison, threshold in TARGETS:
        value, sample_count = results[key]
        print("| %s | %s | %s | n = %d | %s |"
              % (label, target_text, fmt(value), sample_count,
                 verdict(value, comparison, threshold)))
    print()
    print("Supporting numbers, no target set.")
    print()
    print("| metric | measured | n |")
    print("|--------|----------|---|")
    for label, key in [
        ("Precision on scam", "precision"),
        ("Script identification accuracy", "script_accuracy"),
        ("Per turn stage accuracy", "turn_stage_accuracy"),
        ("Verifier coverage, verifiable in principle", "coverage_in_principle"),
        ("Verifier coverage, machine resolvable offline", "coverage_machine"),
    ]:
        value, sample_count = results[key]
        print("| %s | %s | n = %d |" % (label, fmt(value), sample_count))
    print()
    print("Two coverage numbers on purpose. 'In principle' is every claim the")
    print("dataset settles either way, including ones settled by background")
    print("knowledge. 'Machine resolvable' is the subset a deterministic")
    print("offline check actually handles: %s."
          % ", ".join(sorted(MACHINE_RESOLVABLE_KINDS)))
    print("Quote the lower number. It is the one that survives a follow up")
    print("question about how the check works.")

    if show_per_item:
        print()
        print("## Per transcript")
        print()
        print("Turns column is what predict() saw over what is stored on disk.")
        print()
        print("| file | opaque id | type | turns | script true / pred | "
              "stage true / pred | next true / pred | scam call |")
        print("|------|-----------|------|-------|--------------------|"
              "-------------------|------------------|-----------|")
        for item in results["per_item"]:
            print("| %s | %s | %s | %d/%d | %s / %s | %s / %s | %s / %s | %s |" % (
                item["file"],
                item["opaque"],
                item["type"],
                item["turns_seen"], item["turns_total"],
                item["true_script"], item["pred_script"],
                item["true_stage"], item["pred_stage"],
                item["true_next"], item["pred_next"],
                "ok" if item["correct_scam_call"] else "WRONG",
            ))

    warnings = []
    if results["n_total"] < 40:
        warnings.append(
            "%d transcripts loaded, PROJECT.md requires at least 40 with a "
            "20 / 20 scam to legitimate split." % results["n_total"])
    if results["next_stage_accuracy"][1] < 20:
        warnings.append(
            "next stage prediction is measured on only n = %d. Do not put a "
            "percentage on a slide until every scam record contributes."
            % results["next_stage_accuracy"][1])

    if warnings:
        print()
        for warning in warnings:
            print("> Warning: %s" % warning)


def main():
    parser = argparse.ArgumentParser(description="Run the Offscript eval.")
    parser.add_argument("--per-item", action="store_true",
                        help="print a per transcript breakdown as well")
    parser.add_argument("--dir", default=TRANSCRIPT_DIR,
                        help="transcript directory, defaults to data/transcripts")
    args = parser.parse_args()

    records = load_transcripts(args.dir)
    report(score(records), args.per_item)


if __name__ == "__main__":
    main()
