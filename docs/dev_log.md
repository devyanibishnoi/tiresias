# Dev log

Dated entries: what went wrong or was decided, and what was done. This is the only source for the
report's Challenges Faced section.

## 2026-10-17

- Started build from PRD.md. Repo root only had PRD.md and the two author Word files. Moved the
  Word files into `docs/inputs/` and copied the template into `report/template.docx`.
- Only Python 3.14 is installed on the author's machine. No `gh` CLI available, so the GitHub repo
  push step will be left to the author (repo already exists at
  https://github.com/devyanibishnoi/telltale.git).
- First version of the covariate-drift injector (S1) shifted the mean of the informative features
  directly in the direction of their weights. This made average precision go UP after drift
  instead of down: the shift raised the ambient fraud rate in the window, and average precision is
  prevalence-sensitive, so a higher local prevalence looked like better detection even though
  nothing about the model's discrimination had changed. Fixed by (a) choosing a zero-sum shift
  direction so the shift does not move the ambient fraud rate, and (b) adding a severity-scaled
  noise term to the logit to model the real damage (observed features explain less once the
  population has moved into a region the model never trained on). See docs/decisions.md.
- Initial `data/sim_samples/` files saved the full stream per scenario (about 21 MB each, 202 MB
  total), far too large for "small compressed representative streams". Replaced with an 8-window,
  300-row-per-window subsample (about 165 KB per scenario).
- Generator acceptance tests (PRD 5.3) all pass on the 5 tuning seeds (100-104); see
  `tests/test_generator.py` and `tests/test_injector.py`. Phase 1 is done.
