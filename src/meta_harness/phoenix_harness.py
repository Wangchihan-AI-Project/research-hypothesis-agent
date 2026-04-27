from __future__ import annotations

import copy
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List

from src.core.report_generator import generate_phoenix_report


ENHANCED_KEYS = (
    "implementation_roadmap",
    "innovation_analysis",
    "frontier_analysis",
)

KEY_ALIASES = {
    "frontier_analysis": "frontier",
    "implementation_roadmap": "roadmap",
    "innovation_analysis": "innovation",
}

NAME_KEY_ORDER = (
    "frontier_analysis",
    "implementation_roadmap",
    "innovation_analysis",
)

DEFAULT_CANDIDATE_ORDER = (
    "full_enhanced",
    "current_baseline",
    "render_only",
    "frontier_only",
    "roadmap_only",
    "innovation_only",
    "frontier_roadmap",
    "roadmap_innovation",
)


@dataclass
class PhoenixCandidate:
    name: str
    config: Dict[str, Any]


class PhoenixHarness:
    """Phoenix 最小 Harness：基于现有快照结果做统一包装与报告生成。"""

    def __init__(self, project_root: str | Path, candidate: Dict[str, Any]):
        self.project_root = Path(project_root)
        self.candidate = PhoenixCandidate(
            name=candidate["name"],
            config=copy.deepcopy(candidate.get("config", {})),
        )

    def run(self, task_input: Dict[str, Any]) -> Dict[str, Any]:
        raw_result = copy.deepcopy(task_input["task_result"])
        payload = copy.deepcopy(raw_result.get("payload", {}))

        payload = self._apply_candidate(payload, task_input)

        task_result_for_report = {
            "task_id": raw_result.get("task_id", task_input["task_id"]),
            "state": raw_result.get("state", "success"),
            "duration": raw_result.get("duration", 0),
            "payload": payload,
        }

        report_path = generate_phoenix_report(task_result_for_report, task_input.get("user_input", ""))
        report_text = Path(report_path).read_text(encoding="utf-8") if Path(report_path).exists() else ""

        return {
            "candidate": self.candidate.name,
            "task_id": task_input["task_id"],
            "task_name": task_input.get("task_name", task_input["task_id"]),
            "payload": payload,
            "report_path": report_path,
            "report_text": report_text,
            "stage_outputs": payload.get("stage_outputs", []),
            "stage_index_path": payload.get("stage_index_path", ""),
            "metadata": {
                "source_file": task_input.get("source_file", ""),
                "field": task_input.get("field", ""),
                "candidate_config": copy.deepcopy(self.candidate.config),
            },
        }

    def _apply_candidate(self, payload: Dict[str, Any], task_input: Dict[str, Any]) -> Dict[str, Any]:
        merged = copy.deepcopy(payload)
        enhanced = task_input.get("enhanced_output", {}) or {}

        for key in self.candidate.config.get("include_enhanced_keys", []):
            if key in enhanced:
                merged[key] = copy.deepcopy(enhanced[key])

        if self.candidate.config.get("ensure_stage_index") and merged.get("stage_outputs") and not merged.get("stage_index_path"):
            merged["stage_index_path"] = "generated-in-original-run"

        return merged


def _candidate_name_for_keys(include_enhanced_keys: List[str]) -> str:
    ordered_keys = [key for key in NAME_KEY_ORDER if key in include_enhanced_keys]
    if not ordered_keys:
        return "current_baseline"
    if len(ordered_keys) == len(ENHANCED_KEYS):
        return "full_enhanced"
    if len(ordered_keys) == 1:
        return f"{KEY_ALIASES[ordered_keys[0]]}_only"
    return "_".join(KEY_ALIASES[key] for key in ordered_keys)


def build_candidate(
    name: str,
    include_enhanced_keys: List[str] | None = None,
    ensure_stage_index: bool = False,
    is_default_baseline: bool = False,
) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    ordered_keys = [key for key in ENHANCED_KEYS if include_enhanced_keys and key in include_enhanced_keys]
    if ordered_keys:
        config["include_enhanced_keys"] = ordered_keys
    if ensure_stage_index:
        config["ensure_stage_index"] = True
    if is_default_baseline:
        config["is_default_baseline"] = True
    return {
        "name": name,
        "config": config,
    }


def build_candidate_search_space(include_render_only: bool = True) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []

    candidates.append(build_candidate("full_enhanced", list(ENHANCED_KEYS), ensure_stage_index=True, is_default_baseline=True))
    candidates.append(build_candidate("current_baseline"))
    if include_render_only:
        candidates.append(build_candidate("render_only"))

    for size in range(1, len(ENHANCED_KEYS) + 1):
        for combo in combinations(ENHANCED_KEYS, size):
            name = _candidate_name_for_keys(list(combo))
            if name == "full_enhanced":
                continue
            candidates.append(build_candidate(name, list(combo)))

    unique_candidates: List[Dict[str, Any]] = []
    seen_names = set()
    for candidate in candidates:
        name = candidate["name"]
        if name in seen_names:
            continue
        seen_names.add(name)
        unique_candidates.append(candidate)
    return unique_candidates


def build_default_candidates() -> List[Dict[str, Any]]:
    candidate_map = {candidate["name"]: candidate for candidate in build_candidate_search_space(include_render_only=True)}
    return [candidate_map[name] for name in DEFAULT_CANDIDATE_ORDER if name in candidate_map]
