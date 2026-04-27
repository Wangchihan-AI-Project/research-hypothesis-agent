# Output Enhancer 设计日志

## 2026-04-22 - 第一轮补充日志

### 本轮目标
把 `output_enhancer.py` 从“结构化摘要生成器”往“更接近详细报告素材生产器”方向推一层，重点补强：
- frontier_analysis
- implementation_roadmap
- innovation_analysis

目标不是伪造新内容，而是把已有输入信息组织成更可读、更像研究报告的文本和结构。

---

### 改动 1：新增 `_build_domain_context`
**改了什么**
- 从 `title / details / methodology / domain` 中抽关键词
- 输出类似：
  - 以机器学习/预测建模为核心
  - 强调临床或队列场景落地
  - 突出因果识别与偏倚控制

**为什么改**
以前创新分析和前沿分析都缺一个“这是哪类问题”的高层概括，只能直接丢分数和条目，读起来像碎片。

**为什么做成 helper**
因为它会同时服务：
- 创新总结
- 突破潜力说明
- 方法论上下文补充

**小改动说明**
- 如果一个标签都匹配不上，会回退到通用描述，而不是返回空字符串

---

### 改动 2：新增 `_infer_research_focus`
**改了什么**
- 从 `core_hypothesis / details / title / background` 中提取最适合作为“研究焦点”的文本
- 过长时截到 120 字左右

**为什么改**
之前 roadmap、frontier、innovation 各自都在说抽象概念，缺少一个稳定的“当前问题焦点”锚点。

**为什么要截断**
不截断的话，后面很多 narrative 字段会过长，表格里尤其容易变得难看。

**小改动说明**
- 这属于典型的小改动，但很重要：它控制了后续文本长度，否则会到处出现超长句

---

### 改动 3：`generate_innovation_analysis` 增加上下文信息
**改了什么**
- 增加 `inferred_domain` 兜底读取
- 计算 `domain_context`
- 计算 `research_focus`
- 把这些信息写入：
  - `breakthrough_potential`
  - `methodology_analysis`
  - `summary`

**为什么改**
之前创新分析太像“打分解释器”，缺少对研究问题本身的落点描述。

**本次踩到的问题**
- 一开始误用了不存在的 `domain` 变量，触发 `NameError`
- 后来改成从 hypothesis 里兜底取 `domain / field`

**为什么把这个小 bug 记下来**
因为这就是你希望我保留的“小改动日志”——这种变量来源问题以后很容易再次出现，记下来你回头看会更清楚。

---

### 改动 4：重写 `_generate_innovation_summary`
**改了什么**
- 从原来的“几行摘要 + 打分”改成多段式总结
- 现在会写：
  - 创新定位
  - 研究焦点
  - 核心创新点列表
  - 差异化总结
  - 向量新颖度与相似度解释
  - 突破潜力总结
  - 收尾判断

**为什么改**
历史详细样例的一个明显特征是：不是“有创新点列表”就够了，而是会解释“为什么这算创新”。

**为什么没改成纯表格**
创新总结这块更适合段落，不适合只做表格；表格会留下，但 summary 必须是长文本。

---

### 改动 5：`generate_frontier_analysis` 不再只按 PMID 数量走模板
**改了什么**
- 引入 `research_focus`
- 在 `gap_analysis` 末尾追加更贴近当前焦点的缺口描述
- `key_publications / leading_groups / timeline` 都改为依赖更多上下文

**为什么改**
此前最大的问题是：
- 有文献就说“研究活跃”
- 没文献就说“可能原创”
这太模板化了。

**为什么先做启发式增强而不是接入更多外部文献元数据**
- 当前任务重点是先让真实报告更像详细报告
- 真要做到更真实的团队/作者层分析，需要引入更多元数据源，改动会大很多

---

### 改动 6：重写 `_interpret_publications`
**改了什么**
- 新增：
  - `field_signal`
  - `key_reference`
  - `preprint_signal`
- 每条内容不再只是“作为关键参考文献引用”，而是补了“处于什么角色、说明什么问题”

**为什么改**
之前用户看到 PMID 表格时，信息密度太低，几乎没有阅读价值。

**当前取舍**
- 仍然没有真实去抓取标题/摘要
- 只是把已有 ID + 上下文转成更像人写的说明

这是有意的：先把报告观感和解释性拉起来，再决定要不要做更重的文献元数据增强。

---

### 改动 7：重写 `_infer_leading_groups`
**改了什么**
- 不再只返回“建议使用文献计量学工具分析”
- 改成至少返回三类可读对象：
  - research_alliance
  - methodology_team
  - literature_signal

**为什么改**
之前这一段对用户几乎没有信息增量，看起来像占位符。

**为什么现在仍然保留 `action` 字段**
因为 report_generator 已经会展示“建议动作”，保留这个结构能最小代价地提升可读性。

---

### 改动 8：重写 `_construct_frontier_timeline`
**改了什么**
- 时间线仍然保留四段式
- 但描述改成会引用：
  - `domain`
  - `focus`
  - `stage_hint`

**为什么改**
之前的 timeline 完全是固定模板，几乎所有主题看起来都一样。

**为什么没有取消四段式结构**
因为当前 report_generator 已经非常适合消费固定 list[dict] 时间线；如果这里大改结构，会把适配面扩大。

所以这次只换描述，不换骨架。

---

### 改动 9：增强 `_generate_resources`
**改了什么**
- 人力描述变具体，不再只是“1人、2人”
- equipment 和 data 增加 narrative
- 增加 coordination 段

**为什么改**
用户之前明确说 roadmap / resources 不直观、像 Python dict。即使 report_generator 解决了展示问题，如果内容本身还是占位式，也不够像详细报告。

**为什么增加 `narrative` 和 `coordination`**
- `narrative` 是为了给表格外的一点解释性文本素材
- `coordination` 是为了让资源需求更像真实项目规划，而不只是一张清单

---

### 改动 10：增强 `_generate_risks`
**改了什么**
- 风险文案整体变细
- 增加 `方法学风险`
- 会把 `research_focus` 带入风险描述

**为什么改**
以前 risk 太通用，缺少对当前任务最核心风险的点名，尤其是机器学习/因果类任务的泄漏与偏倚风险。

**小改动说明**
- 用关键词判断 `research_focus` 是否涉及因果/模型，是个简单启发式，不是完美分类器
- 但足够支撑当前报告目的

---

### 改动 11：增强 `_generate_feasibility_notes`
**改了什么**
- 可行性备注现在会引用 `research_focus`
- 增加了执行提醒
- 不再只说“评分高/中/低”

**为什么改**
这一段原来太像分数注释，不像给研究者的落地提醒。

**为什么要补 `执行提醒`**
因为这类提示恰好是用户实际会拿来改计划的内容，不该只给抽象判断。

---

### 本模块当前局限
1. 仍然没有真正抓取 PMID 元数据，所以“关键出版物解读”还不够真实
2. leading_groups 目前仍是高质量启发式，不是真正从作者/机构共现分析得出
3. innovation summary 虽然更长了，但仍偏模板化，还可以继续往历史样例靠

### 我建议你后续如果要继续改
优先看：
1. `_interpret_publications`
2. `_infer_leading_groups`
3. `_generate_innovation_summary`
4. `_generate_resources`
5. `_generate_feasibility_notes`

如果下一步要更进一步，最值得做的是：
- 给 publication 增加真实标题/年份/期刊信息
- 给 leading_groups 增加真实作者/机构归纳
- 给 innovation_analysis 引入更细的 narrative 模板分支
