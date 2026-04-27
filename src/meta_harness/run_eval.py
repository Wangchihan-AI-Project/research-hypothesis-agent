from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.meta_harness.phoenix_harness import DEFAULT_CANDIDATE_ORDER, PhoenixHarness, build_candidate_search_space, build_default_candidates
from src.meta_harness.task_sets import load_task_set
from src.meta_harness.evaluator import PhoenixEvaluator

RUNS_DIR = PROJECT_ROOT / "meta_harness_runs"
V2_SUITES = {
    "v2_axes": [
        "v2_frontier_sensitive",
        "v2_roadmap_sensitive",
        "v2_innovation_sensitive",
    ],
}
RANK_TIER_RULE = {
    "top": "rank == 1",
    "strong": "rank > 1 and strength_tags != ['baseline_level']",
    "baseline": "otherwise",
}
SINGLE_RUN_RANK_TIER_RULE = {
    "top": "rank == 1",
    "strong": "rank > 1 and avg_score > current_baseline.avg_score",
    "baseline": "otherwise",
}


def summarize_candidate_scores(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_candidate: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        by_candidate.setdefault(result["candidate"], []).append(result)

    summary: Dict[str, Dict[str, Any]] = {}
    for candidate, items in by_candidate.items():
        scores = [item.get("metrics", {}).get("overall", 0.0) for item in items]
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        summary[candidate] = {
            "count": len(items),
            "avg_score": avg_score,
        }
    return summary


def _compute_strength_tags(
    axis_scores: Dict[str, float | None],
    axis_baselines: Dict[str, float],
    axis_thresholds: Dict[str, float],
) -> List[str]:
    tags: List[str] = []
    axis_tag_map = {
        "v2_frontier_sensitive": "frontier_strong",
        "v2_roadmap_sensitive": "roadmap_strong",
        "v2_innovation_sensitive": "innovation_strong",
    }
    for axis_name, tag_name in axis_tag_map.items():
        score = axis_scores.get(axis_name)
        baseline = axis_baselines.get(axis_name, 0.0)
        threshold = axis_thresholds.get(axis_name, baseline)
        if isinstance(score, (int, float)) and score >= threshold and score > baseline:
            tags.append(tag_name)
    if not tags:
        tags.append("baseline_level")
    return tags


def _compute_rank_tier(rank: int, strength_tags: List[str]) -> str:
    if rank == 1:
        return "top"
    if any(tag != "baseline_level" for tag in strength_tags):
        return "strong"
    return "baseline"


def _build_decision_summary(overall_ranking: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not overall_ranking:
        return {
            "recommended_default": None,
            "recommended_fallback": None,
            "summary": "No candidates available.",
        }

    recommended_default = overall_ranking[0]
    fallback = next(
        (item for item in overall_ranking[1:] if item.get("rank_tier") == "strong"),
        overall_ranking[1] if len(overall_ranking) > 1 else None,
    )

    default_reason = f"排名第1，跨轴平均 {recommended_default['overall_avg']:.4f}"
    if recommended_default.get("strength_tags"):
        default_reason += f"，强项: {', '.join(recommended_default['strength_tags'])}"

    fallback_reason = None
    if fallback is not None:
        fallback_reason = f"排名第{fallback['rank']}，跨轴平均 {fallback['overall_avg']:.4f}"
        if fallback.get("strength_tags"):
            fallback_reason += f"，强项: {', '.join(fallback['strength_tags'])}"

    summary = f"默认推荐 {recommended_default['candidate']}"
    if fallback is not None:
        summary += f"；备选 {fallback['candidate']}"

    return {
        "recommended_default": {
            "candidate": recommended_default["candidate"],
            "rank": recommended_default["rank"],
            "rank_tier": recommended_default["rank_tier"],
            "overall_avg": recommended_default["overall_avg"],
            "reason": default_reason,
        },
        "recommended_fallback": None
        if fallback is None
        else {
            "candidate": fallback["candidate"],
            "rank": fallback["rank"],
            "rank_tier": fallback["rank_tier"],
            "overall_avg": fallback["overall_avg"],
            "reason": fallback_reason,
        },
        "summary": summary,
    }


def save_suite_summary(
    run_name_prefix: str,
    suite_name: str,
    suite_results: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    suite_dir = ensure_run_dir(run_name_prefix)
    axis_names = V2_SUITES[suite_name]
    axis_summaries = {
        axis_name: summarize_candidate_scores(suite_results.get(axis_name, []))
        for axis_name in axis_names
    }

    candidate_names = sorted(
        {
            candidate_name
            for axis_summary in axis_summaries.values()
            for candidate_name in axis_summary.keys()
        }
    )

    summary_lines = [
        "# Meta-Harness Suite 汇总",
        f"\n运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Suite: {suite_name}",
        f"运行前缀: {run_name_prefix}",
        "\n## Candidate 总表\n",
        "| Tier | Candidate | v2_frontier_sensitive | v2_roadmap_sensitive | v2_innovation_sensitive | 跨轴平均 | 强项标签 |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]

    axis_baselines = {
        axis_name: axis_summaries.get(axis_name, {}).get("current_baseline", {}).get("avg_score", 0.4438)
        for axis_name in axis_names
    }

    axis_thresholds = {}
    axis_strength_metadata = {}
    for axis_name in axis_names:
        baseline = axis_baselines[axis_name]
        axis_scores = [item["avg_score"] for item in axis_summaries.get(axis_name, {}).values()]
        axis_best = max(axis_scores) if axis_scores else baseline
        threshold = round((baseline + axis_best) / 2, 4)
        axis_thresholds[axis_name] = threshold
        axis_strength_metadata[axis_name] = {
            "baseline": baseline,
            "best": axis_best,
            "threshold": threshold,
        }

    candidate_rows: List[Dict[str, Any]] = []
    for candidate_name in candidate_names:
        axis_scores: List[float] = []
        axis_values: List[str] = []
        axis_scores_map: Dict[str, float | None] = {}
        for axis_name in axis_names:
            score = axis_summaries.get(axis_name, {}).get(candidate_name, {}).get("avg_score")
            if isinstance(score, (int, float)):
                numeric_score = round(float(score), 4)
                axis_scores.append(numeric_score)
                axis_values.append(f"{numeric_score:.4f}")
                axis_scores_map[axis_name] = numeric_score
            else:
                axis_values.append("-")
                axis_scores_map[axis_name] = None
        overall_avg = round(sum(axis_scores) / len(axis_scores), 4) if axis_scores else 0.0
        candidate_rows.append(
            {
                "candidate": candidate_name,
                "axis_values": axis_values,
                "axis_scores": axis_scores_map,
                "overall_avg": overall_avg,
            }
        )

    candidate_rows.sort(key=lambda item: (-item["overall_avg"], item["candidate"]))

    for index, row_data in enumerate(candidate_rows):
        rank = index + 1
        strength_tags = _compute_strength_tags(row_data["axis_scores"], axis_baselines, axis_thresholds)
        rank_tier = _compute_rank_tier(rank, strength_tags)
        row = [
            rank_tier,
            row_data["candidate"],
            *row_data["axis_values"],
            f"{row_data['overall_avg']:.4f}",
            ", ".join(strength_tags),
        ]
        summary_lines.append(f"| {' | '.join(row)} |")

    summary_lines.append("\n## 强项标签规则\n")
    summary_lines.append("- method: midpoint_between_baseline_and_best")
    for axis_name in axis_names:
        axis_meta = axis_strength_metadata[axis_name]
        summary_lines.append(
            f"- {axis_name}: baseline={axis_meta['baseline']:.4f}, best={axis_meta['best']:.4f}, threshold={axis_meta['threshold']:.4f}"
        )

    summary_lines.append("\n## 排名分层规则\n")
    summary_lines.append(f"- top: {RANK_TIER_RULE['top']}")
    summary_lines.append("- strong: rank > 1 且 strength_tags 不仅为 baseline_level")
    summary_lines.append(f"- baseline: {RANK_TIER_RULE['baseline']}")

    summary_lines.append("\n## 分轴明细\n")
    for axis_name in axis_names:
        summary_lines.append(f"### {axis_name}\n")
        sorted_candidates = sorted(
            axis_summaries[axis_name].items(),
            key=lambda item: (-item[1]["avg_score"], item[0]),
        )
        for candidate_name, candidate_summary in sorted_candidates:
            summary_lines.append(f"- {candidate_name}: avg={candidate_summary['avg_score']}, count={candidate_summary['count']}")
        summary_lines.append("\n")

    overall_ranking: List[Dict[str, Any]] = []
    for index, row_data in enumerate(candidate_rows):
        rank = index + 1
        strength_tags = _compute_strength_tags(row_data["axis_scores"], axis_baselines, axis_thresholds)
        overall_ranking.append(
            {
                "rank": rank,
                "rank_tier": _compute_rank_tier(rank, strength_tags),
                "candidate": row_data["candidate"],
                "overall_avg": row_data["overall_avg"],
                "axis_scores": row_data["axis_scores"],
                "strength_tags": strength_tags,
            }
        )

    decision_summary = _build_decision_summary(overall_ranking)

    summary_lines.append("\n## 决策摘要\n")
    summary_lines.append(f"- 结论: {decision_summary['summary']}")
    if decision_summary["recommended_default"] is not None:
        summary_lines.append(
            f"- 默认推荐: {decision_summary['recommended_default']['candidate']} ({decision_summary['recommended_default']['reason']})"
        )
    if decision_summary["recommended_fallback"] is not None:
        summary_lines.append(
            f"- 备选: {decision_summary['recommended_fallback']['candidate']} ({decision_summary['recommended_fallback']['reason']})"
        )

    (suite_dir / "SUITE_SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")
    with open(suite_dir / "suite_summary.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_time": datetime.now().isoformat(),
                "suite": suite_name,
                "run_name_prefix": run_name_prefix,
                "axes": axis_names,
                "axis_summaries": axis_summaries,
                "strength_tag_rule": {
                    "method": "midpoint_between_baseline_and_best",
                    "axes": axis_strength_metadata,
                },
                "rank_tier_rule": RANK_TIER_RULE,
                "decision_summary": decision_summary,
                "overall_ranking": overall_ranking,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return decision_summary


def ensure_run_dir(run_name: str) -> Path:
    run_dir = RUNS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_candidate_result(run_dir: Path, candidate_name: str, task_name: str, result: Dict[str, Any]) -> None:
    candidate_dir = run_dir / "candidates" / candidate_name / "tasks" / task_name
    candidate_dir.mkdir(parents=True, exist_ok=True)

    with open(candidate_dir / "run_result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    report_src = Path(result.get("report_path", ""))
    if report_src.exists():
        report_dst = candidate_dir / "report.md"
        report_dst.write_text(report_src.read_text(encoding="utf-8"), encoding="utf-8")


def _build_run_decision_summary(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_candidate = summarize_candidate_scores(all_results)
    if not by_candidate:
        return {
            "best_candidate": None,
            "summary": "No candidates available.",
        }

    candidate_priority = {name: index for index, name in enumerate(DEFAULT_CANDIDATE_ORDER)}
    best_candidate, best_stats = sorted(
        by_candidate.items(),
        key=lambda item: (-item[1]["avg_score"], candidate_priority.get(item[0], len(candidate_priority)), item[0]),
    )[0]
    return {
        "best_candidate": {
            "candidate": best_candidate,
            "avg_score": best_stats["avg_score"],
            "count": best_stats["count"],
        },
        "summary": f"当前任务集推荐 {best_candidate}，平均分 {best_stats['avg_score']:.4f}",
    }


def save_run_summary(run_dir: Path, all_results: List[Dict[str, Any]], task_set_name: str) -> Dict[str, Any]:
    summary_md = run_dir / "SUMMARY.md"
    summary_lines = [
        f"# Meta-Harness 运行摘要",
        f"\n运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"任务集: {task_set_name}",
        f"Candidates: {len(set(r['candidate'] for r in all_results))}",
        f"总评估数: {len(all_results)}",
        "\n## Candidate 对比\n",
    ]

    by_candidate = summarize_candidate_scores(all_results)
    candidate_priority = {name: index for index, name in enumerate(DEFAULT_CANDIDATE_ORDER)}
    sorted_candidates = sorted(
        by_candidate.items(),
        key=lambda item: (-item[1]["avg_score"], candidate_priority.get(item[0], len(candidate_priority)), item[0]),
    )

    baseline_avg = by_candidate.get("current_baseline", {}).get("avg_score", 0.0)
    candidate_ranking = []
    for index, (candidate, candidate_summary) in enumerate(sorted_candidates):
        rank = index + 1
        if rank == 1:
            rank_tier = "top"
        elif candidate_summary["avg_score"] > baseline_avg:
            rank_tier = "strong"
        else:
            rank_tier = "baseline"
        candidate_ranking.append(
            {
                "rank": rank,
                "rank_tier": rank_tier,
                "candidate": candidate,
                "avg_score": candidate_summary["avg_score"],
                "count": candidate_summary["count"],
            }
        )

    summary_lines.extend(
        [
            "| Tier | Candidate | 平均分 | 评估次数 |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for item in candidate_ranking:
        summary_lines.append(
            f"| {item['rank_tier']} | {item['candidate']} | {item['avg_score']:.4f} | {item['count']} |"
        )
    summary_lines.append("\n")

    run_decision_summary = _build_run_decision_summary(all_results)

    summary_lines.append("## 决策摘要\n")
    summary_lines.append(f"- 结论: {run_decision_summary['summary']}")
    if run_decision_summary["best_candidate"] is not None:
        summary_lines.append(
            f"- 最佳 candidate: {run_decision_summary['best_candidate']['candidate']} (平均分 {run_decision_summary['best_candidate']['avg_score']:.4f}, 评估次数 {run_decision_summary['best_candidate']['count']})"
        )
        summary_lines.append("\n")

    summary_lines.append("## 排名分层规则\n")
    summary_lines.append(f"- current_baseline.avg_score: {baseline_avg:.4f}")
    summary_lines.append(f"- top: {SINGLE_RUN_RANK_TIER_RULE['top']}")
    summary_lines.append("- strong: rank > 1 且 avg_score > current_baseline.avg_score")
    summary_lines.append(f"- baseline: {SINGLE_RUN_RANK_TIER_RULE['baseline']}")
    summary_lines.append("\n")

    summary_lines.append("## 详细评估\n")
    for r in all_results:
        metrics = r.get("metrics", {})
        summary_lines.append(f"### {r['candidate']} / {r['task_name']}\n")
        summary_lines.append(f"- overall: {metrics.get('overall', 'N/A')}")
        summary_lines.append(f"- section_score: {metrics.get('section_score', 'N/A')}")
        summary_lines.append(f"- payload_field_score: {metrics.get('payload_field_score', 'N/A')}")
        summary_lines.append(f"- content_score: {metrics.get('content_score', 'N/A')}")
        summary_lines.append(f"- readability_score: {metrics.get('readability_score', 'N/A')}")
        summary_lines.append(f"- report_path: `{r.get('report_path', 'N/A')}`")
        summary_lines.append("\n")

    summary_md.write_text("\n".join(summary_lines), encoding="utf-8")

    summary_json = run_dir / "summary.json"
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_time": datetime.now().isoformat(),
                "task_set": task_set_name,
                "candidates": list(by_candidate.keys()),
                "rank_tier_rule": SINGLE_RUN_RANK_TIER_RULE,
                "candidate_ranking": candidate_ranking,
                "decision_summary": run_decision_summary,
                "results": all_results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return run_decision_summary


def build_candidates(candidate_set: str = "default") -> List[Dict[str, Any]]:
    if candidate_set == "default":
        return build_default_candidates()
    if candidate_set == "search_v1":
        return build_candidate_search_space(include_render_only=True)
    raise ValueError(f"Unknown candidate set: {candidate_set}")


def run_eval(
    run_name: str = "run_001",
    task_set_name: str = "baseline_smoke",
    candidates: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    if candidates is None:
        candidates = build_candidates("default")

    run_dir = ensure_run_dir(run_name)
    evaluator = PhoenixEvaluator()
    all_results: List[Dict[str, Any]] = []

    tasks = load_task_set(task_set_name)

    print(f"Meta-Harness 运行开始: {run_name}")
    print(f"Candidates: {[c['name'] for c in candidates]}")
    if candidates:
        print(f"默认基线: {candidates[0]['name']}")
    print(f"任务集: {task_set_name}, 任务数: {len(tasks)}")

    for candidate_spec in candidates:
        print(f"\n=== Candidate: {candidate_spec['name']} ===")
        harness = PhoenixHarness(str(PROJECT_ROOT), candidate_spec)

        for task_input in tasks:
            print(f"  Task: {task_input['task_name']}")
            try:
                run_result = harness.run(task_input)
                metrics = evaluator.evaluate(run_result)
                run_result["metrics"] = metrics

                save_candidate_result(run_dir, candidate_spec["name"], task_input["task_name"], run_result)
                all_results.append(run_result)

                print(f"    score: {metrics['overall']:.4f}")
            except Exception as e:
                print(f"    ERROR: {e}")

    run_decision_summary = save_run_summary(run_dir, all_results, task_set_name)

    print(f"\n运行完成。结果目录: {run_dir}")
    print(f"摘要文件: {run_dir / 'SUMMARY.md'}")
    print(f"结论: {run_decision_summary['summary']}")
    if run_decision_summary["best_candidate"] is not None:
        print(f"最佳 candidate: {run_decision_summary['best_candidate']['candidate']}")

    return all_results


def run_eval_suite(
    run_name_prefix: str,
    suite_name: str,
    candidate_set: str = "default",
) -> Dict[str, List[Dict[str, Any]]]:
    if suite_name not in V2_SUITES:
        raise ValueError(f"Unknown suite: {suite_name}")

    candidates = build_candidates(candidate_set)
    suite_results: Dict[str, List[Dict[str, Any]]] = {}
    for task_set_name in V2_SUITES[suite_name]:
        run_name = f"{run_name_prefix}_{task_set_name}"
        suite_results[task_set_name] = run_eval(
            run_name=run_name,
            task_set_name=task_set_name,
            candidates=candidates,
        )
    decision_summary = save_suite_summary(run_name_prefix, suite_name, suite_results)
    print(f"\nSuite 汇总目录: {ensure_run_dir(run_name_prefix)}")
    print(f"Suite 摘要文件: {ensure_run_dir(run_name_prefix) / 'SUITE_SUMMARY.md'}")
    print(f"结论: {decision_summary['summary']}")
    if decision_summary["recommended_default"] is not None:
        print(f"默认推荐: {decision_summary['recommended_default']['candidate']}")
    if decision_summary["recommended_fallback"] is not None:
        print(f"备选: {decision_summary['recommended_fallback']['candidate']}")
    return suite_results


if __name__ == "__main__":
    import sys

    run_name = sys.argv[1] if len(sys.argv) > 1 else "run_001"
    task_set_name = sys.argv[2] if len(sys.argv) > 2 else "baseline_smoke"
    candidate_set = sys.argv[3] if len(sys.argv) > 3 else "default"

    if task_set_name in V2_SUITES:
        run_eval_suite(
            run_name_prefix=run_name,
            suite_name=task_set_name,
            candidate_set=candidate_set,
        )
    else:
        run_eval(
            run_name=run_name,
            task_set_name=task_set_name,
            candidates=build_candidates(candidate_set),
        )
