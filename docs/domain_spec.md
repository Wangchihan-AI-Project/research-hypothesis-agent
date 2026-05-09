# Domain Spec: Phoenix Research Hypothesis Agent

## Domain Summary

本领域的目标是提升 `research-hypothesis-agent` 这一多智能体研究假说生成系统的最终输出质量，使其真实任务生成的 Markdown 报告更接近 `DETAILED_OUTPUT_REPORT.md` 这类高信息密度、强结构化、用户可直接阅读的详细样例，而不是停留在摘要化、模板化或字段缺失的结果。

当前项目的真实执行主链路由 `src/core/celery_tasks_v75.py` 驱动，其核心阶段已经相对稳定：
- user_input
- hypothesis generation
- red team critique
- defense committee review
- rewrite / patch / compensation
- output enhancement
- final report generation

一个 evaluation unit 定义为：一次完整的 research task 输入及其对应的 Phoenix 多阶段执行过程，以及该过程产出的：
- 最终 `payload`
- 最终 Markdown 报告
- `stage_outputs`
- `stage_index_path`
- 关键中间结构（如 `defense_report`、`frontier_analysis`、`implementation_roadmap`、`innovation_analysis`）

固定不变的部分：
- 主要任务目标：围绕用户输入生成研究假说与完整报告
- 当前 Phoenix 协议的大阶段拓扑，不在首轮搜索中整体推翻
- 现有主执行入口仍以 `src/core/celery_tasks_v75.py` 为准
- 首轮 Meta-Harness 化只搜索 harness logic，不搜索底座模型替换

允许变化的部分：
- 各阶段之间传递哪些字段，以及哪些字段必须保真保留到最终 payload
- 哪些中间产物被完整保留、压缩、重写或同时以 JSON/Markdown 暴露给下游与用户
- `src/agents/defense_committee_agent.py` 输出的 defense 结构粒度
- `src/core/output_enhancer.py` 输出的 frontier / roadmap / innovation 粒度
- `src/core/report_generator.py` 对上游结构的消费与展示顺序
- 是否引入不同的 context construction、memory retention、stage summarization、field selection、candidate branching 策略

冻结 base model：
- 第一阶段默认固定当前项目使用的主模型调用方式，不在首轮 Meta-Harness 搜索中变更模型或新增外部基础设施
- 搜索对象限定为 harness logic，而非换模型

优化预算：
- 初始预算建议以“候选 harness 数 × 真实任务样本数”计
- 保守起步建议：
  - search set: 20-30 个真实或准真实 research tasks
  - held-out set: 10-15 个未参与搜索的任务
  - 每轮候选 harness: 3-5 个
  - 每次迭代只做 1-2 个演化轮次
- 如果成本压力较大，可先对单阶段子问题做局部搜索，例如先只优化 `defense_report -> report_generator` 子链路

## Harness and Search Plan

每个 candidate harness 必须满足统一接口：
1. 接收同样的用户输入与任务配置
2. 跑完整或受控裁剪后的 Phoenix workflow
3. 输出统一结构的最终 `payload`
4. 保留阶段输出、评估结果与日志
5. 可被统一 evaluator 调用并比较

建议的基础 Python 接口形状：

```python
class PhoenixHarness:
    def run(self, task_input: dict) -> dict:
        """
        Return:
        {
            "payload": {...},
            "report_path": "...",
            "stage_outputs": [...],
            "stage_index_path": "...",
            "metrics": {...},
            "metadata": {...}
        }
        """
```

当前项目中最适合优先纳入 harness 搜索空间的真实模块是：
- `src/agents/defense_committee_agent.py`
- `src/core/output_enhancer.py`
- `src/core/report_generator.py`
- `src/core/celery_tasks_v75.py` 中的阶段输出与 payload 保留逻辑

建议优先使用“参数化 harness”而不是“一开始让 proposer 任意改整个工程”。当前最值得参数化的项目内真实变化点包括：
- `defense_report` 是否强制包含：
  - `committee_response`
  - `committee_discussion`
  - `attack_responses`
  - `critical_issues`
  - `recommendations`
- `frontier_analysis` 是否强制包含：
  - `key_publications`
  - `research_trends`
  - `gap_analysis`
  - `leading_groups`
  - `timeline`
  - `year_trend`
- `implementation_roadmap` 是否强制包含：
  - `phases`
  - `resources`
  - `timeline`
  - `risks`
  - `feasibility_notes`
- `innovation_analysis` 是否强制包含：
  - `core_innovations`
  - `novelty_level`
  - `differentiation`
  - `breakthrough_potential`
  - `summary`
- 报告层是否优先展示 structured fields，而不是回退到 heuristic 拼接
- 阶段输出是否保留全文、摘要或双轨输出
- 是否在成功任务里强制回写：
  - `stage_outputs`
  - `stage_index_path`

接口合规性测试：
- `payload` 必须存在且能被 `report_generator` 消费
- report 文件必须生成成功
- `stage_outputs` 必须结构完整
- `outputs/stages/<task_id>/INDEX.md` 必须生成成功
- 不允许 Python 异常、空报告、关键字段缺失
- 必须通过一组轻量 smoke tasks

明确不在首轮范围内的变化：
- 更换底座模型
- 引入全新的外部搜索系统/检索引擎
- 重写整套 Celery 基础设施
- 直接把 UI 层纳入搜索空间
- 把评估目标改成完全人工主观判断而没有结构化标准
- 任意改写整个多阶段拓扑

## Evaluation Plan

### Search-set evaluation
search set 使用真实 Phoenix 任务样本，优先覆盖不同领域与不同复杂度输入。每个 candidate harness 在 search set 上运行并生成：
- 最终报告
- 中间阶段输出
- 结构化指标
- 失败原因与异常路径

当前项目里，优先应验证的并不是“能不能跑”，而是“真实任务下报告是否真的够详细”。因此 search set 评估必须重点观察：
- 蓝方答辩是否不再只剩短裁决
- 红蓝对抗是否可按问题类别展开
- 前沿溯源是否不再只剩 PMID 数量说明和固定模板时间线
- 路线图 / resources / risks / feasibility notes 是否像真实研究计划
- 报告中是否仍出现 Python list/dict 原样字符串或截断残句

### Held-out evaluation
held-out set 使用未参与搜索的任务，避免 harness 只对少数高频模板输入过拟合。建议按以下维度做分层拆分：
- 学科领域
- 输入长度
- 方法复杂度
- 是否会触发 rewrite / patch / compensation
- 是否包含较强的 red team 攻击

### Primary metrics
建议主指标不是单一分数，而是组合质量指标：

1. 报告完整度
- `Hypothesis / Methods / Lineage / Defense Log / Roadmap / Innovation / Scoring` 等 section 是否齐全
- 是否缺少关键上游字段的展示

2. 细节密度
- 是否具有足够具体的信息，而非空泛模板句
- 是否能展开说明研究设计、风险、资源与创新点

3. Defense quality
- `defense_report` 是否包含逐类攻击回应
- 是否包含 `committee_discussion`
- 是否包含 `critical_issues` 与 `recommendations`
- 报告层是否真的展示了这些字段

4. Lineage quality
- 是否包含 `key_publications`、`leading_groups`、`timeline`、`year_trend`
- 是否从结构化数据转成可读内容，而不是生硬拼接

5. Roadmap quality
- 是否包含 `phases`、`resources`、`risks`、`feasibility_notes`
- 是否对真实研究落地有指导价值

6. Innovation quality
- 是否不仅有打分，还能给出差异化、突破潜力与总结段落

7. Readability
- 最终 markdown 是否直观
- 是否避免原始 list/dict 泄露到展示层
- 表格与段落顺序是否符合用户阅读习惯

### Secondary metrics
- 运行时长
- token / API 成本
- 各阶段失败率
- 是否触发 fallback 路径
- 报告中断率
- 关键字段在 payload 中的保留率
- `stage_outputs` 完整率
- `stage_index_path` 回写成功率

### Noise
该任务评估天然带有一定噪声，因为生成式模型输出存在波动。缓解方式：
- 对关键样本重复运行少量试次
- 使用结构化 rubric，而不是只看单次主观印象
- 优先关注明显优势而非极小差异
- 将“字段存在性”与“文本质量”拆开评分

### Candidate runtime
单个 candidate 的评估成本较高，因为需要完整跑多阶段工作流。建议：
- 先做 smoke search
- 再做 restricted search
- 最后只对 frontier candidates 跑完整 held-out

当前项目内可以先用较便宜的验证路径做第一轮 bring-up：
- 先验证 `defense_committee_agent.py` 与 `report_generator.py` 子链路
- 再验证 `output_enhancer.py` 生成的 `frontier_analysis / implementation_roadmap / innovation_analysis`
- 最后再跑完整 Phoenix 成功路径

### Leakage / contamination risk
本项目很容易出现“对某几个已知样例越调越像”的问题。需要防止：
- 用 `DETAILED_OUTPUT_REPORT.md` 直接当优化目标而不是参考风格
- proposer 在 search 时直接接触 held-out 结果
- 把少量验证任务的输出结构硬编码进 harness
- 只对你最近看过的几个样例任务越调越像，而对真实新输入无提升

缓解方式：
- held-out 任务严格隔离
- 指标尽量结构化
- 区分“风格对齐”与“样例复制”
- 保留每轮 candidate 的日志与差异报告
- 用不同领域、不同攻击强度的任务做交叉验证

## Baselines

建议至少保留以下 baseline：

1. Current Phoenix baseline
- 当前主分支工作流，不额外增强
- 以 `src/core/celery_tasks_v75.py` 当前成功路径为准

2. Render-only baseline
- 只改 `src/core/report_generator.py`
- 不改上游 payload 丰富度

3. Upstream-enhanced baseline
- 增强 `src/agents/defense_committee_agent.py` 与 `src/core/output_enhancer.py`
- 报告层保持最小兼容

4. Full-enhanced baseline
- `defense_committee_agent.py` + `output_enhancer.py` + `report_generator.py` 全部增强
- 当前你最近一轮工作已经接近这一版

5. Stage-output baseline
- 同样的主流程，但强制保留所有中间产物
- 用于分析“可见性是否提升调优效率”

建议从一开始就复用的 helper：
- `_write_stage_output`
- `_write_stage_index`
- 统一 report quality scorer
- 统一 payload field-presence checker
- 统一 candidate run logger
- 统一 task split loader

## Experience and Logging

### Offline experience
当前项目可直接利用的离线经验包括：
- `DETAILED_OUTPUT_REPORT.md`
- 历史自测生成报告
- 过去“蓝方太短 / 前沿太模板 / 路线图太空泛 / innovation 太摘要化”的失败案例
- `docs/design/` 下按模块编写的设计日志
- `outputs/stages/<task_id>/` 下的阶段输出与单任务 `INDEX.md`

这些内容适合作为 proposer context，而不是直接作为目标答案。

### Online experience
每个 candidate 应存储：
- candidate 配置/变更摘要
- 最终 payload
- report 文件
- `stage_outputs` 列表
- `stage_index_path`
- 每个关键阶段的输入/输出摘要
- evaluator 指标
- 异常与 fallback 记录
- 与 baseline 的差异说明

高信号调试产物：
- `defense_report`
- `frontier_analysis`
- `implementation_roadmap`
- `innovation_analysis`
- final report markdown
- `outputs/stages/<task_id>/INDEX.md`

建议目录结构：

```text
meta_harness_runs/
  run_001/
    candidates/
      candidate_001/
        config.json
        metrics.json
        summary.md
        tasks/
          <task_id>/
            report.md
            payload.json
            stages/
              INDEX.md
              ...
    frontier.json
    evolution_summary.jsonl
```

建议增加一个小 CLI：
- `list-runs`
- `show-candidate <id>`
- `diff-candidates <a> <b>`
- `show-task <candidate> <task_id>`
- `show-frontier`
- `export-best`

## Open Questions and Unknowns

- 报告质量 rubric 是否完全自动化，还是需要半自动人工打分
- 真实任务样本池的规模与可用性
- 每轮可承受的 API 预算
- 是否允许在首轮搜索中改写阶段拓扑，而不只是改字段与渲染
- 是否需要把“用户中途可干预”也纳入 harness 搜索空间
- candidate harness 第一版是否只允许改 config，不允许直接改源码
