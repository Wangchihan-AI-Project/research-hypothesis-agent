# -*- coding: utf-8 -*-
"""
Prompts 模块入口

V6.0 新增：SaaS云平台版 System Prompts（多数据源支持）
V5.0 新增：24小时无人值守全防御版 System Prompts

模块结构：
- pi_system_prompt.py: PI智能体提示词（V6.0/V5.0信息锚定版）
- auditor_system_prompt.py: 红方审计员提示词（V6.0/V5.0独立查证版）
"""

# ==================== V6.0 版本（推荐） ====================
from .pi_system_prompt import (
    PI_SYSTEM_PROMPT_V60,
    format_pi_prompt_v60,
)

from .auditor_system_prompt import (
    AUDITOR_SYSTEM_PROMPT_V60,
    format_auditor_prompt_v60,
)

# ==================== V5.0 版本 ====================
from .pi_system_prompt import (
    PI_SYSTEM_PROMPT_V50,
    PI_SYSTEM_PROMPT_CURRENT,
    PI_DRAFT_PROMPT_V50,
    format_pi_prompt_v50,
    format_pi_draft_prompt_v50,
    generate_insufficient_support_message
)

from .auditor_system_prompt import (
    AUDITOR_SYSTEM_PROMPT_V50,
    AUDITOR_SYSTEM_PROMPT_CURRENT,
    CROSS_EXAMINATION_PROMPT,
    AUDIT_CHECKLIST_V50,
    QUICK_AUDIT_PROMPT_V50,
    format_auditor_prompt_v50,
    format_cross_examination_prompt,
    get_audit_checklist_v50,
    format_quick_audit_prompt_v50
)

# ==================== V4.1 版本（向后兼容） ====================
PI_SYSTEM_PROMPT_V41 = PI_SYSTEM_PROMPT_V50
PI_DRAFT_PROMPT_V41 = PI_DRAFT_PROMPT_V50
AUDITOR_SYSTEM_PROMPT_V41 = AUDITOR_SYSTEM_PROMPT_V50
AUDIT_CHECKLIST = AUDIT_CHECKLIST_V50
QUICK_AUDIT_PROMPT = QUICK_AUDIT_PROMPT_V50

# 格式化函数别名（向后兼容）
format_pi_prompt = format_pi_prompt_v50
format_pi_draft_prompt = format_pi_draft_prompt_v50
format_auditor_prompt = format_auditor_prompt_v50
format_quick_audit_prompt = format_quick_audit_prompt_v50
get_audit_checklist = get_audit_checklist_v50


__all__ = [
    # V6.0 版本（推荐）
    'PI_SYSTEM_PROMPT_V60',
    'format_pi_prompt_v60',

    'AUDITOR_SYSTEM_PROMPT_V60',
    'format_auditor_prompt_v60',

    # V5.0 版本
    'PI_SYSTEM_PROMPT_V50',
    'PI_SYSTEM_PROMPT_CURRENT',
    'PI_DRAFT_PROMPT_V50',
    'format_pi_prompt_v50',
    'format_pi_draft_prompt_v50',
    'generate_insufficient_support_message',

    'AUDITOR_SYSTEM_PROMPT_V50',
    'AUDITOR_SYSTEM_PROMPT_CURRENT',
    'CROSS_EXAMINATION_PROMPT',
    'AUDIT_CHECKLIST_V50',
    'QUICK_AUDIT_PROMPT_V50',
    'format_auditor_prompt_v50',
    'format_cross_examination_prompt',
    'get_audit_checklist_v50',
    'format_quick_audit_prompt_v50',

    # V4.1 版本（向后兼容）
    'PI_SYSTEM_PROMPT_V41',
    'PI_DRAFT_PROMPT_V41',
    'AUDITOR_SYSTEM_PROMPT_V41',
    'AUDIT_CHECKLIST',
    'QUICK_AUDIT_PROMPT',
    'format_pi_prompt',
    'format_pi_draft_prompt',
    'format_auditor_prompt',
    'format_quick_audit_prompt',
    'get_audit_checklist',
]