import unittest
from types import SimpleNamespace
from unittest.mock import Mock


class UnloadingLifecycleTest(unittest.TestCase):
    def test_loaded_box_is_kept_until_arm_release_finishes(self):
        from scripts.warehouse_unloading_live import Unloading
        obj = Unloading.__new__(Unloading)
        obj.timeline = SimpleNamespace(is_playing=lambda: True, get_current_time=lambda: 1)
        obj.state, obj.pending = 'carrying', False
        obj.transfer = SimpleNamespace(state='loaded', update=Mock())
        obj.gesture = SimpleNamespace(done=False, update=Mock(), reset=Mock())
        obj.loaded, obj.index, obj.placement = [], 0, 'box-a'
        obj.update(None)
        self.assertEqual(obj.loaded, [])
        obj.gesture.done = True
        obj.update(None)
        self.assertEqual(obj.loaded, ['box-a'])
        self.assertEqual(obj.state, 'next')

    def test_shutdown_restores_every_transfer_and_cart(self):
        from scripts.warehouse_unloading_live import Unloading
        obj = Unloading.__new__(Unloading)
        obj.transfers = [Mock(), Mock(), Mock(), Mock()]
        obj.gesture, obj.sync = Mock(), Mock()
        obj.shutdown()
        for transfer in obj.transfers:
            transfer.restore.assert_called_once()
        obj.sync.shutdown.assert_called_once()
