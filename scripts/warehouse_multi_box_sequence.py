"""Isaac-Sim-independent state machine for sequential visual unloading.

The module emits actions only. It never edits USD, starts Play, publishes ROS2,
or moves a Worker/Cart. Runtime adapters must validate each action and report a
completion result back with the exact token.
"""

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class Action:
    token: tuple
    kind: str
    box_id: str | None
    return_pose: object


class Sequence:
    def __init__(self, box_ids):
        self.box_ids = tuple(box_ids)
        if not self.box_ids or any(not isinstance(box, str) or not box for box in self.box_ids):
            raise ValueError('box_ids must contain non-empty strings')
        if len(set(self.box_ids)) != len(self.box_ids):
            raise ValueError('box_ids must be unique')
        self.run_id = uuid4().hex
        self.ordinal = 0
        self.index = 0
        self.return_pose = None
        self.completed_box_ids = ()
        self.current_action = None
        self.finished = False

    def start(self, return_pose):
        if self.current_action is not None or self.finished:
            raise RuntimeError('sequence is already started or finished')
        self.return_pose = return_pose
        return self._issue('plan', self.box_ids[self.index])

    def complete(self, token, result):
        if self.current_action is None:
            if self.finished:
                return None
            raise RuntimeError('sequence has not been started')
        if tuple(token) != self.current_action.token:
            return None
        if not isinstance(result, dict):
            raise ValueError('result must be a dict')
        action = self.current_action
        self.current_action = None
        if action.kind == 'plan':
            if result.get('status') != 'loaded':
                return self._issue('return', None)
            self.completed_box_ids += (action.box_id,)
            self.index += 1
            if self.index < len(self.box_ids):
                return self._issue('plan', self.box_ids[self.index])
            return self._issue('return', None)
        if action.kind == 'return':
            if result.get('status') != 'returned':
                self.finished = True
                self.failure_reason = result.get('reason', 'return_failed')
                return None
            return self._issue('attention', None)
        if action.kind == 'attention':
            self.finished = True
            return None
        raise RuntimeError('unknown action kind: ' + action.kind)

    def _issue(self, kind, box_id):
        self.ordinal += 1
        token = (self.run_id, self.ordinal, kind, box_id)
        action = Action(token, kind, box_id, self.return_pose)
        self.current_action = action
        return action
