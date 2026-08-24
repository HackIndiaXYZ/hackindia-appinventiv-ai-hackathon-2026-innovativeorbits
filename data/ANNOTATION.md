# Annotation guide

Ten minutes. Read it once before your first transcript, then keep it open.

You label **each turn** with a stage from 0 to 5. You are labelling what the
counterparty is *doing in that turn*, not where the conversation has got to
overall. `tools/intake.py` shows you these definitions inline as you go.

---

## Stage 0, no manipulation

Any turn that is not a manipulation move: the victim speaking, a greeting, an
SMS sender header line, a factual answer.

**Yes** — "Kaunsa parcel sir? Maine to koi parcel nahi bheja." (victim)
**Yes** — "AD-HDFCBNK" (sender header line)
**Not this** — "Namaskar, main Cyber Crime Branch se bol raha hoon." A greeting
*fused with* an authority claim is stage 1. The greeting alone is 0.

## Stage 1, authority impersonation

Claiming to be, or to speak for, an institution the target should defer to:
police, a bank, a regulator, a company's support desk, an employer.

**Yes** — "Main Sub-Inspector Rakesh Verma bol raha hoon, Cyber Crime Branch."
**Yes** — "ప్రియమైన కస్టమర్, ఇది బ్యాంక్ వెరిఫికేషన్ విభాగం నుండి అధికారిక సందేశం."
**Not this** — "Rs.4999.00 debited from A/c XX0000. -HDFC Bank." A genuine bank
identifying itself is not impersonation. Legitimate records are always 0.

## Stage 2, manufactured urgency

Compressing the decision window. A deadline, a countdown, a window that closes,
a penalty that grows. The point is denying the target time to check.

**Yes** — "Humare paas sirf do ghante hain, uske baad file court chali jayegi."
**Yes** — "ఈరోజు రాత్రి 11 గంటలలోపు అప్‌డేట్ చేయకపోతే మీ ఖాతా బ్లాక్ అవుతుంది."
**Not this** — "block the card now by sending SMS Block DC 0000 to 7308080808."
Urgency that routes the reader to the institution's own published channel is
not manufactured urgency. Stage 0.

## Stage 3, isolation

Cutting off the second opinion. Do not tell your family. Stay on this call. Do
not open the app. Do not go to the branch. Talk only to me. Often disguised as
confidentiality or as safety advice.

**Yes** — "Ye baat kisi ko mat bataiye. Na wife ko, na bete ko."
**Yes** — "బ్రాంచ్ సర్వర్ డౌన్ ఉంది, ఆన్‌లైన్ మాత్రమే పని చేస్తుంది."
**Not this** — "Never share your OTP with anyone. -HDFC Bank." Generic safety
advice sent by the institution itself is stage 0. It becomes stage 3 only when
it carves out an exception for the speaker: "share it with me, I am the
verification officer."

## Stage 4, escalating fear

Raising the cost of non-compliance beyond the original problem. Arrest, public
exposure, the family, the job, the credit score, contacts being messaged.

**Yes** — "Local police tees minute mein ghar par hogi, media ke saath."
**Yes** — "మీ EMI బౌన్స్ అవుతుంది, CIBIL స్కోర్ దెబ్బతింటుంది."
**Not this** — "If this was not you, report it within 24 hours." Naming a real
consequence of inaction is not escalation. Escalation *adds* a new and larger
harm the target had not been thinking about.

## Stage 5, payment instruction

Asking for money, credentials, or control. A transfer, a UPI collect request,
an OTP, a PIN entry, a remote access app install, a link that takes payment.

**Yes** — "RBI ke verification account mein apna balance transfer karna hoga."
**Yes** — "ఈ లింక్ ఓపెన్ చేసి రూ. 10 వెరిఫికేషన్ చెల్లింపు చేయండి."
**Not this** — "Call 1800 1600 immediately." Directing the reader to a
published helpline asks for nothing. Stage 0.

---

## Tie breaks

These three cause almost all real disagreement. The rules are not negotiable —
consistency between annotators matters more than either of us being right.

**1. A turn carrying two stages at once.**
Label the **higher** stage number. "Warrant aaj shaam chhe baje execute hoga,
aur kisi ko mat bataiye" is both urgency (2) and isolation (3). Label it 3.

*Why:* the stage timeline is meant to show how far the script has advanced. The
higher number is the more advanced move, and taking the maximum keeps
`final_stage` consistent with the labels underneath it.

**2. A turn restating an earlier stage without advancing.**
Label it with that stage again, not 0. Repetition is the script working, not a
pause in it. Three separate isolation instructions get 3, 3, 3.

*Why:* per-turn stage accuracy is scored on every turn. Marking repeats as 0
would teach the matcher that a re-stated threat is not manipulation.

**3. An opening turn that is only a greeting.**
Stage 0. "Namaskar." on its own is 0. "Namaskar, main Cyber Crime Branch se
bol raha hoon" is 1, because the authority claim is in the same turn.

*Why:* if greetings counted, every scam would start at stage 1 by default and
stage 1 would stop meaning anything.

---

## Legitimate records

**Every turn is 0. No exceptions, no matter how urgent the tone.**

This is the rule most likely to be broken, because genuine bank alerts really
do sound alarming — deadlines, large amounts, the words "block" and
"immediately". If you find yourself wanting to label a genuine HDFC alert as
stage 2, stop: that instinct is exactly the false positive we are building this
dataset to measure. Label it 0 and write down in `notes` what tempted you. That
note is useful evidence.

If a record genuinely contains manipulation, it is not a legitimate record.
Re-file it as a scam record.

---

## Claims

For each transcript also list its `hard_claims`. Each one gets a `kind`, an
`expected_verdict` and a `rationale`.

Three verdicts, never two:

| verdict | means |
|---------|-------|
| `verified_true` | resolves against an entry in `data/allowlists/` |
| `verified_false` | provably contradicted |
| `unverifiable` | no source exists to settle it offline |

**Do not round `unverifiable` to `verified_false` to make a scam look worse.**
SMS sender headers are always `unverifiable` — the TRAI DLT registry is not
public. So are individual officer names. Saying "we cannot check this" is a
result we report, not a failure to hide.

A `verified_true` verdict on a helpline, shortcode, domain or UPI handle must
already exist in `data/allowlists/` with a `source_url` and a `verified_on`
date. `eval/validate.py` fails the record otherwise. Never add an allowlist
entry from memory — open the institution's own page and read the value off it.

---

## Double annotation

A random 10 percent of every batch gets labelled independently by both people.
Run `python eval/agreement.py <dir_a> <dir_b>`. If Cohen's kappa is below 0.7,
sit down with the disagreement list it prints and fix this guide before
trusting the rest of that batch.
