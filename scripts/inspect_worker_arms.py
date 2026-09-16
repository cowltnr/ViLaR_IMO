"""Open/Run in Isaac Sim Script Editor while stopped. Read Stage; save JSON only."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT = Path('/home/cowltnr/PycharmProjects/SDV_Robocar')
WORKER = '/World/Characters/Worker_01'
EXPECTED_STAGE = Path('/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd')


def arm_joint_indices(joints):
    words = ('shoulder', 'clavicle', 'upperarm', 'forearm', 'arm', 'elbow', 'wrist', 'hand')
    return [i for i, name in enumerate(joints)
            if any(word in str(name).rsplit('/', 1)[-1].lower() for word in words)]


def inspect_stage(stage):
    from pxr import Usd, UsdGeom, UsdSkel
    worker = stage.GetPrimAtPath(WORKER)
    if not worker or not worker.IsValid():
        raise RuntimeError(f'Worker missing: {WORKER}')
    report = {'stage': stage.GetRootLayer().identifier,
              'meters_per_unit': UsdGeom.GetStageMetersPerUnit(stage),
              'up_axis': str(UsdGeom.GetStageUpAxis(stage)),
              'skeletons': [], 'graphs': [], 'objects': {},
              'stage_modified': False, 'pose_source': 'authored bind/rest, not runtime pose'}
    graph_paths = set()
    for prim in Usd.PrimRange(worker):
        relation = prim.GetRelationship('animationGraph')
        if relation:
            graph_paths.update(str(p) for p in relation.GetTargets())
        if not prim.IsA(UsdSkel.Skeleton):
            continue
        skeleton = UsdSkel.Skeleton(prim)
        joints = [str(j) for j in (skeleton.GetJointsAttr().Get() or [])]
        binds = skeleton.GetBindTransformsAttr().Get()
        rests = skeleton.GetRestTransformsAttr().Get()
        world = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        selected = arm_joint_indices(joints)
        arms = []
        for i in selected:
            entry = {'index': i, 'joint': joints[i]}
            if binds is not None and i < len(binds):
                entry['bind_world_position'] = list((binds[i] * world).ExtractTranslation())
            if rests is not None and i < len(rests):
                entry['rest_local_matrix'] = [[float(rests[i][r][c]) for c in range(4)] for r in range(4)]
            arms.append(entry)
        report['skeletons'].append({'path': str(prim.GetPath()), 'joints': joints,
                                    'arm_joints': arms,
                                    'bind_transform_count': len(binds) if binds is not None else 0,
                                    'rest_transform_count': len(rests) if rests is not None else 0})
    for path in sorted(graph_paths):
        graph = stage.GetPrimAtPath(path)
        nodes = []
        if graph:
            for prim in Usd.PrimRange(graph):
                nodes.append({'path': str(prim.GetPath()), 'type': prim.GetTypeName(),
                              'relationships': {r.GetName(): [str(p) for p in r.GetTargets()]
                                                for r in prim.GetRelationships()},
                              'inputs': {a.GetName(): str(a.Get()) for a in prim.GetAttributes()
                                         if a.GetName().startswith(('inputs:', 'variable'))}})
        report['graphs'].append({'path': path, 'valid': bool(graph), 'nodes': nodes})
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                              [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
    for path in (WORKER, '/World/DynamicActors/CartAssembly',
                 '/World/Environment/Warehouse/Box_24138/SM_CardBoxD_01',
                 '/World/DynamicActors/CartAssembly/o3dyn_pallet_upper'):
        prim = stage.GetPrimAtPath(path)
        if prim:
            bounds = cache.ComputeWorldBound(prim).ComputeAlignedRange()
            report['objects'][path] = {'world_position': list(UsdGeom.Xformable(prim)
                .ComputeLocalToWorldTransform(Usd.TimeCode.Default()).ExtractTranslation()),
                'bounds': None if bounds.IsEmpty() else
                {'min': list(bounds.GetMin()), 'max': list(bounds.GetMax())}}
    if not report['skeletons']:
        report['warning'] = 'No loaded Skeleton found; do not infer joint names.'
    return report


def run():
    import omni.timeline
    import omni.usd
    if not omni.timeline.get_timeline_interface().is_stopped():
        raise RuntimeError('Press Stop before inspecting Worker arms')
    stage = omni.usd.get_context().get_stage()
    if stage is None or Path(stage.GetRootLayer().realPath).resolve() != EXPECTED_STAGE.resolve():
        raise RuntimeError('Open warehouse_cart_worker.usd before running this inspector')
    report = inspect_stage(stage)
    stamp = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d_%H%M%S_%f')
    report['inspected_at_kst'] = stamp
    directory = PROJECT / 'artifacts' / 'runs' / f'worker_arms_inspection_{stamp}'
    directory.mkdir(parents=True, exist_ok=False)
    destination = directory / 'worker_arms.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('WORKER_ARMS_REPORT=' + str(destination))
    print('WORKER_ARMS_SUMMARY=' + json.dumps({
        'skeleton_count': len(report['skeletons']),
        'arm_joint_count': sum(len(s['arm_joints']) for s in report['skeletons']),
        'graph_count': len(report['graphs']), 'stage_modified': False}))
    return report


if __name__ == '__main__':
    report = run()
