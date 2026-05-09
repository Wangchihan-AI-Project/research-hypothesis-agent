# ReAct 实时联网查证引擎 - 使用说明

## 架构升级完成

首席科学家智能体（HypothesisAgent）已完成 ReAct 工具调用架构升级，从"闭卷脑补"升级为"字字有出处"的严谨学者。

---

## 新增文件

### 1. `src/utils/react_tools.py`

ReAct 工具调用核心模块，包含：

- **`SEARCH_PUBMED_TOOL`**: PubMed 检索工具定义（符合 Claude Tool Use 规范）
- **`ReActExecutor`**: ReAct 循环执行器，实现"思考-行动-观察"模式
- **`create_pubmed_tool_implementation()`**: 创建 PubMed 工具实现函数
- **`VERIFICATION_STEEL_IMPRINT`**: 查证钢印（追加到系统提示词）

---

## 修改文件

### `src/agents/hypothesis_agent.py`

1. **导入 ReAct 模块**
   ```python
   from utils.react_tools import (
       ReActExecutor,
       SEARCH_PUBMED_TOOL,
       create_pubmed_tool_implementation,
       VERIFICATION_STEEL_IMPRINT
   )
   ```

2. **系统提示词追加查证钢印**
   - 原 CHIEF_SCIENTIST_SYSTEM_PROMPT 保持不变
   - 自动追加 VERIFICATION_STEEL_IMPRINT（约1800字符）

3. **初始化支持**
   - 新增 `enable_react` 属性（通过 `ENABLE_REACT` 环境变量控制）
   - 新增 `react_executor` 属性（ReAct 执行器）
   - 新增 `tool_calls_log` 属性（记录所有工具调用）

4. **执行模式**
   - `execute()` 方法根据 `enable_react` 自动选择模式
   - ReAct 模式：调用 `_call_llm_with_tools()`
   - 普通模式：调用 `_call_llm()`（原有逻辑）

---

## 查证钢印内容

系统提示词末尾已追加以下内容：

### 1. 开题前置检索 (Evidence Gathering)
- 构思核心科学假说前，必须主动调用 `search_pubmed`
- 拉取近 3 年的至少 5 篇顶刊摘要
- 在机制推演中明确写出参考依据

### 2. 参数级查证 (Parameter Grounding)
- 严禁脑补参数
- 不确定算法包或阈值时，立即调用检索工具
- 查找真实文献中的具体使用方法

### 3. 铁血查重与评分 (Falsification & Scoring)
- 生成 scores 前执行"动态碰撞检测"
- 致命碰撞：methodological_originality 强制低于 4 分
- 每项打分基于 PubMed 检索结果计算

---

## 工具定义

### search_pubmed

```json
{
  "name": "search_pubmed",
  "description": "检索 PubMed 生物医学文献数据库...",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "PubMed检索查询字符串"
      },
      "max_results": {
        "type": "integer",
        "default": 5,
        "minimum": 1,
        "maximum": 20
      },
      "year_start": {
        "type": "integer",
        "default": 2020
      },
      "year_end": {
        "type": "integer"
      }
    },
    "required": ["query"]
  }
}
```

---

## 使用方法

### 1. 启用 ReAct 模式

在 `.env` 文件中设置：

```env
# 启用 ReAct 工具调用（默认启用）
ENABLE_REACT=true

# PubMed API 配置（提高检索限制）
PUBMED_EMAIL=your_email@example.com
PUBMED_API_KEY=your_api_key  # 可选
```

### 2. 运行时日志

启用 ReAct 后，日志中会显示：

```
[ChiefScientist] 初始化 ReAct 工具调用...
[ChiefScientist] ReAct 工具调用已启用 (工具: search_pubmed)
[ChiefScientist] 使用 ReAct 模式调用 LLM...
[ReAct] 开始执行 ReAct 循环...
[ReAct] === 第 1 轮 ===
[ReAct] 工具调用: search_pubmed({'query': 'ADNI hippocampus causal'})
[PubMed工具] 查询: ADNI hippocampus causal
[PubMed工具] 参数: max_results=5, year_range=(2020, 2026)
[PubMed工具] 检索到 5 篇文献
[ReAct] === 第 2 轮 ===
...
[ReAct] 循环完成: 3 轮, 2 次工具调用
```

### 3. 返回结果

`execute()` 返回值中新增：

```python
{
    'success': True,
    'hypotheses': [...],
    'react_enabled': True,  # 是否启用 ReAct
    'tool_calls': [         # 工具调用记录
        {
            'iteration': 1,
            'tool_name': 'search_pubmed',
            'input': {'query': 'ADNI hippocampus', 'max_results': 5},
            'result': '...'  # 检索结果摘要
        }
    ]
}
```

---

## ReAct 循环流程

```
┌─────────────────────────────────────────────────────────────┐
│                     ReAct 循环                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │  思考   │ -> │  行动   │ -> │  观察   │ -> │  思考   │  │
│  │ Reason  │    │  Act    │    │ Observe │    │ Reason  │  │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘  │
│                      │                              │       │
│                      v                              v       │
│               ┌─────────────┐              ┌─────────────┐ │
│               │search_pubmed│              │ 继续思考...  │ │
│               └─────────────┘              └─────────────┘ │
│                      │                              │       │
│                      v                              v       │
│               ┌─────────────┐              ┌─────────────┐ │
│               │ 检索结果    │              │ 最终输出    │ │
│               └─────────────┘              └─────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 示例对话

**用户**：生成一个关于 ADNI 和阿尔茨海默病的研究假设

**模型（思考）**：我需要先检索 ADNI 数据集中海马体积与认知衰退关系的最新研究

**模型（行动）**：调用 `search_pubmed(query="ADNI hippocampus volume cognitive decline causal", max_results=5)`

**模型（观察）**：检索到 5 篇文献，其中 3 篇使用线性混合模型，2 篇使用中介分析

**模型（思考）**：我发现现有研究主要关注线性关系，缺少对非线性阈值效应的探索...

**模型（行动）**：调用 `search_pubmed(query="threshold effect hippocampus cognitive decline")`

**模型（观察）**：检索到关于非线性阈值效应的方法学文献

**模型（思考）**：好的，我现在可以提出一个基于阈值效应的因果中介假设...

**模型（最终输出）**：生成包含具体参考文献的假设...

---

## 测试

运行测试验证功能：

```bash
python test_react_tools.py
```

预期输出：

```
============================================================
ReAct 工具调用测试
============================================================

测试1: 工具定义
  OK 工具定义正确

测试2: 查证钢印
  OK 查证钢印包含所有关键要素

测试3: PubMed 工具实现（模拟模式）
  OK 工具实现正确

测试4: ReAct 执行器初始化
  OK ReAct 执行器初始化成功

测试5: HypothesisAgent ReAct 集成
  OK 系统提示词包含查证钢印
  OK Agent 初始化成功

============================================================
所有测试通过！
============================================================
```

---

## 故障排除

### ReAct 初始化失败

如果看到日志：

```
[ChiefScientist] ReAct 初始化失败，回退到普通模式
```

检查：
1. `ANTHROPIC_API_KEY` 是否正确设置
2. 模型是否支持工具调用（claude-3-5-sonnet-20241022 或更新）
3. 网络连接是否正常

### 回退到普通模式

如果 ReAct 执行失败，系统会自动回退到普通模式（原有逻辑），不影响核心功能。

---

## 后续扩展

可以添加更多工具：

- `search_arxiv`: 检索 arXiv 预印本
- `search_clinical_trials`: 检索临床试验注册信息
- `calculate_power`: 统计功效计算工具
- `validate_assumptions`: 假设验证工具

只需在 `react_tools.py` 中添加工具定义和实现即可。
