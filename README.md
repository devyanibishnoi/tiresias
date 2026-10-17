# telltale

Label-free drift detection and selective retraining for deployed fraud classifiers under delayed
ground truth.

Status: under construction. See `PRD.md` for the full specification.

## Quick start

```
python -m venv .venv
.venv\Scripts\activate          (Windows)
source .venv/bin/activate       (Linux/Mac)
pip install -r requirements.txt
pytest -q
python -m telltale.cli generate-samples
python -m telltale.cli tune
python -m telltale.cli run --config configs/pilot.yaml
python -m telltale.cli run --config configs/main.yaml
python -m telltale.cli profile
python -m telltale.cli make-figures
python -m telltale.cli real-check
python report/build_report.py
```

Requires Python 3.10 or newer.
