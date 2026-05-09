# -*- coding: utf-8 -*-
"""ResearchExperienceLibrary 回归测试。"""

import tempfile
from pathlib import Path

from src.core.research_experience_library import (
    ExperienceQuery,
    ResearchExperienceLibrary,
)


class MockPhoenixContext:
    red_attack_types = ["confounding", "causal_overclaim"]
    score_history = [6.1, 6.4]


def make_library():
    temp_dir = tempfile.TemporaryDirectory()
    path = Path(temp_dir.name) / "experience.jsonl"
    return temp_dir, ResearchExperienceLibrary(path)


def test_save_load_and_deduplicate():
    temp_dir, library = make_library()
    try:
        exp = library._build_experience(
            partition="warning",
            task_id="task-1",
            run_type="test",
            domain="biomedicine",
            topic="Alzheimer causal biomarker",
            tags=["confounding"],
            trigger="defense_failed",
            lesson_summary="混杂控制不足导致防御失败",
            forbidden_patterns=["缺少混杂变量控制"],
            recommended_directions=["加入 DAG 和敏感性分析"],
            evidence={"score_history": [6.0]},
            confidence=0.8,
        )
        assert library.save_many([exp, exp]) == 1
        loaded = library.load_all()
        assert len(loaded) == 1
        assert loaded[0].lesson_summary == "混杂控制不足导致防御失败"
    finally:
        temp_dir.cleanup()


def test_retrieve_and_prompt_guard():
    temp_dir, library = make_library()
    try:
        warning = library._build_experience(
            partition="warning",
            task_id="task-1",
            run_type="test",
            domain="biomedicine",
            topic="Alzheimer causal biomarker",
            tags=["confounding"],
            trigger="red_team_failed",
            lesson_summary="红队指出因果过度声称",
            forbidden_patterns=["只描述相关性但声称因果"],
            recommended_directions=["加入负对照和 E-value"],
            evidence={},
            confidence=0.8,
        )
        other = library._build_experience(
            partition="golden",
            task_id="task-2",
            run_type="test",
            domain="chemistry",
            topic="retrosynthesis",
            tags=["synthesis"],
            trigger="success",
            lesson_summary="逆合成策略成功",
            forbidden_patterns=[],
            recommended_directions=["保持反应中心约束"],
            evidence={},
            confidence=0.9,
        )
        library.save_many([warning, other])
        result = library.retrieve(
            ExperienceQuery(
                topic="Alzheimer biomarker causal inference",
                domain="biomedicine",
                tags=["confounding"],
                limit=1,
            )
        )
        assert len(result.experiences) == 1
        assert result.experiences[0].domain == "biomedicine"
        assert "不得降低" in result.prompt_suffix
        assert "历史科研经验参考" in result.prompt_suffix
    finally:
        temp_dir.cleanup()


def test_extract_from_red_team_failed():
    temp_dir, library = make_library()
    try:
        red_team_result = {
            "attack_report": {
                "verdict": "failed",
                "critical_flaws": ["缺少混杂控制，无法支持因果结论"],
                "severe_issues": ["未说明多重检验校正"],
                "attack_vectors": ["confounding", "multiple_testing"],
            }
        }
        experiences = library.extract_from_red_team(
            "task-1",
            "biomedicine",
            "Alzheimer biomarker",
            1,
            red_team_result,
            MockPhoenixContext(),
        )
        assert len(experiences) == 1
        assert experiences[0].partition == "warning"
        assert "confounding" in experiences[0].tags
        assert experiences[0].forbidden_patterns
    finally:
        temp_dir.cleanup()


def test_extract_from_defense_success_and_failure():
    temp_dir, library = make_library()
    try:
        failed = library.extract_from_defense(
            "task-1",
            "biomedicine",
            "Alzheimer biomarker",
            1,
            {"defense_passed": False, "critical_issues": ["统计功效不足"]},
            {"attack_report": {"attack_vectors": ["power"]}},
            MockPhoenixContext(),
        )
        passed = library.extract_from_defense(
            "task-1",
            "biomedicine",
            "Alzheimer biomarker",
            2,
            {"defense_passed": True, "recommendations": ["保持 E-value 敏感性分析"]},
            {"attack_report": {"attack_vectors": ["power"]}},
            MockPhoenixContext(),
        )
        assert failed[0].partition == "warning"
        assert passed[0].partition == "golden"
    finally:
        temp_dir.cleanup()


def test_infra_failure_is_not_persisted():
    temp_dir, library = make_library()
    try:
        red_team_result = {
            "attack_report": {
                "verdict": "failed",
                "critical_flaws": ["API timeout while calling model"],
                "attack_vectors": ["infra"],
            }
        }
        experiences = library.extract_from_red_team(
            "task-1",
            "biomedicine",
            "Alzheimer biomarker",
            1,
            red_team_result,
            MockPhoenixContext(),
        )
        assert experiences == []
    finally:
        temp_dir.cleanup()


if __name__ == "__main__":
    test_save_load_and_deduplicate()
    test_retrieve_and_prompt_guard()
    test_extract_from_red_team_failed()
    test_extract_from_defense_success_and_failure()
    test_infra_failure_is_not_persisted()
    print("PASS: ResearchExperienceLibrary tests passed")
