# Offscript

Every scam follows a script. We take you off it.

## What this is

A reasoning agent that detects financial scams in India by identifying the
manipulation structure of a conversation instead of blocklisting the sender.

Built for HackIndia x Appinventiv AI Hackathon 2026, Noida, Sep 12 to 13.

## The problem

India runs the world's largest real time payments system and fraud has scaled
with it. Digital arrest scams, fake customer care numbers, KYC expiry messages
and predatory loan app harassment. The people hit hardest are first time
smartphone users, elderly parents and non English speakers.

Every existing defence is a blocklist. Blocklists are reactive by design. A
scammer changes the number and the same script works again tomorrow.
The number is disposable. The script is not.

## The insight

We do not detect the sender. We detect the manipulation structure.

Scams run in stages that stay constant even when the number, the language and
the pretext change.

1. Authority impersonation
2. Manufactured urgency
3. Isolation, meaning do not tell your family
4. Escalating fear
5. Payment instruction

A keyword filter cannot see this. A reasoning system can.

## Architecture

Four agents.

**Listener**
Takes a forwarded message thread or a pasted call transcript and normalises it
into a turn by turn conversation.

**Verifier**
Checks hard claims against ground truth. Does the UPI handle resolve, is the
bank shortcode real, was the URL registered four days ago, does the police case
number match a valid format. This grounds the verdict in facts rather than vibes.

**Script Matcher**
Maps the conversation against the script library and outputs which stage of
which script the user is currently at, with evidence spans.

**Guardian**
Explains in the user's own language what is happening, predicts what the
scammer will ask for next, and can alert a trusted family contact.

## What makes this win

1. A measured false positive rate on real non scam urgent messages
2. A stage timeline instead of a confidence score
3. Live prediction of the scammer's next move, shown on stage
4. Framed as a drop in SDK for any Indian fintech app, not a research demo

## Script library

Five scripts for v1.

| id | name | typical channel |
|----|------|-----------------|
| digital_arrest | Fake police or CBI custody threat | call |
| kyc_expiry | Bank or wallet KYC expiry | sms, whatsapp |
| fake_support | Fake customer care number | call |
| loan_app | Predatory loan app harassment | whatsapp, call |
| task_scam | Job or task based investment scam | telegram, whatsapp |

## Evaluation

The eval set is the moat. 40 transcripts minimum.

- 20 scam transcripts across the five scripts
- 20 legitimate urgent messages, meaning real bank OTP, real delivery OTP,
  real EMI reminder, real card block alert

Metrics reported on the final slide.

| metric | target |
|--------|--------|
| Recall on scam | above 0.90 |
| False positive rate on legitimate | below 0.10 |
| Stage accuracy | above 0.70 |
| Next stage prediction accuracy | above 0.60 |

## Scope

In scope for 24 hours.

- Single page web app, paste a transcript, see a stage timeline
- Four deterministic verifier checks
- Hindi and Telugu output from Guardian
- Telegram alert to a trusted contact
- Eval numbers on the 40 item set

Out of scope. Do not build these.

- Real WhatsApp or telecom integration
- Login, accounts, user database
- Mobile app
- Anything blockchain
- Live external APIs the venue wifi could break

## Day of timeline

| hours | work |
|-------|------|
| 0 to 2 | Round 1 architecture pitch, already prepared |
| 2 to 8 | Listener and Script Matcher end to end on five transcripts |
| 8 to 12 | Verifier, four checks |
| 12 to 16 | Timeline UI, prediction, Hindi output |
| 16 to 19 | Run eval, capture numbers, record backup demo video |
| 19 to 20 | Cleanup before code freeze at hour 20 |
| 20 to 24 | Finale pitch rehearsal, six runs minimum |

## Demo script for the finale

1. Paste the first half of a real digital arrest transcript
2. Timeline lights up to Stage 3, Isolation
3. Offscript predicts the next two moves out loud
4. Reveal the real second half of the transcript, the prediction matches
5. Paste a real HDFC transaction alert, Offscript stays silent
6. Show the eval table

## Repo layout

    offscript/
      PROJECT.md
      data/
        transcripts/          scam and legitimate, one json per item
        schema.json
      scripts/
        digital_arrest.yaml
        kyc_expiry.yaml
        fake_support.yaml
        loan_app.yaml
        task_scam.yaml
      eval/
        run_eval.py
        metrics.md
      prompts/
        script_matcher.md
        guardian.md
      deck/

## Rules note

Confirm with organisers whether pre written code is allowed. Dataset, research
and deck are normally fine. Product code is normally not.
