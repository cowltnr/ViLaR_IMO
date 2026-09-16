"""Open/Run in Isaac Sim Script Editor while STOPPED. Inspection, NOT motion.

Reads the already loaded Stage and NavMesh; writes one new JSON report only.
Does not install callbacks, configure People, alter USD, Bake, save, or Play.
"""

import importlib
import json
from pathlib import Path
import sys

PROJECT = Path('/home/cowltnr/PycharmProjects/SDV_Robocar')
EXPECTED_STAGE = Path('/home/cowltnr/LimoIsaacSIM/USD/cart_simulation_env/warehouse_cart_worker.usd')


def run():
    import omni.timeline
    import omni.usd
    if not omni.timeline.get_timeline_interface().is_stopped():
        raise RuntimeError('Press Stop before multi-box inspection')
    stage = omni.usd.get_context().get_stage()
    if stage is None or Path(stage.GetRootLayer().realPath).resolve() != EXPECTED_STAGE.resolve():
        raise RuntimeError('Open the expected warehouse_cart_worker.usd before inspection')
    if str(PROJECT) not in sys.path:
        sys.path.insert(0, str(PROJECT))
    importlib.invalidate_caches()
    from scripts import warehouse_multi_box_config as config
    from scripts import warehouse_multi_box_inspection as inspection
    from scripts import warehouse_composite_support as composite_support
    importlib.reload(config)
    importlib.reload(inspection)
    # Script Editor can retain an older module object across repeated runs.
    # Reload the converter as well as the inspector so the verified-lid API and
    # geometry logic always match the current source file.
    importlib.reload(composite_support)
    # Capture the existing layer text to detect accidental edits by this inspector.
    layers_before = {layer.identifier: layer.ExportToString() for layer in stage.GetLayerStack()}
    report = inspection.inspect_stage(stage, config.BOX_PATHS, config.PALLET_PATH,
                                      config.WORKER_PATH, config.WAREHOUSE_PATH)
    report['configuration'] = {name: getattr(config, name) for name in dir(config) if name.isupper()}
    try:
        report['lid_meshes'] = inspection.collect_lid_meshes(stage, config.PALLET_PATH)
        report['lid_surface_candidates'] = [
            {'surface_id': s.surface_id, 'lower': s.lower, 'upper': s.upper,
             'z_min': s.z_min, 'z_max': s.z_max, 'verified': s.verified}
            for s in composite_support.lid_surfaces_from_mesh_report(
                report['lid_meshes'], verified_ids=config.COMPOSITE_VERIFIED_LID_PATHS)]
    except Exception as error:
        report['lid_meshes'] = []
        report['lid_surface_candidates'] = []
        report['lid_mesh_error'] = str(error)
    try:
        import carb
        import omni.anim.navigation.core as nav
        interface = nav.acquire_interface()
        mesh = interface.get_navmesh()
        if mesh is None:
            raise RuntimeError('No existing NavMesh; inspector will not Bake')
        def closest(point):
            p = mesh.query_closest_point(carb.Float3(*point))
            return tuple(float(p[i]) for i in range(3)) if p is not None else None
        def path(start, end):
            route = mesh.query_shortest_path(start_pos=carb.Float3(*start), end_pos=carb.Float3(*end))
            return [tuple(float(p[i]) for i in range(3)) for p in route.get_points()] if route is not None else []
        report['navmesh'] = inspection.probe_navmesh(report, closest, path, config.PROBE_DISTANCES_M,
                                                    config.PROBE_ANGLES_DEG, config.MAX_NAVMESH_SNAP_M)
        report['source_approaches'] = inspection.select_source_approaches(report['navmesh'])
        report['navmesh']['triangle_count'] = sum(len(mesh.get_draw_triangles(i)) // 3
                                                 for i in range(interface.get_area_count()))
    except Exception as error:
        report['navmesh'] = {'status': 'unavailable', 'error': str(error), 'motion_ready': False}
        report['source_approaches'] = []
    try:
        # Constructor reads skeleton/graph only; deliberately never call install/start.
        from scripts.warehouse_worker_reach_gesture import ReachGesture
        gesture = ReachGesture(stage, config.WORKER_PATH, reach=2, hold=8, lower=2, distance=.4)
        report['arms'] = {'source': 'authored_bind_pose_not_runtime',
                          'shoulders_local': gesture.shoulders, 'arm_lengths_m': gesture.arm_lengths}
    except Exception as error:
        report['arms'] = {'error': str(error), 'source': 'unavailable'}
    try:
        from pxr import Usd, UsdGeom
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
            [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy])
        report['cart'], _ = inspection._object(stage, config.CART_PATH, cache)
        report['cart_geometry'] = []
        cart = stage.GetPrimAtPath(config.CART_PATH)
        for prim in Usd.PrimRange(cart, Usd.TraverseInstanceProxies()):
            if prim.IsA(UsdGeom.Boundable):
                try:
                    report['cart_geometry'].append({'path': str(prim.GetPath()),
                        'world_bounds': inspection._bounds_dict(cache.ComputeWorldBound(prim).ComputeAlignedRange())})
                except ValueError:
                    pass
    except Exception as error:
        report['cart_error'] = str(error)
    layers_after = {layer.identifier: layer.ExportToString() for layer in stage.GetLayerStack()}
    report['stage_modified'] = layers_before != layers_after
    if report['stage_modified']:
        report['geometry_errors'].append('stage_changed_during_inspection_do_not_restore_user_edits')
    destination = inspection.save_report(report, PROJECT / 'artifacts' / 'runs')
    print('WAREHOUSE_MULTI_BOX_REPORT=' + str(destination))
    print('WAREHOUSE_MULTI_BOX_SUMMARY=' + json.dumps({
        'box_count': len(report['boxes']), 'geometry_errors': report['geometry_errors'],
        'lid_mesh_count': len(report['lid_meshes']),
        'lid_surface_candidate_count': len(report['lid_surface_candidates']),
        'lid_mesh_errors': [m['path'] for m in report['lid_meshes'] if m.get('error')],
        'boxes': [{'path': b['path'], 'rack_candidates': b['rack_candidates'], 'issues': b['issues']}
                  for b in report['boxes']],
        'navmesh_status': report['navmesh']['status'], 'stage_modified': report['stage_modified'],
        'source_approach_count': len([x for x in report.get('source_approaches', [])
                                      if x.get('status') == 'connected_probe_selected']),
        'motion_ready': False}, ensure_ascii=False))
    print('[Multi-box Inspection] Report only. No Play, Bake, Save, or motion configured.')
    return report


if __name__ == '__main__':
    report = run()
