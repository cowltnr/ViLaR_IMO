"""Offline recorded-geometry comparison; never imports Isaac Sim or edits USD."""
import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from scripts import warehouse_multi_box_config as c
from scripts.warehouse_composite_support import lid_surfaces_from_mesh_report, plan_with_slides, plan_full_load


def run(report_path, output_path):
    raw = report_path.read_bytes()
    r = json.loads(raw)
    surfaces = lid_surfaces_from_mesh_report(r['lid_meshes'],verified_ids=c.COMPOSITE_VERIFIED_LID_PATHS)
    boxes = tuple((b['path'],b['world_bounds']['size']) for b in r['boxes'])
    # Recorded NavMesh probe floor elevation, not an invented runtime shoulder pose.
    floor = r['source_approaches'][0]['navmesh_point'][2]
    limit = floor + min(r['arms']['shoulders_local'][k][2] + r['arms']['arm_lengths_m'][k]*.9*.95
                        for k in ('left','right'))
    policy = dict(max_gap=c.COMPOSITE_MAX_GAP_M,max_height_delta=c.COMPOSITE_MAX_HEIGHT_DELTA_M,
        min_coverage=c.COMPOSITE_MIN_COVERAGE,edge_margin=c.EDGE_MARGIN_M,placement_gap=c.PLACEMENT_GAP_M)
    loaded = ()
    for name,size in boxes:
        plan = plan_with_slides(name,size,surfaces,loaded,
            max_top=limit+size[2]/2-c.LIFT_CLEARANCE_M,
            max_relocations=c.MAX_RELOCATIONS,max_states=c.MAX_SEARCH_STATES,**policy)
        if plan is None:
            break
        loaded = (*plan.relocated,plan.placement)
    full = plan_full_load(boxes,surfaces,max_center_height=limit,
        clearance=c.LIFT_CLEARANCE_M,max_states=c.MAX_SEARCH_STATES,**policy)
    result = dict(validation_level='recorded_geometry',input=str(report_path),
        input_sha256=hashlib.sha256(raw).hexdigest(),
        at=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
        policy=policy,arm_center_limit=limit,baseline_count=len(loaded),
        candidate=asdict(full),live_verified=False,
        limitations=['AABB support heuristic','recorded cart pose only',
                     'no full transport collision check','no runtime arm reach validation'])
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with output_path.open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({'baseline':len(loaded),'candidate':len(full.placements),
                      'complete':full.complete,'report':str(output_path)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('report',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    run(args.report,args.output)
