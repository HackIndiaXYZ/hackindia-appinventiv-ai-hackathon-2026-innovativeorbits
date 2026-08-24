# Transcript collection tracker

40 transcripts minimum, 20 scam and 20 legitimate. The legitimate half is the
half that wins, because it is the only way to report a false positive rate.
Most teams collect scam data only and then cannot show that number.

**Read [ANNOTATION.md](ANNOTATION.md) before your first transcript.** Then use
the intake tool rather than writing JSON by hand — it shows the stage
definitions inline, derives `truncate_at_turn` and `next_stage` for you, warns
on anything that looks like a real mobile number, and refuses to write a record
that does not validate:

```
python tools/intake.py raw/my_transcript.txt
```

Run `python eval/validate.py` after every batch.

## Quality gates

Three things must be true before a batch is trusted. All three are checkable,
none of them is a matter of opinion.

| gate | requirement | where it is checked |
|------|-------------|---------------------|
| Double annotation | a random 10 percent of each batch labelled independently by both people, Cohen's kappa above 0.7 | `python eval/agreement.py <dir_a> <dir_b>` |
| Legitimate verifiability | at least 8 of the 20 legitimate records carry a verifiable hard claim | count below, `verifier_coverage` in `run_eval.py` |
| Verifier coverage | share of all hard claims settled as verified_true or verified_false rather than unverifiable, reported with its n | `python eval/run_eval.py` |

On double annotation: stage labelling is subjective, and if one person's
stage 3 is another person's stage 2 then the eval measures nothing. Pick the
10 percent at random *before* labelling, not after. If kappa comes out below
0.7, do not relabel quietly — work through the disagreement list `agreement.py`
prints, fix `ANNOTATION.md` so the same argument cannot recur, then relabel.

On coverage: there is no target number, because the honest answer depends on
what the corpus contains. What matters is that it is reported at all. A system
that says "we could settle 68 percent of the claims and we are telling you
which 32 percent we could not" is stronger in front of judges than one that
silently guesses.

## Scam half, 20 items

Spread across all five scripts and across languages. Do not let
digital_arrest dominate just because it is the easiest to find.

| script | target | collected | ids |
|--------|--------|-----------|-----|
| digital_arrest | 5 | 1 | scam_digital_arrest_01 |
| kyc_expiry | 4 | 1 | scam_kyc_expiry_01 |
| fake_support | 4 | 0 | |
| loan_app | 4 | 0 | |
| task_scam | 3 | 0 | |

Language spread across those 20, aim for roughly:

| language | target | collected |
|----------|--------|-----------|
| hinglish | 6 | 1 |
| hindi | 4 | 0 |
| telugu | 4 | 1 |
| tenglish | 3 | 0 |
| english | 3 | 0 |

**Every scam record must be stored complete, through stage 5.** Do not stop
collecting at stage 4 because the demo cuts there. The cut is expressed as
`truncate_at_turn` and applied inside `eval/run_eval.py`, which means all 20
scam records contribute to next stage prediction accuracy instead of only the
few that happen to end early. If a source transcript genuinely has no stage 5,
say so in `notes` — but prefer sources that show the full arc.

## Legitimate half, 20 items

These must be genuinely urgent and genuinely alarming, otherwise the false
positive rate is meaningless. A cheerful marketing SMS is not a hard negative.

| kind | target | collected | ids |
|------|--------|-----------|-----|
| Bank transaction alert, large amount | 4 | 1 | legit_bank_alert_01 |
| OTP message, bank or payments app | 3 | 0 | |
| Delivery OTP or courier reattempt | 2 | 0 | |
| EMI due or bounce reminder | 3 | 0 | |
| Card block or suspicious login alert | 3 | 0 | |
| Genuine bank call asking to verify a transaction | 2 | 0 | |
| Electricity or gas disconnection notice, genuine | 2 | 0 | |
| Insurance or policy lapse reminder, genuine | 1 | 0 | |

**At least 8 of the 20 legitimate records must contain a hard claim whose
`expected_verdict` is `verified_true`** — a real published helpline, a real SMS
shortcode, a real institutional domain, a real merchant UPI handle.
Currently: 1 of 8.

This is a hard requirement, not a nice to have. The Verifier's `true` path is
what separates a scam *detector* from a scam *confirmer*, and right now it
would be measured on a single sample, which is an anecdote rather than a
number. Every such value goes into `data/allowlists/bank_shortcodes.json` with
a `source_url` before it goes into a transcript.

Deliberately include the hardest negatives available:

- A genuine bank fraud team call. It impersonates nobody, but it has authority,
  urgency and asks the customer to act. This is the record most likely to break
  a naive detector.
- A genuine EMI bounce warning that mentions CIBIL. The kyc_expiry script uses
  exactly this threat at stage 4.
- A genuine electricity disconnection SMS with a same day deadline. Urgency
  alone must not trigger a flag.

## Sources

| source | good for | note |
|--------|----------|------|
| r/india, r/IndiaTech, r/personalfinanceindia | scam screenshots and call write ups | search "digital arrest", "loan app", "scam call" |
| r/developersIndia, r/bangalore, r/hyderabad | task scam and loan app threads | often full chat logs |
| YouTube sting and scambaiting channels | full call transcripts, best for digital_arrest | transcribe, do not embed audio |
| News reports, The Hindu, Indian Express, TOI cyber crime desks | verified case detail and amounts | good for source credibility on the slide |
| Cybercrime.gov.in and RBI Sachet advisories | official phrasing of real scams | also a source of legitimate message formats |
| Bank websites, published alert formats | the legitimate half | HDFC, SBI, ICICI publish their exact alert wording |
| Family and friends WhatsApp forwards | both halves | get consent, then strip every identifier |

## Anonymisation checklist, per record

- [ ] No real personal phone number, account number, card number, UPI handle
- [ ] No real victim name, invented name substituted
- [ ] Scam URLs rewritten to the reserved `.invalid` TLD
- [ ] No screenshots or images stored, text only
- [ ] `source.reference` names the source without naming a private individual
- [ ] Consent noted in `notes` for anything from a personal forward

## Labelling consistency

Two rules that keep stage labels comparable across labellers.

1. Label a turn by what the counterparty is **doing in that turn**, not by the
   overall stage of the conversation. A turn that only answers a question is 0.
2. `final_stage` is the highest label reached across the complete stored
   transcript, never the last label. A script that returns to isolation after
   reaching payment still has `final_stage` 5. `eval/validate.py` enforces
   this. The harness does not score against it — it scores against the highest
   stage inside the truncated prefix, which it derives itself.

3. `truncate_at_turn` goes on the last turn labelled stage 4. `next_stage` is
   then the stage of the first manipulative turn after that, which validate.py
   also derives and checks. If you get one wrong the validator tells you the
   value it expected, so do not compute it by hand.

4. A claim you cannot check against a published source is `unverifiable`, not
   `false`. Rounding unverifiable to false inflates the Verifier's numbers and
   collapses the moment someone asks how the check works.
