# 两阶段漏斗过滤架构 (Two-Stage Funnel Screening)

## 架构概述

文献侦察员现在采用**两阶段漏斗过滤架构**，实现从海量文献中快速筛选出高质量相关文献。

```
┌─────────────────────────────────────────────────────────────────┐
│                    两阶段漏斗过滤架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐                                        │
│  │   第一阶段：海量粗筛    │  Stage 1: Broad Screening             │
│  ├──────────────────────┤                                        │
│  │ • PubMed API 检索     │  • Fetch 500 papers (title + abstract)  │
│  │ • 获取 500 篇候选      │  • Fast relevance scoring              │
│  │ • 快速相关性评分       │  • Select top 40                       │
│  │ • 筛选 Top 40         │                                        │
│  └──────────┬───────────┘                                        │
│             │                                                    │
│             ▼                                                    │
│  ┌──────────────────────┐                                        │
│  │   第二阶段：深度精读    │  Stage 2: Deep Reading                │
│  ├──────────────────────┤                                        │
│  │ • 精选 40 篇高分文献   │  • Top 40 high-score papers           │
│  │ • 获取全文/详细摘要     │  • Fetch full text/detailed abstract │
│  │ • 输出高质量文献集      │  • Output quality paper set           │
│  └──────────────────────┘                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 相关性评分器 (`RelevanceScorer`)

**位置**: `src/utils/relevance_scorer.py`

**评分策略**:
- **TF-IDF 评分** (60%): 基于词频-逆文档频率计算相似度
- **关键词匹配** (40%): 基于预定义生物医学术语权重词典
- **额外加分项**:
  - 标题包含查询词 (+0.1)
  - 摘要长度适中 (+0.05)
  - 包含机器学习元素 (+0.1~0.15)
  - 高影响因子期刊 (+0.1)

**生物医学术语权重示例**:
```python
'machine learning': 3.0
'deep learning': 3.0
'crispr': 2.5
'single-cell': 2.5
'genomics': 2.0
'bioinformatics': 2.0
```

### 2. 论文搜索智能体 (`PaperSearchAgent`)

**新增方法**: `execute_two_stage_funnel()`

**参数**:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `query` | 必需 | 搜索关键词 |
| `stage1_max` | 500 | 第一阶段粗筛数量 |
| `stage2_top_k` | 40 | 第二阶段精选数量 |
| `fetch_full_text` | True | 是否获取全文 |
| `enable_filter` | False | 是否启用期刊质量过滤 |

**返回结构**:
```python
{
    'success': True,
    'papers': [...],           # 精选论文列表
    'stage1_stats': {
        'total_fetched': 500,
        'selected_papers': 40,
        'min_score': 0.235,
        'max_score': 0.892
    },
    'stage2_stats': {
        'total_processed': 40,
        'pdf_count': 15,
        'abstract_count': 25
    }
}
```

### 3. 工作流协调器 (`Orchestrator`)

**更新方法**: `search_papers()`

**新增参数**:
- `use_two_stage_funnel`: 是否使用两阶段漏斗（默认 True，推荐）
- `stage1_max`: 第一阶段最大结果数
- `stage2_top_k`: 第二阶段精选数量

## API 并发限制处理

### PubMed API 限制
- **无 API Key**: 3 请求/秒
- **有 API Key**: 10 请求/秒

### 解决方案
1. **批量处理**: 每批 100 篇论文
2. **延迟机制**: 批次间自动延迟
3. **进度显示**: 实时显示处理进度

```python
# 批量评分示例
batch_scorer = BatchScorer(batch_size=100)
results = batch_scorer.score_large_dataset(
    papers=all_papers,
    query="machine learning cancer",
    top_k=40
)
```

## 使用示例

### 方式 1: 直接使用 PaperSearchAgent

```python
from src.agents.paper_search_agent import PaperSearchAgent

agent = PaperSearchAgent()

result = agent.execute_two_stage_funnel({
    'query': 'machine learning cancer genomics',
    'stage1_max': 500,
    'stage2_top_k': 40,
    'fetch_full_text': True
})

# 获取精选论文
top_papers = result['papers']
for paper in top_papers:
    print(f"Score: {paper['relevance_score']:.3f}")
    print(f"Title: {paper['title']}")
```

### 方式 2: 通过 Orchestrator 使用

```python
from src.core.orchestrator import Orchestrator

orchestrator = Orchestrator()
orchestrator.start_session("machine learning cancer")

# 使用两阶段漏斗（默认启用）
result = orchestrator.search_papers(
    query="machine learning cancer genomics",
    use_two_stage_funnel=True,
    stage1_max=500,
    stage2_top_k=40
)
```

### 方式 3: 运行测试

```bash
python test_two_stage_funnel.py
```

## 评分逻辑保证

### 防止漏掉关键文献

1. **多维度评分**: 结合 TF-IDF 和关键词匹配
2. **标题高权重**: 标题匹配获得 3x 权重
3. **数据科学元素**: ML/DL 方法论文自动加分
4. **期刊质量**: 高影响因子期刊额外加分
5. **评分透明度**: 所有论文保留评分，可回溯分析

### 排序逻辑

```python
# 1. 计算综合评分
score = tfidf_score * 0.6 + keyword_score * 0.4 + bonus_score

# 2. 降序排序
papers.sort(key=lambda p: p['relevance_score'], reverse=True)

# 3. 返回 Top K
return papers[:top_k]
```

## 性能对比

| 指标 | 单阶段模式 | 两阶段漏斗 |
|------|-----------|-----------|
| 初步获取数量 | 50 篇 | 500 篇 |
| API 调用次数 | 1 次 | 1-2 次 |
| 评分覆盖 | 无 | 全量 500 篇 |
| 全文获取 | 5 篇 | Top 40 篇 |
| 漏检风险 | 高 | 低 |
| 处理时间 | ~10 秒 | ~30 秒 |

## 文件清单

| 文件 | 说明 |
|------|------|
| `src/utils/relevance_scorer.py` | 相关性评分器 |
| `src/agents/paper_search_agent.py` | 论文搜索智能体（已更新） |
| `src/core/orchestrator.py` | 工作流协调器（已更新） |
| `test_two_stage_funnel.py` | 测试文件 |

## 配置建议

### 小规模探索
```python
{
    'stage1_max': 100,
    'stage2_top_k': 10,
    'fetch_full_text': False
}
```

### 标准研究
```python
{
    'stage1_max': 500,
    'stage2_top_k': 40,
    'fetch_full_text': True
}
```

### 深度调研
```python
{
    'stage1_max': 1000,
    'stage2_top_k': 100,
    'fetch_full_text': True,
    'enable_filter': True  # 额外启用期刊质量过滤
}
```
