# tools/

Dataset tooling. Not product code — nothing here ships, nothing here calls a
model or the network.

## intake.py

Turns a raw pasted conversation into a schema valid record in
`data/transcripts/`, walking you through stage labelling one turn at a time
with the definitions from `data/ANNOTATION.md` shown inline.

```
python tools/intake.py raw/my_transcript.txt
```

Raw format, one turn per line, speaker then a TAB then the text:

```
counterparty	Namaskar, main Cyber Crime Branch se bol raha hoon.
victim	Kaunsa parcel sir?
counterparty	FIR number 0000/2026 register ho chuki hai.
```

Speaker is `counterparty`, `victim` or `system`. Blank lines and lines
starting with `#` are ignored.

What it does for you:

- shows the six stage definitions and the three tie break rules while you label
- skips per turn prompting on legitimate records, since they are all stage 0
- suggests `truncate_at_turn` at the last stage 4 turn and refuses a cut that
  leaves a stage 5 turn inside the prefix
- derives `ground_truth.next_stage` from the cut rather than asking you
- forces `unverifiable` on sender header claims
- warns if anything matching an Indian mobile number, ten digits starting 6 to
  9, appears in the text
- runs `eval/validate.py` before exiting and **deletes the file it just wrote**
  if validation fails, so `data/transcripts/` never holds a broken record

Put raw files wherever you like. `raw/` is a reasonable habit; nothing reads
that directory automatically.
