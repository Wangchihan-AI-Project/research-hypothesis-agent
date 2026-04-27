from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class EvalTask:
    task_id: str
    task_name: str
    field: str
    user_input: str
    task_result: Dict[str, Any]
    source_file: str
    enhanced_output: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "field": self.field,
            "user_input": self.user_input,
            "task_result": self.task_result,
            "source_file": self.source_file,
            "enhanced_output": self.enhanced_output,
        }


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MULTIFIELD_PATH = PROJECT_ROOT / "multifield_final.json"
ENHANCED_OUTPUT_PATH = PROJECT_ROOT / "enhanced_full_output_demo.json"
REAL_SAMPLE_PATH = PROJECT_ROOT / "meta_harness_real_sample.json"
V2_TASKS_DIR = PROJECT_ROOT / "data" / "meta_harness_v2"


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_enhanced_output() -> Dict[str, Any]:
    if not ENHANCED_OUTPUT_PATH.exists():
        return {}
    data = _load_json(ENHANCED_OUTPUT_PATH)
    return {
        "implementation_roadmap": data.get("implementation_roadmap", {}),
        "innovation_analysis": data.get("innovation_analysis", {}),
        "frontier_analysis": data.get("frontier_analysis", {}),
    }


def _build_eval_task_from_result(result: Dict[str, Any], source_file: Path, enhanced_output: Dict[str, Any] | None = None) -> EvalTask:
    payload = result.get("payload", {}) if isinstance(result, dict) else {}
    hypothesis = payload.get("hypothesis", {}) if isinstance(payload, dict) else {}
    task_id = result.get("task_id") or source_file.stem
    field = payload.get("domain") or result.get("field") or source_file.parent.name
    user_input = hypothesis.get("title") or result.get("user_input") or task_id
    task_name = result.get("task_name") or f"{field}-{str(task_id)[:8]}"
    return EvalTask(
        task_id=task_id,
        task_name=task_name,
        field=field,
        user_input=user_input,
        task_result=result,
        source_file=str(source_file),
        enhanced_output=enhanced_output or {},
    )


def _load_multifield_tasks() -> List[EvalTask]:
    raw = _load_json(MULTIFIELD_PATH)
    enhanced = _load_enhanced_output()
    tasks: List[EvalTask] = []

    for item in raw:
        field = item.get("field", "unknown")
        data = item.get("data", {})
        result = data.get("result", {})
        task_id = result.get("task_id") or data.get("task_id") or field
        payload = result.get("payload", {})
        user_input = data.get("input") or data.get("user_input") or payload.get("hypothesis", {}).get("title", "")
        tasks.append(
            EvalTask(
                task_id=task_id,
                task_name=f"{field}-{task_id[:8]}",
                field=field,
                user_input=user_input,
                task_result=result,
                source_file=str(MULTIFIELD_PATH),
                enhanced_output=enhanced,
            )
        )

    return tasks


def _load_real_sample_task() -> List[EvalTask]:
    if not REAL_SAMPLE_PATH.exists():
        return []

    result = _load_json(REAL_SAMPLE_PATH)
    payload = result.get("payload", {})
    hypothesis = payload.get("hypothesis", {})
    user_input = hypothesis.get("title", result.get("task_id", "real-sample"))

    return [
        EvalTask(
            task_id=result.get("task_id", "meta-harness-real-sample"),
            task_name="real-defense-stage-sample",
            field=payload.get("domain", "real-sample"),
            user_input=user_input,
            task_result=result,
            source_file=str(REAL_SAMPLE_PATH),
            enhanced_output={},
        )
    ]


def _load_v2_group(group_name: str) -> List[EvalTask]:
    group_dir = V2_TASKS_DIR / group_name
    if not group_dir.exists():
        return []

    enhanced = _load_enhanced_output()
    tasks: List[EvalTask] = []
    for path in sorted(group_dir.glob("*.json")):
        result = _load_json(path)
        if not isinstance(result, dict):
            continue
        include_enhanced = result.pop("include_enhanced_output", False)
        include_enhanced_keys = result.pop("include_enhanced_keys", [])
        selected_enhanced: Dict[str, Any] = {}
        if include_enhanced:
            if include_enhanced_keys:
                selected_enhanced = {
                    key: enhanced[key]
                    for key in include_enhanced_keys
                    if key in enhanced
                }
            else:
                selected_enhanced = enhanced
        tasks.append(
            _build_eval_task_from_result(
                result=result,
                source_file=path,
                enhanced_output=selected_enhanced,
            )
        )
    return tasks


def _slice_or_all(tasks: List[EvalTask], count: int) -> List[EvalTask]:
    return tasks[:count] if len(tasks) >= count else tasks


def _build_v2_frontier_sensitive(multifield_tasks: List[EvalTask], real_sample_tasks: List[EvalTask]) -> List[EvalTask]:
    loaded = _load_v2_group("frontier_sensitive")
    if loaded:
        return loaded
    return _slice_or_all(multifield_tasks, 2)


def _build_v2_roadmap_sensitive(multifield_tasks: List[EvalTask], real_sample_tasks: List[EvalTask]) -> List[EvalTask]:
    loaded = _load_v2_group("roadmap_sensitive")
    if loaded:
        return loaded
    return _slice_or_all(multifield_tasks[2:], 2)


def _build_v2_innovation_sensitive(multifield_tasks: List[EvalTask], real_sample_tasks: List[EvalTask]) -> List[EvalTask]:
    loaded = _load_v2_group("innovation_sensitive")
    if loaded:
        return loaded
    candidates = _slice_or_all(multifield_tasks[4:], 1)
    if real_sample_tasks:
        candidates = candidates + real_sample_tasks[:1]
    return candidates


def _build_v2_mixed_sensitive(multifield_tasks: List[EvalTask], real_sample_tasks: List[EvalTask]) -> List[EvalTask]:
    mixed_loaded = _load_v2_group("mixed_sensitive")
    if mixed_loaded:
        return mixed_loaded
    return (
        _build_v2_frontier_sensitive(multifield_tasks, real_sample_tasks)
        + _build_v2_roadmap_sensitive(multifield_tasks, real_sample_tasks)
        + _build_v2_innovation_sensitive(multifield_tasks, real_sample_tasks)
    )


def load_task_set(name: str) -> List[Dict[str, Any]]:
    multifield_tasks = _load_multifield_tasks()
    real_sample_tasks = _load_real_sample_task()
    task_sets = {
        "baseline_smoke": multifield_tasks[:1],
        "search_set_small": multifield_tasks[:2],
        "heldout_small": multifield_tasks[2:3],
        "defense_stage_sample": real_sample_tasks,
        "search_set_plus_defense": multifield_tasks[:2] + real_sample_tasks,
        "multifield_full": multifield_tasks,
        "multifield_plus_defense": multifield_tasks + real_sample_tasks,
        "heldout_plus_defense": multifield_tasks[2:] + real_sample_tasks,
        "v2_frontier_sensitive": _build_v2_frontier_sensitive(multifield_tasks, real_sample_tasks),
        "v2_roadmap_sensitive": _build_v2_roadmap_sensitive(multifield_tasks, real_sample_tasks),
        "v2_innovation_sensitive": _build_v2_innovation_sensitive(multifield_tasks, real_sample_tasks),
        "v2_mixed_sensitive": _build_v2_mixed_sensitive(multifield_tasks, real_sample_tasks),
    }

    if name not in task_sets:
        raise ValueError(f"Unknown task set: {name}")
    return [task.to_dict() for task in task_sets[name]]
