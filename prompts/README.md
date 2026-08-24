# prompts/

Empty on purpose.

PROJECT.md lists `script_matcher.md` and `guardian.md` here. Those are written
on the day, inside the event window, along with the rest of the product.

The inputs they will need already exist and can be read now:

- `../scripts/*.yaml` gives the Script Matcher its stage definitions, phrasing
  patterns per language, and the two likely next moves per stage.
- `../data/schema.json` defines the output shape the Script Matcher must
  produce, which is `final_stage`, `next_stage`, `script` and per turn
  `stage_labels`.
- `../eval/run_eval.py` defines exactly what `predict()` must return, which is
  what the Script Matcher prompt has to be built to emit.
