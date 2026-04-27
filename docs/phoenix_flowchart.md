# 凤凰协议完整流程图

## 一、主流程图

```mermaid
flowchart TD
    A[用户输入研究想法] --> B[意图清洗网关]
    B --> C{通过清洗?}
    C -->|否| D[拒绝请求]
    C -->|是| E[动态 RAG 路由器]
    E --> F[多源检索聚合]
    F --> G[PI Agent 假设生成]
    G --> H[物理铁闸校验]
    H --> I{物理冲突?}
    I -->|是| J[PHOENIX_REWRITE 物理锚定重写]
    J --> K{重写成功?}
    K -->|否| L[HARD_FAILURE 硬性失败]
    K -->|是| G
    I -->|否| M[RED_ATTACK 红方攻击]
    M --> N[生成攻击报告]
    N --> O[BLUE_DEFENSE 蓝方答辩]
    O --> P{答辩结果}
    P -->|通过| Q[计算 Science Score]
    P -->|失败| R[记录攻击类型失败]
    Q --> S{Score 大于等于 8.5?}
    S -->|是| T[SUCCESS 最终成功]
    S -->|否| U{分数停滞?}
    U -->|是| V[EXTERNAL_COMPENSATION 外部算法补偿]
    U -->|否| W[继续演化]
    V --> W
    R --> X{攻击类型连续失败大于等于3���?}
    X -->|是| Y[PHOENIX_ROLLBACK 补丁无效累积回溯]
    X -->|否| Z[PHOENIX_PATCH 方法论补丁注入]
    Y --> Y1{找到回溯目标?}
    Y1 -->|否| L
    Y1 -->|是| Y2[创建回溯版本 加入失败黑名单 生成避让提示]
    Y2 --> Y3[重置失败计数]
    Y3 --> G
    Z --> Z1[分级检索补丁]
    Z1 --> Z2[PHOENIX_RETRY 补丁后重试]
    Z2 --> Z3{重试结果}
    Z3 -->|通过| T
    Z3 -->|失败| AG{迭代上限?}
    AG -->|是| AH[MAX_PHOENIX_EXCEEDED 超过演化上限]
    AG -->|否| R
    W --> AG
```

## 二、状态机转换图

```mermaid
stateDiagram-v2
    [*] --> INITIAL: 用户提交
    INITIAL --> HYPOTHESIS_GEN: 假设准备就绪
    HYPOTHESIS_GEN --> PHOENIX_REWRITE: 物理公理冲突
    HYPOTHESIS_GEN --> RED_ATTACK: 开始红方攻击
    PHOENIX_REWRITE --> PHOENIX_RETRY: 重写完成
    PHOENIX_REWRITE --> HARD_FAILURE: 不可恢复冲突
    RED_ATTACK --> BLUE_DEFENSE: 开始蓝方��辩
    BLUE_DEFENSE --> SUCCESS: 成功阈值达成
    BLUE_DEFENSE --> PHOENIX_PATCH: 答辩失败
    BLUE_DEFENSE --> SCORE_STAGNANT: 分数停滞检测
    SCORE_STAGNANT --> EXTERNAL_COMPENSATION: 停滞触发
    EXTERNAL_COMPENSATION --> PHOENIX_PATCH: 补偿完成
    PHOENIX_PATCH --> PHOENIX_RETRY: 补丁应用完成
    PHOENIX_RETRY --> SUCCESS: 防御通过
    PHOENIX_RETRY --> PHOENIX_PATCH: 答辩失败
    PHOENIX_RETRY --> PHOENIX_ROLLBACK: 攻击类型无法解决
    PHOENIX_ROLLBACK --> PHOENIX_RETRY: 回溯完成
    HYPOTHESIS_GEN --> MAX_PHOENIX_EXCEEDED: 迭代上限
    PHOENIX_PATCH --> MAX_PHOENIX_EXCEEDED: 迭代上限
    PHOENIX_RETRY --> MAX_PHOENIX_EXCEEDED: 迭代上限
    EXTERNAL_COMPENSATION --> MAX_PHOENIX_EXCEEDED: 迭代上限
    SUCCESS --> [*]
    HARD_FAILURE --> [*]
    MAX_PHOENIX_EXCEEDED --> [*]
```

## 三、回溯机制详细流程

```mermaid
flowchart TD
    A[蓝方答辩失败] --> B[记录攻击类型失败次数]
    B --> C{同一攻击类型失败大于等于3次?}
    C -->|否| D[继续补丁循环]
    C -->|是| E[触发 PHOENIX_ROLLBACK]
    E --> F[获取版本演化链]
    F --> G[遍历候选版本]
    G --> H{版本不含该攻击类型?}
    H -->|否| I[跳过该版本]
    I --> G
    H -->|是| J{版本分数大于等于当前分数减1.0?}
    J -->|否| K[记录分数过低]
    K --> G
    J -->|是| L[选中该版本]
    L --> M[创建回溯版本 v1.x_rollback]
    M --> N[将攻击类型加入失败黑名单]
    N --> O[生成避让提示]
    O --> P[重置失败计数]
    P --> Q[注入避让提示到 PI Agent]
    Q --> R[生成新假设]
    G -->|遍历完毕无目标| S{放宽限制重试}
    S -->|仍无目标| T{使用最早版本?}
    T -->|是| U[返回最早版本]
    T -->|否| V[HARD_FAILURE]
    S -->|找到| L
    R --> W[继续演化流程]
```

## 四、版本演化链示例

```mermaid
flowchart LR
    V1[v1.0 初始版本 Score 6.5] -->|Data Leakage| V2[v1.1 方法论补丁 Score 7.2]
    V2 -->|Endogeneity| V3[v1.2 方法论补丁 Score 8.2]
    V3 -->|蓝方通过| V4[v1.3 最终版本 Score 8.9]
    V5[v1.0 初始版本 Score 6.5] -->|Data Leakage| V6[v1.1 补丁 Score 7.2]
    V6 -->|Data Leakage 补丁无效| V7[v1.2 补丁 Score 7.5]
    V7 -->|Data Leakage 补丁无效| V8[v1.3 补丁 Score 7.8]
    V8 -->|Data Leakage 第3次失败| R1[触发回溯]
    R1 --> V9[v1.4_rollback 回溯恢复 注入避让提示]
    V9 -->|新研究方向| V10[v1.5 Score 8.2]
    V10 -->|蓝方通过| V11[v1.6 最终版本 Score 9.1]
    style R1 fill:#ff6b6b,color:#fff
    style V9 fill:#ffd93d,color:#000
    style V4 fill:#6bcb77,color:#fff
    style V11 fill:#6bcb77,color:#fff
```

## 五、智能体协作架构

```mermaid
flowchart TB
    User[用户] --> Sanitizer[意图清洗网关]
    Sanitizer --> RAG[动态 RAG 路由器]
    RAG --> PubMed[PubMed]
    RAG --> ArXiv[ArXiv]
    RAG --> SemanticScholar[Semantic Scholar]
    RAG --> PI[PI Agent 首席科学家 假设生成]
    PI --> StateMachine[Phoenix 状态机]
    StateMachine --> Red[RedTeam Agent 红方攻击者 漏洞检测]
    Red --> Blue[Defense Committee 蓝方答辩委员会 可行性审查]
    Blue --> GenAI[GenAI Expert AI ML 专家]
    Blue --> Biostats[Biostats Agent 生物统计专家]
    Blue --> StateMachine
    StateMachine --> PatchInjector[补丁注入器]
    PatchInjector --> RollbackHandler[回溯处理器]
    RollbackHandler --> PI
    StateMachine --> VersionManager[版本管理器]
    VersionManager --> SQLite[(SQLite 数据库)]
```

## 六、配置参数关系图

```mermaid
flowchart TD
    MAX_ITER[MAX_PHOENIX_ITERATIONS 8 最大演化次数] -->|超过| FAIL1[MAX_PHOENIX_EXCEEDED]
    MAX_REWRITE[MAX_REWRITE_ATTEMPTS 3 物理重写上限] -->|超过| FAIL2[HARD_FAILURE]
    MAX_PATCH[MAX_PATCH_ATTEMPTS 5 方法论补丁上限] -->|超过| FAIL1
    MAX_ROLLBACK[MAX_ROLLBACK_ATTEMPTS 2 最大回溯次数] -->|超过| FAIL2
    MIN_SCORE[MIN_SUCCESS_SCORE 8.5 成功最低分数] -->|达成| SUCCESS[SUCCESS]
    THRESHOLD[ATTACK_TYPE_FAILURE_THRESHOLD 3 触发回溯的失败次数] -->|触发| ROLLBACK[PHOENIX_ROLLBACK]
    TOLERANCE[ROLLBACK_SCORE_TOLERANCE 1.0 回溯评分容忍度] -->|保护| TARGET[回溯目标选择]
    DEPTH[ROLLBACK_DEPTH_LIMIT 3 回溯深度限制] -->|限制| TARGET
```

---

## 使用说明

1. 将上述 Mermaid 代码复制到支持 Mermaid 的 Markdown 编辑器中查看
2. 推荐工具：
   - [Mermaid Live Editor](https://mermaid.live/)
   - VS Code + Mermaid 插件
   - GitHub/GitLab Markdown 预览
   - Notion / Obsidian
