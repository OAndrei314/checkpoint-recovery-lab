import math
import random

import pytest

from checkpoint_lab import compare_intervals, simulate


def run(**overrides):
    scenario = dict(useful_seconds=100, interval_seconds=30,
                    checkpoint_seconds=5, recovery_seconds=10)
    return simulate(**(scenario | overrides))


def test_no_failures_has_no_final_checkpoint():
    r = run()
    assert (r.total_seconds, r.completed_checkpoints) == (115, 3)


def test_hand_calculated_work_failure():
    # save at 35, fail at 40 (lose 5), recover to 50; complete at 130.
    r = run(failure_times_seconds=[40])
    assert (r.total_seconds, r.lost_work_seconds, r.recovery_seconds) == (130, 5, 10)
    assert (r.failures, r.completed_checkpoints) == (1, 3)


def test_failure_during_checkpoint_does_not_save_progress():
    r = run(failure_times_seconds=[32])
    assert (r.total_seconds, r.lost_work_seconds, r.checkpoint_seconds) == (157, 30, 17)
    assert r.completed_checkpoints == 3


def test_repeated_failure_restarts_recovery():
    r = run(failure_times_seconds=[40, 42, 45])
    assert (r.total_seconds, r.recovery_seconds, r.failures) == (135, 15, 3)
    assert r.lost_work_seconds == 5


def test_completion_wins_boundary_ties():
    r = run(failure_times_seconds=[35])
    assert (r.total_seconds, r.lost_work_seconds) == (125, 0)
    r = run(failure_times_seconds=[115, 200])
    assert r.failures == 0


def test_failure_at_zero_and_zero_overheads():
    r = run(checkpoint_seconds=0, recovery_seconds=0, failure_times_seconds=[0, 30, 100])
    assert (r.total_seconds, r.lost_work_seconds, r.failures) == (100, 0, 2)


def test_interval_longer_than_job():
    r = run(interval_seconds=1000)
    assert r.total_seconds == 100
    assert r.completed_checkpoints == 0


def test_wall_time_is_conserved_over_random_traces():
    rng = random.Random(314)
    for _ in range(200):
        r = run(interval_seconds=rng.uniform(1, 100), checkpoint_seconds=rng.uniform(0, 12),
                recovery_seconds=rng.uniform(0, 30),
                failure_times_seconds=sorted(rng.sample(range(300), 12)))
        assert r.total_seconds == pytest.approx(r.useful_seconds + r.lost_work_seconds
                                               + r.checkpoint_seconds + r.recovery_seconds)
        assert 0 < r.efficiency <= 1


@pytest.mark.parametrize("overrides", [
    {"useful_seconds": 0}, {"interval_seconds": -1}, {"checkpoint_seconds": -1},
    {"recovery_seconds": math.inf}, {"interval_seconds": math.nan},
    {"interval_seconds": True}, {"failure_times_seconds": [4, 4]},
    {"failure_times_seconds": [4, 3]}, {"failure_times_seconds": [-1]},
    {"failure_times_seconds": [math.nan]},
])
def test_invalid_scenarios_are_rejected(overrides):
    with pytest.raises(ValueError):
        run(**overrides)


def test_comparison_replays_generator_trace_for_every_candidate():
    scenario = dict(useful_seconds=100, checkpoint_seconds=5, recovery_seconds=10)
    ranked = compare_intervals(intervals_seconds=[30, 60], failure_times_seconds=iter([40]), **scenario)
    assert ranked == sorted([simulate(interval_seconds=i, failure_times_seconds=[40], **scenario)
                             for i in (30, 60)], key=lambda r: (r.total_seconds, r.interval_seconds))


def test_comparison_requires_candidates():
    with pytest.raises(ValueError):
        compare_intervals(intervals_seconds=[])
