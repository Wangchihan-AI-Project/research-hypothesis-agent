# -*- coding: utf-8 -*-
"""
伦理与数据合规审查员智能体 (AI Ethics & Bias Reviewer)
顶级期刊的伦理审稿人，专门审查数据泄露、人群偏见、隐私合规

核心身份：
- Nature/Science期刊伦理审稿人
- 精通数据泄露检测、偏见消除、公平性机器学习
- 强制要求外部验证、隐私保护、合规声明

审查重点：
1. 数据泄露风险：特征选择、时序分割、交叉验证
2. 人群偏见：种族、性别、年龄、地域偏差
3. 隐私合规：HIPAA、GDPR、知情同意
4. 外部验证：独立队列、多中心验证

一票否决：
- 存在明显数据泄露漏洞
- 单一人群数据无外部验证
- 缺乏隐私保护机制
- 无公平性约束的医学AI
"""
from typing import Dict, List, Optional, Any
import json
import sys
import os
import re
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
import anthropic
from utils.llm_utils import SafeExtractor, LLMParseError
import time


# ============ 数据泄露检测标准 ============

DATA_LEAKAGE_CHECKS = {
    'feature_selection_leakage': {
        'description': '特征选择在CV外进行',
        'detection': ['特征选择在训练前', '未使用Pipeline', '使用全部数据选特征'],
        'solution': '使用嵌套交叉验证，特征选择在CV内部'
    },
    'temporal_leakage': {
        'description': '时序数据未按时间分割',
        'detection': ['随机分割时序数据', '使用未来信息', '时间序列随机CV'],
        'solution': '使用TimeSeriesSplit，按时间顺序分割'
    },
    'target_leakage': {
        'description': '特征中包含目标变量信息',
        'detection': ['特征与目标高度相关', '治疗后指标预测治疗前', '包含诊断结果'],
        'solution': '审查特征来源，移除泄露特征'
    },
    'preprocessing_leakage': {
        'description': '预处理使用全局统计',
        'detection': ['使用全部数据标准化', '缺失值用全局均值', '批次校正用全部数据'],
        'solution': '预处理仅在训练集fit，测试集仅transform'
    }
}

# ============ 偏见检测标准 ============

BIAS_CHECKS = {
    'demographic_bias': {
        'race': '种族偏见 - 单一人群模型',
        'gender': '性别偏见 - 未考虑性别差异',
        'age': '年龄偏见 - 年龄分布不均',
        'geography': '地域偏见 - 单中心数据'
    },
    'selection_bias': {
        'description': '选择偏差 - 样本不代表目标人群',
        'examples': ['仅纳入健康人群', '排除少数民族', '局限于特定医院']
    },
    'measurement_bias': {
        'description': '测量偏差 - 数据采集方式不均',
        'examples': ['不同设备采集', '不同标准诊断', '标签质量不一']
    },
    'algorithmic_bias': {
        'description': '算法偏差 - 模型放大偏见',
        'examples': ['类别不平衡未处理', '使用敏感特征', '无公平性约束']
    }
}

# ============ 合规标准 ============

COMPLIANCE_STANDARDS = {
    'hipaa': {
        'name': 'HIPAA (美国)',
        'requirements': ['数据去标识化', '访问控制', '审计日志', '患者知情同意']
    },
    'gdpr': {
        'name': 'GDPR (欧盟)',
        'requirements': ['数据最小化', '目的限定', '知情同意', '删除权']
    },
    'china_pipl': {
        'name': '个人信息保护法 (中国)',
        'requirements': ['知情同意', '目的限定', '最小必要', '安全保护']
    }
}


class EthicsReviewerAgent(BaseAgent):
    """伦理与数据合规审查员智能体"""

    def __init__(self):
        super().__init__("伦理与数据合规审查员", agent_type="ethics_reviewer")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        self.max_retries = 3
        self.model = os.getenv("ETHICS_REVIEWER_MODEL", "claude-opus-4-6")
        self.extractor = SafeExtractor()

    def execute(self, input_data: Dict) -> Dict:
        """执行伦理审查"""
        hypothesis_data = input_data.get('hypothesis_data', {})
        tech_analysis = input_data.get('tech_analysis', {})
        clinical_review = input_data.get('clinical_review', {})
        pathology_review = input_data.get('pathology_review', {})
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            return {'success': False, 'error': '缺少假设数据'}

        # 执行三维度审查
        leakage_check = self._check_data_leakage(hypothesis_data, tech_analysis)
        bias_check = self._check_bias(hypothesis_data)
        compliance_check = self._check_compliance(hypothesis_data, clinical_review)

        # 生成审查报告
        ethics_review = {
            'leakage_check': leakage_check,
            'bias_check': bias_check,
            'compliance_check': compliance_check,
            'overall_status': self._determine_status(leakage_check, bias_check, compliance_check)
        }

        # 生成修正方案
        revised_proposal = self._generate_revised_proposal(
            hypothesis_data, ethics_review
        )

        # 保存报告
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"Ethics_Review_{timestamp}.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(revised_proposal)

        return {
            'success': True,
            'ethics_review': ethics_review,
            'revised_proposal': revised_proposal,
            'report_path': report_path,
            'approved': ethics_review['overall_status'] != 'rejected'
        }

    def _check_data_leakage(self, hypothesis: dict, tech_analysis: dict) -> Dict:
        """检测数据泄露风险"""
        desc = hypothesis.get('description', '').lower()
        validation = hypothesis.get('validation_plan', '').lower()

        risks = []

        # 检查特征选择泄露
        if 'feature selection' in desc or '特征选择' in desc:
            if 'cross validation' not in desc and '交叉验证' not in desc:
                risks.append({'type': 'feature_selection', 'severity': 'high',
                    'issue': '特征选择可能未在CV内部进行'})

        # 检查时序泄露
        if any(kw in desc for kw in ['time series', 'longitudinal', '时序', '纵向']):
            if 'temporal' not in desc and '时间分割' not in desc:
                risks.append({'type': 'temporal', 'severity': 'high',
                    'issue': '时序数据应按时间分割，而非随机分割'})

        # 检查预处理泄露
        if 'normalization' in desc or '标准化' in desc:
            risks.append({'type': 'preprocessing', 'severity': 'medium',
                'issue': '预处理必须仅在训练集fit'})

        return {'risks': risks, 'risk_count': len(risks),
            'status': 'pass' if len(risks) == 0 else 'warning' if len(risks) <= 2 else 'fail'}

    def _check_bias(self, hypothesis: dict) -> Dict:
        """检测人群偏见"""
        desc = hypothesis.get('description', '').lower()
        expected = hypothesis.get('expected_value', '').lower()

        biases = []

        # 检查单中心数据
        if 'single center' in desc or '单中心' in desc or 'hospital' in desc:
            biases.append({'type': 'geographic', 'severity': 'high',
                'issue': '单中心数据存在地域偏见，需外部验证'})

        # 检查种族/人群覆盖
        if not any(kw in desc for kw in ['multi-ethnic', 'cross-population', 'diverse', '多种族']):
            biases.append({'type': 'demographic', 'severity': 'medium',
                'issue': '需验证模型在不同人群中的公平性'})

        # 检查公平性约束
        if 'fairness' not in desc and '公平' not in desc:
            biases.append({'type': 'algorithmic', 'severity': 'medium',
                'issue': '医学AI模型需加入公平性约束'})

        return {'biases': biases, 'bias_count': len(biases),
            'status': 'pass' if len(biases) == 0 else 'warning' if len(biases) <= 2 else 'fail'}

    def _check_compliance(self, hypothesis: dict, clinical_review: dict) -> Dict:
        """检查隐私合规"""
        desc = hypothesis.get('description', '').lower()

        issues = []

        # 检查隐私保护
        if not any(kw in desc for kw in ['privacy', 'de-identified', 'anonymized', '隐私', '脱敏']):
            issues.append({'type': 'privacy', 'severity': 'high',
                'issue': '需明确数据隐私保护措施'})

        # 检查外部验证
        if 'external validation' not in desc and '外部验证' not in desc:
            issues.append({'type': 'validation', 'severity': 'high',
                'issue': '临床AI模型必须有独立外部验证'})

        return {'issues': issues, 'issue_count': len(issues),
            'status': 'pass' if len(issues) == 0 else 'warning' if len(issues) <= 1 else 'fail'}

    def _determine_status(self, leakage: Dict, bias: Dict, compliance: Dict) -> str:
        """确定总体状态"""
        if leakage['status'] == 'fail' or bias['status'] == 'fail' or compliance['status'] == 'fail':
            return 'rejected'
        elif leakage['status'] == 'warning' or bias['status'] == 'warning' or compliance['status'] == 'warning':
            return 'needs_revision'
        return 'approved'

    def _generate_revised_proposal(self, hypothesis: dict, ethics_review: dict) -> str:
        """生成伦理修正方案"""
        cn_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        title = hypothesis.get('title', '未命名研究')
        status = ethics_review['overall_status']

        status_display = {'approved': '🟢 APPROVED', 'needs_revision': '🟡 NEEDS REVISION',
            'rejected': '🔴 REJECTED'}

        proposal = f"""# 伦理合规、偏见消除与外部验证策略

**生成时间**: {cn_time}
**智能体**: 伦理与数据合规审查员 (AI Ethics & Bias Reviewer)
**研究题目**: {title}

---

## 一、伦理审查决议

**总体状态**: {status_display.get(status, status)}

---

## 二、数据泄露风险审查

### 2.1 检测结果

**风险数量**: {ethics_review['leakage_check']['risk_count']}
**状态**: {ethics_review['leakage_check']['status'].upper()}

"""

        for risk in ethics_review['leakage_check']['risks']:
            proposal += f"- ⚠️ [{risk['severity'].upper()}] {risk['issue']}\n"

        if ethics_review['leakage_check']['risk_count'] == 0:
            proposal += "- ✅ 未检���到明显数据泄露风险\n"

        proposal += """

### 2.2 数据泄露防护方案

**强制要求**:
```python
# 正确的Pipeline设计
from sklearn.pipeline import Pipeline
from sklearn.feature_selection import SelectKBest
from sklearn.model_selection import cross_val_score

# 特征选择必须在CV内部
pipeline = Pipeline([
    ('selector', SelectKBest(k=10)),
    ('classifier', RandomForestClassifier())
])

# 嵌套交叉验证
from sklearn.model_selection import GridSearchCV, cross_val_score
nested_cv = GridSearchCV(pipeline, param_grid, cv=5)
scores = cross_val_score(nested_cv, X, y, cv=5)
```

**时序数据分割**:
```python
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)
for train, test in tscv.split(X):
    # 确保训练数据在测试数据之前
    assert train.max() < test.min()
```

---

## 三、人群偏见审查

### 3.1 检测结果

**偏见数量**: {ethics_review['bias_check']['bias_count']}
**状态**: {ethics_review['bias_check']['status'].upper()}

"""

        for bias in ethics_review['bias_check']['biases']:
            proposal += f"- ⚠️ [{bias['type']}] {bias['issue']}\n"

        if ethics_review['bias_check']['bias_count'] == 0:
            proposal += "- ✅ 未检测到明显人群偏见\n"

        proposal += """

### 3.2 偏见消除策略

**公平性约束**:
```python
# Fairlearn - 公平性约束库
from fairlearn.reductions import ExponentiatedGradient, DemographicParity

# 添加公平性约束
constraint = DemographicParity()
mitigator = ExponentiatedGradient(estimator, constraint)
mitigator.fit(X, y, sensitive_features=gender)
```

**多人群验证**:
- 必须在至少2个独立人群队列中验证
- 报告各人群的AUROC/AUPRC差异
- 若差异>0.05，需分析原因并改进

---

## 四、隐私合规审查

### 4.1 检测结果

**合规问题数量**: {ethics_review['compliance_check']['issue_count']}
**状态**: {ethics_review['compliance_check']['status'].upper()}

"""

        for issue in ethics_review['compliance_check']['issues']:
            proposal += f"- ⚠️ [{issue['type']}] {issue['issue']}\n"

        if ethics_review['compliance_check']['issue_count'] == 0:
            proposal += "- ✅ 符合隐私合规要求\n"

        proposal += """

### 4.2 隐私保护方案

**差分隐私**:
```python
from diffprivlib.models import LogisticRegression
dp_model = LogisticRegression(epsilon=1.0)  # 隐私预算
dp_model.fit(X_train, y_train)
```

**联邦学习**:
```python
# 多中心联邦学习
import tensorflow_federated as tff

# 各中心本地训练，��共享模型参数
@tff.tf_computation
def local_train(model_weights, local_data):
    # 本地训练，数据不出中心
    return updated_weights
```

---

## 五、外部验证强制要求

### 5.1 为什么外部验证不可跳过？

> **医学AI铁律**: 没有外部验证的医学AI模型，不能用于临床决策。

**原因**:
1. 内部验证可能过拟合
2. 单中心数据存在偏见
3. 不同人群的模型表现可能差异巨大

### 5.2 外部验证最低标准

| 验证类型 | 要求 | 最低标准 |
|----------|------|----------|
| **独立队列验证** | 不同医院/地区数据 | N ≥ 500 |
| **跨人群验证** | 不同种族/国家 | 至少2个人群 |
| **时间验证** | 不同时间段数据 | 间隔≥1年 |

---

## 六、合规声明模板

本研究遵守以下数据伦理规范：

1. **数据来源**: 所有数据来源于公开数据库或经伦理委员会批准的研究
2. **隐私保护**: 数据已去标识化，符合HIPAA/GDPR要求
3. **知情同意**: 原始研究已获得参与者知情同意
4. **公平性声明**: 模型已在多个人群中验证公平性
5. **透明度**: 算法逻辑可解释，代码已开源

---

## 七、审查结论

"""

        if status == 'approved':
            proposal += "**🟢 APPROVED** - 方案符合伦理规范，可进入数据获取阶段\n"
        elif status == 'needs_revision':
            proposal += "**🟡 NEEDS REVISION** - 存在潜在风险，需修正后重新审查\n"
        else:
            proposal += "**🔴 REJECTED** - 存在严重伦理问题，必须重新设计\n"

        proposal += f"""

---

*本方案由伦理与数据合规审查员智能体生成*
*生成时间: {cn_time}*
"""

        return proposal


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    agent = EthicsReviewerAgent()
    result = agent.execute({
        'hypothesis_data': {
            'title': '多中心肺癌预测模型',
            'description': '基于单中心数据的深度学习预测模型',
            'validation_plan': '使用交叉验证评估模型性能'
        },
        'output_dir': 'reports'
    })

    if result['success']:
        print(f"审查状态: {result['ethics_review']['overall_status']}")
        print(f"报告路径: {result['report_path']}")