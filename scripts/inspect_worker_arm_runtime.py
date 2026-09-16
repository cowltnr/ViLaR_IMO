"""Open/Run before Play: capture once after reaching, without controlling Timeline.

Reads the existing Warehouse runtime handle, not a fresh Character path lookup.
Writes one new diagnostic JSON only. Safe to arm while stopped or playing.
"""

import builtins
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT = Path('/home/cowltnr/PycharmProjects/SDV_Robocar')
EXPECTED_STAGE = Path('/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd')
PROBE_NAME = '_warehouse_arm_runtime_probe'


def vector3(value):
    try:
        values = ([float(value.x), float(value.y), float(value.z)] if hasattr(value, 'x')
                  else [float(v) for v in value])
        return values if len(values) == 3 and all(math.isfinite(v) for v in values) else None
    except (ValueError, TypeError, AttributeError):
        return None


def ready_to_sample(gesture, now, playing):
    return (playing and gesture is not None and getattr(gesture, 'character', None) is not None
            and getattr(gesture, 'started', None) is not None and not gesture.done
            and now >= gesture.started + gesture.reach + .25)


def collect(gesture, transfer, now):
    import carb
    character = gesture.character
    report = {'simulation_time': now, 'elapsed': now - gesture.started,
              'box_path': transfer.box_path, 'box_state': transfer.state,
              'box_center': vector3(transfer.current_center),
              'graph_reference_chains': gesture.graph.chains,
              'estimated_shoulders_local': gesture.shoulders,
              'arm_lengths': gesture.arm_lengths, 'targets': {}, 'joints': {},
              'height_feedback': getattr(gesture, 'height_feedback_report', {}),
              'stage_modified': False, 'timeline_modified': False,
              'note': 'Runtime API joint queries; invalid/unavailable queries are not measurements.'}
    for side in ('left', 'right'):
        values = character.get_variable('WarehouseReach' + side.title() + 'Target')
        report['targets'][side] = vector3(values[0]) if values else None
    weights = character.get_variable('WarehouseReachWeight')
    report['weight'] = float(weights[0]) if weights else None
    names = {'LeftArm', 'LeftForeArm', 'LeftHand', 'RightArm', 'RightForeArm', 'RightHand'}
    names.update(name for chain in gesture.graph.chains.values() for name in chain)
    for name in sorted(names):
        position = carb.Float3(float('nan'), float('nan'), float('nan'))
        rotation = carb.Float4(0,0,0,1)
        try:
            result = character.get_joint_transform(name, position, rotation)
            point = vector3(position) if result is not False else None
            report['joints'][name] = {'world_position': point, 'valid': point is not None,
                                      'api_result': str(result)}
        except Exception as error:
            report['joints'][name] = {'world_position': None, 'valid': False, 'error': str(error)}
    return report


class RuntimeProbe:
    def __init__(self, stage, timeline):
        self.stage, self.timeline = stage, timeline
        self.subscription = None

    def close(self):
        self.subscription = None

    def update(self, event):
        import omni.usd
        if omni.usd.get_context().get_stage() != self.stage:
            self.close()
            print('[Arm Probe] CANCELLED: Stage changed.')
            return
        session = getattr(builtins, '_warehouse_runtime_bootstrap_session', None)
        handle = getattr(session, '_cart_handle', None)
        gesture = getattr(handle, 'gesture', None)
        now = self.timeline.get_current_time()
        if not ready_to_sample(gesture, now, self.timeline.is_playing()):
            return
        # One shot, including errors: do not spam or modify the motion runtime.
        self.close()
        try:
            report = collect(gesture, handle.transfer, now)
            report['stage'] = self.stage.GetRootLayer().identifier
            stamp = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d_%H%M%S_%f')
            report['captured_at_kst'] = stamp
            directory = PROJECT / 'artifacts' / 'runs' / ('worker_arm_runtime_' + stamp)
            directory.mkdir(parents=True, exist_ok=False)
            destination = directory / 'arm_runtime.json'
            destination.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False),
                                   encoding='utf-8')
            print('WORKER_ARM_RUNTIME_REPORT=' + str(destination))
            print('WORKER_ARM_RUNTIME_SUMMARY=' + json.dumps({
                'box_z': report['box_center'][2] if report['box_center'] else None,
                'targets': report['targets'], 'weight': report['weight'],
                'joints': report['joints']}, ensure_ascii=False, allow_nan=False))
        except Exception as error:
            print(f'[Arm Probe] FAILED: {error}; no motion settings changed.')


def run():
    import omni.kit.app
    import omni.timeline
    import omni.usd
    stage = omni.usd.get_context().get_stage()
    if stage is None or Path(stage.GetRootLayer().realPath).resolve() != EXPECTED_STAGE.resolve():
        raise RuntimeError('Open warehouse_cart_worker.usd first')
    previous = getattr(builtins, PROBE_NAME, None)
    if previous is not None:
        previous.close()
    probe = RuntimeProbe(stage, omni.timeline.get_timeline_interface())
    probe.subscription = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        probe.update, name='WarehouseArmRuntimeProbe')
    setattr(builtins, PROBE_NAME, probe)
    print('[Arm Probe] ARMED: waiting for active reach +0.25s. Press Play manually; no Pause needed.')
    return probe


if __name__ == '__main__':
    probe = run()
