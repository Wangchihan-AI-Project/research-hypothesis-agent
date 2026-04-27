# Stage Outputs 设计日志

## 2026-04-22 - 第一轮补充日志

### 本轮目标
在多智能体流程中，为每个关键阶段留一个用户可见的中间产物文件，避免用户只能看到最终结果，看不到：
- hypothesis 生成后到底长什么样
- red team 实际输出了什么
- defense 拿到了什么并给了什么判断
- enhancer 生成了哪些补充材料
- final report 前的最终 payload 是什么

---

### 改动 1：在 `celery_tasks_v75.py` 中增加阶段输出 helper
**改了什么**
新增了：
- `_get_stage_output_dir`
- `_build_stage_markdown`
- `_write_stage_output`

**为什么改**
如果把阶段输出写入逻辑散落在每个状态分支里，后面很快会失控；统一 helper 更方便维护。

**为什么同时写 JSON 和 Markdown**
- JSON 适合程序检查、排查结构字段
- Markdown 适合你直接打开看内容

**小改动说明**
- 文件路径统一放在：`outputs/stages/<task_id>/`
- 文件名带顺序号，避免阶段多了之后排序混乱
- `stage_name` 做了安全字符清洗，避免路径名里出现奇怪字符

---

### 改动 2：在演化循环开始前写入 `user_input` 阶段
**改了什么**
在进入多阶段演化前，先写：
- 原始输入
- user_domain
- detected_domain
- sources
- verified_ids

**为什么改**
你提的核心需求是“到下一个智能体前能看到上一个输出”。第一步当然应该是先把流程入口固定下来，不然连最开始系统拿到了什么都看不到。

---

### 改动 3：在 hypothesis 生成后立即留档
**改了什么**
新增阶段文件：
- `iteration_X_hypothesis`

**为什么改**
这是后续所有 agent 的共同输入源，最值得先看。

**为什么放在解析/保存后、物理锚定前**
因为这个时点最能代表“PI 智能体产出的原始结果”，还没被后续重写/补丁污染。

---

### 改动 4：在 red team 后留档
**改了什么**
新增阶段文件：
- `iteration_X_red_team`

**为什么改**
这样你能直接看到红方是怎么攻击的，不需要等到最终报告再间接看摘要。

---

### 改动 5：在 defense 后留档
**改了什么**
新增阶段文件：
- `iteration_X_defense`

**为什么改**
这是你最关心的链路之一：
- red team 说了什么
- defense 怎么回应
- 最终有没有通过

如果这个阶段不单独落盘，很多问题只能从最终 report 倒推，不直观。

---

### 改动 6：重写 / patch / compensation 阶段也留档
**改了什么**
新增：
- `iteration_X_rewrite`
- `iteration_X_patch`
- `iteration_X_compensation`

**为什么改**
这些阶段是凤凰协议真正发生“自我修复”的地方，如果不留档，你就不知道到底改了什么。

**为什么 compensation 额外保存 external algorithms**
因为补偿阶段不只是新 hypothesis，还有“为什么这样补”的外部算法来源，这对你判断这一步是否合理很重要。

---

### 改动 7：enhanced output 单独留档
**改了什么**
新增：
- `enhanced_output`

**为什么改**
这一步是 report 详细度的关键来源之一，值得单独看，而不是只混在 final payload 里。

---

### 改动 8：final payload 单独留档，并回写到 payload 内
**改了什么**
- 成功路径下新增：`final_payload`
- 同时把 `stage_outputs` 列表塞回最终 `payload`

**为什么改**
这样你可以：
1. 在文件系统里直接看每一步
2. 在最终任务结果里也拿到这些阶段文件的路径索引

这两层入口都保留，查问题更方便。

---

### 本轮中途修复的小问题
**问题**
第一次写 helper 时，误把带 `+` 的 patch 标记直接写进了 Python 文件。

**修复**
随后清掉了这些 `+`，并重新检查 helper 代码块。

**为什么记这个**
这就是典型的小改动日志：不是业务逻辑，但会影响代码是否能跑。

---

### 改动 9：新增单次任务的 `INDEX.md`
**改了什么**
- 新增 `_write_stage_index`
- 在 `outputs/stages/<task_id>/` 下自动生成 `INDEX.md`
- 把每个阶段的 `.md` / `.json` 链接串起来

**为什么改**
如果阶段文件越来越多，用户逐个找会很累。索引页可以把一次任务的所有中间产物按顺序列出来，直接点开看。

**为什么还保留 `stage_outputs` 字段**
因为：
- `INDEX.md` 适合人看
- `stage_outputs` 适合程序拿路径

两层入口保留更稳。

**小改动说明**
- 在 `_write_stage_output` 返回值里补了 `order`，这样索引页可以稳定排序
- 成功任务的最终 `payload` 里会再加一个 `stage_index_path`

---

### 当前阶段输出文件的预期位置
- `outputs/stages/<task_id>/stage_00_user_input.*`
- `outputs/stages/<task_id>/stage_11_iteration_1_hypothesis.*`
- `outputs/stages/<task_id>/stage_12_iteration_1_red_team.*`
- `outputs/stages/<task_id>/stage_13_iteration_1_defense.*`
- ...
- `outputs/stages/<task_id>/stage_90_enhanced_output.*`
- `outputs/stages/<task_id>/stage_99_final_payload.*`

每个阶段都会同时有：
- `.json`
- `.md`

---

### 当前局限
1. 目前阶段输出是文件级留档，还没有自动在前端 UI 中做分步展示
2. 如果某阶段没执行成功，就不会有对应文件，这是正常现象，但需要你知道不是“漏写”，而是“没走到”
3. 现在还没给这些 stage 输出做专门的目录索引页，后面可以再补

### 你后续如果要继续改
优先看：
1. `_write_stage_output`
2. 演化循环里各状态分支调用 `_write_stage_output` 的位置
3. 最终 payload 中 `stage_outputs` 的写入逻辑

如果下一步继续增强，我建议：
- 再补一个 `outputs/stages/<task_id>/INDEX.md`
- 把每个阶段文件自动链接起来
- 这样你看单次任务会更顺手
