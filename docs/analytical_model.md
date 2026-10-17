# Analytical model

Written before the pilot and main runs, as PRD Section 10 requires. The quantities below (A1 to
A5) are derived from the method's structure and from statistics measured on the tuning seeds
only (100 to 104). Section 14.1 of the report compares these predictions with what the main run
actually measured.

## A1. Detection delay of the CUSUM monitor

The evidence combiner runs a one-sided CUSUM: at each window the accumulated sum S_t is
max(0, S_{t-1} + E_t - k), where E_t is that window's combined evidence and k is the slack. An
alarm fires the first time S_t exceeds the height h.

Once a sudden covariate drift starts, the evidence jumps from its pre-drift level (close to 1,
by construction, since evidence is scaled so that 1.0 sits at the edge of normal) to a much
higher post-onset level. Call the average excess of evidence over the slack after onset mu
(mu = mean(E_t) - k, measured on post-onset windows of the tuning seeds). Since S_t accumulates
mu each window after onset, the CUSUM needs about h / mu windows to cross the height, plus one
window because the stream only reveals whether drift is present at the granularity of a whole
window. So the predicted delay is:

    delay ~= h / mu + 1 window

For gradual drift (S2), the evidence itself ramps up linearly over the ramp length (30 windows,
window 60 to 90) rather than jumping immediately, so the accumulated excess over window t is
closer to a triangular (ramp) sum instead of a constant mu per window. The ramp version of the
same idea integrates the growing excess until the running sum crosses h, which pushes the
predicted delay for S2 later than the sudden-onset case at the same severity.

mu is estimated separately for each severity from the post-onset evidence of S1 on the tuning
seeds, holding the slack and height fixed at their tuned values (see A2).

## A2. False alarm rate

Under no drift, E_t fluctuates around 1.0 with sampling noise. The in-control average run length
(ARL), the expected number of windows between false alarms, is estimated directly by simulating
the tuned CUSUM against the null evidence stream (S0 and S6, tuning seeds, Section 6.5). The
predicted false alarm rate per 100 windows is then:

    false alarm rate per 100 ~= 100 / ARL

The tuning procedure (Phase 3) searches a grid of (slack, height) pairs and keeps only the ones
whose simulated false alarm rate on S0 and S6 is at or below the 1-per-100 target, picking the
smallest height among those (fastest detection for the same false-alarm budget).

## A3. Exposure

Exposure is the number of windows between a drift event's true onset and the deployment of a
model corrected for it. Each strategy has a different exposure path:

- Label-free path (M0, M1, M1a, M1b, normal case): detection delay (A1) + label delay D + maturity
  wait m. The alarm fires at onset + delay, but the retrain only executes once D + m windows of
  post-alarm labels have matured, per the deferred-retrain rule (PRD 6.6).
- Label-only path (B3, and M1 whenever the backstop wins the race): D + the number of matured
  windows the backstop needs to accumulate enough CUSUM evidence of a recall drop. Structurally
  this is at least D (the first matured window already reflects the drift) plus whatever the
  backstop's own detection delay is on matured-window recall.
- Oracle (B2): D + m exactly, since the oracle retrains the instant enough post-event labels have
  matured, with no detection delay at all.
- Fixed schedule (B1): on average K / 2 windows, since an event is equally likely to land anywhere
  in the schedule's cycle.

## A4. Retrain count

- Fixed schedule (B1): about (number of evaluation windows) / K.
- Label-free / combined framework (M0, M1, M1a, M1b): about (number of true drift events in the
  scenario) + (false alarm rate) x (number of evaluation windows), since every true event should
  trigger one retrain and every false alarm also triggers one.

## A5. Compute

    compute seconds ~= retrain_count x (measured seconds per retrain)
                      + (number of windows) x (measured seconds per monitored window)

Both measured constants come from `tiresias.cli profile` (Section 9 item 7, Section 13 component
sheet), not from this document.

## Status

A1 to A5 are stated here in general form. The concrete numbers (slack, height, mu, ARL, measured
seconds per retrain and per window) are filled in docs/first_pass_prediction.md and compared with
observed values in the report's Section 14.1 table, after the tuning, pilot and main runs.
