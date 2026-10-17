"""Reference rebuild uses out-of-fold scores, PRD Section 15.1 item 9."""

import numpy as np

from tiresias.models import Retrainer, fit_model, out_of_fold_scores


def test_out_of_fold_scores_differ_from_in_sample():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(4000, 5))
    y = (X[:, 0] + rng.normal(scale=0.3, size=4000) > 0).astype(int)
    window_ids = np.repeat(np.arange(20), 200)

    in_sample_model = fit_model(X, y, random_state=0)
    in_sample_scores = in_sample_model.predict_proba(X)[:, 1]
    oof_scores = out_of_fold_scores(X, y, window_ids, random_state=0)

    # OOF scores are never computed by a model that saw that exact row during
    # training, so they should be a visibly worse (less overconfident) fit
    # than the in-sample scores of the same model class on the same data.
    from sklearn.metrics import log_loss

    assert log_loss(y, oof_scores) > log_loss(y, in_sample_scores)


def test_retrainer_returns_model_and_aligned_reference_material():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(2000, 5))
    y = (X[:, 0] > 0).astype(int)
    window_ids = np.repeat(np.arange(10), 200)

    retrainer = Retrainer(random_state=0)
    result = retrainer.fit(X, y, window_ids)

    assert result.X.shape == X.shape
    assert result.oof_scores.shape == (2000,)
    assert result.window_ids.shape == (2000,)
    preds = result.model.predict_proba(X[:5])
    assert preds.shape == (5, 2)
