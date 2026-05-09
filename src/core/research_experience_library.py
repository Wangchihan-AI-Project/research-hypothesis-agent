# -*- coding: utf-8 -*-
"""
科研经验库 v1

将 Phoenix / 红队 / 防御流程中的成功策略和失败教训沉淀为可检索 JSONL 经验。
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.context_rollback import LessonLearned, RollbackTrigger
from src.utils.logger import get_central_logger

logger = get_central_logger()

SCHEMA_VERSION = "research_experience_v1"
DEFAULT_EXPERIENCE_PATH = Path("data/research_experience_library.jsonl")
INFRA_ERROR_KEYWORDS = (
    "api",
    "timeout",
    "timed out",
    "redis",
    "celery",
    "json",
    "parse",
    "网络",
    "超时",
    "连接",
    "不可用",
)
QUALITY_GUARD_TEXT = (
    "注意：以上历史经验只用于避免重复错误，不构成当前研究证据；"
    "不得降低新颖性、因果严谨性、可验证性和防御委员会通过标准。"
)


@dataclass
class ResearchExperience:
    """一条可复用科研经验。"""

    experience_id: str
    partition: str
    created_at: str
    task_id: str
    run_type: str
    domain: str
    topic_fingerprint: str
    tags: List[str]
    trigger: str
    lesson_summary: str
    forbidden_patterns: List[str] = field(default_factory=list)
    recommended_directions: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    quality: Dict[str, Any] = field(default_factory=dict)
    source_refs: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchExperience":
        allowed = cls.__dataclass_fields__.keys()
        cleaned = {key: data.get(key) for key in allowed if key in data}
        cleaned.setdefault("schema_version", SCHEMA_VERSION)
        cleaned.setdefault("forbidden_patterns", [])
        cleaned.setdefault("recommended_directions", [])
        cleaned.setdefault("evidence", {})
        cleaned.setdefault("quality", {})
        cleaned.setdefault("source_refs", {})
        return cls(**cleaned)

    def to_lesson_learned(self) -> LessonLearned:
        trigger_type = RollbackTrigger.RED_TEAM_REJECT
        if self.trigger in {"defense_failed", "patch_ineffective"}:
            trigger_type = RollbackTrigger.DEFENSE_FAILED
        elif self.trigger in {"validation_failed"}:
            trigger_type = RollbackTrigger.VALIDATION_FAILED
        return LessonLearned(
            trigger_type=trigger_type,
            lesson_summary=self.lesson_summary,
            forbidden_patterns=self.forbidden_patterns,
            recommended_directions=self.recommended_directions,
            collision_evidence=self.evidence.get("collision_evidence", []),
            confidence=float(self.quality.get("confidence", 0.8)),
        )


@dataclass
class ExperienceQuery:
    """经验检索请求。"""

    topic: str
    domain: str = "unknown"
    tags: List[str] = field(default_factory=list)
    limit: int = 3
    min_confidence: float = 0.6


@dataclass
class ExperienceRetrievalResult:
    """经验检索结果。"""

    experiences: List[ResearchExperience]
    prompt_suffix: str
    retrieval_reason: Dict[str, Any]


class ResearchExperienceLibrary:
    """JSONL 科研经验库。"""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT_EXPERIENCE_PATH

    @classmethod
    def default(cls) -> "ResearchExperienceLibrary":
        return cls(DEFAULT_EXPERIENCE_PATH)

    def load_all(self) -> List[ResearchExperience]:
        if not self.path.exists():
            return []

        experiences: List[ResearchExperience] = []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        experiences.append(ResearchExperience.from_dict(data))
                    except Exception as e:
                        logger.warning(f"跳过损坏经验记录: {e}")
        except Exception as e:
            logger.warning(f"读取科研经验库失败: {e}")
            return []
        return experiences

    def append(self, experience: ResearchExperience) -> bool:
        return self.save_many([experience]) > 0

    def save_many(self, experiences: List[ResearchExperience]) -> int:
        valid_experiences = [exp for exp in experiences if self._is_persistable(exp)]
        if not valid_experiences:
            return 0

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            existing_ids = {exp.experience_id for exp in self.load_all()}
            new_items = []
            for exp in valid_experiences:
                if exp.experience_id in existing_ids:
                    continue
                new_items.append(exp)
                existing_ids.add(exp.experience_id)
            if not new_items:
                return 0

            with self.path.open("a", encoding="utf-8") as f:
                for exp in new_items:
                    f.write(json.dumps(exp.to_dict(), ensure_ascii=False) + "\n")
            return len(new_items)
        except Exception as e:
            logger.warning(f"保存科研经验失败: {e}")
            return 0

    def retrieve(self, query: ExperienceQuery) -> ExperienceRetrievalResult:
        candidates = []
        for exp in self.load_all():
            confidence = float(exp.quality.get("confidence", 0.8))
            if confidence < query.min_confidence:
                continue
            score = self._score_experience(exp, query)
            if score > 0:
                candidates.append((score, exp))

        candidates.sort(key=lambda item: item[0], reverse=True)
        selected = [exp for _, exp in candidates[: max(1, query.limit)]]
        return ExperienceRetrievalResult(
            experiences=selected,
            prompt_suffix=self.build_prompt_suffix(selected),
            retrieval_reason={
                "matched_count": len(candidates),
                "selected_count": len(selected),
                "query_domain": query.domain,
                "query_tags": query.tags,
            },
        )

    def build_prompt_suffix(self, experiences: List[ResearchExperience], max_chars: int = 1800) -> str:
        if not experiences:
            return ""

        lines = [
            "\n【历史科研经验参考 - 不得替代当前验证】",
            "以下经验来自过往 Phoenix / 红队 / 防御流程，仅用于避免重复错误和借鉴有效策略。",
        ]
        for idx, exp in enumerate(experiences[:3], 1):
            lines.append(f"\n{idx}. [{exp.partition}/{exp.trigger}] {exp.lesson_summary[:160]}")
            if exp.forbidden_patterns:
                forbidden = "；".join(exp.forbidden_patterns[:3])
                lines.append(f"   避免: {forbidden[:240]}")
            if exp.recommended_directions:
                recommended = "；".join(exp.recommended_directions[:2])
                lines.append(f"   可尝试: {recommended[:220]}")
            if exp.tags:
                lines.append(f"   标签: {', '.join(exp.tags[:6])}")
        lines.append(f"\n{QUALITY_GUARD_TEXT}")

        prompt = "\n".join(lines)
        if len(prompt) > max_chars:
            prompt = prompt[: max_chars - len(QUALITY_GUARD_TEXT) - 8].rstrip() + "\n" + QUALITY_GUARD_TEXT
        return prompt

    def extract_from_red_team(
        self,
        task_id: str,
        domain: str,
        topic: str,
        iteration: int,
        red_team_result: Optional[Dict[str, Any]],
        phoenix_context: Any,
    ) -> List[ResearchExperience]:
        if not red_team_result:
            return []
        attack_report = red_team_result.get("attack_report", {})
        verdict = str(attack_report.get("verdict", "")).lower()
        critical_flaws = _as_list(attack_report.get("critical_flaws"))
        severe_issues = _as_list(attack_report.get("severe_issues"))
        moderate_concerns = _as_list(attack_report.get("moderate_concerns"))
        attack_vectors = _as_list(attack_report.get("attack_vectors"))
        if verdict != "failed" and not critical_flaws and not severe_issues:
            return []

        patterns = _clean_text_items(critical_flaws + severe_issues + moderate_concerns)
        if not patterns or _contains_infra_failure(patterns):
            return []

        attack_types = _as_list(getattr(phoenix_context, "red_attack_types", []))
        tags = _normalize_tags(["red_team_failed", *attack_vectors, *attack_types])
        summary = _first_non_empty(patterns, "红队审计指出当前假设存在严谨性风险。")
        return [
            self._build_experience(
                partition="warning",
                task_id=task_id,
                run_type="phoenix_red_team",
                domain=domain,
                topic=topic,
                tags=tags,
                trigger="red_team_failed",
                lesson_summary=summary,
                forbidden_patterns=patterns,
                recommended_directions=["生成假设时提前显式回应红队攻击点", "补充因果、统计和文献锚定约束"],
                evidence={
                    "iteration": iteration,
                    "critical_flaws": critical_flaws,
                    "severe_issues": severe_issues,
                    "moderate_concerns": moderate_concerns,
                    "attack_vectors": attack_vectors,
                    "verdict": verdict,
                    "red_attack_types": attack_types,
                },
                confidence=0.82 if critical_flaws else 0.72,
            )
        ]

    def extract_from_defense(
        self,
        task_id: str,
        domain: str,
        topic: str,
        iteration: int,
        defense_result: Optional[Dict[str, Any]],
        red_team_result: Optional[Dict[str, Any]],
        phoenix_context: Any,
    ) -> List[ResearchExperience]:
        if not defense_result:
            return []

        defense_passed = bool(defense_result.get("defense_passed", False))
        final_verdict = str(defense_result.get("final_verdict") or defense_result.get("verdict") or "")
        critical_issues = _as_list(defense_result.get("critical_issues"))
        recommendations = _as_list(defense_result.get("recommendations"))
        attack_report = red_team_result.get("attack_report", {}) if red_team_result else {}
        attack_vectors = _as_list(attack_report.get("attack_vectors"))
        attack_types = _as_list(getattr(phoenix_context, "red_attack_types", []))
        score_history = _as_list(getattr(phoenix_context, "score_history", []))

        if defense_passed:
            summary = "防御委员会通过，当前假设结构具备较好的答辩稳定性。"
            partition = "golden"
            trigger = "defense_passed"
            forbidden_patterns: List[str] = []
            recommended_directions = _clean_text_items(recommendations) or ["保持当前机制链条、统计防御和文献锚定的组合结构"]
            confidence = 0.86
        else:
            patterns = _clean_text_items(critical_issues + _as_list(attack_report.get("critical_flaws")) + _as_list(attack_report.get("severe_issues")))
            if not patterns or _contains_infra_failure(patterns):
                return []
            summary = _first_non_empty(patterns, "防御委员会未通过，当前假设仍存在关键风险。")
            partition = "warning"
            trigger = "defense_failed"
            forbidden_patterns = patterns
            recommended_directions = _clean_text_items(recommendations) or ["在下一轮生成前先修复防御委员会指出的关键问题"]
            confidence = 0.84

        return [
            self._build_experience(
                partition=partition,
                task_id=task_id,
                run_type="phoenix_defense",
                domain=domain,
                topic=topic,
                tags=_normalize_tags([trigger, *attack_vectors, *attack_types]),
                trigger=trigger,
                lesson_summary=summary,
                forbidden_patterns=forbidden_patterns,
                recommended_directions=recommended_directions,
                evidence={
                    "iteration": iteration,
                    "defense_passed": defense_passed,
                    "final_verdict": final_verdict,
                    "critical_issues": critical_issues,
                    "recommendations": recommendations,
                    "score_history": score_history,
                    "red_attack_types": attack_types,
                },
                confidence=confidence,
            )
        ]

    def extract_from_final_payload(
        self,
        task_id: str,
        domain: str,
        topic: str,
        payload: Dict[str, Any],
        state: str,
    ) -> List[ResearchExperience]:
        if not payload:
            return []

        if state == "success" or payload.get("hypothesis"):
            audit_context = payload.get("audit_context", {})
            score_history = _as_list(audit_context.get("score_history"))
            red_attack_types = _as_list(audit_context.get("red_attack_types"))
            summary = "Phoenix 工作流最终成功，当前假设通过了红队与防御闭环。"
            return [
                self._build_experience(
                    partition="golden",
                    task_id=task_id,
                    run_type="phoenix_final",
                    domain=domain,
                    topic=topic,
                    tags=_normalize_tags(["phoenix_success", *red_attack_types]),
                    trigger="success",
                    lesson_summary=summary,
                    forbidden_patterns=[],
                    recommended_directions=["优先复用本次成功的机制链、证据锚定和防御结构"],
                    evidence={
                        "audit_context": audit_context,
                        "red_team_report": payload.get("red_team_report", {}),
                        "defense_report": payload.get("defense_report", {}),
                    },
                    confidence=0.9 if score_history else 0.82,
                )
            ]

        reason = str(payload.get("reason") or payload.get("failure_state") or "")
        if not reason or _contains_infra_failure([reason]):
            return []
        return [
            self._build_experience(
                partition="warning",
                task_id=task_id,
                run_type="phoenix_final",
                domain=domain,
                topic=topic,
                tags=_normalize_tags(["phoenix_failure", payload.get("failure_state", "")]),
                trigger="phoenix_failure",
                lesson_summary=reason[:240],
                forbidden_patterns=[reason[:240]],
                recommended_directions=["下一轮生成前优先规避导致 Phoenix 失败的机制或方法学路径"],
                evidence={"payload": payload},
                confidence=0.72,
            )
        ]

    def _build_experience(
        self,
        partition: str,
        task_id: str,
        run_type: str,
        domain: str,
        topic: str,
        tags: List[str],
        trigger: str,
        lesson_summary: str,
        forbidden_patterns: List[str],
        recommended_directions: List[str],
        evidence: Dict[str, Any],
        confidence: float,
    ) -> ResearchExperience:
        clean_tags = _normalize_tags(tags)
        clean_summary = str(lesson_summary or "").strip()[:300]
        experience_id = _stable_id(domain, partition, trigger, clean_summary, clean_tags)
        score_history = _as_list(evidence.get("score_history"))
        quality = {
            "confidence": confidence,
            "science_score_max": max(score_history) if score_history else None,
        }
        return ResearchExperience(
            experience_id=experience_id,
            partition=partition,
            created_at=datetime.now().isoformat(),
            task_id=task_id,
            run_type=run_type,
            domain=domain or "unknown",
            topic_fingerprint=_topic_fingerprint(topic),
            tags=clean_tags,
            trigger=trigger,
            lesson_summary=clean_summary,
            forbidden_patterns=_clean_text_items(forbidden_patterns)[:5],
            recommended_directions=_clean_text_items(recommended_directions)[:4],
            evidence=evidence,
            quality=quality,
            source_refs={},
        )

    def _score_experience(self, exp: ResearchExperience, query: ExperienceQuery) -> float:
        score = 0.0
        if query.domain and exp.domain and query.domain.lower() == exp.domain.lower():
            score += 3.0

        query_tags = {tag.lower() for tag in query.tags or [] if tag}
        exp_tags = {tag.lower() for tag in exp.tags if tag}
        score += len(query_tags & exp_tags) * 2.0

        query_tokens = _tokens(query.topic)
        exp_text = " ".join([exp.lesson_summary, " ".join(exp.tags), " ".join(exp.forbidden_patterns), " ".join(exp.recommended_directions)])
        exp_tokens = _tokens(exp_text)
        if query_tokens and exp_tokens:
            overlap = len(query_tokens & exp_tokens)
            score += min(3.0, overlap / max(1, len(query_tokens)) * 3.0)

        score += min(1.0, float(exp.quality.get("confidence", 0.8)))
        if exp.partition == "golden":
            score += 0.8
        elif exp.partition == "mixed":
            score += 0.6
        elif exp.partition == "warning":
            score += 0.4
        return score

    def _is_persistable(self, exp: ResearchExperience) -> bool:
        if exp.partition not in {"golden", "warning", "mixed"}:
            return False
        if not exp.lesson_summary or _contains_infra_failure([exp.lesson_summary]):
            return False
        if exp.partition == "warning" and not exp.forbidden_patterns:
            return False
        return True


def _stable_id(domain: str, partition: str, trigger: str, summary: str, tags: List[str]) -> str:
    raw = "|".join([domain or "unknown", partition, trigger, summary, ",".join(sorted(tags))])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _topic_fingerprint(topic: str) -> str:
    return hashlib.sha256((topic or "").strip().lower().encode("utf-8")).hexdigest()[:12]


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def _clean_text_items(items: List[Any]) -> List[str]:
    cleaned = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, dict):
            text = item.get("issue") or item.get("flaw") or item.get("description") or item.get("text") or json.dumps(item, ensure_ascii=False)
        else:
            text = str(item)
        text = re.sub(r"\s+", " ", text).strip()
        if text and text not in cleaned:
            cleaned.append(text[:300])
    return cleaned


def _normalize_tags(tags: List[Any]) -> List[str]:
    normalized = []
    for tag in tags:
        if tag is None:
            continue
        text = str(tag).strip().lower().replace(" ", "_")
        text = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "", text)
        if text and text not in normalized:
            normalized.append(text[:60])
    return normalized[:12]


def _first_non_empty(items: List[str], default: str) -> str:
    for item in items:
        if item:
            return item[:240]
    return default


def _contains_infra_failure(items: List[str]) -> bool:
    text = " ".join(str(item).lower() for item in items)
    return any(keyword in text for keyword in INFRA_ERROR_KEYWORDS)


def _tokens(text: str) -> set:
    if not text:
        return set()
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}|[\u4e00-\u9fff]{2,}", text.lower()))
