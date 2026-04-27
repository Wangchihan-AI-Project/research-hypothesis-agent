from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List


class PhoenixEvaluator:
    REQUIRED_SECTIONS = {
        "hypothesis": "【1. Hypothesis",
        "methods": "【2. Methods",
        "lineage": "【3. Lineage",
        "defense": "【4. Defense Log",
        "roadmap": "【5. Roadmap",
        "innovation": "【6. Innovation",
        "scoring": "【评分汇总】",
    }

    def evaluate(self, run_result: Dict[str, Any]) -> Dict[str, Any]:
        payload = run_result.get("payload", {})
        report_text = run_result.get("report_text") or self._read_text(run_result.get("report_path", ""))

        section_checks = {
            name: (marker in report_text)
            for name, marker in self.REQUIRED_SECTIONS.items()
        }
        section_score = self._ratio(sum(section_checks.values()), len(section_checks))

        payload_field_checks = {
            "defense_committee_discussion": bool(self._nested_get(payload, ["defense_report", "committee_discussion"])),
            "defense_attack_responses": bool(self._nested_get(payload, ["defense_report", "attack_responses"])),
            "frontier_key_publications": bool(self._nested_get(payload, ["frontier_analysis", "key_publications"])),
            "frontier_leading_groups": bool(self._nested_get(payload, ["frontier_analysis", "leading_groups"])),
            "roadmap_resources": bool(self._nested_get(payload, ["implementation_roadmap", "resources"])),
            "roadmap_risks": bool(self._nested_get(payload, ["implementation_roadmap", "risks"])),
            "innovation_summary": bool(self._nested_get(payload, ["innovation_analysis", "summary"])),
            "stage_outputs": bool(payload.get("stage_outputs")),
            "stage_index_path": bool(payload.get("stage_index_path")),
        }
        payload_field_score = self._ratio(sum(payload_field_checks.values()), len(payload_field_checks))

        content_checks = {
            "lineage_publications_rendered": "#### 关键出版物" in report_text and "暂无前沿溯源信息" not in report_text,
            "lineage_timeline_rendered": "#### 时间线演进" in report_text,
            "lineage_trends_rendered": "#### 研究趋势" in report_text,
            "defense_committee_rendered": "#### 蓝方答辩" in report_text,
            "defense_attack_response_rendered": "逐项回应" in report_text or "委员会讨论" in report_text,
            "roadmap_rendered": "暂无路线图信息。" not in report_text and "#### 实施阶段" in report_text,
            "innovation_rendered": "暂无创新点分析信息。" not in report_text and "#### 创新总结" in report_text,
            "stage_outputs_visible": bool(run_result.get("stage_outputs")) or bool(run_result.get("stage_index_path")),
        }
        content_score = self._ratio(sum(content_checks.values()), len(content_checks))

        absence_flags = {
            "missing_red_attack_detail": "暂无红方攻击明细。" in report_text,
            "missing_roadmap_content": "暂无路线图信息。" in report_text,
            "missing_innovation_content": "暂无创新点分析信息。" in report_text,
        }

        readability_flags = self._readability_flags(report_text)
        readability_score = self._ratio(4 - len(readability_flags), 4)

        rubric = {
            "defense_quality": self._ratio(
                int(payload_field_checks["defense_committee_discussion"]) +
                int(payload_field_checks["defense_attack_responses"]) +
                int(content_checks["defense_committee_rendered"]) +
                int(content_checks["defense_attack_response_rendered"]) -
                int(absence_flags["missing_red_attack_detail"]),
                4,
            ),
            "lineage_quality": self._ratio(
                int(payload_field_checks["frontier_key_publications"]) +
                int(payload_field_checks["frontier_leading_groups"]) +
                int(content_checks["lineage_publications_rendered"]) +
                int(content_checks["lineage_timeline_rendered"]) +
                int(content_checks["lineage_trends_rendered"]),
                5,
            ),
            "roadmap_quality": self._ratio(
                int(payload_field_checks["roadmap_resources"]) +
                int(payload_field_checks["roadmap_risks"]) +
                int(content_checks["roadmap_rendered"]) -
                int(absence_flags["missing_roadmap_content"]),
                3,
            ),
            "innovation_quality": self._ratio(
                int(payload_field_checks["innovation_summary"]) +
                int(content_checks["innovation_rendered"]) -
                int(absence_flags["missing_innovation_content"]),
                2,
            ),
            "readability": readability_score,
        }

        overall = round(
            (section_score * 0.2)
            + (payload_field_score * 0.25)
            + (content_score * 0.35)
            + (readability_score * 0.2),
            4,
        )

        return {
            "overall": overall,
            "section_score": section_score,
            "payload_field_score": payload_field_score,
            "content_score": content_score,
            "readability_score": readability_score,
            "section_checks": section_checks,
            "payload_field_checks": payload_field_checks,
            "content_checks": content_checks,
            "absence_flags": absence_flags,
            "rubric": rubric,
            "readability_flags": readability_flags,
        }

    def _read_text(self, path: str) -> str:
        if not path:
            return ""
        report_path = Path(path)
        if not report_path.exists():
            return ""
        return report_path.read_text(encoding="utf-8")

    def _nested_get(self, data: Dict[str, Any], path: List[str]) -> Any:
        current: Any = data
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    def _readability_flags(self, report_text: str) -> List[str]:
        flags: List[str] = []
        if "{similarity:.2f}" in report_text:
            flags.append("unformatted_template_placeholder")
        if re.search(r"\[[^\]]*\{[^\]]*\}\]", report_text):
            flags.append("raw_list_or_dict_leak")
        if re.search(r"\{[^\n{}]*:[^\n{}]*\}", report_text):
            flags.append("raw_inline_dict_leak")
        if re.search(r"[：:]\s*\.\.\.|\bvs\. [^\n]{0,120}\.\.\.|\b差异: [^\n]{0,120}\.\.\.", report_text):
            flags.append("truncated_sentence")
        return sorted(set(flags))

    def _ratio(self, numerator: int | float, denominator: int | float) -> float:
        if not denominator:
            return 0.0
        numerator = max(0.0, float(numerator))
        return round(min(1.0, numerator / float(denominator)), 4)
