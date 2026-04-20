# -*- coding: utf-8 -*-
"""
Modality-Aware Preprocessing System (模态感知预处理系统)
根据数据模态（Modality）动态匹配对应的预处理逻辑
彻底切断单细胞残留，���现领域对齐
"""

from typing import Dict, List, Optional, Tuple
import re


class ModalityDetector:
    """数据模态检测器 - 识别研究涉及的数据类型"""

    # 单细胞/基因组学关键词（需要严格隔离）
    SINGLE_CELL_KEYWORDS = {
        'scRNA', 'single.*cell', '单细胞', 'cell.*type', '细胞类型',
        'gene.*expression', '基因表达', 'transcriptom', '转录组',
        'UMI', 'mitochondrial', '线粒体', 'batch.*effect.*cell',
        'Seurat', 'Scanpy', 'scvi'
    }

    # 神经影像/ADNI 关键词
    NEURO_IMAGING_KEYWORDS = {
        'MRI', 'fMRI', 'PET', 'CT', 'DTI', 'EEG', 'MEG',
        'structural.*MRI', 'functional.*MRI', 'diffusion.*tensor',
        '神经影像', '脑影像', '脑成像', '脑部.*扫描'
    }

    # ADNI 特定关键词
    ADNI_KEYWORDS = {
        'ADNI', 'Alzheimer.*Disease.*Neuroimaging.*Initiative',
        '阿尔茨海默病.*神经影像.*计划'
    }

    # 脑脊液/血液生物标志物
    CSF_BLOOD_KEYWORDS = {
        'CSF', 'cerebrospinal.*fluid', '脑脊液',
        'plasma', 'serum', 'blood.*biomarker',
        '血浆', '血清', '血液.*标志物'
    }

    # 临床/EHR 数据
    CLINICAL_KEYWORDS = {
        'EHR', 'electronic.*health.*record', '电子健康档案',
        'clinical.*trial', '临床试验', 'cohort', '队列'
    }

    @classmethod
    def detect_modality(cls, text: str) -> Dict[str, bool]:
        """
        检测文本中的数据模态

        Returns:
            {
                'is_single_cell': bool,
                'is_neuro_imaging': bool,
                'is_adni': bool,
                'is_csf_blood': bool,
                'is_clinical': bool,
                'primary_modality': str  # 主要模态
            }
        """
        text_lower = text.lower()

        result = {
            'is_single_cell': False,
            'is_neuro_imaging': False,
            'is_adni': False,
            'is_csf_blood': False,
            'is_clinical': False,
            'primary_modality': 'unknown'
        }

        # 检测单细胞（最高优先级排除）
        for pattern in cls.SINGLE_CELL_KEYWORDS:
            if re.search(pattern, text_lower):
                result['is_single_cell'] = True
                result['primary_modality'] = 'single_cell'
                break

        # 检测 ADNI（神经影像特化）
        for pattern in cls.ADNI_KEYWORDS:
            if re.search(pattern, text_lower):
                result['is_adni'] = True
                result['is_neuro_imaging'] = True
                result['primary_modality'] = 'adni'
                break

        # 检测神经影像
        if not result['is_neuro_imaging']:
            for pattern in cls.NEURO_IMAGING_KEYWORDS:
                if re.search(pattern, text_lower):
                    result['is_neuro_imaging'] = True
                    if result['primary_modality'] == 'unknown':
                        result['primary_modality'] = 'neuro_imaging'
                    break

        # 检测 CSF/血液
        for pattern in cls.CSF_BLOOD_KEYWORDS:
            if re.search(pattern, text_lower):
                result['is_csf_blood'] = True
                if result['primary_modality'] == 'unknown':
                    result['primary_modality'] = 'csf_blood'
                break

        # 检测临床数据
        for pattern in cls.CLINICAL_KEYWORDS:
            if re.search(pattern, text_lower):
                result['is_clinical'] = True
                if result['primary_modality'] == 'unknown':
                    result['primary_modality'] = 'clinical'
                break

        return result


class ModalityAwarePreprocessor:
    """模态感知预处理器 - 根据数据类型生成对应的预处理逻辑"""

    @staticmethod
    def generate_preprocessing_protocol(modality_info: Dict[str, bool],
                                        hypothesis_data: Dict) -> str:
        """
        根据检测到的模态生成对应的预处理协议

        Args:
            modality_info: ModalityDetector 检测结果
            hypothesis_data: 假设数据

        Returns:
            预处理协议字符串（Markdown格式）
        """
        primary_modality = modality_info['primary_modality']

        # ========== ADNI 专用预处理协议 ==========
        if primary_modality == 'adni':
            return ModalityAwarePreprocessor._get_adni_preprocessing()

        # ========== 神经影像预处理协议 ==========
        elif primary_modality == 'neuro_imaging':
            return ModalityAwarePreprocessor._get_neuro_imaging_preprocessing()

        # ========== CSF/血液生物标志物预处理协议 ==========
        elif primary_modality == 'csf_blood':
            return ModalityAwarePreprocessor._get_csf_blood_preprocessing()

        # ========== 临床数据预处理协议 ==========
        elif primary_modality == 'clinical':
            return ModalityAwarePreprocessor._get_clinical_preprocessing()

        # ========== 单细胞预处理协议（严格隔离） ==========
        elif primary_modality == 'single_cell':
            return ModalityAwarePreprocessor._get_single_cell_preprocessing()

        # ========== 默认通用预处理协议 ==========
        else:
            return ModalityAwarePreprocessor._get_generic_preprocessing()

    @staticmethod
    def _get_adni_preprocessing() -> str:
        """
        ADNI 专用预处理协议

        聚焦于：
        - 影像配准 (Registration)
        - 强度标准化 (Intensity Normalization)
        - 纵向数据对齐 (Longitudinal Alignment)
        """
        return """## 数据预处理阶段 - ADNI 专用流程

### 1. 影像数据预处理

#### 1.1 结构像 MRI (sMRI) 预处理
```python
import ants
import nibabel as nib
from nilearn import image

# ===== 步骤1: 影像配准 (Registration) =====
# 将所有受试者的 T1 加权像配准到标准空间 (MNI152)

def register_to_mni(t1_path, output_path):
    \"\"\"
    ANTs SyN 配准：高度精确的非线性配准
    \"\"\"
    # 固定图像：MNI152 模板
    fixed = ants.image_read('MNI152_T1_1mm_brain.nii.gz')
    moving = ants.image_read(t1_path)

    # 1. 粗配准（仿射变换）
    reg1 = ants.registration(fixed=fixed, moving=moving,
                               type_of_transform='Affine')

    # 2. 精细配准（SyN非线性变换）
    reg2 = ants.registration(fixed=fixed, moving=moving,
                               type_of_transform='SyN')

    # 3. 应用变换
    warped = ants.apply_transforms(fixed=fixed, moving=moving,
                                    transformlist=reg2['fwdtransforms'])

    # 4. 保存配准后的图像
    ants.image_write(warped, output_path)
    return warped

# ===== 步骤2: 强度标准化 (Intensity Normalization) =====
def intensity_normalization(img_path):
    \"\"\"
    Z-score 标准化 + 白质信号归一化
    \"\"\"
    import numpy as np

    img = nib.load(img_path)
    data = img.get_fdata()

    # 白质掩膜提取（使用 FSL FAST 或 SPM 脑组织分割）
    # 这里假设已有白质掩膜
    wm_mask = extract_wm_mask(img_path)  # 外部调用

    # 白质信号均值和标准差
    wm_mean = np.mean(data[wm_mask > 0])
    wm_std = np.std(data[wm_mask > 0])

    # Z-score 标准化
    normalized_data = (data - wm_mean) / wm_std

    # 保存标准化后的图像
    normalized_img = nib.Nifti1Image(normalized_data, img.affine, img.header)
    return normalized_img

# ===== 步骤3: 纵向数据对齐 (Longitudinal Alignment) =====
def longitudinal_alignment(subject_timepoints):
    \"\"\"
    同一受试者多时间点数据的纵向对齐
    使用 ANTs 的纵向配准模块
    \"\"\"
    baseline = subject_timepoints[0]

    aligned_timepoints = []
    for tp in subject_timepoints[1:]:
        # 配准到基线
        reg = ants.registration(fixed=baseline, moving=tp,
                                type_of_transform='SyN')
        warped = ants.apply_transforms(fixed=baseline, moving=tp,
                                        transformlist=reg['fwdtransforms'])
        aligned_timepoints.append(warped)

    return [baseline] + aligned_timepoints
```

#### 1.2 PET 预处理
```python
# ===== FDG-PET/AV45-PAM 预处理 =====
def preprocess_pet(pet_path, t1_path, output_path):
    \"\"\"
    PET 影像预处理：配准到 T1，部分容积效应校正
    \"\"\"
    # 1. PET 配准到 T1
    pet = ants.image_read(pet_path)
    t1 = ants.image_read(t1_path)

    reg = ants.registration(fixed=t1, moving=pet,
                            type_of_transform='Affine')

    pet_aligned = ants.apply_transforms(fixed=t1, moving=pet,
                                          transformlist=reg['fwdtransforms'])

    # 2. 部分容积效应校正 (PVC)
    # 使用 RBV (Region-based voxel-wise) 方法
    # 这里需要分割后的脑区掩膜

    # 3. SUVR 标准化 (Standardized Uptake Value Ratio)
    # 使用全脑 cerebellum 或 pons 作为参考区

    return pet_aligned
```

### 2. CSF/血液生物标志物预处理

```python
import pandas as pd
from sklearn.impute import KNNImputer
from scipy import stats

def preprocess_biomarkers(csf_df):
    \"\"\"
    CSF 生物标志物预处理
    - Aβ42, Aβ40, p-tau, t-tau
    - 批次效应校正
    - 缺失值插补
    \"\"\"
    # 1. 异常值检测（3σ原则）
    z_scores = stats.zscore(csf_df[['AB42', 'AB40', 'PTAU', 'TTAU']])
    outliers = np.abs(z_scores) > 3

    # 2. 批次效应校正（ComBat，使用检测批次作为协变量）
    from pycombat import Combat
    corrected = Combat().fit_transform(csf_df.values,
                                        batch=csf_df['batch'])

    # 3. 缺失值多重插补（MICE）
    from sklearn.experimental import enable_iterative_imputer
    from sklearn.impute import IterativeImputer

    mice = IterativeImputer(max_iter=10, random_state=42)
    csf_imputed = mice.fit_transform(csf_df)

    return pd.DataFrame(csf_imputed, columns=csf_df.columns)
```

### 3. 纵向数据分析准备

```python
def prepare_longitudinal_data(adni_data):
    \"\"\"
    纵向数据准备：构建混合效应模型所需的数据结构
    \"\"\"
    # 时间对齐：统一访视时间点（Baseline, M12, M24, M36, M48）
    time_mapping = {'bl': 0, 'm06': 6, 'm12': 12, 'm24': 24, 'm36': 36, 'm48': 48}

    adni_long = adni_data.copy()
    adni_long['time_months'] = adni_long['visit'].map(time_mapping)

    # 受试者内中心化（Within-subject centering）
    # 用于分离受试者间变异和受试者内变异
    adni_long['centered_age'] = adni_long.groupby('RID')['AGE'].transform(
        lambda x: x - x.mean()
    )

    return adni_long
```

### 4. 质量控制清单

- [ ] 影像配准质量检查（配准误差 < 2mm）
- [ ] 强度标准化验证（均值=0, 标准差=1）
- [ ] 纵向对齐验证（同一受试者时间点间一致性）
- [ ] PET SUVR 参考区选取一致性检查
- [ ] CSF 标志物批次效应评估（PCA 可视化）
- [ ] 缺失模式分析（MCAR/MAR/MNAR）
"""

    @staticmethod
    def _get_neuro_imaging_preprocessing() -> str:
        """通用神经影像预处理协议"""
        return """## 数据预处理阶段 - 神经影像数据

### 1. 影像预处理标准流程

#### 1.1 结构像预处理 (SPM12/FSL)
- **头动校正** (Realignment)
- **空间标准化** (Spatial Normalization to MNI152)
- **分割** (Segmentation: GM/WM/CSF)
- **平滑** (Smoothing: 6-8mm FWHM)

#### 1.2 功能像预处理 (fMRI)
- **层间时间校正** (Slice Timing Correction)
- **头动校正** (Realignment)
- **空间标准化** (Normalization)
- **平滑** (Smoothing: 6mm FWHM)
- **去噪声** (Denoising: aCompCor)

### 2. 质量控制指标

- FD_Jenkinson < 0.5mm (头动位移)
- SNR > 100 (信噪比)
- 覆盖率 > 90% (脑区覆盖)
"""

    @staticmethod
    def _get_csf_blood_preprocessing() -> str:
        """CSF/血液生物标志物预处理协议"""
        return """## 数据预处理阶段 - 生物标志物数据

### 1. 实验前质量控制

#### 1.1 样本采集标准
- **CSF**: 采集量 > 1mL，无血液污染
- **血浆**: 禁止溶血样本
- **储存**: -80°C 保存，避免反复冻融

#### 1.2 检测平台标准化
- 统一检测平台（如 Elecsys, INNO-BIA）
- 批内/批间 CV < 10%

### 2. 数据预处理

```python
# 1. 异常值检测（3σ原则）
# 2. 批次效应校正（ComBat）
# 3. 缺失值插补（MICE: m=5）
# 4. 标准化（Z-score）
```

### 3. 质量控制清单

- [ ] 溶血指标（血红蛋白）检测
- [ ] 批次效应评估（PCA 可视化）
- [ ] 缺失模式分析（Little's MCAR 检验）
"""

    @staticmethod
    def _get_clinical_preprocessing() -> str:
        """临床数据预处理协议"""
        return """## 数据预处理阶段 - 临床/EHR 数据

### 1. 数据清洗

#### 1.1 变量筛选
- 剔除缺失率 > 30% 的变量
- 剔除方差 = 0 的常数变量

#### 1.2 异常值处理
- 连续变量：Winsorize (1st/99th percentile)
- 分类变量：合并稀有类别 (< 5%)

### 2. 缺失值处理

```python
# MCAR/MAR 识别
# Little's MCAR 检验
# 缺失模式可视化（missingno.matrix）

# 多重插补（MICE）
from sklearn.impute import IterativeImputer
mice = IterativeImputer(max_iter=10, random_state=42)
```

### 3. 数据质量报告

- [ ] 变量完整性报告
- [ ] 分布正态性检验
- [ ] 多重共线性检测 (VIF < 5)
"""

    @staticmethod
    def _get_single_cell_preprocessing() -> str:
        """单细胞数据预处理协议（严格隔离）"""
        return """## 数据预处理阶段 - 单细胞多组学数据

**警告**: 以下协议仅用于单细胞/空间转录组数据！

### 1. 原始数据质控

#### 1.1 细胞级质控标准
- **线粒体基因比例** < 20%
- **检测基因数** > 200 (低质量细胞剔除)
- **UMI 计数** > 500 (空液滴剔除)
- **核糖体基因比例** < 50%

#### 1.2 基因级质控标准
- **低表达基因过滤**：在 < 10 个细胞中表达的基因
- **高变基因选择**：前 2000 HVGs

### 2. 批次效应校正

```python
import scanpy as sc

# ComBat-seq 校正
import scvi
scvi.model.SCVI.setup_anndata(adata)
vae = scvi.model.SCVI(adata)
adata.layers['corrected'] = vae.get_normalized_expression()
```

### 3. 降维与聚类

- **PCA** (前 50 PCs)
- **UMAP/tSNE** 降维可视化
- **Leiden/Louvain** 聚群
"""

    @staticmethod
    def _get_generic_preprocessing() -> str:
        """通用预处理协议"""
        return """## 数据预处理阶段 - 通用流程

### 1. 数据清洗
- 异常值检测与处理
- 缺失值插补（MICE/KNN）
- 标准化（Z-score/Min-Max）

### 2. 质量控制
- 数据完整性检查
- 分布验证
- 多重共线性检测

### 3. 特征工程
- 特征选择
- 特征变换
- 维度 reduction（如需要）
"""


class MediationAnalysisValidator:
    """中介分析验证器 - 确保因果推断的严谨性"""

    @staticmethod
    def get_bootstrap_mediation_code() -> str:
        """
        生成带 Bootstrap 的中介分析代码（因果推断金标准）

        使用 R 的 mediation 包，包含：
        - 非参数 Bootstrap 置信区间
        - 敏感性分析
        - 效应量分解（a, b, c, c' paths）
        """
        return """## 因果中介分析 - Bootstrap 实现（金标准）

### R 代码实现

```r
# 安装并加载 mediation 包
install.packages("mediation")
library(mediation)

# ===== 数据准备 =====
# X: 自变量 (暴露)
# M: 中介变量
# Y: 因变量 (结局)
# C: 协变量向量

# ===== 中介分析模型 =====
set.seed(12345)  # 确保可复现

# 1. 中介模型 (a path): M ~ X + C
model_m <- lm(M ~ X + C1 + C2 + C3, data = dataset)

# 2. 结局模型 (b/c' paths): Y ~ X + M + C
model_y <- lm(Y ~ X + M + C1 + C2 + C3, data = dataset)

# 3. Bootstrap 中介分析（非参数置信区间）
mediate_fit <- mediate(
    model.m = model_m,      # 中介模型
    model.y = model_y,      # 结局模型
    treat = "X",            # 自变量名
    mediator = "M",         # 中介变量名
    covariates = c("C1", "C2", "C3"),  # 协变量
    boot = TRUE,            # 启用 Bootstrap（金标准）
    sims = 5000,            # Bootstrap 抽样次数（建议 ≥ 5000）
    boot.ci.type = "bca",   # BCa 置信区间（偏差校正）
    conf.level = 0.95       # 95% 置信区间
)

# ===== 结果输出 =====
summary(mediate_fit)

# 输出解读：
# ACME (Average Causal Mediation Effect): 平均因果中介效应
# ADE (Average Direct Effect): 平均直接效应
# Total Effect: 总效应
# Prop.Mediated: 中介比例

# ===== Bootstrap 置信区间 =====
# 关键：查看 Bootstrap 得到的置信区间
# 如果置信区间不包含 0，则中介效应显著

# 提取 Bootstrap p 值
p_value_acme <- mediate_fit$d0$p  # ACME 的 p 值
p_value_ade <- mediate_fit$z0$p  # ADE 的 p 值

# ===== 敏感性分析 =====
# 检验中介效应对未测量混杂的敏感性
sens <- medsens(mediate_fit, rho.by = 0.1, R = 5000)
plot(sens)

# ===== 效应量报告 =====
cat("\\n=== 中介效应分析报告 ===\\n")
cat(sprintf("ACME: %.3f [%.3f, %.3f]\\n",
    mediate_fit$d0.avg,
    mediate_fit$d0.ci[1],
    mediate_fit$d0.ci[2]))
cat(sprintf("ADE: %.3f [%.3f, %.3f]\\n",
    mediate_fit$z0.avg,
    mediate_fit$z0.ci[1],
    mediate_fit$z0.ci[2]))
cat(sprintf("Total Effect: %.3f [%.3f, %.3f]\\n",
    mediate_fit$tau.coef,
    mediate_fit$tau.ci[1],
    mediate_fit$tau.ci[2]))
cat(sprintf("Proportion Mediated: %.1f%%\\n",
    mediate_fit$n0 * 100))
```

### Python 备选方案（使用 statsmodels）

```python
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.mediation import Mediation

# ===== 数据准备 =====
X = dataset['X'].values
M = dataset['M'].values
Y = dataset['Y'].values
C = dataset[['C1', 'C2', 'C3']].values

# ===== Bootstrap 中介分析 =====
mediate = Mediation(
    outcome_model=sm.OLS(Y, sm.add_constant(np.column_stack([X, M, C]))),
    mediator_model=sm.OLS(M, sm.add_constant(np.column_stack([X, C]))),
    exposure_var=0,      # X 在模型中的索引
    mediator_var=0       # M 在模型中的索引
)

# Bootstrap 置信区间
mediate_results = mediate.fit_bootstrap(
    n_bootstrap=5000,     # Bootstrap 抽样次数
    confidence_level=0.95
)

# 结果输出
print(f"ACME: {mediate_results.acme:.3f} [{mediate_results.acme_ci_lower:.3f}, {mediate_results.acme_ci_upper:.3f}]")
print(f"ADE: {mediate_results.ade:.3f} [{mediate_results.ade_ci_lower:.3f}, {mediate_results.ade_ci_upper:.3f}]")
print(f"Total Effect: {mediate_results.total_effect:.3f}")

# Bootstrap p 值
p_acme = mediate_results.test_acme()[1]  # ACME 的 p 值
p_ade = mediate_results.test_ade()[1]    # ADE 的 p 值
```

### 关键注意事项

1. **Bootstrap 是金标准**：
   - 非参数 Bootstrap 不假设正态分布
   - BCa 置信区间修正偏差
   - 抽样次数 ≥ 5000 确保稳定性

2. **效应量报告**：
   - ACME: 中介效应的大小
   - ADE: 直接效应的大小（X → Y，不经过 M）
   - Proportion Mediated: ACME / Total Effect

3. **敏感性分析**：
   - 使用 Rho 参数模拟未测量混杂
   - 检验结论在不同 Rho 水平下的稳健性

4. **p 值解读**：
   - ACME 的 p 值：检验中介效应是否显著
   - ADE 的 p 值：检验直接效应是否显著
   - 使用 Bootstrap p 值，而非 Sobel 检验（假设正态）
"""

# 验证规则：检查中介分析代码是否包含 Bootstrap
VALIDATION_RULES = {
    'bootstrap_required': {
        'keywords': ['boot', 'bootstrap', 'bca', 'percentile'],
        'min_sims': 5000,
        'error_msg': '中介分析必须包含 Bootstrap 置信区间（金标准）'
    },
    'effect_decomposition': {
        'required': ['acme', 'ade', 'total'],
        'error_msg': '必须报告 ACME, ADE, Total Effect'
    },
    'sensitivity_analysis': {
        'keywords': ['rho', 'sensitivity', 'medsens'],
        'error_msg': '必须包含敏感性分析（未测量混杂评估）'
    }
}


def validate_mediation_analysis(code: str) -> Dict[str, any]:
    """
    验证中介分析代码是否符合因果推断金标准

    Returns:
        {
            'is_valid': bool,
            'errors': List[str],
            'warnings': List[str]
        }
    """
    result = {
        'is_valid': True,
        'errors': [],
        'warnings': []
    }

    code_lower = code.lower()

    # 检查 Bootstrap
    if 'bootstrap' not in code_lower and 'boot' not in code_lower:
        result['errors'].append(VALIDATION_RULES['bootstrap_required']['error_msg'])
        result['is_valid'] = False

    # 检查效应量分解
    for effect in VALIDATION_RULES['effect_decomposition']['required']:
        if effect not in code_lower:
            result['warnings'].append(f"缺少 {effect.upper()} 报告")

    # 检查敏感性分析
    has_sensitivity = any(kw in code_lower for kw in VALIDATION_RULES['sensitivity_analysis']['keywords'])
    if not has_sensitivity:
        result['warnings'].append(VALIDATION_RULES['sensitivity_analysis']['error_msg'])

    return result
