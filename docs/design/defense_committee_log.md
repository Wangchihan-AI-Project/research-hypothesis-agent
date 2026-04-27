# Defense Committee 设计日志

## 2026-04-22 - 第一轮补充日志

### 本轮目标
让 `defense_report` 不再只有简短裁决，而是能为报告层提供更完整、可展开的蓝方答辩素材，尤其是：
- 委员会讨论摘要
- 按攻击类型拆开的回应内容
- 快速裁决/保守裁决路径下也有足够信息量

---

### 改动 1：补了 `_extract_technical_safeguards`
**位置**: `src/agents/defense_committee_agent.py`

**改了什么**
- 新增 `_extract_technical_safeguards(blue_package)`
- 统一从 `blue_package -> hypothesis_data -> methodology -> technical_safeguards` 提取措施
- 兼容 `list` 和单字符串

**为什么改**
之前代码在多个分支里各自手写 safeguards 提取逻辑，后续如果要扩展快速裁决、保守裁决、逐攻击回应，会不断重复。

**为什么这样做**
选择抽成单独 helper，而不是每个分支继续内联读取，是为了让：
- 快速裁决
- 深度审议前准备
- 保守裁决
都复用同一份预处理结果。

**小改动说明**
- 如果 `methodology` 不是 dict，直接返回空列表，而不是报错
- 如果 safeguards 是单个字符串，也转成单元素列表，避免后面分支判断过多

**你如果要改**
- 想支持更多来源时，可从这个 helper 往外扩，比如补 `validation_protocol`、`bias_control` 的联合提取

---

### 改动 2：补了 `_summarize_issue_labels`
**改了什么**
- 新增问题摘要 helper，把 `critical_flaws / severe_issues` 压成可直接写进裁决文案的短摘要

**为什么改**
之前快速裁决里的 `committee_response` 太短，只会说“发现 N 个问题”，但没有告诉用户最关键的问题是什么。

**为什么不直接拼原始列表**
- 原始列表太长，不适合塞进一句裁决
- 直接 `str(list)` 可读性差，容易又回到 Python 原样输出的问题

**小改动说明**
- 对非 dict 条目也做了兼容，避免历史/异常 payload 直接丢信息

---

### 改动 3：补了 `_build_attack_responses`
**改了什么**
- 新增按攻击类型组织的答辩结构
- 输出字段形态为：
  - `attack_type`
  - `issue`
  - `response`

**为什么改**
这是这轮上游增强的核心之一。报告层之前只能拿到：
- `committee_response`
- `final_verdict`
- `recommendations`

这不足以把蓝方答辩展开成“按问题类别逐条回应”的样子，所以必须在上游先产出结构化字段。

**为什么字段这样命名**
- 没直接叫 `defense_points`，因为这里本质上是“对攻击的回应”
- `attack_responses` 更贴近当前数据来源和展示用途

**小改动说明**
- 如果某条红方问题不是 dict，也会尽量转成一条可显示记录
- safeguard / suggestion / recommendation 会按顺序拼接，尽量保留信息量

**当前局限**
- 目前还是启发式拼接，不是 LLM 为每一条攻击单独长篇生成
- 但已经足够让报告层展开，不再只剩一段总评

---

### 改动 4：补了 `_build_committee_discussion`
**改了什么**
- 新增委员会讨论摘要构造逻辑
- 会把：
  - 致命缺陷数量
  - 严重问题数量
  - 中等疑虑数量
  - 关键问题摘要
  - safeguards 摘要
组合成一段更完整的 discussion

**为什么改**
prompt 里原本已经要求 `committee_discussion`，但快速裁决和保守裁决根本没这部分；所以即使不进入深度审议，也应该有一个可展示的 discussion。

**为什么不直接复用 `committee_response`**
- `committee_response` 偏“正式裁决口径”
- `committee_discussion` 更适合提供内部推理摘要，供报告层展开
- 两者语义不同，保留双字段更利于下游渲染

---

### 改动 5：重写 `_quick_verdict` 的结果结构
**改了什么**
- 在 definitive 的 fail / pass 分支里新增：
  - `committee_discussion`
  - `attack_responses`
- 同时把 `committee_response` 从“纯短句”扩成“短裁决 + 关键问题摘要”

**为什么改**
之前快速裁决一旦触发，信息量会突然塌缩，后面的报告生成器再强也无能为力。

**本次取舍**
- 保留“有 safeguards 时进入深度审议”的旧行为，不直接改掉
- 因为这条逻辑本身是合理的，当前主要问题不是它存在，而是 definitive 分支太短

**小改动说明**
- `critical_issues` / `recommendations` 现在都加了 `isinstance(..., dict)` 判断，避免异常结构导致报错

---

### 改动 6：扩展深度审议 prompt 的 JSON 输出要求
**改了什么**
- 在 `_build_deliberation_prompt` 里，给 LLM 的 JSON 结构新增：
  - `attack_responses`
- 同时把 `committee_discussion` 描述写得更明确：
  - 需要比 `committee_response` 更细
  - 要体现角色争议和共识

**为什么改**
如果 prompt 不要求，深度审议就算本来能写更细，也不会稳定返回结构化字段。

**为什么不一次塞更多字段**
我刻意没一下子加太多字段，比如主席意见/方法论专家意见/领域专家意见分栏，因为那会让当前解析和报告层改动面更大。先把最有价值、最容易消费的字段落地。

---

### 改动 7：扩展 `_parse_deliberation_response`
**改了什么**
- 之前只保留：
  - `committee_response`
  - `final_verdict`
  - `critical_issues`
  - `recommendations`
- 现在额外保留：
  - `committee_discussion`
  - `attack_responses`

**为什么改**
这是之前最直接的信息损失点：prompt 要了，但 parse 阶段丢了。

**小改动说明**
- 继续保留原字段兼容，不会破坏旧调用方

---

### 改动 8：扩展 `_conservative_verdict`
**改了什么**
- 保守裁决现在也会返回：
  - `committee_discussion`
  - `attack_responses`

**为什么改**
之前如果深度审议失败，系统会退回保守裁决，结果又变成短文本，导致信息量断崖式下降。

**为什么重要**
这类“失败时降级”路径特别容易让最终报告变差，所以这次特意补上。

---

### 本模块当前已知问题
1. 有 safeguards 时仍优先进入深度审议，这会导致如果验证脚本没真正跑完 deep path，报告里看不到新增字段
2. `attack_responses` 目前是规则拼接，信息密度比历史长文仍弱一些
3. prompt 里虽然要求更细，但真实返回质量仍取决于 LLM 输出稳定性

### 我建议你后续如果要继续改
优先看这几个点：
1. `_quick_verdict`
2. `_build_attack_responses`
3. `_build_deliberation_prompt`
4. `_parse_deliberation_response`

如果你想把委员会输出做得更像“逐专家辩论纪要”，下一步最自然的扩展点就是在深度审议 JSON 里加入：
- `chair_opinion`
- `methodology_opinion`
- `domain_opinion`
- `clinical_opinion`

但我这次先没这么做，是为了控制改动面。
