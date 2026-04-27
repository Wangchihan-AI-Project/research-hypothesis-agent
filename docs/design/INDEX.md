# 设计日志索引

## 阅读顺序建议
1. [`report_generator_log.md`](./report_generator_log.md)
   - 先看报告最终是如何被渲染出来的
   - 适合快速理解“用户最终会看到什么”

2. [`defense_committee_log.md`](./defense_committee_log.md)
   - 再看蓝方答辩与委员会输出是如何生成的
   - 适合理解 Defense Log 为什么能展开、哪些字段来自上游

3. [`output_enhancer_log.md`](./output_enhancer_log.md)
   - 再看前沿分析、路线图、创新分析这些内容素材是如何补强的
   - 适合理解为什么报告细节会变多、哪些地方仍然偏模板化

4. [`stage_outputs_log.md`](./stage_outputs_log.md)
   - 最后看多阶段流程是如何留中间产物的
   - 适合理解每个智能体之间会保留哪些可见输出文件

5. [`meta_harness_experiment_log.md`](./meta_harness_experiment_log.md)
   - 再看 Meta-Harness 最小实验框架跑出了什么结论
   - 适合理解哪类增强最值、当前默认基线应该选什么

---

## 各文件用途

### `report_generator_log.md`
关注点：
- 报告层如何消费上游字段
- 蓝方答辩如何渲染
- 前沿溯源如何展示
- 新字段如何兼容旧 payload

适合你在这些情况下先看：
- 觉得“显示出来的格式不对”
- 想改表格、段落、分节顺序
- 想知道为什么某段内容没显示出来

---

### `defense_committee_log.md`
关注点：
- `defense_report` 增加了哪些新字段
- 快速裁决 / 深度审议 / 保守裁决 各自产出什么
- 为什么加入 `committee_discussion` 和 `attack_responses`

适合你在这些情况下先看：
- 觉得蓝方答辩太短
- 想把委员会输出改得更像“逐条答辩”或“逐专家讨论”
- 想知道报告层某条蓝方内容到底来自哪里

---

### `output_enhancer_log.md`
关注点：
- `frontier_analysis`
- `implementation_roadmap`
- `innovation_analysis`
的上游生成逻辑为什么这样设计

适合你在这些情况下先看：
- 觉得前沿分析太模板化
- 觉得路线图、资源、风险还不够像真实研究计划
- 想继续把创新分析写得更像长文

---

### `stage_outputs_log.md`
关注点：
- 多阶段流程如何留中间产物
- 每个智能体前后会写出哪些阶段文件
- 最终 payload 如何索引这些阶段输出
- 单次任务的 `INDEX.md` 如何组织阶段文件

适合你在这些情况下先看：
- 想看到每一步智能体到底产出了什么
- 想排查是哪一个阶段开始变差
- 想把阶段输出进一步做成 UI 或索引页

---

### `meta_harness_experiment_log.md`
关注点：
- Phoenix Meta-Harness 最小实验框架目前能评估什么
- 哪类增强真正带来了分数提升
- 为什么 `render_only` 无效、为什么 `full_enhanced` 变成当前最优基线

适合你在这些情况下先看：
- 想知道当前实验默认基线该选什么
- 想知道下一轮是继续补样本还是开始做 proposer
- 想快速回看这一轮实验到底得出了哪些结论

---

## 我后续追加日志的规则
后面我会继续按这个规则追加：
- 每次按模块写入对应日志
- 记录大改动和小改动
- 写清：
  - 改了什么
  - 为什么改
  - 为什么不选别的方案
  - 当前局限
  - 如果你要继续改，建议从哪下手

---

## 当前状态
当前已补的日志对应的是 2026-04-22 这一轮关于以下内容的改动复盘：
- 防御委员会输出增强
- 输出增强器文本补强
- 报告生成器对新字段的适配
- 多阶段流程的阶段输出留档设计与实现
