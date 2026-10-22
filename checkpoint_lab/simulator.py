"""Replay a finite job against failures in wall-clock time.

A completed checkpoint is durable. A failure discards all useful work since it
and restarts recovery. Stage completion wins ties with a failure timestamp.
"""
from dataclasses import dataclass
import math
from collections.abc import Iterable


@dataclass(frozen=True)
class Result:
    interval_seconds: float
    total_seconds: float
    useful_seconds: float
    lost_work_seconds: float
    checkpoint_seconds: float
    recovery_seconds: float
    failures: int
    completed_checkpoints: int

    @property
    def efficiency(self) -> float:
        return self.useful_seconds / self.total_seconds


def _number(value: float, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


def simulate(*, useful_seconds: float, interval_seconds: float,
             checkpoint_seconds: float, recovery_seconds: float,
             failure_times_seconds: Iterable[float] = ()) -> Result:
    """Complete a job, returning a decomposition of its elapsed wall time.

    Failures are strictly increasing absolute seconds from job start. Failures
    during a checkpoint invalidate that incomplete checkpoint; failures during
    recovery restart its full duration. Failures after completion are ignored.
    """
    useful = _number(useful_seconds, "useful_seconds", positive=True)
    interval = _number(interval_seconds, "interval_seconds", positive=True)
    checkpoint = _number(checkpoint_seconds, "checkpoint_seconds")
    recovery = _number(recovery_seconds, "recovery_seconds")
    failures = tuple(_number(t, "failure timestamp") for t in failure_times_seconds)
    if any(b <= a for a, b in zip(failures, failures[1:])):
        raise ValueError("failure timestamps must be strictly increasing")

    wall = progress = durable = lost = checkpoint_spent = recovery_spent = 0.0
    next_failure = failure_count = completed_checkpoints = 0

    def stage(duration: float) -> tuple[float, bool]:
        nonlocal wall
        end = wall + duration
        if duration > 0 and end == wall:
            raise ValueError("duration is too small for the current wall-clock precision")
        timestamp = failures[next_failure] if next_failure < len(failures) else math.inf
        interrupted = timestamp < end
        elapsed = timestamp - wall if interrupted else duration
        wall = timestamp if interrupted else end
        return elapsed, interrupted

    def fail_and_recover() -> None:
        nonlocal next_failure, failure_count, lost, progress, recovery_spent
        lost += progress - durable
        progress = durable
        next_failure += 1
        failure_count += 1
        while True:
            elapsed, interrupted = stage(recovery)
            recovery_spent += elapsed
            if not interrupted:
                return
            next_failure += 1
            failure_count += 1

    while progress < useful:
        target = min(durable + interval, useful)
        if target <= progress:
            raise ValueError("interval is too small for the current work precision")
        elapsed, interrupted = stage(target - progress)
        progress += elapsed
        if interrupted:
            fail_and_recover()
            continue
        # Work is complete: do not write an unnecessary final checkpoint.
        progress = target
        if progress == useful:
            break
        elapsed, interrupted = stage(checkpoint)
        checkpoint_spent += elapsed
        if interrupted:
            fail_and_recover()
        else:
            durable = progress
            completed_checkpoints += 1

    return Result(interval, wall, useful, lost, checkpoint_spent, recovery_spent,
                  failure_count, completed_checkpoints)


def compare_intervals(*, intervals_seconds: Iterable[float], **scenario) -> list[Result]:
    """Rank candidate intervals by completion time on the same trace.

    This is a retrospective comparison, not an estimate of an optimal policy on
    unseen failures. Materialize the trace once so generator inputs replay fairly.
    """
    intervals = tuple(intervals_seconds)
    if not intervals:
        raise ValueError("at least one checkpoint interval is required")
    scenario = dict(scenario)
    scenario["failure_times_seconds"] = tuple(scenario.get("failure_times_seconds", ()))
    results = [simulate(interval_seconds=i, **scenario) for i in intervals]
    return sorted(results, key=lambda r: (r.total_seconds, r.interval_seconds))
