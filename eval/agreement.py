#!/usr/bin/env python3
"""Inter annotator agreement on stage labels.

Two people label the same raw transcripts independently into two directories.
This reports how much they actually agree, per stage and overall, computes
Cohen's kappa, and lists the exact turns they disagreed on so the two of you
can sit down and fix the guide rather than argue from memory.

Standard library only. Kappa is implemented directly, no sklearn.

Usage:
    python eval/agreement.py data/annot_a data/annot_b
    python eval/agreement.py data/annot_a data/annot_b --quiet

Records are matched by id. A record present in only one directory is reported
and skipped. Two records with the same id but different turn counts are an
error, because they cannot be the same source transcript.

Why kappa and not plain percent agreement: most turns in any transcript are
stage 0, so two annotators who both label everything 0 would score about 80
percent agreement while having demonstrated nothing. Kappa subtracts the
agreement you would expect from chance given each annotator's own label
distribution. Above 0.7 is the bar in data/COLLECTION.md.
"""

import argparse
import json
import os
import sys

STAGES = [0, 1, 2, 3, 4, 5]

STAGE_NAMES = {
    0: "no manipulation",
    1: "authority",
    2: "urgency",
    3: "isolation",
    4: "escalating fear",
    5: "payment instruction",
}


def load_dir(directory):
    """Return {record_id: record} for every json file in a directory."""
    if not os.path.isdir(directory):
        sys.exit("error: not a directory: %s" % directory)

    records = {}
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        with open(path, "r", encoding="utf-8-sig") as handle:
            try:
                record = json.load(handle)
            except ValueError as exc:
                sys.exit("error: %s is not valid JSON: %s" % (path, exc))
        record_id = record.get("id")
        if not record_id:
            sys.exit("error: %s has no id" % path)
        records[record_id] = record

    if not records:
        sys.exit("error: no records found in %s" % directory)
    return records


def cohens_kappa(pairs):
    """Cohen's kappa for two annotators over a list of (label_a, label_b).

    kappa = (po - pe) / (1 - pe)

    po is observed agreement. pe is the agreement expected by chance, which is
    the sum over categories of P(a picks it) * P(b picks it). Returns None when
    kappa is undefined, which happens when both annotators used exactly one
    category and it was the same one, so pe is 1 and there is nothing for
    chance correction to divide by.
    """
    total = len(pairs)
    if total == 0:
        return None

    agreed = sum(1 for a, b in pairs if a == b)
    po = agreed / float(total)

    count_a = {}
    count_b = {}
    for a, b in pairs:
        count_a[a] = count_a.get(a, 0) + 1
        count_b[b] = count_b.get(b, 0) + 1

    pe = 0.0
    for label in set(list(count_a) + list(count_b)):
        pe += (count_a.get(label, 0) / float(total)) * \
              (count_b.get(label, 0) / float(total))

    if abs(1.0 - pe) < 1e-12:
        return None
    return (po - pe) / (1.0 - pe)


def interpret(kappa):
    if kappa is None:
        return "undefined"
    if kappa < 0.0:
        return "worse than chance"
    if kappa < 0.20:
        return "slight"
    if kappa < 0.40:
        return "fair"
    if kappa < 0.60:
        return "moderate"
    if kappa < 0.80:
        return "substantial"
    return "almost perfect"


def compare(records_a, records_b, name_a, name_b):
    shared = sorted(set(records_a) & set(records_b))
    only_a = sorted(set(records_a) - set(records_b))
    only_b = sorted(set(records_b) - set(records_a))

    pairs = []
    disagreements = []

    for record_id in shared:
        a = records_a[record_id]
        b = records_b[record_id]
        labels_a = a.get("stage_labels", [])
        labels_b = b.get("stage_labels", [])

        if len(labels_a) != len(labels_b):
            sys.exit("error: %s has %d labels in %s but %d in %s. These cannot "
                     "be the same source transcript."
                     % (record_id, len(labels_a), name_a, len(labels_b), name_b))

        turns = a.get("turns", [])
        for index, (label_a, label_b) in enumerate(zip(labels_a, labels_b)):
            pairs.append((label_a, label_b))
            if label_a != label_b:
                text = turns[index]["text"] if index < len(turns) else ""
                disagreements.append({
                    "record": record_id,
                    "turn": index,
                    "a": label_a,
                    "b": label_b,
                    "text": text,
                })

    return {
        "shared": shared,
        "only_a": only_a,
        "only_b": only_b,
        "pairs": pairs,
        "disagreements": disagreements,
    }


def report(result, name_a, name_b, quiet):
    pairs = result["pairs"]
    total = len(pairs)

    print("# Inter annotator agreement")
    print()
    print("A: %s" % name_a)
    print("B: %s" % name_b)
    print()

    if result["only_a"]:
        print("> Only in A, skipped: %s" % ", ".join(result["only_a"]))
    if result["only_b"]:
        print("> Only in B, skipped: %s" % ", ".join(result["only_b"]))
    if result["only_a"] or result["only_b"]:
        print()

    if total == 0:
        sys.exit("error: no overlapping records to compare")

    agreed = total - len(result["disagreements"])
    kappa = cohens_kappa(pairs)

    print("Compared %d records, %d turns." % (len(result["shared"]), total))
    print()
    print("| metric | value |")
    print("|--------|-------|")
    print("| Percent agreement | %.3f |" % (agreed / float(total)))
    print("| Cohen's kappa | %s |"
          % ("%.3f" % kappa if kappa is not None else "undefined"))
    print("| Interpretation | %s |" % interpret(kappa))
    print("| Turns compared | n = %d |" % total)
    print()

    # Per stage: of the turns A called stage s, how often did B agree, and
    # vice versa. Both directions matter, one annotator over-applying a stage
    # looks different from the other under-applying it.
    print("## Per stage")
    print()
    print("| stage | name | A used | B used | agreed | agreement |")
    print("|-------|------|--------|--------|--------|-----------|")
    for stage in STAGES:
        used_a = sum(1 for a, _ in pairs if a == stage)
        used_b = sum(1 for _, b in pairs if b == stage)
        both = sum(1 for a, b in pairs if a == stage and b == stage)
        either = sum(1 for a, b in pairs if a == stage or b == stage)
        share = ("%.2f" % (both / float(either))) if either else "n/a"
        print("| %d | %s | %d | %d | %d | %s |"
              % (stage, STAGE_NAMES[stage], used_a, used_b, both, share))
    print()
    print("Agreement column is Jaccard: turns both called this stage, over "
          "turns either called this stage.")

    if not quiet and result["disagreements"]:
        print()
        print("## Disagreements, %d turns" % len(result["disagreements"]))
        print()
        print("Work through these together, then fix data/ANNOTATION.md so the")
        print("same disagreement cannot happen again.")
        print()
        print("| record | turn | A | B | text |")
        print("|--------|------|---|---|------|")
        for item in result["disagreements"]:
            text = item["text"].replace("|", "/")
            if len(text) > 70:
                text = text[:67] + "..."
            print("| %s | %d | %d | %d | %s |"
                  % (item["record"], item["turn"], item["a"], item["b"], text))

    print()
    if kappa is None:
        print("> Kappa is undefined here. Both annotators used a single "
              "category, so there is nothing for chance correction to work "
              "with. Compare a batch with real stage variety.")
    elif kappa < 0.7:
        print("> BELOW THE BAR. data/COLLECTION.md requires kappa above 0.7 "
              "before the rest of this batch is trusted. Resolve the "
              "disagreements above and re-label.")
    else:
        print("> Above the 0.7 bar. This batch can be trusted.")


def main():
    parser = argparse.ArgumentParser(
        description="Report inter annotator agreement on stage labels.")
    parser.add_argument("dir_a", help="first annotator's directory")
    parser.add_argument("dir_b", help="second annotator's directory")
    parser.add_argument("--quiet", action="store_true",
                        help="skip the per turn disagreement list")
    args = parser.parse_args()

    records_a = load_dir(args.dir_a)
    records_b = load_dir(args.dir_b)
    result = compare(records_a, records_b, args.dir_a, args.dir_b)
    report(result, args.dir_a, args.dir_b, args.quiet)


if __name__ == "__main__":
    main()
