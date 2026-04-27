# Meta-Harness 实验结论摘要

## 2026-04-22 - 第一轮最小实验框架结论

### 本轮目标
把 `research-hypothesis-agent` 现有 Phoenix 工作流先包成一个最小可评估的 Meta-Harness 原型，回答三个问题：
1. 现在这个项目能不能用 harness 方式做结构化比较
2. 哪类增强最值得优先保留
3. 真实报告质量提升主要来自哪几个模块，而不是只凭直觉判断

---

### 本轮完成了什么
已完成：
- 新增最小实验层：`src/meta_harness/`
  - `phoenix_harness.py`
  - `task_sets.py`
  - `evaluator.py`
  - `run_eval.py`
- 用已有结果文件和增强快照构建了最小 task set
- 加入了一份高信号样本：
  - 含 `committee_discussion`
  - 含 `attack_responses`
  - 含 `stage_outputs`
  - 含 `stage_index_path`
- 建立了可重复运行的 candidate 比较框架
- 完成了一轮 candidate 细分实验与 innovation 文本修复回归验证

这意味着后面不需要再靠“看起来好像更详细了”来判断，而是可以用统一分数和对比结果说话。

---

### evaluator 当前在看什么
当前 evaluator 主要看三层：

#### 1. section 完整度
检查报告里是否出现：
- Hypothesis
- Methods
- Lineage
- Defense Log
- Roadmap
- Innovation
- Scoring

#### 2. payload 关键字段存在性
重点检查：
- `defense_report.committee_discussion`
- `defense_report.attack_responses`
- `frontier_analysis.key_publications`
- `frontier_analysis.leading_groups`
- `implementation_roadmap.resources`
- `implementation_roadmap.risks`
- `innovation_analysis.summary`
- `stage_outputs`
- `stage_index_path`

#### 3. 报告正文真实内容
不是只看字段在 payload 里有没有，而是检查正文里是否真的展开出来了，例如：
- 是否有关键出版物 section
- 是否有 timeline / trends
- 是否有蓝方答辩与逐项回应
- 是否还是显示“暂无路线图信息”
- 是否还是显示“暂无创新点分析信息”

这套评估已经足够做第一轮方向性判断。

---

### 本轮实验里最重要的结果

#### 结论 1：`render_only` 基本没价值
在当前实验里，`render_only` 与 `current_baseline` 分数一致。

这说明：
- 只改 `report_generator.py`
- 不补上游 `payload`
- 无法显著提升真实报告质量

这点非常关键，因为它验证了用户之前的直觉是对的：
**不是模板不够像，而是上游内容本身不够。**

---

#### 结论 2：`frontier_analysis + implementation_roadmap` 是最早显著起效的增强组合
在 candidate 细分实验的早期结果中：
- `frontier_only` 明显优于 baseline
- `roadmap_only` 也优于 baseline
- `frontier_roadmap` 一开始是最高分��合

说明在第一轮实验里，最稳定的收益首先来自：
- 前沿溯源更详细
- 路线图更完整

也就是说，用户感知最明显的“报告更像详细样例”提升，首先来自这两块。

---

#### 结论 3：`innovation_only` 最初反而拉低了效果
最初 `innovation_only` 分数甚至不如 baseline，原因不是“创新分析没意义”，而是：
- 文本里有模板占位符没有格式化
- 存在截断句
- 可读性被 evaluator 扣分

这是一个很好的实验信号：
**有些增强模块不是逻辑没用，而是输出文本质量拖了后腿。**

---

#### 结论 4：修完 innovation 可读性后，`full_enhanced` 变成当前最优 candidate
修复内容包括：
- `output_enhancer.py` 中 `breakthrough_potential.factors` 的占位符格式化问题
- `differentiation` 中的硬截断
- `innovation summary` 的截断与段落组织问题
- `research_focus` 过长污染文本的问题

修完并重生成增强快照后：
- `innovation_only` 上升到 `0.5722`
- `roadmap_innovation` 上升到 `0.6384`
- `full_enhanced` 上升到 `0.7338`

而对照项：
- `frontier_roadmap`: `0.6861`
- `current_baseline`: `0.5246`

这说明：
**完整增强路线在文本质量被修正后，已经优于只做 frontier + roadmap 的中间方案。**

---

### 关于 defense / stage outputs 的结论
本轮还确认了两件重要事实：

#### 1. richer defense 字段是有价值的
通过修复 `defense_committee_agent.py` 的 deep deliberation prompt 问题后，已经成功生成了包含以下字段的高信号样本：
- `committee_discussion`
- `attack_responses`

并且报告正文里也能被渲染为更像“逐条答辩”的结构。

#### 2. stage outputs 机制已经可以进入实验闭环
已经成功生成并纳入评估：
- `stage_outputs`
- `stage_index_path`
- `outputs/stages/<task_id>/INDEX.md`

这意味着“每一步都可见”这条需求，不再只是实现功能，而是已经进入可评估状态。

---

### 当前推荐的实验默认基线
如果下一轮继续做 Meta-Harness 实验，我建议默认以：

- `full_enhanced`

作为当前最优基线。

该基线现在也已经被提升为 `src/meta_harness/phoenix_harness.py` 中 `build_default_candidates()` 返回列表里的默认首项，方便后续实验直接把它作为第一参考对象。

理由：
1. 已在混合样本集上取得当前最高平均分
2. 同时覆盖：
   - frontier
   - roadmap
   - innovation
   - richer defense sample
   - stage outputs sample
3. 文本可读性问题已经得到一轮实证修复
4. 当前实验表明，它已经优于 `frontier_roadmap` 这样的中间增强组合

---

### 当前不建议优先做的方向
1. 单独继续打磨 `render_only`
   - 收益太低
2. 在没有新 sample 的情况下继续调 evaluator
   - 当前 evaluator 已足够支撑方向判断
3. 过早引入 proposer 自动搜索
   - 现在更值得先固定基线和补样本池

---

### 我建议下一轮优先做什么
按优先级排序：

#### 优先级 1：继续扩高信号 task set
尤其是再补：
- 更多真实 defense-rich 样本
- 更多包含 `stage_outputs` / `stage_index_path` 的成功任务
- 不同领域的 rich sample

#### 优先级 2：把 `full_enhanced` 当作正式实验基线
后续所有 candidate 和模块性优化，都先和它比，而不是和旧 baseline 比。

#### 优先级 3：如果再做模块优化，优先看这两块
- defense richer output 的稳定下传
- frontier / roadmap / innovation 中过长文本的进一步中文化和压缩表达

---

### 本轮一句话总结
第一轮 Meta-Harness 原型实验已经证明：

**Phoenix 报告质量的真实提升，主要来自上游 richer payload + 结构化增强内容，而不��单纯渲染层修补；当前最优默认基线已经变成 `full_enhanced`。**
