#!/usr/bin/env python3
"""Validate every transcript in data/transcripts against data/schema.json.

Standard library only, no jsonschema dependency. Implements the subset of
JSON Schema actually used by data/schema.json: type, enum, const, required,
properties, additionalProperties, items, minItems, minLength, minimum,
maximum, pattern, not, allOf and if/then.

It also runs cross field checks that JSON Schema cannot express cleanly:
  - stage_labels has exactly one entry per turn
  - no duplicate hard_claim within a record
  - every verified_true verdict on an addressable claim resolves against a
    verified entry in data/allowlists/
  - every allowlist entry with a verified_on date also has a source_url
  - final_stage equals the highest value in stage_labels
  - truncate_at_turn is in range and cuts before any stage 5 turn
  - ground_truth.next_stage matches what truncate_at_turn implies
  - the record id matches its filename
  - ids are unique across the dataset

Exits 1 and prints every problem if anything fails.

Usage:
    python eval/validate.py
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(REPO_ROOT, "data", "schema.json")
TRANSCRIPT_DIR = os.path.join(REPO_ROOT, "data", "transcripts")
ALLOWLIST_DIR = os.path.join(REPO_ROOT, "data", "allowlists")

# Claim kinds that name a specific addressable value, so a verified_true
# verdict on one has to resolve against an allowlist entry. Kinds outside this
# set, such as institution_identity or legal_claim, are corroborated by
# reasoning rather than looked up by value.
ADDRESSABLE_KINDS = {"upi_handle", "shortcode", "helpline", "domain"}


# ---------------------------------------------------------------------------
# Minimal JSON Schema validator
# ---------------------------------------------------------------------------

def type_matches(value, expected):
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        # bool is a subclass of int in Python, exclude it explicitly.
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValueError("unsupported type in schema: %r" % expected)


def validate(value, schema, path, errors):
    if "type" in schema:
        expected = schema["type"]
        options = expected if isinstance(expected, list) else [expected]
        if not any(type_matches(value, option) for option in options):
            errors.append("%s: expected type %s, got %s"
                          % (path, "/".join(options), type(value).__name__))
            return

    if "const" in schema and value != schema["const"]:
        errors.append("%s: expected constant %r, got %r" % (path, schema["const"], value))

    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: %r is not one of %r" % (path, value, schema["enum"]))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: string shorter than %d" % (path, schema["minLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append("%s: %r does not match pattern %s"
                          % (path, value, schema["pattern"]))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: %r is below minimum %r" % (path, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("%s: %r is above maximum %r" % (path, value, schema["maximum"]))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("%s: needs at least %d items, has %d"
                          % (path, schema["minItems"], len(value)))
        if "items" in schema:
            for index, item in enumerate(value):
                validate(item, schema["items"], "%s[%d]" % (path, index), errors)

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append("%s: missing required field %r" % (path, key))

        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in value:
                validate(value[key], subschema, "%s.%s" % (path, key), errors)

        additional = schema.get("additionalProperties")
        if additional is False:
            for key in value:
                if key not in properties:
                    errors.append("%s: unexpected field %r" % (path, key))
        elif isinstance(additional, dict):
            for key, item in value.items():
                if key not in properties:
                    validate(item, additional, "%s.%s" % (path, key), errors)

    if "not" in schema:
        probe = []
        validate(value, schema["not"], path, probe)
        if not probe:
            forbidden = schema["not"].get("required")
            if forbidden:
                errors.append("%s: field(s) %s are not allowed on this record"
                              % (path, ", ".join(repr(f) for f in forbidden)))
            else:
                errors.append("%s: matches a forbidden schema" % path)

    for index, subschema in enumerate(schema.get("allOf", [])):
        if "if" in subschema:
            probe = []
            validate(value, subschema["if"], path, probe)
            if not probe and "then" in subschema:
                validate(value, subschema["then"], path, errors)
        else:
            validate(value, subschema, path, errors)


# ---------------------------------------------------------------------------
# Cross field checks
# ---------------------------------------------------------------------------

def derived_next_stage(stage_labels, cut):
    """The stage of the first manipulative turn after the truncation point.

    Kept identical to the copy in run_eval.py on purpose. Both files are meant
    to run standalone with no shared import, so this is duplicated rather than
    factored out. If you change one, change the other.
    """
    for label in stage_labels[cut + 1:]:
        if label > 0:
            return label
    return None


def cross_checks(record, filename, allowlist_values, errors):
    path = filename

    turns = record.get("turns")
    labels = record.get("stage_labels")
    if isinstance(turns, list) and isinstance(labels, list) and len(turns) != len(labels):
        errors.append("%s: stage_labels has %d entries but there are %d turns"
                      % (path, len(labels), len(turns)))

    truth = record.get("ground_truth")

    claims = record.get("hard_claims")
    if isinstance(claims, list):
        seen = set()
        for entry in claims:
            if not isinstance(entry, dict):
                continue
            text = entry.get("claim")
            if text in seen:
                errors.append("%s: hard_claim %r appears twice" % (path, text))
            seen.add(text)

            # A verified_true verdict on something addressable must actually
            # resolve against the allowlist. This is what stops a number being
            # asserted true from memory, which is exactly how a wrong helpline
            # got into this dataset once already.
            if (entry.get("expected_verdict") == "verified_true"
                    and entry.get("kind") in ADDRESSABLE_KINDS):
                if text not in allowlist_values:
                    errors.append(
                        "%s: hard_claim %r is marked verified_true but is not a "
                        "verified entry in data/allowlists/. Add it there with a "
                        "source_url and a verified_on date, or change the verdict "
                        "to unverifiable." % (path, text))

    if isinstance(truth, dict) and isinstance(labels, list) and labels:
        highest = max(labels)
        if truth.get("final_stage") != highest:
            errors.append("%s: final_stage is %r but the highest stage_label is %r"
                          % (path, truth.get("final_stage"), highest))

    cut = record.get("truncate_at_turn")
    if isinstance(cut, int) and isinstance(labels, list) and isinstance(turns, list):
        if cut >= len(turns) - 1:
            errors.append("%s: truncate_at_turn is %d but there are only %d turns, "
                          "the cut must leave at least one turn held out"
                          % (path, cut, len(turns)))
        elif max(labels[:cut + 1]) >= 5:
            errors.append("%s: truncate_at_turn %d leaves a stage 5 turn inside the "
                          "prefix, so the payment instruction is not actually held back"
                          % (path, cut))
        else:
            expected_next = derived_next_stage(labels, cut)
            if isinstance(truth, dict) and truth.get("next_stage") != expected_next:
                errors.append("%s: ground_truth.next_stage is %r but truncate_at_turn "
                              "%d implies %r"
                              % (path, truth.get("next_stage"), cut, expected_next))

    expected_name = "%s.json" % record.get("id")
    if filename != expected_name:
        errors.append("%s: id %r implies the filename should be %s"
                      % (path, record.get("id"), expected_name))


# ---------------------------------------------------------------------------
# Allowlists
# ---------------------------------------------------------------------------

ALLOWLIST_FIELDS = ["institution", "value", "kind", "source_url", "verified_on"]


def load_allowlists(errors):
    """Return the set of allowlist values that are actually verified.

    An entry counts only if it carries both a source_url and a verified_on
    date. Entries with verified_on null are parked on purpose so a gap stays
    visible, and are deliberately NOT returned here.
    """
    verified = set()
    if not os.path.isdir(ALLOWLIST_DIR):
        errors.append("data/allowlists/ is missing")
        return verified

    for name in sorted(os.listdir(ALLOWLIST_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(ALLOWLIST_DIR, name)
        with open(path, "r", encoding="utf-8-sig") as handle:
            try:
                document = json.load(handle)
            except ValueError as exc:
                errors.append("allowlists/%s: invalid JSON, %s" % (name, exc))
                continue

        for index, entry in enumerate(document.get("entries", [])):
            where = "allowlists/%s[%d]" % (name, index)
            for field in ALLOWLIST_FIELDS:
                if field not in entry:
                    errors.append("%s: missing required field %r" % (where, field))
            if entry.get("verified_on") and not entry.get("source_url"):
                errors.append("%s: has verified_on but no source_url. Every "
                              "verified entry must point at the institution's own "
                              "published page." % where)
            elif entry.get("verified_on") and entry.get("source_url"):
                verified.add(entry["value"])

    return verified


# ---------------------------------------------------------------------------

def main():
    # utf-8-sig, not utf-8: Windows editors and PowerShell redirection happily
    # write a BOM, and a BOM makes json.load fail on an otherwise valid file.
    with open(SCHEMA_PATH, "r", encoding="utf-8-sig") as handle:
        schema = json.load(handle)

    if not os.path.isdir(TRANSCRIPT_DIR):
        sys.exit("error: %s does not exist" % TRANSCRIPT_DIR)

    filenames = sorted(f for f in os.listdir(TRANSCRIPT_DIR) if f.endswith(".json"))
    if not filenames:
        sys.exit("error: no transcripts found in %s" % TRANSCRIPT_DIR)

    errors = []
    seen_ids = {}
    counts = {"scam": 0, "legitimate": 0}
    allowlist_values = load_allowlists(errors)

    for filename in filenames:
        full = os.path.join(TRANSCRIPT_DIR, filename)
        with open(full, "r", encoding="utf-8-sig") as handle:
            try:
                record = json.load(handle)
            except ValueError as exc:
                errors.append("%s: invalid JSON, %s" % (filename, exc))
                continue

        validate(record, schema, filename, errors)
        cross_checks(record, filename, allowlist_values, errors)

        record_id = record.get("id")
        if record_id in seen_ids:
            errors.append("%s: duplicate id %r, already used by %s"
                          % (filename, record_id, seen_ids[record_id]))
        else:
            seen_ids[record_id] = filename

        if record.get("type") in counts:
            counts[record["type"]] += 1

    if errors:
        print("VALIDATION FAILED, %d problem(s) in %d file(s):"
              % (len(errors), len(filenames)))
        for error in errors:
            print("  - %s" % error)
        sys.exit(1)

    print("VALIDATION PASSED: %d transcripts, %d scam, %d legitimate."
          % (len(filenames), counts["scam"], counts["legitimate"]))
    if len(filenames) < 40:
        print("Note: PROJECT.md requires at least 40 with a 20 / 20 split. "
              "%d still to collect." % (40 - len(filenames)))


if __name__ == "__main__":
    main()
