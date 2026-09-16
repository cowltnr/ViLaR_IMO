"""Read composed Stage geometry without editing layers or runtime state.

Rack AABBs are candidates, not proof of a support face or clear extraction path.
World AABBs transformed to pallet local space deliberately overestimate sizes.
"""

from itertools import product
import math


def _point(value):
    if value is None:
        return None
    value = tuple(value)
    return value if len(value) == 3 and all(math.isfinite(v) for v in value) else None


def collect_lid_meshes(stage, pallet_path):
    """Export actual mesh topology for support analysis, never infer it from bbox."""
    from pxr import Usd, UsdGeom
    pallet = stage.GetPrimAtPath(pallet_path)
    if not pallet:
        raise ValueError('Pallet missing: ' + pallet_path)
    result = []
    for prim in Usd.PrimRange(pallet, Usd.TraverseInstanceProxies()):
        relative_path = str(prim.GetPath())[len(str(pallet.GetPath())) + 1:]
        if not prim.IsA(UsdGeom.Mesh) or 'lid' not in relative_path.lower():
            continue
        mesh = UsdGeom.Mesh(prim)
        entry = {'path': str(prim.GetPath()), 'support_verified': False,
                 'visibility': str(mesh.ComputeVisibility()),
                 'subdivision_scheme': str(mesh.GetSubdivisionSchemeAttr().Get())}
        points = mesh.GetPointsAttr().Get()
        counts = mesh.GetFaceVertexCountsAttr().Get()
        indices = mesh.GetFaceVertexIndicesAttr().Get()
        if (points is None or counts is None or indices is None
                or not len(points) or not len(counts)
                or sum(counts) != len(indices) or any(n < 3 for n in counts)
                or any(i < 0 or i >= len(points) for i in indices)
                or any(not math.isfinite(v) for p in points for v in p)):
            entry['error'] = 'missing_or_invalid_mesh_topology'
        else:
            matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            entry.update(points_local=[list(p) for p in points],
                         face_vertex_counts=list(counts), face_vertex_indices=list(indices),
                         hole_indices=list(mesh.GetHoleIndicesAttr().Get() or []),
                         orientation=str(mesh.GetOrientationAttr().Get()),
                         world_matrix=[list(row) for row in matrix])
        result.append(entry)
    return result


def probe_navmesh(report, closest, query_path, distances, angles, max_snap):
    """Read candidate connectivity only; does not authorize collision-free motion."""
    from scripts.configure_warehouse_worker_behavior import validate_destination_path
    result = {'status': 'queried_not_motion_validated', 'boxes': [], 'motion_ready': False}
    start = _point(report['worker_authored_position'])
    snapped = _point(closest(start)) if start is not None else None
    if snapped is None or math.dist(start, snapped) > max_snap:
        result['status'] = 'worker_outside_snap_tolerance'
        return result
    result['worker_closest_point'] = snapped
    for box in report['boxes']:
        center = _point(box['world_center'])
        entry = {'path': box['path'], 'probes': []}
        if center is not None:
            for distance, angle in product(distances, angles):
                rad = math.radians(angle)
                candidate = (center[0] + distance * math.cos(rad),
                             center[1] + distance * math.sin(rad), start[2])
                goal = _point(closest(candidate))
                item = {'candidate': candidate, 'navmesh_point': goal, 'connected': False}
                if goal is not None:
                    item['snap_distance_m'] = math.dist(candidate, goal)
                    item['box_horizontal_distance_m'] = math.dist(goal[:2], center[:2])
                    if item['snap_distance_m'] <= max_snap:
                        points = list(query_path(snapped, goal) or [])
                        if points and all(_point(p) is not None for p in points):
                            try:
                                validate_destination_path(points, snapped, goal)
                                item.update(connected=True, path_points=points)
                            except RuntimeError:
                                pass
                entry['probes'].append(item)
        result['boxes'].append(entry)
    return result


def select_source_approaches(navmesh_report):
    """Select deterministic connected approach points for source inspection.

    This only selects an already queried NavMesh probe. It does not certify
    extraction clearance, arm reach, collision-free carrying, or rack support.
    """
    selected = []
    for box in navmesh_report.get('boxes', []):
        connected = [probe for probe in box.get('probes', []) if probe.get('connected')]
        if not connected:
            selected.append({'path': box.get('path'), 'status': 'no_connected_probe'})
            continue
        best = min(connected, key=lambda probe: (
            float(probe.get('box_horizontal_distance_m', float('inf'))),
            float(probe.get('snap_distance_m', float('inf'))),
            tuple(probe.get('navmesh_point') or (float('inf'),) * 3)))
        selected.append({
            'path': box.get('path'),
            'status': 'connected_probe_selected',
            'candidate': best.get('candidate'),
            'navmesh_point': best.get('navmesh_point'),
            'snap_distance_m': best.get('snap_distance_m'),
            'box_horizontal_distance_m': best.get('box_horizontal_distance_m'),
            'path_points': best.get('path_points', []),
            'extraction_clearance_validated': False,
            'arm_reach_validated': False,
        })
    return selected


def save_report(report, runs_directory):
    """Only a new JSON artifact is written; no existing artifact is overwritten."""
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from pathlib import Path
    from uuid import uuid4
    stamp = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d_%H%M%S_%f')
    directory = Path(runs_directory) / ('warehouse_multi_box_inspection_' + stamp + '_' + uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False)
    destination = directory / 'scene_report.json'
    data = dict(report, inspected_at_kst=stamp)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return destination


def _bounds_dict(bounds):
    if bounds.IsEmpty():
        raise ValueError('No loaded geometry')
    low, high = tuple(bounds.GetMin()), tuple(bounds.GetMax())
    if not all(math.isfinite(v) for v in (*low, *high)) or any(a >= b for a, b in zip(low, high)):
        raise ValueError('Invalid or zero-volume geometry bounds')
    return {'lower': low, 'upper': high,
            'size': tuple(b - a for a, b in zip(low, high)),
            'center': tuple((a + b) / 2 for a, b in zip(low, high))}


def _rigid(matrix):
    if not all(math.isfinite(matrix[i][j]) for i in range(4) for j in range(4)):
        return False
    if abs(matrix.GetDeterminant() - 1) > 1e-4:
        return False
    if any(abs(sum(matrix[i][k] * matrix[j][k] for k in range(3)) - int(i == j)) > 1e-4
           for i in range(3) for j in range(3)):
        return False
    return True


def _rigid_upright(matrix):
    return _rigid(matrix) and all(abs(matrix[2][i] - int(i == 2)) < 1e-4 for i in range(3))


def _object(stage, path, cache):
    from pxr import Usd, UsdGeom, UsdPhysics
    prim = stage.GetPrimAtPath(path)
    if not prim or not UsdGeom.Xformable(prim):
        raise ValueError('Missing or non-transformable prim: ' + path)
    matrix = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    result = {'path': path, 'world_bounds': _bounds_dict(cache.ComputeWorldBound(prim).ComputeAlignedRange()),
              'world_matrix': tuple(tuple(float(v) for v in row) for row in matrix),
              'rigid_upright': _rigid_upright(matrix), 'rigid_transform': _rigid(matrix), 'issues': []}
    if not result['rigid_transform']:
        result['issues'].append('non_rigid_transform')
    if prim.IsInstanceProxy() or prim.IsInstance():
        result['issues'].append('instanced_target')
    if UsdGeom.Xformable(prim).TransformMightBeTimeVarying():
        result['issues'].append('animated_transform')
    relatives = list(Usd.PrimRange(prim))
    parent = prim.GetParent()
    while parent and not parent.IsPseudoRoot():
        relatives.append(parent)
        parent = parent.GetParent()
    if any(p.HasAPI(UsdPhysics.RigidBodyAPI)
           and UsdPhysics.RigidBodyAPI(p).GetRigidBodyEnabledAttr().Get() is not False for p in relatives):
        result['issues'].append('active_rigid_body')
    return result, matrix


def inspect_stage(stage, box_paths, pallet_path, worker_path, warehouse_path):
    from pxr import Usd, UsdGeom, Gf
    if stage is None:
        raise ValueError('No Stage open')
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
    report = {'stage': stage.GetRootLayer().identifier, 'stage_modified': False,
              'motion_ready': False, 'meters_per_unit': UsdGeom.GetStageMetersPerUnit(stage),
              'up_axis': str(UsdGeom.GetStageUpAxis(stage)), 'geometry_errors': [],
              'boxes': [], 'pallet': None, 'worker_authored_position': None,
              'rack_geometry': [], 'packing_preview': None,
              'unverified': ['rack_support_faces', 'extraction_and_carry_sweeps',
                             'runtime_arm_reach', 'cart_obstacles', 'return_path_at_parked_pose']}
    if report['up_axis'] != 'Z' or abs(report['meters_per_unit'] - 1) > 1e-6:
        report['geometry_errors'].append('requires_meter_Z_up_stage')
    inverse = None
    try:
        pallet, matrix = _object(stage, pallet_path, cache)
        report['pallet'] = pallet
        pallet['local_bounds'] = _bounds_dict(cache.ComputeUntransformedBound(
            stage.GetPrimAtPath(pallet_path)).ComputeAlignedRange())
        if not pallet['rigid_upright']:
            report['geometry_errors'].append('pallet_is_not_rigid_upright')
        elif not report['geometry_errors']:
            inverse = matrix.GetInverse()
    except (ValueError, RuntimeError) as error:
        report['geometry_errors'].append('pallet: ' + str(error))
    worker = stage.GetPrimAtPath(worker_path)
    if worker and UsdGeom.Xformable(worker):
        position = tuple(UsdGeom.Xformable(worker).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()).ExtractTranslation())
        if all(math.isfinite(v) for v in position):
            report['worker_authored_position'] = position
        else:
            report['geometry_errors'].append('nonfinite_worker_pose')
    else:
        report['geometry_errors'].append('worker_missing')
    warehouse = stage.GetPrimAtPath(warehouse_path)
    if not warehouse:
        report['geometry_errors'].append('warehouse_missing')
    else:
        # Group all geometry by outer named rack instance; do not count mesh
        # parents/children/posts as different racks, or discard parent geometry.
        rack_groups = {}
        for prim in Usd.PrimRange(warehouse, Usd.TraverseInstanceProxies()):
            if 'rackshelf' not in str(prim.GetPath()).lower() or not prim.IsA(UsdGeom.Boundable):
                continue
            try:
                bounds = _bounds_dict(cache.ComputeWorldBound(prim).ComputeAlignedRange())
                owner, ancestor = prim, prim
                while ancestor and ancestor != warehouse:
                    if 'rackshelf' in ancestor.GetName().lower():
                        owner = ancestor
                    ancestor = ancestor.GetParent()
                rack_groups.setdefault(str(owner.GetPath()), []).append(bounds)
            except ValueError:
                continue
        for owner, bounds in sorted(rack_groups.items()):
            low = Gf.Vec3d(*(min(b['lower'][i] for b in bounds) for i in range(3)))
            high = Gf.Vec3d(*(max(b['upper'][i] for b in bounds) for i in range(3)))
            report['rack_geometry'].append({'path': owner,
                'world_bounds': _bounds_dict(Gf.Range3d(low, high)),
                'geometry_count': len(bounds), 'grouping': 'outer_named_rack_candidate'})
    for path in box_paths:
        box = {'path': path, 'issues': [], 'world_center': None,
               'pallet_local_center': None, 'pallet_local_bounds': None, 'rack_candidates': []}
        try:
            obj, _ = _object(stage, path, cache)
            box.update(obj)
            bounds = obj['world_bounds']
            box['world_center'] = bounds['center']
            for rack in report['rack_geometry']:
                rb = rack['world_bounds']
                if (all(rb['lower'][i] <= bounds['center'][i] <= rb['upper'][i] for i in (0, 1))
                        and bounds['lower'][2] <= rb['upper'][2]
                        and bounds['upper'][2] >= rb['lower'][2]):
                    box['rack_candidates'].append(rack['path'])
            if len(box['rack_candidates']) != 1:
                box['issues'].append('ambiguous_rack' if box['rack_candidates'] else 'rack_not_found')
            if inverse is not None:
                points = [inverse.Transform(Gf.Vec3d(*p)) for p in product(*zip(bounds['lower'], bounds['upper']))]
                low = tuple(min(p[i] for p in points) for i in range(3))
                high = tuple(max(p[i] for p in points) for i in range(3))
                box['pallet_local_bounds'] = {'lower': low, 'upper': high,
                                              'size': tuple(high[i] - low[i] for i in range(3))}
                box['pallet_local_center'] = tuple((low[i] + high[i]) / 2 for i in range(3))
        except (ValueError, RuntimeError) as error:
            box['issues'].append(str(error))
            report['geometry_errors'].append(path + ': ' + str(error))
        report['boxes'].append(box)
    report['status'] = 'needs_scene_review' if report['geometry_errors'] or any(
        b['issues'] for b in report['boxes']) else 'geometry_collected_not_motion_validated'
    return report
