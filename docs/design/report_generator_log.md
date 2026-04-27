# Report Generator 设计日志

## 2026-04-22 - 第一轮补充日志

### 本轮目标
让 `report_generator.py` 不只是“把字段打出来”，而是能把这轮新增的上游字段尽量完整、直观地渲染出来，尤其是：
- 蓝方答辩
- 前沿溯源
- 新字段兼容展示

---

### 改动 1：重写 `_build_blue_defense_rows`
**改了什么**
- 现在优先消费：
  - `committee_response`
  - `committee_discussion`
  - `attack_responses`
- 然后才回退到：
  - red team 原问题
  - technical safeguards
  - recommendations

**为什么改**
之前蓝方答辩虽然已经做过一轮增强，但本质还是靠：
- 技术保障列表
- 总体裁决
去“猜”逐条回应。

既然这次上游已经补了结构化字段，就应该先相信上游，不要继续主要依赖回填推断。

**为什么保留旧回退逻辑**
因为真实任务里未必每次都能拿到新字段，尤其在：
- 老任务结果
- 保守降级路径
- 不完整 payload
下，仍然需要兜底。

**小改动说明**
- `attack_responses` 里如果不是 dict，也尽量按文本展示，而不是直接丢弃
- `committee_discussion` 会先切句，再合并前若干句，避免整段原样灌进表格太难读

---

### 改动 2：蓝方答辩展示顺序调整
**改了什么**
现在蓝方表格大致顺序变成：
1. 委员会结论
2. 总体答辩
3. 委员会讨论
4. 逐项回应
5. 旧式 safeguard 回填
6. 需修复问题
7. 委员会建议

**为什么改**
这是为了更像人读报告的顺序：
先看结论，再看总评，再看细项。

**为什么不把逐项回应放最前面**
因为用户先需要建立全局判断，否则一上来全是细节，阅读成本高。

---

### 改动 3：前沿溯源增加“前沿解读”扩展位
**改了什么**
- 在 `leading_groups` 后增加对：
  - `frontier_analysis.summary`
  - `frontier_analysis.context`
的展示入口

**为什么改**
这次上游增强后，未来 frontier_analysis 很可能不止有列表和表格字段，可能还会携带一段更适合自然语言展示的总结。

**为什么现在先加入口**
这是提前做兼容，避免后面上游加了字段但报告层没显示。

**小改动说明**
- 目前验证样例里这段不一定有值，所以加的是“有则显示”的逻辑，不会影响旧输出

---

### 改动 4：继续保留 `_build_defense_paragraph` 的兜底角色
**改了什么**
这次没有删掉旧 helper，而是让它在新字段缺失时继续工作。

**为什么没删**
虽然现在更推荐直接用 `attack_responses`，但历史 payload 和降级路径里，它仍然是必要的兜底工具。

**取舍说明**
- 现在是“新增结构优先，旧 heuristic 次之”
- 不是“完全抛弃旧逻辑”

这样更稳。

---

### 改动 5：验证中发现一个非渲染器问题
**发生了什么**
验证报告里蓝方答辩 section 没出现完整新内容。

**原因**
不是 `_build_blue_defense_rows` 渲染坏了，而是验证脚本构造的 payload 走到了：
- quick verdict 检测到 safeguards
- 进入 deep deliberation 路径
- 但验证脚本没有真正拿到完整 deep result

导致 `defense_report` 在临时验证 payload 里是空或不完整的。

**为什么把这个写进 report_generator 日志**
因为从用户角度看，很容易误判成“报告渲染器没生效”。实际上问题在验证路径，不在这里。

---

### 当前模块还没做但值得继续做的点
1. `field_signal / key_reference / research_alliance` 这类英文 type 在展示层还能更自然一点
   - 例如映射成中文标签
2. 蓝方答辩表格可以进一步按“总体 / 分项 / 修复清单��分小节，而不只是单表
3. 对超长文本还可以做更精细的分段，而不是仅靠切句拼前几句

### 我建议你后续如果要继续改
优先看：
1. `_build_blue_defense_rows`
2. `_generate_defense_log_section`
3. `_generate_lineage_section`

如果下一步要进一步提升“像历史详细报告”的感觉，最值的是：
- 给 frontier 类型名做中文映射
- 给蓝方答辩拆成多个子区块
- 针对长段 summary 增加更自然的段落输出，而不是全塞表格
