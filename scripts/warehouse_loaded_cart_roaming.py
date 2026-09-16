"""Control flow for loaded-cart roaming.

Not a standalone launcher.
Does not start Play, bake NavMesh, or save USD.

The caller supplies simulator-specific operations through `actions`.
"""

import time
from scripts import warehouse_roaming_config as config
from scripts.warehouse_roaming_goals import RoamingGoalPicker


class LoadedCartRoaming:
    def __init__(self, actions):
        """
        actions must provide these methods:

        begin_return()
            Keep Cart parked and begin returning Worker to the
            original cart-operating position and heading.

        return_complete()
            Return True only after position AND heading are verified.

        attach_loaded_boxes()
            Preserve each loaded box's transform relative to Cart.
            Must not move a box when attaching it.

        resume_cart()
            Resume Worker-Cart synchronization without a Cart jump.
            Must verify the operating pose before releasing the hold.

        worker_position()
            Return the current Worker world position: (x, y, z).

        route_check_steps(points)
            Yield between Worker/Cart footprint checks; return True only if valid.

        begin_move(goal)
            Queue one People GoTo command owned by this controller.

        move_complete(goal)
            Return True only after movement completes at the goal.

        update_loaded_boxes()
            Update loaded box transforms from the current Cart pose.

        stop_owned_motion()
            Cancel only commands owned by this controller.
            Keep Cart parked at its current pose.

        restore_loaded_boxes()
            Remove only the cargo-follow overrides owned here.
            Existing stack code remains responsible for restoring
            boxes to their original source positions on Stop.
        """
        self.actions = actions
        self.picker = RoamingGoalPicker()

        self.state = "idle"
        self.goal = None
        self.search = None
        self.started_at = None
        self.retry_at = None
        self.cargo_attached = False
        self.failure = None
        self.validation = None

    def start(self, now):
        """Call once, after all selected boxes have been loaded."""
        if self.state != "idle":
            raise RuntimeError("Roaming has already been started")

        self.started_at = now
        self.state = "returning"

        try:
            self.actions.begin_return()
        except Exception as error:
            self._fail(error)
            return

        print("[Loaded Roaming] RETURNING_TO_CART")

    def update(self, now):
        """Call once per update, only while Timeline is playing."""
        if self.state in ("idle", "failed", "closed"):
            return

        try:
            if self.cargo_attached:
                self.actions.update_loaded_boxes()

            if self.state == "returning":
                if self.actions.return_complete():
                    self.actions.attach_loaded_boxes()
                    self.cargo_attached = True

                    self.actions.resume_cart()
                    self._begin_search()
                    print("[Loaded Roaming] CART_CONNECTED")

                elif now - self.started_at > config.MOVE_TIMEOUT_SECONDS:
                    raise RuntimeError("Worker return timed out")

                return

            if self.state == "searching":
                self._search_one_candidate(now)
                return

            if self.state == "validating":
                self._advance_validation(now)
                return

            if self.state == "moving":
                if self.actions.move_complete(self.goal):
                    print("[Loaded Roaming] ARRIVED:", self.goal)
                    self._begin_search()

                elif now - self.started_at > config.MOVE_TIMEOUT_SECONDS:
                    raise RuntimeError("Roaming movement timed out")

                return

            if self.state == "retry_wait" and now >= self.retry_at:
                self._begin_search()

        except Exception as error:
            self._fail(error)

    def _begin_search(self):
        self._close_search()

        self.goal = None
        self.search = self.picker.candidate_steps(
            self.actions.worker_position()
        )
        self.state = "searching"

    def _search_one_candidate(self, now):
        # Consume only one candidate per update.
        # A single route query can still take noticeable time.
        try:
            result = next(self.search)
        except StopIteration:
            self._wait_before_retry(now)
            return

        if not result["accepted"]:
            return

        self.goal = tuple(result["goal"])
        self._close_search()
        self.validation=self.actions.route_check_steps(result['points'])
        self.state='validating'

    def _advance_validation(self,now):
        started=time.monotonic()
        try:
            for _ in range(config.GUARD_STEPS_PER_FRAME):
                next(self.validation)
                if time.monotonic()-started>=config.GUARD_FRAME_BUDGET_SECONDS:
                    break
        except StopIteration as result:
            self.validation=None
            if result.value is not True:
                reason=getattr(self.actions,'last_guard_reason',None)
                print('[Loaded Roaming] REJECTED_GOAL:', reason)
                self._wait_before_retry(now)
                return
            self.actions.begin_move(self.goal)
            self.started_at=now
            self.state='moving'
            print('[Loaded Roaming] MOVING:',self.goal)

    def _wait_before_retry(self, now):
        self._close_search()
        self.retry_at = now + config.RETRY_SECONDS
        self.state = "retry_wait"
        print("[Loaded Roaming] NO_SAFE_GOAL; retrying later")

    def _close_search(self):
        if self.validation is not None:
            self.validation.close()
            self.validation=None
        if self.search is not None:
            self.search.close()
            self.search = None

    def _fail(self, error):
        self._close_search()
        self.failure = str(error)
        self.state = "failed"

        try:
            self.actions.stop_owned_motion()
        except Exception as stop_error:
            self.failure += "; stop failed: " + str(stop_error)

        print("[Loaded Roaming] FAILED:", self.failure)
        print("[Loaded Roaming] Inspect the scene and press Stop")

    def close(self):
        """Call before the existing stack/synchronizer cleanup."""
        if self.state == "closed":
            return

        self._close_search()

        try:
            self.actions.stop_owned_motion()
        finally:
            try:
                if self.cargo_attached:
                    self.actions.restore_loaded_boxes()
            finally:
                self.cargo_attached = False
                self.state = "closed"
