# Verdict validation (Phase 8)

Confirms the *rules themselves* match real-world judgement — not that the code is
deterministic (unit tests already pin that). You provide a labelled ground truth;
the harness runs a real scan and compares the tool's verdicts to your labels.

## How to use

1. Copy the template and fill it with domains you can verify by hand
   (view-source / DevTools / the font's EULA). Aim for **20–30 domains** with a
   mix of `ok` / `needs_check` / `violation`.

   ```bash
   cp validation/labels.example.yaml validation/labels.yaml   # gitignored
   ```

2. Run the validation (this performs **real scans** — it hits the network; it is
   not part of CI):

   ```bash
   uv run fontsentry validate --labels validation/labels.yaml --out validation/result.md
   ```

## Reading the result

- **Agreement** — share of *detected* labelled fonts whose verdict the tool got right.
- **False negatives** — the unsafe direction: the tool said `OK` where you did not.
  These are called out separately and make the command exit non-zero, because a
  missed problem is worse than a false alarm.
- **Not detected** — a font you labelled that the tool didn't find (a detection
  gap, distinct from a verdict disagreement).

Publish the number **and where the tool is wrong** — being honest about the error
is the point (see `docs/methodology.md`). The label set is the ground truth, so
disagreements are as likely to reveal a label mistake as a rule mistake; review both.

## Files

- `labels.example.yaml` — committed template.
- `labels.yaml` — your real labels (gitignored).
- `result.md` — the generated summary (gitignored).
