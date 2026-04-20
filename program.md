# Research Hypothesis Agent - 研究策略配置

> 类似 Karpathy autoresearch 的 `program.md`，人类通过修改此文件来引导 Agent 的研究行为。
> Agent 在启动时会读取此文件，根据其中的策略执行研究任务。

---

## 研究目标 (Research Goals)

### 研究领域
- **主要领域**: 计算生物学 / 神经科学 / 生物医学 AI
- **目标期刊级别**: Nature / Science / Cell 级别
- **研究深度**: 博士论文开题深度

### 假设标准
- **颠覆性分数** (transformative_impact): >= 8.0
- **原创性分数** (methodological_originality): >= 7.5
- **可行性分数** (poc_feasibility): >= 7.0
- **综合平均分**: >= 7.5

---

## 搜索策略 (Search Strategy)

### 论文检索参数
```yaml
paper_search:
  # 两阶段漏斗配置
  use_two_stage_funnel: true
  stage1_max: 500        # 第一阶段粗筛数量
  stage2_top_k: 40       # 第二阶段精读数量

  # 质量过滤
  min_if: 5.0            # 最低影响因子阈值（0 = 不限）
  date_range:
    start: 2020          # 起始年份
    end: 2026            # 结束年份（自动更新为当前年）

  # 全文获取
  fetch_full_text: true
  max_full_text: 10      # 最多获取全文的论文数
```

### 关键词策略
- 自动扩展关键词: 是
- 使用 MeSH 术语优化: 是
- 组合搜索策略: 启用

---

## 假设生成策略 (Hypothesis Generation)

### 核心配置
```yaml
hypothesis_generation:
  # 数量配置
  num_hypotheses: 3      # 每轮生成假设数量
  best_of_n: 3           # 多轨并行原型数（选最优）

  # 验证阈值
  min_score_threshold: 7.5   # 最低通过分数
  enable_prevalidation: true # 启用预验证

  # 激进突变
  radical_pivot_threshold: 5.0  # 低于此分触发破坏性重构
  max_internal_retries: 2      # 内部重试次数
```

### 思想钢印 (Core Principles)
1. **模态锁死**: 宏观数据禁止微观术语，微观数据禁止宏观术语
2. **零推诿**: 永久禁用 "N/A"、"暂无"、"待定" 等词汇
3. **去口号化**: 所有方法必须落实到具体参数和代码包

### 七段式输出结构
1. 破局点批判 (Gap Analysis) [>=150字]
2. 核心科学假说 (Core Hypothesis) [>=100字]
3. 颠覆性创新点 (Innovation) [>=150字]
4. 底层逻辑与反事实推演 (Mechanism) [>=300字]
5. 详尽技术路线 (Technical Roadmap) [>=400字]
6. 转化价值 (Translational Impact) [>=200字]
7. 证伪方案 (Falsification Plan) [>=200字]

---

## 审计策略 (Audit Strategy)

### 全球查新探针
```yaml
global_prior_art:
  enabled: true
  min_novelty_score: 50  # 全球新颖性最低分数（/100）
  collision_threshold: 0.7  # 碰撞相似度阈值
```

### 暗盒预审（三方会审）
```yaml
dark_box_audit:
  enabled: true
  phases:
    - global_novelty      # 全球查新
    - biostats_hardcore   # 统计硬核审计
    - red_team_attack     # 红队攻击

  # 反馈循环
  max_audit_iterations: 2  # 审计迭代次数
```

### 红蓝对抗
```yaml
red_blue_defense:
  enabled: true
  red_team_intensity: high  # low / medium / high
  defense_committee: true   # 终审答辩委员会
```

---

## 自主循环模式 (Autonomous Mode)

> 类似 Karpathy autoresearch 的自主实验循环：Agent 自动迭代，直到达标或超时

```yaml
autonomous_mode:
  enabled: false         # 默认关闭，手动开启

  # 循环参数
  max_iterations: 5      # 最大迭代次数
  target_score: 8.0      # 目标综合分数
  time_budget_minutes: 60  # 总时间预算（分钟）

  # 自动决策
  auto_select_papers: true   # 自动选择最高分论文
  auto_approve_hypothesis: false  # 假设是否自动通过（建议人工确认）
  auto_technical_analysis: true   # 自动技术分析

  # 失败策略
  on_failure:
    action: radical_pivot  # radical_pivot / retry / abort
    max_pivot_attempts: 2  # 激进突变尝试次数

  # 日志输出
  experiment_log: true    # 记录每次迭代日志
  output_dir: experiments/  # 实验日志目录
```

---

## 资源配置 (Resource Configuration)

### 计算资源
```yaml
resources:
  gpu_recommendation: auto  # auto / specific model
  estimated_cost_limit: 100  # USD 上限
  max_runtime_hours: 24
```

### Agent 模型配置
```yaml
agents:
  hypothesis_agent: claude-opus-4-6
  validation_agent: claude-opus-4-6
  tech_analysis_agent: claude-opus-4-6
  red_team_agent: claude-opus-4-6
```

---

## 输出配置 (Output Configuration)

### 报告格式
```yaml
output:
  report_format: markdown
  include_scores: true
  include_audit_log: true
  include_tool_calls: true

  # 报告目录
  reports_dir: reports/
  experiments_dir: experiments/
```

### 可视化
```yaml
visualization:
  knowledge_graph: true   # 生成知识图谱
  hypothesis_network: true  # 假设关系网络
```

---

## 使用说明

### 如何修改此文件

1. **修改研究目标**: 调整 `研究目标` 部分，设定你的领域和目标期刊级别
2. **调整搜索策略**: 修改 `min_if` 和 `date_range` 来控制论文质量
3. **配置假设标准**: 调整各项分数阈值来控制假设质量
4. **开启自主模式**: 将 `autonomous_mode.enabled` 设为 `true`，Agent 将自动迭代

### 启动研究

```bash
# CLI 方式
python main.py

# Web UI 方式 (V7.1 异步架构)
streamlit run app_v7.py
```

### 自主模式启动

在 CLI 或 Web UI 中输入：

```
请根据 program.md 启动自主研究模式，关键词: [你的研究关键词]
```

---

## 版本信息

- **配置版本**: v2.0 (V6.0 轻量指令模式)
- **创建日期**: 2026-04-16
- **参考项目**: Karpathy autoresearch (https://github.com/karpathy/autoresearch)

---

## V6.0 防御层配置 (Defense Layer)

> 系统防御机制配置：熔断器、锚定校验、意图清洗

```yaml
defense_layer:
  intent_sanitizer:
    enabled: true           # 是否启用意图清洗网关
    strict_mode: true       # 严格模式（更严格的输入检测）

  global_fuse:
    enabled: true           # 是否启用全局熔断器
    hard_cap: 15            # API调用熔断上限（单次任务最大调用次数）
    warning_threshold: 10   # 预警阈值（达到此值开始警告）

  hard_link_anchor:
    enabled: true           # 是否启用硬链接锚定校验
    strict_mode: true       # 严格模式（校验所有 PMID/ArXiv/DOI）
```

---

## V6.0 工作流参数配置 (Workflow Parameters)

> 核心工作流行为参数：反馈循环、并行生成、阈值设置

```yaml
workflow_params:
  max_feedback_loop: 1      # 反馈循环最大次数（DefenseCommittee 失败后回溯修正次数）
  best_of_n: 3              # 多轨并行原型数（一次生成 N 个假设，选最优）
  radical_pivot_threshold: 5.0  # 激进突变触发阈值（低于此分触发破坏性重构）
  max_audit_iterations: 2   # 审计迭代次数（全球查新和内生审计的最大迭代）
  remedial_search:
    max_results: 5          # 补救搜索结果数（反馈循环中针对性补全搜索）
```

---

## V6.0 Celery异步任务配置 (Async Tasks)

> Celery 任务队列配置：超时、重试、Redis 连接

```yaml
async_tasks:
  redis_url: "redis://localhost:6379/0"  # Redis 连接 URL（可通过环境变量 REDIS_URL 覆盖）

  task_soft_time_limit: 300   # 任务软超时（秒）= 5分钟
  task_hard_time_limit: 600   # 任务硬超时（秒）= 10分钟
  task_max_retries: 3         # 任务最大重试次数
  webhook_timeout: 30         # Webhook 回调超时（秒）
```

---

## V6.0 数据源路由配置 (Data Source Routing)

> 动态数据源选择：根据研究领域自动选择 PubMed/ArXiv/Semantic Scholar

```yaml
data_source_routing:
  # 领域→数据源映射（覆盖默认映射）
  domain_mapping:
    computational_biology: ["pubmed", "arxiv"]
    neuroscience: ["pubmed"]
    ai: ["arxiv", "semantic_scholar", "pubmed"]
    medicine: ["pubmed"]
    computer_science: ["arxiv", "semantic_scholar"]
    physics: ["arxiv", "semantic_scholar"]
    psychology: ["semantic_scholar", "pubmed"]

  # 各数据源检索上限
  source_limits:
    pubmed: 30           # PubMed 最大检索结果数
    arxiv: 20            # ArXiv 最大检索结果数
    semantic_scholar: 20 # Semantic Scholar 最大检索结果数
```

---

## V6.0 Agent编排配置 (Agent Orchestration)

> Agent 启用/禁用、模型选择、延迟初始化

```yaml
agent_orchestration:
  # Agent 启用状态（设为 false 则跳过该 Agent）
  enabled_agents:
    paper_search: true
    hypothesis: true
    validation: true
    tech_analysis: true
    genai_expert: true
    comp_bio: true
    digital_pathology: true
    biostats: true
    clinical_md: true
    data_hunter: true
    data_governance: true
    resource_estimator: true
    ethics_reviewer: true
    coder: true
    red_team: true
    defense_committee: true
    thesis_writer: true

  # Agent 模型选择（可针对不同 Agent 使用不同模型）
  agent_models:
    hypothesis_agent: "claude-opus-4-6"
    validation_agent: "claude-opus-4-6"
    red_team_agent: "claude-haiku-4-5-20251001"  # 红队可用更便宜模型

  lazy_init: false      # 延迟初始化（true 则按需初始化 Agent）
```

---

## V6.0 否决报告配置 (Rejection Report)

> 科研否决报告生成配置：变废为宝，提供碰撞文献和改进建议

```yaml
rejection_report:
  enabled: true              # 是否生成否决报告
  detail_level: high         # 详细程度：low / medium / high
  min_collision_papers: 3    # 最少碰撞文献数（报告必须包含）
  min_logical_flaws: 2       # 最少逻辑断裂点数（报告必须包含）
  include_alternative_directions: true  # 是否包含替代研究方向建议
```

---

## 热重载说明

> 修改此文件后，系统可热重载配置，无需重启

### 如何触发热重载

在代码中调用：
```python
from core.program_config import reload_program_config
reload_program_config()
```

或在 CLI 中：
```
/reload-config
```

---

## 配置层级优先级

> 配置值的读取优先级（从高到低）

1. **环境变量**: 如 `REDIS_URL`、`TASK_SOFT_TIME_LIMIT`
2. **program.md**: 此文件中的 YAML 配置
3. **默认值**: program_config.py 中的 DEFAULT_CONFIG

---

## 快速修改指南

### 降低 API 调用上限（省钱）
```yaml
defense_layer:
  global_fuse:
    hard_cap: 10  # 从 15 降到 10
```

### 调整假设通过难度
```yaml
hypothesis_generation:
  min_score_threshold: 8.0  # 从 7.5 提高到 8.0
```

### 切换数据源
```yaml
data_source_routing:
  domain_mapping:
    neuroscience: ["pubmed", "semantic_scholar"]  # 新增 S2
```

### 禁用特定 Agent
```yaml
agent_orchestration:
  enabled_agents:
    digital_pathology: false  # 跳过数字病理学 Agent
```

---

## 版本信息

- **配置版本**: v2.0 (V6.0 轻量指令模式)
- **更新日期**: 2026-04-16
- **参考项目**: Karpathy autoresearch (https://github.com/karpathy/autoresearch)