# raw/

Drop raw transcripts here, one file per conversation, then run:

```
python tools/intake.py raw/<file>.txt
```

Format is one turn per line, speaker then a TAB then the text:

```
counterparty	Namaskar, main Cyber Crime Branch se bol raha hoon.
victim	Kaunsa parcel sir?
counterparty	FIR number 0000/2026 register ho chuki hai.
```

Speaker is `counterparty`, `victim` or `system`. Blank lines and lines
starting with `#` are ignored.

`.txt` files in this directory are gitignored, because raw text may still
contain identifiers that have not been stripped yet. Anonymisation happens on
the way into `data/transcripts/`, not here.
