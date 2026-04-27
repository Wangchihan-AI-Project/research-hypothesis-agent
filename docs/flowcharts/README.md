# 凤凰协议流程图索引

## 文件列表

| 文件 | 图表名称 | 描述 |
|------|----------|------|
| `01_main_flow.mmd` | 主流程图 | 从用户输入到终态的完整流程 |
| `02_state_machine.mmd` | 状态机转换图 | Phoenix 状态间的转换关系 |
| `03_rollback_detail.mmd` | 回溯机制详细流程 | V7.7 新增的回溯逻辑 |
| `04_version_evolution.mmd` | 版本演化链示例 | 正常演化 vs 回溯演化对比 |
| `05_agent_architecture.mmd` | 智能体协作架构 | 各智能体间的交互关系 |
| `06_config_params.mmd` | 配置参数关系图 | 各配置参数如何影响终态判断 |

---

## 使用方法

### 1. Mermaid Live Editor（推荐）

打开 https://mermaid.live/ ，复制 `.mmd` 文件的**全部内容**粘贴到左侧编辑器。

### 2. VS Code 预览

安装 `Markdown Preview Mermaid Support` 插件，创建 `.md` 文件：

```markdown
```mermaid
{{ 复制 .mmd 文件内容 }}
```
```

### 3. 批量预览脚本

```bash
# 在 docs/flowcharts 目录下运行
for f in *.mmd; do echo "=== $f ===" && cat "$f"; done
```

---

## 图表预览

### 主流程图 (01_main_flow.mmd)

展示完整演化流程：
- 入口阶段：意图清洗 → RAG 检索
- 假设生成：PI Agent → 物理校验
- 红蓝对抗：攻击 → 答辩
- 演化阶段：补丁 → 重试 → 回溯

### 状态机转换图 (02_state_machine.mmd)

Phoenix 状态转换关系：
- 12 个状态节点
- 3 个终态（SUCCESS / HARD_FAILURE / MAX_PHOENIX_EXCEEDED）
- V7.7 新增 PHOENIX_ROLLBACK 状态

### 回溯机制详细流程 (03_rollback_detail.mmd)

触发条件和执行流程：
- 触发条件：同一攻击类型连续失败 ≥ 3 次
- 目标查找：评分保护 + 深度限制
- 执行动作：创建回溯版本 + 避让提示

### 版本演化链示例 (04_version_evolution.mmd)

两种演化路径对比：
- 正常演化：v1.0 → v1.1 → v1.2 → v1.3
- 回溯演化：触发回溯 → 注入避让 → 新方向

### 智能体协作架构 (05_agent_architecture.mmd)

五层架构：
- 用户层 → 入口层 → 智能体层 → 演化层 → 数据层

### 配置参数关系图 (06_config_params.mmd)

参数与终态的关系：
- 迭代限制 → MAX_PHOENIX_EXCEEDED / HARD_FAILURE
- 分数配置 → SUCCESS
- 回溯配置 → PHOENIX_ROLLBACK