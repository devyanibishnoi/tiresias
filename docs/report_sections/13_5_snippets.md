## 13.5 Short code snippets (PRD 13.1 rule 5: at most four, each under 25 lines)

## PSI computation (`telltale/monitors/stats.py`)

```python
def psi_from_fractions(ref_frac, cur_frac, eps=1e-4):
    rf = ref_frac + eps
    cf = cur_frac + eps
    return np.sum((cf - rf) * np.log(cf / rf), axis=-1)

def psi_fast(edges, ref_frac, current, eps=1e-4):
    counts = np.bincount(digitize(current, edges), minlength=len(ref_frac)).astype(float)
    cur_frac = counts / counts.sum()
    return float(psi_from_fractions(ref_frac, cur_frac, eps))
```

## CUSUM update (`telltale/monitors/cusum.py`)

```python
def update(self, evidence: float) -> bool:
    self.S = max(0.0, self.S + evidence - self.slack)
    if self._cooldown_remaining > 0:
        self._cooldown_remaining -= 1
        return False
    if self.S > self.height:
        self.S = 0.0
        self._cooldown_remaining = self.cooldown
        return True
    return False
```

## Leakage guard (`telltale/data/label_vault.py`)

```python
def get(self, window: int, now: int) -> np.ndarray:
    if now - window < self.label_delay:
        raise LeakageError(
            f"window {window} labels requested at t={now}, "
            f"but they only mature at t={window + self.label_delay}"
        )
    return self._y[window]
```

## Retrain policy decision (`telltale/simulator.py`, inside the window loop)

```python
if alarm_label_free and pending_retrain_at is None:
    pending_retrain_at = t + cfg.label_delay + cfg.maturity_wait
    pending_source = "label_free"

if alarm_backstop:
    pending_retrain_at = t          # backstop takes over immediately
    pending_source = "backstop"
```

## Console output blocks and screenshots

[AUTHOR TO INSERT TERMINAL SCREENSHOT]

[AUTHOR TO INSERT TERMINAL SCREENSHOT]
