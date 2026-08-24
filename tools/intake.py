#!/usr/bin/env python3
"""Offscript transcript intake.

Turns a raw pasted conversation into a schema valid record in
data/transcripts, walking you through stage labelling one turn at a time.

Standard library only. No network. No model calls. Nothing is sent anywhere.

Input format: a plain text file, one turn per line, speaker then a TAB then
the text. Blank lines and lines starting with # are ignored.

    counterparty<TAB>Namaskar, main Cyber Crime Branch se bol raha hoon.
    victim<TAB>Kaunsa parcel sir?
    counterparty<TAB>FIR number 0000/2026 register ho chuki hai.

Usage:
    python tools/intake.py raw/my_transcript.txt

It refuses to write an invalid record: after writing it runs eval/validate.py
and deletes the file again if validation fails, so data/transcripts never
contains something the harness cannot read.

Read data/ANNOTATION.md before your first transcript.
"""

import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSCRIPT_DIR = os.path.join(REPO_ROOT, "data", "transcripts")
VALIDATOR = os.path.join(REPO_ROOT, "eval", "validate.py")

SPEAKERS = ["counterparty", "victim", "system"]
SCRIPT_IDS = ["digital_arrest", "kyc_expiry", "fake_support", "loan_app", "task_scam"]
LANGUAGES = ["telugu", "hindi", "english", "hinglish", "tenglish"]
CHANNELS = ["call", "sms", "whatsapp", "telegram"]
SOURCE_KINDS = ["reddit", "youtube", "news", "personal_forward",
                "official_advisory", "reconstructed"]
CLAIM_KINDS = ["upi_handle", "shortcode", "helpline", "domain", "case_number",
               "sender_header", "bank_account", "officer_identity",
               "institution_identity", "legal_claim", "payment_promise"]
VERDICTS = ["verified_true", "verified_false", "unverifiable"]

STAGE_HELP = [
    "0  no manipulation      victim speaking, a greeting, a sender header line",
    "1  authority            claims to be police, a bank, a regulator, support",
    "2  urgency              a deadline, a countdown, a penalty that grows",
    "3  isolation            do not tell anyone, stay on the call, only me",
    "4  escalating fear      arrest, exposure, the family, CIBIL, contacts",
    "5  payment instruction  transfer, OTP, PIN, collect request, remote app",
]

TIE_BREAKS = (
    "  Two stages in one turn      -> label the HIGHER number\n"
    "  Restates an earlier stage   -> label that stage again, not 0\n"
    "  Greeting only               -> 0. Greeting plus authority claim -> 1\n"
    "  Legitimate record           -> every turn is 0, however urgent it sounds"
)

# Indian mobile numbers are ten digits starting 6 to 9. We never want one in
# the dataset, so warn on anything that looks like one.
PHONE_PATTERN = re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)")


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------

def ask(prompt, default=None):
    suffix = " [%s]" % default if default else ""
    while True:
        try:
            answer = input("%s%s: " % (prompt, suffix)).strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit("\naborted, nothing written")
        if answer:
            return answer
        if default is not None:
            return default
        print("  required")


def ask_choice(prompt, options, default=None):
    print("  options: %s" % ", ".join(options))
    while True:
        answer = ask(prompt, default)
        if answer in options:
            return answer
        print("  must be one of: %s" % ", ".join(options))


def ask_int(prompt, low, high):
    while True:
        answer = ask(prompt)
        try:
            value = int(answer)
        except ValueError:
            print("  needs a number")
            continue
        if low <= value <= high:
            return value
        print("  must be between %d and %d" % (low, high))


def ask_yes_no(prompt, default="n"):
    answer = ask("%s (y/n)" % prompt, default).lower()
    return answer.startswith("y")


# ---------------------------------------------------------------------------
# Reading the raw file
# ---------------------------------------------------------------------------

def read_raw(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        lines = handle.read().splitlines()

    turns = []
    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" not in line:
            sys.exit("line %d has no tab. Format is: speaker<TAB>text\n  %s"
                     % (number, line[:70]))
        speaker, text = line.split("\t", 1)
        speaker = speaker.strip()
        text = text.strip()
        if speaker not in SPEAKERS:
            sys.exit("line %d: speaker %r must be one of %s"
                     % (number, speaker, ", ".join(SPEAKERS)))
        if not text:
            sys.exit("line %d has an empty text field" % number)
        turns.append({"speaker": speaker, "text": text})

    if not turns:
        sys.exit("no usable turns found in %s" % path)
    return turns


def warn_about_phone_numbers(turns):
    hits = []
    for index, turn in enumerate(turns):
        for match in PHONE_PATTERN.findall(turn["text"]):
            hits.append((index, match))
    if not hits:
        return

    print()
    print("!" * 70)
    print("WARNING: what looks like a real Indian mobile number appears in the")
    print("text. The dataset must never contain one. Replace it with a")
    print("placeholder such as 0000000000 in the raw file and run again.")
    for index, match in hits:
        print("  turn %d: %s" % (index, match))
    print("!" * 70)
    if not ask_yes_no("Continue anyway? Only say yes if this is a published "
                      "institutional helpline"):
        sys.exit("aborted, nothing written")


# ---------------------------------------------------------------------------
# Labelling
# ---------------------------------------------------------------------------

def label_turns(turns, is_legitimate):
    if is_legitimate:
        print()
        print("Legitimate record: every turn is stage 0 by rule, so no")
        print("per turn prompting. See data/ANNOTATION.md.")
        return [0] * len(turns)

    print()
    print("=" * 70)
    print("STAGE LABELLING, one turn at a time")
    print("=" * 70)
    for line in STAGE_HELP:
        print("  " + line)
    print()
    print("Tie breaks:")
    print(TIE_BREAKS)
    print("=" * 70)

    labels = []
    for index, turn in enumerate(turns):
        print()
        print("turn %d of %d  [%s]" % (index, len(turns) - 1, turn["speaker"]))
        print("  %s" % turn["text"])
        if turn["speaker"] == "victim":
            print("  (victim turns are almost always 0)")
        labels.append(ask_int("  stage 0-5", 0, 5))
    return labels


def pick_truncation(labels):
    """The last turn labelled stage 4, which is where the harness will cut."""
    candidates = [i for i, label in enumerate(labels) if label == 4]
    if candidates:
        suggested = candidates[-1]
    else:
        fives = [i for i, label in enumerate(labels) if label == 5]
        suggested = (fives[0] - 1) if fives else (len(labels) - 2)

    print()
    print("Truncation point. The harness hands predict() turns 0 to N and")
    print("holds back the rest as the next stage answer. Rule: the last turn")
    print("labelled stage 4.")
    print("  suggested: %d" % suggested)

    while True:
        value = ask_int("  truncate_at_turn", 0, len(labels) - 2)
        if max(labels[:value + 1]) >= 5:
            print("  that leaves a stage 5 turn inside the prefix, so the")
            print("  payment instruction would not be held back. Pick lower.")
            continue
        return value


def derived_next_stage(labels, cut):
    for label in labels[cut + 1:]:
        if label > 0:
            return label
    return None


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------

def collect_claims():
    print()
    print("=" * 70)
    print("HARD CLAIMS, one at a time. Blank claim to finish.")
    print("=" * 70)
    print("Verdicts: verified_true resolves against data/allowlists/,")
    print("          verified_false is provably contradicted,")
    print("          unverifiable means no source exists to settle it.")
    print("Sender headers and individual officer names are ALWAYS")
    print("unverifiable. Do not round unverifiable to verified_false.")

    claims = []
    while True:
        print()
        try:
            text = input("  claim (blank to finish): ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit("\naborted, nothing written")
        if not text:
            return claims

        kind = ask_choice("  kind", CLAIM_KINDS)
        if kind == "sender_header":
            print("  note: sender headers cannot be checked, forcing unverifiable")
            verdict = "unverifiable"
        else:
            verdict = ask_choice("  expected_verdict", VERDICTS)

        if verdict == "verified_true" and kind in ("upi_handle", "shortcode",
                                                   "helpline", "domain"):
            print("  this must already be in data/allowlists/ with a source_url")
            print("  and a verified_on date, or validation will fail.")

        rationale = ask("  rationale, why this verdict")
        claims.append({
            "claim": text,
            "kind": kind,
            "expected_verdict": verdict,
            "rationale": rationale,
        })


# ---------------------------------------------------------------------------

def build_record(turns):
    print()
    print("=" * 70)
    print("METADATA")
    print("=" * 70)

    record_type = ask_choice("type", ["scam", "legitimate"])
    is_legitimate = record_type == "legitimate"

    script = None
    if not is_legitimate:
        script = ask_choice("script", SCRIPT_IDS)

    language = ask_choice("language", LANGUAGES)
    channel = ask_choice("channel", CHANNELS)

    print()
    print("Source. Needed so we can defend the dataset if judges ask.")
    source_kind = ask_choice("  source kind", SOURCE_KINDS)
    reference = ask("  reference, URL or publication or 'family whatsapp forward'")
    collected_on = ask("  collected on, YYYY-MM-DD")

    suffix = ask("id suffix, e.g. 02. Full id becomes %s_<suffix>"
                 % (script if script else "legit_" + record_type))
    if is_legitimate:
        record_id = "legit_%s" % suffix
    else:
        record_id = "scam_%s_%s" % (script, suffix)
    record_id = re.sub(r"[^a-z0-9_]", "_", record_id.lower())

    labels = label_turns(turns, is_legitimate)

    record = {
        "id": record_id,
        "type": record_type,
        "script": script,
        "language": language,
        "channel": channel,
        "source": {
            "kind": source_kind,
            "reference": reference,
            "collected_on": collected_on,
        },
        "turns": turns,
        "stage_labels": labels,
    }

    if not is_legitimate:
        cut = pick_truncation(labels)
        record["truncate_at_turn"] = cut
        next_stage = derived_next_stage(labels, cut)
    else:
        next_stage = None

    record["hard_claims"] = collect_claims()
    record["ground_truth"] = {
        "is_scam": not is_legitimate,
        "script": script,
        "final_stage": max(labels) if labels else 0,
        "next_stage": next_stage,
    }

    print()
    record["notes"] = ask("notes, why this is a hard case and what a keyword "
                          "filter would get wrong")

    return record


def write_and_validate(record):
    path = os.path.join(TRANSCRIPT_DIR, "%s.json" % record["id"])
    if os.path.exists(path):
        if not ask_yes_no("%s already exists. Overwrite?" % os.path.basename(path)):
            sys.exit("aborted, nothing written")

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print()
    print("wrote %s, validating..." % path)
    result = subprocess.run([sys.executable, VALIDATOR],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())

    if result.returncode != 0:
        os.remove(path)
        print()
        print("VALIDATION FAILED, the file was deleted so the dataset stays")
        print("clean. Fix the problems above and run intake again.")
        sys.exit(1)

    print()
    print("done: %s" % path)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip())

    raw_path = sys.argv[1]
    if not os.path.isfile(raw_path):
        sys.exit("no such file: %s" % raw_path)

    turns = read_raw(raw_path)
    print("read %d turns from %s" % (len(turns), raw_path))
    warn_about_phone_numbers(turns)
    write_and_validate(build_record(turns))


if __name__ == "__main__":
    main()
