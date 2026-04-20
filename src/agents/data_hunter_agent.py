# -*- coding: utf-8 -*-
"""
数据猎犬智能体 (Data Hunter Agent)
机器学习友好的开源数据集评估与推荐专家

核心任务：
- 评估数据集的机器学习友好度
- 检测数据质量问题（类别不平衡、缺失值、数据泄露风险）
- 推荐适合ML训练��高质量数据集
- 提供数据预处理和采样策略建议
"""
from typing import Dict, List, Optional, Any
import json
import sys
import os
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base import BaseAgent
import anthropic


# ============ 机器学习友好度评估标准 ============

ML_FRIENDLINESS_CRITERIA = {
    'sample_size': {
        'excellent': 'N ≥ 10,000 (深度学习)',
        'good': '1,000 ≤ N < 10,000 (传统ML)',
        'fair': '500 ≤ N < 1,000 (简单模型)',
        'poor': 'N < 500 (仅限探索性分析)',
        'ml_threshold': {
            'deep_learning': 10000,
            'traditional_ml': 1000,
            'statistical_methods': 500
        }
    },
    'label_quality': {
        'excellent': '专家标注，一致性 > 90%',
        'good': '半监督标注，一致性 > 80%',
        'fair': '弱监督或噪声标签',
        'poor': '无标注或标签质量未知'
    },
    'feature_quality': {
        'excellent': '特征工程完善，维度 < 1000',
        'good': '特征可用，维度 < 5000',
        'fair': '特征需要大量预处理',
        'poor': '特征维度灾难（>10000）或严重缺失'
    },
    'class_balance': {
        'excellent': '平衡数据集（最大/最小比 < 3）',
        'good': '轻微不平衡（3 ≤ 比 < 10）',
        'fair': '中度不平衡（10 ≤ 比 < 50）',
        'poor': '严重不平衡（比 ≥ 50）',
        'recommended_sampling': {
            'oversample': 'SMOTE、ADASYN',
            'undersample': 'RandomUnderSampler、NearMiss',
            'hybrid': 'SMOTE + Tomek links',
            'class_weight': '调整损失权重'
        }
    },
    'missing_data': {
        'excellent': '无缺失或 < 5%',
        'good': '5-20% 缺失（可插补）',
        'fair': '20-50% 缺失（需特殊处理）',
        'poor': '> 50% 缺失（不可用）',
        'imputation_methods': [
            'KNN插补',
            'MICE (Multiple Imputation by Chained Equations)',
            '矩阵分解',
            '深度学习插补（如GAIN）'
        ]
    }
}

# 推荐的开源数据集（按ML友好度排序）
RECOMMENDED_DATASETS = {
    'single_cell_ml_friendly': [
        {
            'name': 'Tabula Sapiens',
            'accession': 'GSE238078 / tabula-sapiens-consortium.org',
            'sample_size': '~500,000 cells',
            'ml_friendly_score': 'excellent',
            'label_quality': 'excellent (cell type annotations)',
            'use_cases': ['细胞类型分类', '轨迹推断', '批次效应校正'],
            'python_libs': ['scanpy', 'scvi-tools', 'scvelo'],
            'notes': '高质量的跨组织单细胞图谱，标签完善'
        },
        {
            'name': 'Human Cell Atlas',
            'accession': 'data.humancellatlas.org',
            'sample_size': '>10,000,000 cells',
            'ml_friendly_score': 'excellent',
            'label_quality': 'excellent',
            'use_cases': ['大规模细胞类型分类', '跨组织泛化研究'],
            'python_libs': ['scanpy', 'cellxgene'],
            'notes': '目前最大规模的单细胞数据集'
        },
        {
            'name': 'Perturb-seq (CRISPR screens)',
            'accession': 'GSE132610 / opencravats.org',
            'sample_size': '~100,000 cells',
            'ml_friendly_score': 'excellent',
            'label_quality': 'excellent (perturbation labels)',
            'use_cases': ['因果推断', '基因功能预测'],
            'python_libs': ['scikit-learn', 'statsmodels'],
            'notes': '有明确的因果标签，非常适合因果ML研究'
        }
    ],
    'genomics_ml_friendly': [
        {
            'name': 'TCGA (The Cancer Genome Atlas)',
            'accession': 'portal.gdc.cancer.gov',
            'sample_size': '~11,000 patients, 33 cancer types',
            'ml_friendly_score': 'excellent',
            'label_quality': 'excellent (clinical annotations)',
            'use_cases': ['生存分析', '癌症亚型分类', '药物反应预测'],
            'python_libs': ['tcga_utils', 'lifelines', 'scikit-survival'],
            'notes': '多组学数据 + 临床标签，ML友好'
        },
        {
            'name': 'UK Biobank',
            'accession': 'ukbiobank.ac.uk',
            'sample_size': '~500,000 participants',
            'ml_friendly_score': 'excellent',
            'label_quality': 'excellent',
            'use_cases': ['全基因组关联分析', '疾病预测', '多模态建模'],
            'python_libs': ['pandas', 'numpy', 'xgboost'],
            'notes': '最大规模的人群队列，包含基因组+表型+影像'
        },
        {
            'name': 'gnomAD (genome aggregation database)',
            'accession': 'gnomad.broadinstitute.org',
            'sample_size': '~150,000 genomes',
            'ml_friendly_score': 'good',
            'label_quality': 'good (population labels)',
            'use_cases': ['变异频率预测', '路径性评分'],
            'python_libs': ['pandas', 'cyvcf2'],
            'notes': '用于训练变异预测模型'
        }
    ],
    'ehr_clinical_ml_friendly': [
        {
            'name': 'MIMIC-IV',
            'accession': 'physionet.org/content/mimiciv',
            'sample_size': '~300,000 ICU admissions',
            'ml_friendly_score': 'excellent',
            'label_quality': 'excellent',
            'use_cases': ['死亡率预测', '长度of stay预测', '药物推荐'],
            'python_libs': ['pandas', 'numpy', 'scikit-learn'],
            'notes': '高质量EHR数据，时间序列丰富'
        },
        {
            'name': 'eICU Collaborative Database',
            'accession': 'physionet.org/content/eicu-crd',
            'sample_size': '~200,000 ICU patients',
            'ml_friendly_score': 'good',
            'label_quality': 'good',
            'use_cases': ['跨中心泛化研究', '临床预测模型'],
            'python_libs': ['pandas', 'tslearn'],
            'notes': '多中心数据，适合泛化研究'
        }
    ],
    'spatial_omics_ml_friendly': [
        {
            'name': '10x Visium Datasets',
            'accession': 'www.10xgenomics.com/resources/datasets',
            'sample_size': 'Multiple tissues, 5K spots/sample',
            'ml_friendly_score': 'good',
            'label_quality': 'fair (需要额外注释)',
            'use_cases': ['空间模式识别', '细胞互作预测'],
            'python_libs': ['squidpy', 'scanpy', 'napari'],
            'notes': '空间转录组数据，需要配对H&E图像'
        },
        {
            'name': 'Human Tumor Atlas Network (HTAN)',
            'accession': 'humantumoratlas.org',
            'sample_size': 'Various cancer types',
            'ml_friendly_score': 'good',
            'label_quality': 'excellent',
            'use_cases': ['肿瘤微环境分析', '空间-细胞联合建模'],
            'python_libs': ['scanpy', 'squidpy'],
            'notes': '高质量的空间多组学数据'
        }
    ]
}


class DataHunterAgent(BaseAgent):
    """
    数据猎犬智能体

    角色：机器学习友好的开源数据集评估与推荐专家
    专长：数据质量评估、ML友好度分析、采样策略推荐
    """

    def __init__(self):
        super().__init__("数据猎犬智能体", agent_type="data_hunter")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)

    def execute(self, input_data: Dict) -> Dict:
        """
        执行数据集评估与推荐

        Args:
            input_data: {
                'hypothesis_data': dict - 假设数据
                'validation_result': dict - 验证报告
                'output_dir': str - 输出目录
            }

        Returns:
            {
                'success': bool,
                'datasets': list - 推荐的数据集列表
                'ml_assessment': dict - ML友好度评估
                'report_path': str - 报告保存路径
            }
        """
        hypothesis_data = input_data.get('hypothesis_data', {})
        validation_result = input_data.get('validation_result', {})
        output_dir = input_data.get('output_dir', 'reports')

        if not hypothesis_data:
            return {
                'success': False,
                'error': '缺少假设数据'
            }

        # 提取研究主题和数据需求
        paradigm = hypothesis_data.get('paradigm_framework', '')
        challenge = hypothesis_data.get('grand_challenge', '')

        # 构建推荐
        recommendation = self._generate_dataset_recommendation(
            paradigm=paradigm,
            challenge=challenge,
            hypothesis_data=hypothesis_data
        )

        # 保存报告
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(output_dir, f"Dataset_Hunter_Report_{timestamp}.md")

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(recommendation['report'])

        return {
            'success': True,
            'datasets': recommendation['datasets'],
            'ml_assessment': recommendation['ml_assessment'],
            'report_path': report_path
        }

    def _generate_dataset_recommendation(self, paradigm: str, challenge: str,
                                         hypothesis_data: dict) -> Dict:
        """生成数据集推荐"""

        # 根据前沿框架推荐数据集类别
        paradigm_lower = paradigm.lower()

        recommended_datasets = []
        dataset_category = ''

        if 'single' in paradigm_lower or 'cell' in paradigm_lower:
            recommended_datasets = RECOMMENDED_DATASETS['single_cell_ml_friendly']
            dataset_category = '单细胞多组学'
        elif 'spatial' in paradigm_lower or '空间' in paradigm:
            recommended_datasets = RECOMMENDED_DATASETS['spatial_omics_ml_friendly']
            dataset_category = '空间组学'
        elif 'causal' in paradigm_lower or 'genomic' in paradigm_lower or 'cancer' in paradigm_lower:
            recommended_datasets = RECOMMENDED_DATASETS['genomics_ml_friendly']
            dataset_category = '基因组学'
        elif 'ehr' in paradigm_lower or 'clinical' in paradigm_lower:
            recommended_datasets = RECOMMENDED_DATASETS['ehr_clinical_ml_friendly']
            dataset_category = '临床电子健康记录'
        else:
            # 默认推荐多类别
            recommended_datasets = (
                RECOMMENDED_DATASETS['single_cell_ml_friendly'][:2] +
                RECOMMENDED_DATASETS['genomics_ml_friendly'][:2]
            )
            dataset_category = '综合推荐'

        # 生成ML友好度评估
        ml_assessment = self._assess_ml_friendliness(recommended_datasets)

        # 生成报告
        report = self._generate_ml_report(
            paradigm=paradigm,
            challenge=challenge,
            dataset_category=dataset_category,
            datasets=recommended_datasets,
            ml_assessment=ml_assessment
        )

        return {
            'datasets': recommended_datasets,
            'ml_assessment': ml_assessment,
            'report': report
        }

    def _assess_ml_friendliness(self, datasets: list) -> Dict:
        """评估数据集的ML友好度"""

        assessments = []

        for ds in datasets:
            sample_size_str = ds.get('sample_size', 'N/A')

            # 提取样本数量
            import re
            match = re.search(r'([\d,]+)', sample_size_str.replace(',', ''))
            sample_size = int(match.group(1)) if match else 0

            # ML友好度评分
            if sample_size >= 10000:
                ml_score = 'excellent'
                ml_note = '适合深度学习模型训练'
            elif sample_size >= 1000:
                ml_score = 'good'
                ml_note = '适合传统机器学习方法'
            elif sample_size >= 500:
                ml_score = 'fair'
                ml_note = '仅适合简单模型或探索性分析'
            else:
                ml_score = 'poor'
                ml_note = '样本量不足，需考虑迁移学习或数据增强'

            assessments.append({
                'name': ds.get('name', 'N/A'),
                'ml_friendly_score': ml_score,
                'sample_size': sample_size_str,
                'ml_note': ml_note,
                'label_quality': ds.get('label_quality', 'N/A'),
                'recommended_libs': ds.get('python_libs', [])
            })

        return {
            'assessments': assessments,
            'overall_recommendation': 'excellent' if any(a['ml_friendly_score'] == 'excellent' for a in assessments) else 'good'
        }

    def _generate_ml_report(self, paradigm: str, challenge: str, dataset_category: str,
                           datasets: list, ml_assessment: dict) -> str:
        """生成ML友好度评估报告"""

        cn_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        report = f"""# 数据猎犬：机器学习友好度评估报告

**生成时间**: {cn_time}
**智能体**: 数据猎犬 (Data Hunter)
**评估类别**: {dataset_category}

---

## 研究需求分析

**前沿框架**: {paradigm}

**大挑战**: {challenge}

---

## 机器学习友好度评估标准

| 维度 | Excellent | Good | Fair | Poor |
|------|-----------|------|------|------|
| **样本量** | N ≥ 10,000 | 1,000 ≤ N < 10,000 | 500 ≤ N < 1,000 | N < 500 |
| **标签质量** | 专家标注，一致性 > 90% | 半监督，一致性 > 80% | 弱监督或噪声 | 无标注 |
| **特征质量** | 维度 < 1000，特征工程完善 | 维度 < 5000 | 需大量预处理 | 维度灾难 |
| **类别平衡** | 最大/最小比 < 3 | 3 ≤ 比 < 10 | 10 ≤ 比 < 50 | 比 ≥ 50 |
| **缺失数据** | 无缺失或 < 5% | 5-20% | 20-50% | > 50% |

---

## 推荐数据集详情

"""

        for i, ds in enumerate(datasets, 1):
            report += f"### {i}. {ds['name']}\n\n"
            report += f"- **Accession**: `{ds['accession']}`\n"
            report += f"- **样本规模**: {ds['sample_size']}\n"
            report += f"- **ML友好度**: **{ds['ml_friendly_score'].upper()}**\n"
            report += f"- **标签质量**: {ds['label_quality']}\n"
            report += f"- **适用场景**: {', '.join(ds['use_cases'])}\n"
            report += f"- **推荐Python库**: {', '.join(ds['python_libs'])}\n"
            report += f"- **备注**: {ds['notes']}\n\n"

        report += f"""

---

## ML友好度评估结果

"""

        for assessment in ml_assessment['assessments']:
            report += f"### {assessment['name']}\n\n"
            report += f"- **ML友好度评分**: **{assessment['ml_friendly_score'].upper()}**\n"
            report += f"- **样本规模**: {assessment['sample_size']}\n"
            report += f"- **评估说明**: {assessment['ml_note']}\n"
            report += f"- **标签质量**: {assessment['label_quality']}\n"
            report += f"- **推荐工具**: {', '.join(assessment['recommended_libs'])}\n\n"

        report += f"""
---

## 数据科学红线提醒

### 1. 样本量与模型复杂度匹配

- **深度学习**: 样本量应 ≥ 10,000
- **传统ML (Random Forest, XGBoost)**: 样本量应 ≥ 1,000
- **统计方法**: 样本量应 ≥ 500

**规则**: 样本数 ≥ 10 × 参数量

### 2. 类别不平衡处理策略

| 不平衡程度 | 推荐策略 |
|------------|----------|
| 轻微 (3-10倍) | class_weight='balanced' |
| 中度 (10-50倍) | SMOTE/ADASYN 过采样 |
| 严重 (≥50倍) | SMOTE + Tomek links 混合采样 |

### 3. 数据泄露防护

- ❌ 特征选择在交叉验证**之前**进行
- ❌ 时序数据未按时间分割训练/测试集
- ❌ 使用未来信息（如治疗后指标预测治疗前）

**正确做法**:
```python
from sklearn.model_selection import StratifiedKFold
from sklearn.feature_selection import SelectKBest
from sklearn.pipeline import Pipeline

# 特征选择必须在CV内部进行
pipeline = Pipeline([
    ('selector', SelectKBest(k=10)),
    ('classifier', RandomForestClassifier())
])

cv = StratifiedKFold(n_splits=5)
cross_val_score(pipeline, X, y, cv=cv)
```

### 4. 评估指标选择

| 任务类型 | 主要指标 | 辅助指标 | 统计检验 |
|----------|----------|----------|----------|
| 二分类（平衡） | AUROC | Accuracy, F1 | DeLong test |
| 二分类（不平衡） | AUPRC | F1, Precision | Bootstrap CI |
| 生存分析 | C-index | Time-dependent AUROC | Log-rank test |
| 回归 | R², RMSE | MAE | Pearson correlation |

---

## 推荐预处理Pipeline

```python
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import KNNImputer
from imblearn.over_sampling import SMOTE

# 1. 数据加载
data = pd.read_csv('dataset.csv')

# 2. 样本纳排标准（根据研究定义）
included = data[
    (data['quality_score'] > threshold) &
    (data['age'] >= 18) &
    (data['missing_rate'] < 0.5)
]

# 3. 特征-标签分离
X = included.drop(['label'], axis=1)
y = included['label']

# 4. 训练-测试集划分（时序数据需按时间分割）
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2,
    stratify=y,  # 保持类别分布
    random_state=42
)

# 5. 缺失值插补（仅用训练集fit）
imputer = KNNImputer(n_neighbors=5)
X_train_imputed = imputer.fit_transform(X_train)
X_test_imputed = imputer.transform(X_test)  # 重要：不fit测试集

# 6. 标准化（仅用训练集fit）
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train_imputed)
X_test_scaled = scaler.transform(X_test_imputed)

# 7. 类别不平衡处理（仅对训练集）
smote = SMOTE(random_state=42)
X_train_res, y_train_res = smote.fit_resample(
    X_train_scaled, y_train
)

# 8. 模型训练
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    class_weight='balanced',  # 处理剩余不平衡
    random_state=42
)
model.fit(X_train_res, y_train_res)

# 9. 评估
from sklearn.metrics import roc_auc_score, average_precision_score
y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
auroc = roc_auc_score(y_test, y_pred_proba)
auprc = average_precision_score(y_test, y_pred_proba)

print(f"AUROC: {auroc:.3f}, AUPRC: {auprc:.3f}")
```

---

*本报告由数据猎犬智能体生成*
*生成时间: {cn_time}*
"""

        return report


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    # 测试数据猎犬
    data_hunter = DataHunterAgent()

    result = data_hunter.execute({
        'hypothesis_data': {
            'title': 'CausalSC: 因果发现与深度学习耦合的单细胞因果推断框架',
            'paradigm_framework': '因果推断 + 深度学习 + 单细胞组学',
            'grand_challenge': '单细胞数据的因果盲区：如何从观测数据中推断基因调控的因果关系？'
        },
        'validation_result': {},
        'output_dir': 'reports'
    })

    if result['success']:
        print("数据集推荐报告已生成")
        print(f"保存路径: {result['report_path']}")
        print(f"推荐数据集数量: {len(result['datasets'])}")
