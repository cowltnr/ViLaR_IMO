"""Pure orchestration adapter for the future Isaac multi-box runtime.

The adapter owns no Isaac objects and never starts Timeline. A simulator-facing
executor can consume the returned RuntimeAction, perform one validated action,
and call ``complete`` with its result.
"""

from dataclasses import dataclass

from scripts.warehouse_multi_box_preflight import collect_source_approaches
from scripts.warehouse_multi_box_sequence import Action, Sequence


@dataclass(frozen=True)
class RuntimeAction:
    action: Action
    source_approach: object = None


class WarehouseMultiBoxRuntime:
    def __init__(self, box_ids, *, max_snap_distance_m=.15):
        self.box_ids = tuple(box_ids)
        self.max_snap_distance_m = max_snap_distance_m
        self.sequence = None
        self.source_approaches = {}

    def prepare(self, report, return_pose):
        if self.sequence is not None:
            raise RuntimeError('runtime is already prepared')
        approaches, reason = collect_source_approaches(
            report, self.box_ids, max_snap_distance_m=self.max_snap_distance_m)
        if reason:
            return {'status': 'blocked', 'reason': reason, 'action': None}
        self.source_approaches = {item.box_id: item for item in approaches}
        self.sequence = Sequence(self.box_ids)
        return self._wrap(self.sequence.start(return_pose))

    def complete(self, token, result):
        if self.sequence is None:
            raise RuntimeError('runtime is not prepared')
        action = self.sequence.complete(token, result)
        return None if action is None else self._wrap(action)

    def _wrap(self, action):
        return RuntimeAction(action, self.source_approaches.get(action.box_id))
