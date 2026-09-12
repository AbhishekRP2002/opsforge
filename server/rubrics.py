"""Expose the canonical episode reward through OpenEnv's trajectory interface."""

from openenv.core.rubrics import TrajectoryRubric


class ItopsOutcomeRubric(TrajectoryRubric):
    """Keep all credit on the terminal action; prior steps receive zero."""

    def score_trajectory(self, trajectory) -> float:
        if not trajectory or not trajectory[-1][1].done:
            return 0.0
        return float(trajectory[-1][1].reward)

    def compute_step_rewards(self) -> list[float]:
        if not self._trajectory:
            return []
        return [0.0] * (len(self._trajectory) - 1) + [
            self.score_trajectory(self._trajectory)
        ]

    def reset(self) -> None:
        super().reset()
        self.last_score = None

    def diagnostics(self) -> dict:
        return {
            "name": type(self).__name__,
            "last_score": self.last_score,
            "steps": len(self._trajectory),
            "step_rewards": self.compute_step_rewards(),
        }
