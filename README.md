# Research Hypothesis Agent

**全域通用、24小时无人值守的自动化科研假说生成与演化引擎**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io/)
[![Celery](https://img.shields.io/badge/Queue-Celery-green.svg)](https://docs.celeryproject.org/)

---

## 项目愿景

**科研不是 ChatGPT 的问答游戏，而是精密的逻辑推演与对抗验证。**

这是一台**科研级精密仪器**，而非简单的 AI 聊天机器人。通过**凤凰协议演化机制**重构了科研假设生成范式——**从阻断型逻辑升级为演化型逻辑**。

---

## 核心架构

### 凤凰协议演化机制

当用户提出研究想法时，系统执行以下流程：

```
用户输入 → 意图清洗 → 多源检索 → PI 假设生成 → 物理铁闸校验
    → 红方攻击 → 蓝方答辩 → [失败触发 Phoenix 补丁] → 版本演进 → 成功
    ↘ [补丁无效累积 → 回溯 + 避让提示] ↗
```

**演化型逻辑（而非阻断型）**：
- 物理冲突 → 重写，而非直接拦截
- 蓝方失败 → 补丁注入，而非终止
- 分数停滞 → 外部补偿检索，而非放弃
- 补丁无效累积 → 回溯 + 避让提示，而非循环死磕

### Phoenix 状态机

| 状态 | 描述 | 触发条件 |
|------|------|----------|
| `INITIAL` | 初始输入 | 用户提交 |
| `HYPOTHESIS_GEN` | PI 假设生成 | 检索完成 |
| `RED_ATTACK` | 红方攻击审计 | 假设生成完成 |
| `BLUE_DEFENSE` | 蓝方答辩审查 | 红方攻击完成 |
| `PHOENIX_REWRITE` | 物理锚定重写 | 物理公理冲突 |
| `PHOENIX_PATCH` | 方法论补丁注入 | 蓝方答辩失败 |
| `PHOENIX_RETRY` | 补丁后重试 | 补丁应用完成 |
| `PHOENIX_ROLLBACK` | 🔙 补丁无效累积回溯 | 同一攻击类型连续失败 3 次 |
| `SCORE_STagnant` | 分数停滞检测 | 连续2轮无提升 |
| `EXTERNAL_COMPENSATION` | 外部算法补偿 | 停滞触发 |
| `SUCCESS` | 最终成功 | Science Score ≥ 8.5 |
| `MAX_PHOENIX_EXCEEDED` | 超过演化上限 | 迭代 > 8 次 |

### 智能体协作架构

| 智能体 | 角色 | 核心职责 |
|--------|------|----------|
| **HypothesisAgent** | PI 首席科学家 | 生成科研假设（Nature 审稿人标准） |
| **RedTeamAgent** | 红方攻击者 | 检测数据穿越、内生性偏倚、多重检验问题 |
| **DefenseCommittee** | 蓝方答辩委员会 | 物理可行性审查、裁决通过/失败 |
| **GenAIExpertAgent** | 生成式AI专家 | AI/ML 方法论审查 |
| **BiostatsAgent** | 生物统计专家 | 统计方法审查 |

---

## 核心功能模块

### 1. 意图清洗网关 (Intent Sanitizer)

入口前置检测，阻断脏数据：
- 越狱关键词检测（OWASP LLM Top 10）
- 语义隧道攻击检测（防止"研究系统自身"类攻击）
- 科学范畴验证
- 非科学输入自动拒绝

### 2. 动态 RAG 路由器 (Dynamic RAG Router)

智能数据源路由：
- **领域关键词检测** → 自动路由到最优数据源
- **数据源优先级**：PubMed（PRIMARY）、ArXiv（PRIMARY）、Semantic Scholar（SECONDARY）
- **超时降级机制**：主数据源超时自动切换备用源
- **并发检索聚合**：多数据源结果智能合并

支持数据源：
- PubMed（医学/生命科学）
- ArXiv（计算机科学/物理学/数学）
- Semantic Scholar（全学科）
- CrossRef（DOI 元数据）

### 3. 混合适应度评分 (Hybrid Fitness)

防奖励欺骗的核心评分机制：
- **向量创新分 × 0.6 + 红方严谨分 × 0.4**
- **甜点区算法 (Adjacent Possible)**：相似度 0.40-0.65 得高分
- **语义深度校验**：过滤高频学术泛词，防止甜点区逆向欺骗

### 4. 红方攻击检查清单

以 Nature 审稿人标准攻击假设：

| 攻击类型 | 检查内容 | 严重级别 |
|----------|----------|----------|
| Data Leakage | CV外特征选择、信息泄露、样本泄漏 | 致命 |
| Endogeneity | 未闭合后门路径、遗漏变量偏倚 | 致命 |
| Multiple Testing | FDR/Bonferroni 校正缺失、P-hacking | 严重 |
| Statistical Power | 样本量不足、功效分析缺失 | 严重 |
| Causal Inference | DAG 不完整、敏感性分析缺失 | 严重 |
| Reproducibility | 随机种子未固定、代码未公开 | 中等 |

### 5. 物理公理锚定审查

V7.4-F 新增的物理可行性验证：
- **信号捕获审查**：验证传感器/检测手段是否存在
- **因果链物理验证**：X → M → Y 的物理传导路径是否成立
- **科幻命题识别**：自动拒绝无法推导物理层面传感器逻辑的假设

### 6. 输出增强模块 (Output Enhancer)

生成三种科研资产：

**Implementation Roadmap（落地指南）**
- 阶段规划：Phase 1/2/3 定义
- 资源需求：GPU 类型、数据集权限
- 时间线：里程碑与验证周期
- 风险评估与预算估算

**Innovation Analysis（创新分析）**
- 核心创新点识别
- 新颖度等级：breakthrough / incremental
- 与现有研究的差异化分析

**Frontier Analysis（前沿分析）**
- 2026 SoTA 前沿定位
- 关键出版物解读
- Gap Analysis 研究空白识别

---

## V7.7 回溯机制

**补丁无效累积回溯**：当同一攻击类型连续失败 3 次时，触发版本回溯：

- **智能目标选择**：回溯到攻击类型首次出现前的版本
- **评分保护**：不回溯到分数低于当前 - 1.0 的版本
- **深度限制**：最多回溯 3 个版本，避免浪费已有演化
- **失败黑名单**：记录无法解决的攻击类型，生成新假设时注入避让提示

详见下方 [V7.7 回溯机制](#v77-回溯机制) 章节。

---

## V8.0 新增功能

### 自然语言对话 CLI

命令行界面新增多轮对话模式：

```bash
python -m src.cli.main
```

功能：
- **IntentParser 语义理解**：解析用户自然语言意图
- **ContextManager 会话管理**：多轮对话上下文保持
- **自主循环模式**：Auto-Iterate 自动���代生成
- **策略配置管理**：查看/修改 program.md 研究策略

### Meta Harness 评估框架

多候选方案对比评估系统：

```bash
python -m src.meta_harness.run_eval --suite v2_axes
```

功能：
- **三轴敏感度测试**：frontier_sensitive / roadmap_sensitive / innovation_sensitive
- **候选方案对比**：多配置并行评估
- **自动排名**：top / strong / baseline 层级标注
- **结果持久化**：JSON 报告输出

---

## 支持领域

| 类别 | 领域 |
|------|------|
| **物理科学** | physics, chemistry, astronomy |
| **计算机科学** | computer_science, mathematics, artificial_intelligence |
| **工程材料** | materials_science, engineering |
| **地球环境** | environmental_science, geoscience |
| **生命医学** | medicine, biology, neuroscience, genomics, proteomics, immunology, pharmacology, biochemistry, molecular_biology, cell_biology, pathology, microbiology, virology, epidemiology |
| **计算生物学** | bioinformatics, biostatistics, computational_biology |
| **临床医学** | cardiology, oncology, radiology, psychiatry, surgery, pediatrics |
| **社会科学** | psychology, economics |

---

## 快速开始

### 环境要求

- Python 3.9+
- Redis 6.0+（可选，用于 Celery 分布式）
- 4GB+ RAM

### 1. 安装依赖

```bash
git clone https://github.com/your-org/research-hypothesis-agent.git
cd research-hypothesis-agent
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 API Keys
```

核心配置：

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-xxxxx
CLAUDE_MODEL=claude-sonnet-4-6

# PubMed（可选，提高请求限制）
PUBMED_API_KEY=your_ncbi_api_key
PUBMED_EMAIL=your_email@example.com

# Redis（Celery 消息队列）
REDIS_URL=redis://localhost:6379/0

# Phoenix 协议
PHOENIX_MAX_ITERATIONS=8
PHOENIX_SUCCESS_THRESHOLD=8.5
```

### 3. 启动服务

**方式一：Streamlit Web UI**

```bash
streamlit run app.py
```

访问 `http://localhost:8501`

**方式二：CLI 命令行**

```bash
python -m src.cli.main
```

**方式三：分布式模式（Celery + Redis）**

```bash
# 终端 1: Redis
docker run -d -p 6379:6379 redis:6-alpine

# 终端 2: Celery Worker
celery -A src.core.celery_tasks_v75 worker --loglevel=info --pool=solo

# 终端 3: Streamlit UI
streamlit run app.py
```

---

## 项目结构

```
research-hypothesis-agent/
├── app.py                         # Streamlit Web UI 主入口
├── src/
│   ├── core/
│   │   ├── phoenix_state_machine.py      # Phoenix 状态机
│   │   ├── celery_tasks_v75.py           # Celery 任务编排
│   │   ├── hypothesis_version_manager.py # 版本演化链
│   │   ├── output_enhancer.py            # 输出增强模块
│   │   ├── hybrid_fitness.py             # 混合适应度评分
│   │   ├── physical_validator.py         # 物理铁闸校验
│   │   ├── intent_sanitizer.py           # 意图清洗网关
│   │   ├── rag_router.py                 # 动态 RAG 路由器
│   │   ├── score_trend_detector.py       # 分数趋势检测
│   │   ├── promise_score_calculator.py   # Promise Score
│   │   └── methodology_patch_priority.py # 补丁优先级
│   ├── agents/
│   │   ├── hypothesis_agent.py           # PI 假设生成
│   │   ├── red_team_agent.py             # 红方攻击
│   │   ├── defense_committee_agent.py    # 蓝方答辩
│   │   ├── genai_expert_agent.py         # 生成式AI专家
│   │   ├── biostats_agent.py             # 生物统计专家
│   │   └── paper_search_agent.py         # 文献检索
│   ├── cli/
│   │   └── main.py                       # V8.0 CLI 入口
│   ├── meta_harness/
│   │   ├── run_eval.py                   # Meta 评估运行器
│   │   ├── evaluator.py                  # 评估器
│   │   ├── phoenix_harness.py            # Phoenix Harness
│   │   └── task_sets.py                  # 任务集定义
│   ├── prompts/
│   │   └── phoenix_rewrite_prompt.py     # Phoenix 重写提示词
│   ├── utils/
│   │   ├── pubmed.py                     # PubMed API
│   │   ├── logger.py                     # 集中式日志
│   │   └ report_export.py                # 报告导出
│   │   └ oa_paper_fetcher.py             # OA 论文获取
│   │   └ relevance_scorer.py             # 相关性评分
│   │   └ token_utils.py                  # Token 压缩
│   │   └ journal_if.py                   # 期刊影响因子
│   └ └ data_sources/
│   │   └ semantic_scholar_searcher.py    # Semantic Scholar
│   └── ui/                                # UI 组件
├── data/                                  # SQLite 数据库
├── reports/                               # 生成报告
├── logs/                                  # 系统日志
├── meta_harness_runs/                     # Meta 评估结果
├── outputs/                               # Pipeline 输出
└── docs/                                  # 文档
```

---

## 测试验证

### 核心测试文件

| 测试文件 | 测试内容 |
|----------|----------|
| `test_v75_integration.py` | Phoenix 状态机、版本链、分数趋势 |
| `test_v75_e2e_audit.py` | 状态转换一致性、JSON 序列化、SQLite 持久化 |
| `test_output_enhanced.py` | Roadmap、Innovation、Frontier 输出 |
| `smoke_test_v75.py` | 全链路冒烟测试 |
| `blind_test_v7_4_g.py` | 盲测验证 |

运行测试：

```bash
python test_v75_integration.py
python test_v75_e2e_audit.py
python smoke_test_v75.py
```

---

## Phoenix 协议配置

```yaml
# src/core/phoenix_state_machine.py
PHOENIX_CONFIG:
  MAX_PHOENIX_ITERATIONS: 8      # 最大演化次数
  MAX_REWRITE_ATTEMPTS: 3        # 物理重写上限
  MAX_PATCH_ATTEMPTS: 5          # 方法论补丁上限
  SCORE_STagnant_THRESHOLD: 2    # 停滞判定阈值
  SCORE_RISE_MIN_DELTA: 0.5      # 每轮最小上升
  MIN_SUCCESS_SCORE: 8.5         # 成功最低阈值
  COMPENSATION_SEARCH_DEPTH: 3   # 外部补偿检索深度
  # V7.7: 回溯机制配置
  ATTACK_TYPE_FAILURE_THRESHOLD: 3   # 同一攻击类型连续失败 3 次触发回溯
  MAX_ROLLBACK_ATTEMPTS: 2           # 最大回溯尝试次数
  ROLLBACK_DEPTH_LIMIT: 3            # 回溯深度限制（最多回溯 3 个版本）
  ROLLBACK_SCORE_TOLERANCE: 1.0      # 回溯评分容忍度（不回溯到分数低于当前-1.0 的版本）
```

---

## V7.7 回溯机制

### 问题背景

当同一攻击类型（如 Data Leakage）连续多次补丁无效时，系统可能陷入"补丁循环"：
- 补丁 → 重试 → 同样攻击失败 → 补丁 → ...
- 浪费迭代次数，无法真正解决问题

### 解决方案

**补丁无效累积回溯**（PHOENIX_ROLLBACK）：
1. **触发条件**：同一攻击类型连续失败 ≥ 3 次
2. **回溯目标**：找到该攻击类型首次出现前的版本
3. **评分保护**：不回溯到分数过低的版本（容忍度 1.0）
4. **深度限制**：最多回溯 3 个版本，避免回溯到非常早期的版本
5. **失败黑名单**：记录无法解决的攻击类型，生成新假设时注入避让提示

### 回溯流程

```
补丁连续失败 (Data Leakage × 3)
    ↓
触发 PHOENIX_ROLLBACK
    ↓
查找回溯目标版本（不含 Data Leakage，分数 ≥ 当前 - 1.0）
    ↓
创建回溯版本（v1.4_rollback）
    ↓
注入避让提示："请避开 Data Leakage 方向，采用不同的特征选择策略"
    ↓
重置失败计数，继续演化
```

### 版本类型

| 版本类型 | 描述 | 示例 |
|----------|------|------|
| `initial` | 初始版本 | v1.0 |
| `physical_fix` | 物理锚定修正 | v1.1 |
| `methodology_patch` | 方法论补丁 | v1.2 |
| `rollback` | 🔙 回溯恢复 | v1.4_rollback |
| `final` | 最终版本 | v1.5 |

---

## 版本演化示例

### 正常演化流程

```
v1.0 (初始版本, Science Score: 6.5)
  ↓ 红方攻击：数据泄露
v1.1 (方法论补丁, Science Score: 7.8)
  ↓ 红方攻击：内生性偏倚
v1.2 (方法论补丁, Science Score: 8.2)
  ↓ 蓝方通过
✅ v1.3 (最终版本, Science Score: 8.9)
```

### 回溯演化流程

```
v1.0 (初始版本, Score: 6.5)
  ↓ 红方攻击：Data Leakage
v1.1 (方法论补丁, Score: 7.2)
  ↓ 红方攻击：Data Leakage (补丁无效)
v1.2 (方法论补丁, Score: 7.5)
  ↓ 红方攻击：Data Leakage (补丁无效)
v1.3 (方法论补丁, Score: 7.8)
  ↓ 红方攻击：Data Leakage (补丁无效)
🔥 Data Leakage 连续失败 3 次 → 触发回溯
  ↓
v1.4_rollback (回溯到 v1.0 方向, 注入避让提示)
  ↓ 生成新假设（避开 Data Leakage，改用不同的特征选择策略）
v1.5 (新研究方向, Score: 8.2)
  ↓ 蓝方通过
✅ v1.6 (最终版本, Score: 9.1)
```

---

## 开发者规范

### Git Commit 规范

```
<type>(<scope>): <subject>

type: feat|fix|docs|style|refactor|test|chore
scope: phoenix|agent|gateway|orchestrator|storage|ui|cli|meta
subject: 简短描述 (<= 50 字符)

示例:
feat(cli): 新增 V8.0 自然语言对话模式
feat(meta): 添加三轴敏感度评估框架
fix(phoenix): 修复 numpy 类型序列化问题
refactor(output): 重构输出增强模块
```

---

## 致谢

架构设计深受以下启发：
- **Nature 系列期刊**的审稿标准
- **Causal Inference** (Pearl, 2009) 因果图理论
- **Red Teaming** 在 AI 安全领域的实践
- **Multi-Agent Systems** 对抗协作范式
- **Evolutionary Algorithms** 迭代优化思想

---

<div align="center">

**失败不是终点，而是演化的起点。**

**这不是魔法，这是工程。**

</div>