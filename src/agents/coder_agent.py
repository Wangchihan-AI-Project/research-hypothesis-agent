# -*- coding: utf-8 -*-
"""
高级生信/AI研发工程师智能体 (Bioinformatics Code Generator)
全栈 Python/R 工程师，专门��成可执行的生物信息学代码骨架

核心任务：
- 读取博士开题报告和数据集信息
- 生成完整的代码实现指南
- 输出 requirements.txt、数据加载代码、核心模型代码

工作流位置：接在 Thesis Writer 之后，整个流程最末端
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
from core.reproducibility_engine import EnvironmentFreezer
from utils.llm_utils import SafeExtractor, LLMParseError


# ============ 生物信息学常用依赖库（严格版本锁定） ============
# 注意：所有版本号使用 == 格式，确保绝对可复现性

BIOINFO_REQUIREMENTS = {
    'single_cell': {
        'core': [
            'scanpy==1.10.1',
            'anndata==0.10.3',
            'scvi-tools==0.20.3',
            'scvelo==0.3.2',
            'cell2location==0.1.2'
        ],
        'ml': [
            'torch==2.0.1',
            'torch-scatter==2.3.1',
            'torch-sparse==0.6.3',
            'torch-geometric==2.3.1',
            'pyg-lib==0.3.1'
        ],
        'visualization': [
            'matplotlib==3.7.2',
            'seaborn==0.12.2',
            'plotly==5.15.0'
        ]
    },
    'genomics': {
        'core': [
            'pandas==2.0.3',
            'numpy==1.24.3',
            'scikit-learn==1.3.0',
            'scipy==1.11.1'
        ],
        'genomics_specific': [
            'mygene==3.2.2',
            'myvariant==1.0.0',
            'gseapy==1.0.3',
            'lifelines==0.27.8',
            'pycox==0.2.0'
        ],
        'tcga': [
            'tcga_utils==0.3.0',
            'cBioPortalData==0.1.0'
        ]
    },
    'spatial': {
        'core': [
            'squidpy==1.4.1',
            'spatialdata==0.2.2',
            'napari-spatialdata==0.1.0'
        ],
        'image': [
            'openslide-python==1.1.2',
            'tifffile==2023.8.0',
            'imagecodecs==2023.8.0'
        ]
    },
    'graph_ml': {
        'core': [
            'torch==2.0.1',
            'torch-geometric==2.3.1',
            'torch-scatter==2.3.1',
            'torch-sparse==0.6.3',
            'dgl==1.1.0'
        ],
        'gnn_models': [
            'ogb==1.3.6',
            'torch-cluster==1.6.1',
            'torch-spline-conv==1.2.2'
        ]
    },
    'foundation_model': {
        'core': [
            'transformers==4.35.2',
            'accelerate==0.24.1',
            'peft==0.6.1',
            'bitsandbytes==0.41.1'
        ],
        'genomics_specific': [
            'geneformer==0.1.0',
            'nucleotide-transformer==0.1.0',
            'hyenadna==0.1.0'
        ]
    },
    'causal_inference': {
        'core': [
            'dowhy==0.11.1',
            'econml==0.14.0',
            'causal-learn==0.1.3'
        ],
        'discovery': [
            'cdt==0.6.0',
            'lingam==0.1.0'
        ]
    }
}

# ============ 代码模板 ============

DATA_LOADING_TEMPLATE = """
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
数据加载与预处理模块
项目：{project_name}
作者：BioAI Code Generator
\"\"\"

import os
import numpy as np
import pandas as pd
import scanpy as sc
from pathlib import Path
from typing import Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# ==================== 配置 ====================
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"

# 创建目录
for dir_path in [DATA_DIR, RAW_DIR, PROCESSED_DIR, CACHE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==================== {data_type} 数据加载 ====================

class {dataset_class}Loader:
    \"\"\"{data_type}数据加载器\"\"\"

    def __init__(self, data_path: str = None):
        self.data_path = Path(data_path) if data_path else RAW_DIR
        self.adata = None

    def load_from_file(self, file_path: str) -> sc.AnnData:
        \"\"\"从文件加载{data_type}数据\"\"\"
        # 根据文件类型选择加载方法
        if file_path.endswith('.h5ad'):
            self.adata = sc.read_h5ad(file_path)
        elif file_path.endswith('.h5'):
            import h5py
            # H5 文件加载逻辑
            pass
        elif file_path.endswith('.csv'):
            # CSV 文件加载逻辑
            data = pd.read_csv(file_path, index_col=0)
            self.adata = sc.AnnData(data)
        else:
            raise ValueError(f"不支持的文件格式: {{file_path}}")

        return self.adata

    def quality_control(self) -> sc.AnnData:
        \"\"\"质量控制\"\"\"
        if self.adata is None:
            raise ValueError("请先加载数据")

        # 计算QC指标
        self.adata.var['mt'] = self.adata.var_names.str.startswith('MT-')
        sc.pp.calculate_qc_metrics(
            self.adata,
            qc_vars=['mt'],
            percent_top=None,
            log1p=False,
            inplace=True
        )

        # 过滤低质量细胞
        sc.pp.filter_cells(self.adata, min_genes=200)
        sc.pp.filter_genes(self.adata, min_cells=3)

        # 过滤异常值
        self.adata = self.adata[
            (self.adata.obs.n_genes_by_counts < 5000) &
            (self.adata.obs.pct_counts_mt < 20)
        ].copy()

        return self.adata

    def normalize(self) -> sc.AnnData:
        \"\"\"标准化\"\"\"
        # 保存原始数据
        self.adata.layers['counts'] = self.adata.X.copy()

        # 对数归一化
        sc.pp.normalize_total(self.adata, target_sum=1e4)
        sc.pp.log1p(self.adata)

        return self.adata

    def highly_variable_genes(self, n_top_genes: int = 2000) -> sc.AnnData:
        \"\"\"识别高变基因\"\"\"
        sc.pp.highly_variable_genes(
            self.adata,
            n_top_genes=n_top_genes,
            flavor='seurat_v3'
        )
        self.adata = self.adata[:, self.adata.var.highly_variable].copy()

        return self.adata

    def pca_embedding(self, n_comps: int = 50) -> sc.AnnData:
        \"\"\"PCA降维\"\"\"
        sc.tl.pca(self.adata, n_comps=n_comps, svd_solver='arpack')
        return self.adata

    def neighbor_graph(self, n_neighbors: int = 15) -> sc.AnnData:
        \"\"\"构建邻域图\"\"\"
        sc.pp.neighbors(self.adata, n_neighbors=n_neighbors)
        return self.adata

    def umap_embedding(self) -> sc.AnnData:
        \"\"\"UMAP降维\"\"\"
        sc.tl.umap(self.adata)
        return self.adata

    def leiden_clustering(self, resolution: float = 0.5) -> sc.AnnData:
        \"\"\"Leiden聚类\"\"\"
        sc.tl.leiden(self.adata, resolution=resolution)
        return self.adata

    def full_pipeline(self, file_path: str) -> sc.AnnData:
        \"\"\"完整预处理流程\"\"\"
        print(f"加载数据: {{file_path}}")
        self.load_from_file(file_path)

        print("质量控制...")
        self.quality_control()

        print("标准化...")
        self.normalize()

        print("识别高变基因...")
        self.highly_variable_genes()

        print("PCA降维...")
        self.pca_embedding()

        print("构建邻域图...")
        self.neighbor_graph()

        print("UMAP降维...")
        self.umap_embedding()

        print("Leiden聚类...")
        self.leiden_clustering()

        print(f"处理完成: {{self.adata.shape}}")
        return self.adata


# ==================== 主函数 ====================

if __name__ == "__main__":
    # 使用示例
    loader = {dataset_class}Loader()

    # 替换为实际数据路径
    adata = loader.full_pipeline("path/to/your/data.h5ad")

    # 保存处理后的数据
    adata.write(PROCESSED_DIR / "processed_data.h5ad")

    print("\\n数据预处理完成！")
    print(f"细胞数: {{adata.n_obs}}")
    print(f"基因数: {{adata.n_vars}}")
```
"""

MODEL_TEMPLATE = """
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
{model_name} 模型定义
项目：{project_name}
架构：{architecture_type}
\"\"\"

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import {gnn_layers}
from torch_geometric.data import Data, Batch
from typing import Optional, Dict, List, Tuple
import math


# ==================== {model_name} 模型 ====================

class {model_class}(nn.Module):
    \"\"\"
    {model_description}

    Args:
        in_channels: 输入特征维度
        hidden_channels: 隐藏层维度
        out_channels: 输出维度
        num_layers: GNN层数
        dropout: Dropout比例
        heads: 注意力头数（GAT）
    \"\"\"

    def __init__(
        self,
        in_channels: int,
        hidden_channels: int = 256,
        out_channels: int = 128,
        num_layers: int = 3,
        dropout: float = 0.1,
        heads: int = 4
    ):
        super().__init__()

        self.in_channels = in_channels
        self.hidden_channels = hidden_channels
        self.out_channels = out_channels
        self.num_layers = num_layers
        self.dropout = dropout

        # 输入嵌入层
        self.input_encoder = nn.Linear(in_channels, hidden_channels)

        # GNN层
        self.convs = nn.ModuleList()
        self.batch_norms = nn.ModuleList()

        for i in range(num_layers):
            if i == 0:
                in_dim = hidden_channels
            else:
                in_dim = hidden_channels * heads

            self.convs.append(
                {gnn_layer_class}(in_dim, hidden_channels, heads=heads, dropout=dropout)
            )
            self.batch_norms.append(nn.BatchNorm1d(hidden_channels * heads))

        # 输出层
        self.output_encoder = nn.Sequential(
            nn.Linear(hidden_channels * heads, hidden_channels),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels, out_channels)
        )

        # 可选：分类/预测头
        self.prediction_head = nn.Sequential(
            nn.Linear(out_channels, out_channels // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(out_channels // 2, num_classes)
        )

        self.reset_parameters()

    def reset_parameters(self):
        \"\"\"初始化参数\"\"\"
        for conv in self.convs:
            if hasattr(conv, 'reset_parameters'):
                conv.reset_parameters()
        for bn in self.batch_norms:
            bn.reset_parameters()
        for module in [self.input_encoder, self.output_encoder, self.prediction_head]:
            for layer in module:
                if isinstance(layer, nn.Linear):
                    nn.init.xavier_uniform_(layer.weight)
                    if layer.bias is not None:
                        nn.init.zeros_(layer.bias)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: Optional[torch.Tensor] = None,
        batch: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        \"\"\"
        前向传播

        Args:
            x: 节点特征 [num_nodes, in_channels]
            edge_index: 边索引 [2, num_edges]
            edge_attr: 边特征 [num_edges, edge_dim]
            batch: 批次索引 [num_nodes]

        Returns:
            节点/图级别表示
        \"\"\"
        # 输入编码
        x = self.input_encoder(x)
        x = F.relu(x)
        x = F.dropout(x, p=self.dropout, training=self.training)

        # GNN层
        for i, (conv, bn) in enumerate(zip(self.convs, self.batch_norms)):
            x = conv(x, edge_index, edge_attr)
            x = bn(x)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)

        # 输出编码
        x = self.output_encoder(x)

        return x

    def predict(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        batch: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        \"\"\"预测任务\"\"\"
        embeddings = self.forward(x, edge_index, batch=batch)

        if batch is not None:
            # 图级别预测
            from torch_geometric.nn import global_mean_pool
            x = global_mean_pool(embeddings, batch)
        else:
            # 节点级别预测
            x = embeddings

        return self.prediction_head(x)

    def embed(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        \"\"\"获取嵌入表示\"\"\"
        return self.forward(x, edge_index, edge_attr)


# ==================== 对比学习变体 ====================

class {model_class}Contrastive(nn.Module):
    \"\"\"
    带对比学习的{model_name}变体
    使用SimCLR/MoCO风格的对比损失
    \"\"\"

    def __init__(
        self,
        encoder: {model_class},
        projection_dim: int = 128,
        temperature: float = 0.5
    ):
        super().__init__()

        self.encoder = encoder
        self.temperature = temperature

        # 投影头
        self.projection_head = nn.Sequential(
            nn.Linear(encoder.out_channels, encoder.out_channels),
            nn.ReLU(),
            nn.Linear(encoder.out_channels, projection_dim)
        )

    def forward(
        self,
        x1: torch.Tensor,
        x2: torch.Tensor,
        edge_index1: torch.Tensor,
        edge_index2: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        \"\"\"对比学习前向传播\"\"\"

        # 获取投影
        z1 = self.projection_head(self.encoder.embed(x1, edge_index1))
        z2 = self.projection_head(self.encoder.embed(x2, edge_index2))

        # L2归一化
        z1 = F.normalize(z1, dim=1)
        z2 = F.normalize(z2, dim=1)

        return z1, z2

    def contrastive_loss(
        self,
        z1: torch.Tensor,
        z2: torch.Tensor,
        batch_size: int
    ) -> torch.Tensor:
        \"\"\"计算对比损失（NT-Xent）\"\"\"

        # 拼接正样本对
        z = torch.cat([z1, z2], dim=0)
        # [2N, D]

        # 计算相似度矩阵
        sim_matrix = torch.mm(z, z.t()) / self.temperature
        # [2N, 2N]

        # 创建标签（对角线移位）
        labels = torch.arange(batch_size).to(z.device)
        labels = torch.cat([labels + batch_size, labels])

        # 排除自身
        mask = torch.eye(2 * batch_size, dtype=torch.bool).to(z.device)
        sim_matrix = sim_matrix.masked_fill(mask, -float('inf'))

        # 计算交叉熵损失
        loss = F.cross_entropy(
            sim_matrix.reshape(-1, sim_matrix.size(-1)),
            labels.repeat(2)
        )

        return loss


# ==================== 因果推断变体 ====================

class {model_class}Causal(nn.Module):
    \"\"\"
    带因果推断的{model_name}变体
    使用前门准则/后门准则调整
    \"\"\"

    def __init__(
        self,
        encoder: {model_class},
        treatment_dim: int,
        outcome_dim: int,
        hidden_dim: int = 128
    ):
        super().__init__()

        self.encoder = encoder

        # 倾向性得分网络（Propensity Score）
        self.propensity_net = nn.Sequential(
            nn.Linear(encoder.out_channels, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid()
        )

        # 结果网络（Outcome Network）
        self.outcome_net_treated = nn.Sequential(
            nn.Linear(encoder.out_channels, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, outcome_dim)
        )

        self.outcome_net_control = nn.Sequential(
            nn.Linear(encoder.out_channels, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, outcome_dim)
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        treatment: Optional[torch.Tensor] = None
    ) -> Dict[str, torch.Tensor]:
        \"\"\"因果推断前向传播\"\"\"

        # 获取嵌入
        embeddings = self.encoder.embed(x, edge_index)

        # 计算倾向性得分
        propensity = self.propensity_net(embeddings)

        # 计算潜在结果
        y_treated = self.outcome_net_treated(embeddings)
        y_control = self.outcome_net_control(embeddings)

        # 估计因果效应（ATE）
        if treatment is not None:
            # 观察到的结果
            y_observed = treatment * y_treated + (1 - treatment) * y_control

            # 逆概率加权（IPW）
            ipw = treatment / propensity + (1 - treatment) / (1 - propensity)
            ate = (y_treated - y_control).mean()

            return {{
                'embeddings': embeddings,
                'propensity': propensity,
                'y_treated': y_treated,
                'y_control': y_control,
                'y_observed': y_observed,
                'ate': ate
            }}
        else:
            return {{
                'embeddings': embeddings,
                'propensity': propensity,
                'y_treated': y_treated,
                'y_control': y_control
            }}

    def causal_loss(
        self,
        predictions: Dict[str, torch.Tensor],
        treatment: torch.Tensor,
        outcome: torch.Tensor,
        alpha: float = 0.5
    ) -> torch.Tensor:
        \"\"\"因果推断损失\"\"\"

        # 结果损失（MSE）
        outcome_loss = F.mse_loss(predictions['y_observed'], outcome)

        # 倾向性损失（BCE）
        propensity_loss = F.binary_cross_entropy(
            predictions['propensity'].squeeze(),
            treatment
        )

        # 平衡损失（协变量平衡）
        treated_embed = predictions['embeddings'][treatment == 1]
        control_embed = predictions['embeddings'][treatment == 0]

        if len(treated_embed) > 0 and len(control_embed) > 0:
            balance_loss = torch.abs(
                treated_embed.mean(dim=0) - control_embed.mean(dim=0)
            ).mean()
        else:
            balance_loss = torch.tensor(0.0).to(predictions['embeddings'].device)

        # 总损失
        total_loss = outcome_loss + alpha * propensity_loss + balance_loss

        return total_loss


# ==================== 训练器 ====================

class {model_class}Trainer:
    \"\"\"{model_name}训练器\"\"\"

    def __init__(
        self,
        model: nn.Module,
        device: str = 'cuda' if torch.cuda.is_available() else 'cpu',
        learning_rate: float = 1e-3
    ):
        self.model = model.to(device)
        self.device = device

        self.optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=learning_rate,
            weight_decay=1e-5
        )

        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=10
        )

    def train_epoch(
        self,
        train_loader: torch.utils.data.DataLoader,
        epoch: int
    ) -> float:
        \"\"\"训练一个epoch\"\"\"
        self.model.train()
        total_loss = 0.0

        for batch in train_loader:
            batch = batch.to(self.device)

            # 前向传播
            self.optimizer.zero_grad()
            output = self.model(batch.x, batch.edge_index, batch.batch)

            # 计算损失（根据任务调整）
            loss = self._compute_loss(output, batch)

            # 反向传播
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()

            total_loss += loss.item()

        return total_loss / len(train_loader)

    def evaluate(
        self,
        test_loader: torch.utils.data.DataLoader
    ) -> Dict[str, float]:
        \"\"\"评估模型\"\"\"
        self.model.eval()
        total_loss = 0.0
        all_preds = []
        all_labels = []

        with torch.no_grad():
            for batch in test_loader:
                batch = batch.to(self.device)
                output = self.model(batch.x, batch.edge_index, batch.batch)

                loss = self._compute_loss(output, batch)
                total_loss += loss.item()

                # 收集预测结果
                if hasattr(output, 'predict'):
                    preds = output.predict(batch.x, batch.edge_index, batch.batch)
                else:
                    preds = output

                all_preds.append(preds.cpu())
                all_labels.append(batch.y.cpu())

        # 计算指标
        all_preds = torch.cat(all_preds)
        all_labels = torch.cat(all_labels)

        from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

        metrics = {{
            'loss': total_loss / len(test_loader),
            'accuracy': accuracy_score(all_labels.numpy(), all_preds.argmax(dim=1).numpy()),
            'f1': f1_score(all_labels.numpy(), all_preds.argmax(dim=1).numpy(), average='macro')
        }}

        return metrics

    def _compute_loss(self, output, batch):
        \"\"\"计算损失（根据任务调整）\"\"\"
        # 分类任务
        if hasattr(batch, 'y'):
            return F.cross_entropy(output, batch.y)
        # 其他任务...
        return output.loss if hasattr(output, 'loss') else torch.tensor(0.0)

    def fit(
        self,
        train_loader: torch.utils.data.DataLoader,
        val_loader: torch.utils.data.DataLoader,
        num_epochs: int = 100,
        early_stopping_patience: int = 20
    ):
        \"\"\"完整训练流程\"\"\"
        best_val_loss = float('inf')
        patience_counter = 0

        for epoch in range(num_epochs):
            # 训练
            train_loss = self.train_epoch(train_loader, epoch)

            # 验证
            val_metrics = self.evaluate(val_loader)
            val_loss = val_metrics['loss']

            # 学习率调度
            self.scheduler.step(val_loss)

            # 早停
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # 保存最佳模型
                torch.save(self.model.state_dict(), 'best_model.pth')
            else:
                patience_counter += 1
                if patience_counter >= early_stopping_patience:
                    print(f"Early stopping at epoch {{epoch}}")
                    break

            if epoch % 10 == 0:
                print(f"Epoch {{epoch}}: train_loss={{train_loss:.4f}}, val_loss={{val_loss:.4f}}")


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 模型初始化
    model = {model_class}(
        in_channels=1000,  # 基因数
        hidden_channels=256,
        out_channels=128,
        num_layers=3,
        dropout=0.1
    )

    # 训练器
    trainer = {model_class}Trainer(model, learning_rate=1e-3)

    # 开始训练（需要准备数据加载器）
    # trainer.fit(train_loader, val_loader, num_epochs=100)

    print("模型初始化完成！")
    print(f"参数量: {{sum(p.numel() for p in model.parameters()):,}}")
```
"""


class CoderAgent(BaseAgent):
    """
    高级生信/AI研发工程师智能体 (Production-Ready Bioinformatics Code Engineer)

    Core Mandate:
    - 生产环境标准: 所有代码必须达到生产环境部署标准
    - 可移植性: 代码必须能在不同环境中稳定运行
    - 极致性能优化: 追求算法的最优性能表现
    - 完��的单元测试: 每个函数必须有对应的单元测试

    评估标准:
    - 新颖性: 代码架构或实现方式是否有创新
    - 严谨性: 代码质量是否达到生产标准
    - 颠覆性: 是否通过代码优化实现性能突破

    禁止: "玩具代码"，忽视错误处理、边界条件
    """

    def __init__(self):
        super().__init__("高级生信/AI研发工程师", agent_type="coder")
        base_url = os.getenv("ANTHROPIC_BASE_URL") or None
        if base_url:
            self.client = anthropic.Anthropic(api_key=self.api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)

        # 防弹机制
        self.max_retries = 3
        self.extractor = SafeExtractor()
        self.min_guide_length = 2000  # 代码指南最小长度

    def execute(self, input_data: Dict) -> Dict:
        """
        执行代码生成任务

        Args:
            input_data: {
                'thesis_proposal': str - 博士开题报告
                'datasets': list - 数据集信息
                'paradigm_framework': str - 前沿框架
                'output_dir': str - 输出目录
            }

        Returns:
            {
                'success': bool,
                'code_guide': str - 代码实现指南
                'requirements': str - requirements.txt内容
                'data_loader_code': str - 数据加载代码
                'model_code': str - 模型代码
                'guide_path': str - 指南保存路径
            }
        """
        thesis_proposal = input_data.get('thesis_proposal', '')
        datasets = input_data.get('datasets', [])
        paradigm_framework = input_data.get('paradigm_framework', '')
        output_dir = input_data.get('output_dir', 'reports')

        if not thesis_proposal:
            return {
                'success': False,
                'error': '缺少开题报告'
            }

        # 分析研究类型
        research_type = self._analyze_research_type(thesis_proposal, paradigm_framework)

        # 生成代码指南
        code_guide = self._generate_code_guide(
            thesis_proposal=thesis_proposal,
            datasets=datasets,
            paradigm_framework=paradigm_framework,
            research_type=research_type
        )

        # 保存指南
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        guide_path = os.path.join(output_dir, f"Code_Implementation_Guide_{timestamp}.md")

        with open(guide_path, 'w', encoding='utf-8') as f:
            f.write(code_guide)

        # 验证生成的代码指南
        if not code_guide or len(code_guide.strip()) < self.min_guide_length:
            raise ValueError(f"生成的代码指南过短: {len(code_guide) if code_guide else 0} 字符，最少需要 {self.min_guide_length} 字符")

        # P2-2 修复：验证必要章节存在
        required_sections = {
            'requirements': ['requirements.txt', '依赖', 'environment', '环境配置', 'pip install'],
            '数据加载': ['数据加载', 'dataset', 'dataloader', '数据预处理', 'DataLoader', 'data load'],
            '模型架构': ['模型架构', 'model', 'network', '神经网络', 'Model', 'architecture'],
            '训练策略': ['训练', 'train', '优化', 'optimizer', '损失函数', 'loss', 'training']
        }

        missing_sections = []
        for section_name, keywords in required_sections.items():
            # 检查是否包含任何相关关键词
            if not any(kw in code_guide for kw in keywords):
                missing_sections.append(section_name)

        if missing_sections:
            raise ValueError(f"生成的代码指南缺少必要章节: {', '.join(missing_sections)}")

        return {
            'success': True,
            'code_guide': code_guide,
            'guide_path': guide_path,
            'research_type': research_type
        }

    def _analyze_research_type(self, thesis_proposal: str, paradigm_framework: str) -> str:
        """分析研究类型"""
        content = (thesis_proposal + ' ' + paradigm_framework).lower()

        # 检测关键词
        if any(kw in content for kw in ['single cell', '单细胞', 'scrna', 'scanpy', 'seurat']):
            return 'single_cell'
        elif any(kw in content for kw in ['spatial', '空间', 'spatial transcript', 'histology']):
            return 'spatial'
        elif any(kw in content for kw in ['gnn', 'graph', 'network', 'graph neural', '图神经网络']):
            return 'graph_ml'
        elif any(kw in content for kw in ['transformer', 'foundation model', 'pre-train', 'bert', 'gpt']):
            return 'foundation_model'
        elif any(kw in content for kw in ['causal', 'causality', '因果', 'intervention', 'do-calculus']):
            return 'causal_inference'
        else:
            return 'genomics'

    def _generate_code_guide(
        self,
        thesis_proposal: str,
        datasets: list,
        paradigm_framework: str,
        research_type: str
    ) -> str:
        """生成代码实现指南"""

        # 提取项目名称
        project_name = self._extract_project_name(thesis_proposal)

        # 生成 requirements.txt
        requirements = self._generate_requirements(research_type)

        # 生成数据加载代码
        data_loader_code = self._generate_data_loader_code(
            research_type, project_name, datasets
        )

        # 生成模型代码
        model_code = self._generate_model_code(
            research_type, paradigm_framework, project_name
        )

        # 组装完整指南
        cn_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        guide = f"""# 核心代码实现指南

**生成时间**: {cn_time}
**智能体**: 高级生信/AI研发工程师 (Bioinformatics Code Generator)
**项目名称**: {project_name}
**研究类型**: {self._get_research_type_name(research_type)}

---

## 目录

1. [环境配置](#环境配置)
2. [数据加载与预处理](#数据加载与预处理)
3. [核心模型实现](#核心模型实现)
4. [训练与评估](#训练与评估)
5. [可视化与分析](#可视化与分析)

---

## 环境配置

### Python 版本

建议使用 Python 3.9 或更高版本。

### 安装依赖

创建虚拟环境并安装依赖：

```bash
# 创建虚拟环境
conda create -n bioai python=3.10
conda activate bioai

# 安装 PyTorch (根据您的 CUDA 版本调整)
pip install torch==2.0.0 torchvision==0.15.0 torchaudio==2.0.0 --index-url https://download.pytorch.org/whl/cu118

# 安装 PyTorch Geometric
pip install torch-geometric==2.3.0
pip install torch-scatter torch-sparse -f https://data.pyg.org/whl/torch-2.0.0+cu118.html

# 安装其他依赖
pip install -r requirements.txt
```

### requirements.txt

```text
# ==================== 核心科学计算库 ====================
numpy>=1.24.0
pandas>=2.0.0
scipy>=1.10.0
scikit-learn>=1.3.0

# ==================== 深度学习框架 ====================
torch>=2.0.0
torchvision>=0.15.0
torchaudio>=2.0.0

# ==================== 图神经网络 ====================
torch-geometric>=2.3.0
torch-scatter>=2.3.0
torch-sparse>=0.6.0
pyg-lib>=0.3.0

{requirements}

# ==================== 可视化 ====================
matplotlib>=3.7.0
seaborn>=0.12.0
plotly>=5.14.0

# ==================== 生物信息学专用库 ====================
# 根据具体研究类型选择安装
# scanpy>=1.10.0  # 单细胞分析
# squidpy>=1.4.0  # 空间转录组
# scvi-tools>=0.20.0  # 概率生成模型

# ==================== 工具库 ====================
tqdm>=4.65.0
tensorboard>=2.13.0
wandb>=0.15.0
python-dotenv>=1.0.0
pyyaml>=6.0

# ==================== Jupyter 支持 ====================
jupyter>=1.0.0
ipywidgets>=8.0.0
```

---

## 数据加载与预处理

### 数据集信息

"""

        # 添加数据集信息
        if datasets:
            guide += "根据开题报告，将使用以下数据集：\n\n"
            for i, dataset in enumerate(datasets[:5], 1):
                if isinstance(dataset, dict):
                    guide += f"{i}. **{dataset.get('name', 'N/A')}** - {dataset.get('accession', 'N/A')}\n"
                    guide += f"   - {dataset.get('description', '')}\n\n"
                else:
                    guide += f"{i}. {dataset}\n"
        else:
            guide += "请根据开题报告中的数据获取部分，从以下数据库下载数据：\n\n"
            guide += "- **单细胞数据**: Human Cell Atlas, GEO (GSEXXXXX)\n"
            guide += "- **基因组数据**: TCGA, ICGC, cBioPortal\n"
            guide += "- **空间数据**: Spatial Transcriptomics, 10x Visium\n\n"

        guide += f"""
{data_loader_code}

### 数据预处理流程

根据研究类型，标准的预处理流程包括：

1. **质量控制** - 过滤低质量细胞/基因
2. **标准化** - 对数归一化、TPM/FPKM
3. **特征选择** - 高变基因选择
4. **降维** - PCA、UMAP、t-SNE
5. **批次校正** - Harmony、BBKNN、ComBat

---

## 核心模型实现

### 模型架构

根据开题报告的研究方案，核心模型采用 **{paradigm_framework}** 框架。

{model_code}

### 模型训练策略

1. **预训练**（如适用）：在大规模数据上进行自监督预训练
2. **微调**：在特定任务数据上进行有监督微调
3. **评估**：使用独立测试集进行性能评估

---

## 训练与评估

### 训练脚本

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"训练脚本\"\"\"

import torch
from torch.utils.data import DataLoader
from your_model import {project_name.replace(' ', '').replace('-', '')}Model, {project_name.replace(' ', '').replace('-', '')}Trainer
from your_data import {project_name.replace(' ', '').replace('-', '')}Dataset

# 配置
CONFIG = {{
    'batch_size': 32,
    'learning_rate': 1e-3,
    'num_epochs': 100,
    'early_stopping_patience': 20,
    'device': 'cuda' if torch.cuda.is_available() else 'cpu'
}}

# 加载数据
train_dataset = {project_name.replace(' ', '').replace('-', '')}Dataset(split='train')
val_dataset = {project_name.replace(' ', '').replace('-', '')}Dataset(split='val')

train_loader = DataLoader(train_dataset, batch_size=CONFIG['batch_size'], shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=CONFIG['batch_size'])

# 初始化模型
model = {project_name.replace(' ', '').replace('-', '')}Model(
    in_channels=train_dataset.num_features,
    hidden_channels=256,
    out_channels=128,
    num_classes=train_dataset.num_classes
)

# 训练
trainer = {project_name.replace(' ', '').replace('-', '')}Trainer(model, learning_rate=CONFIG['learning_rate'])
trainer.fit(train_loader, val_loader, num_epochs=CONFIG['num_epochs'])

# 评估
test_metrics = trainer.evaluate(test_loader)
print(f"Test Accuracy: {{test_metrics['accuracy']:.4f}}")
```

---

## 可视化与分析

### 结果可视化

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"可视化脚本\"\"\"

import matplotlib.pyplot as plt
import seaborn as sns
import scanpy as sc

# 设置绘图风格
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['font.size'] = 12

# 1. UMAP 可视化
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 原始标签
sc.pl.umap(adata, color='cell_type', ax=axes[0], show=False)
axes[0].set_title('Original Cell Types')

# 预测标签
sc.pl.umap(adata, color='predicted', ax=axes[1], show=False)
axes[1].set_title('Predicted Labels')

plt.tight_layout()
plt.savefig('umap_comparison.png', dpi=300)

# 2. 混淆矩阵
from sklearn.metrics import confusion_matrix
cm = confusion_matrix(true_labels, pred_labels)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
plt.xlabel('Predicted')
plt.ylabel('True')
plt.savefig('confusion_matrix.png', dpi=300)

# 3. ROC 曲线
from sklearn.metrics import roc_curve, auc
fpr, tpr, _ = roc_curve(true_labels, pred_probs)
roc_auc = auc(fpr, tpr)

plt.figure()
plt.plot(fpr, tpr, label=f'ROC curve (AUC = {{roc_auc:.2f}})')
plt.plot([0, 1], [0, 1], 'k--')
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.legend()
plt.savefig('roc_curve.png', dpi=300)
```

---

## 项目结构

```
{project_name.replace(' ', '-').lower()}/
├── data/
│   ├── raw/              # 原始数据
│   ├── processed/        # 处理后数据
│   └── cache/            # 缓存文件
├── models/
│   ├── __init__.py
│   ├── gnn_model.py      # GNN模型定义
│   ├── data_loader.py    # 数据加载
│   └── trainer.py        # 训练器
├── notebooks/
│   └── exploration.ipynb # 探索性分析
├── scripts/
│   ├── train.py          # 训练脚本
│   ├── evaluate.py       # 评估脚本
│   └── visualize.py      # 可视化脚本
├── configs/
│   └── config.yaml       # 配置文件
├── requirements.txt      # 依赖列表
├── setup.py              # 安装脚本
└── README.md             # 项目说明
```

---

## 常见问题

### Q1: CUDA out of memory

**解决方案**:
- 减小 batch_size
- 使用梯度累积
- 使用混合精度训练 (torch.cuda.amp)

### Q2: 数据加载慢

**解决方案**:
- 使用 HDF5 (.h5ad) 格式存储
- 预处理并缓存数据
- 使用多进程数据加载

### Q3: 模型不收敛

**解决方案**:
- 检查学习率
- 增加模型容量
- 添加正则化 (Dropout, BatchNorm)
- 检查数据质量和标签

---

## 参考资源

- **PyTorch**: https://pytorch.org/docs/stable/index.html
- **PyTorch Geometric**: https://pyg.org/
- **Scanpy**: https://scanpy.readthedocs.io/
- **单细胞最佳实践**: https://www.sc-best-practices.org/

---

*本代码指南由高级生信/AI研发工程师智能体生成*
*生成时间: {cn_time}*
"""

        return guide

    def _extract_project_name(self, thesis_proposal: str) -> str:
        """提取项目名称"""
        # 尝试从标题中提取
        lines = thesis_proposal.split('\n')
        for line in lines[:20]:  # 只检查前20行
            line = line.strip()
            if line.startswith('#') or line.startswith('##'):
                # 移除 Markdown 标题符号
                title = line.lstrip('#').strip()
                if title and len(title) < 100:
                    return title
            elif '项目名称' in line or '题目' in line:
                # 尝试提取冒号后的内容
                if ':' in line or '：' in line:
                    title = line.split(':', 1)[-1].split('：', 1)[-1].strip()
                    if title and len(title) < 100:
                        return title

        return "BioAI_Project"

    def _get_research_type_name(self, research_type: str) -> str:
        """获取研究类型中文名"""
        names = {
            'single_cell': '单细胞多组学',
            'spatial': '空间转录组学',
            'graph_ml': '图神经网络',
            'foundation_model': '大模型微调',
            'causal_inference': '因果推断',
            'genomics': '基因组学'
        }
        return names.get(research_type, '通用生物信息学')

    def _generate_requirements(self, research_type: str) -> str:
        """
        生成 requirements.txt 内容（严格版本锁定）

        重要：所有依赖包使用 == 精确版本号，确保可复现性
        """
        if research_type in BIOINFO_REQUIREMENTS:
            req_dict = BIOINFO_REQUIREMENTS[research_type]
            requirements_lines = [
                "# 生物信息学项目依赖包",
                "# 生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "# 注意：所有版本使用 == 格式，确保绝对可复现性",
                "# 如需更新版本，请手动修改并测试",
                ""
            ]
            for category, packages in req_dict.items():
                requirements_lines.append(f"# {category.replace('_', ' ').title()}")
                for pkg in packages:
                    # 验证版本格式
                    if '==' not in pkg:
                        requirements_lines.append(f"{pkg}  # 警告：未指定精确版本")
                    else:
                        requirements_lines.append(pkg)
                requirements_lines.append("")
            return '\n'.join(requirements_lines)
        return "# 未找到相关依赖配置"

    def _generate_data_loader_code(
        self,
        research_type: str,
        project_name: str,
        datasets: list
    ) -> str:
        """生成数据加载代码"""

        # 根据研究类型确定类名和数据类型
        type_config = {
            'single_cell': {
                'class_name': 'SingleCell',
                'data_type': '单细胞转录组'
            },
            'spatial': {
                'class_name': 'SpatialOmics',
                'data_type': '空间组学'
            },
            'graph_ml': {
                'class_name': 'GraphData',
                'data_type': '图结构'
            },
            'foundation_model': {
                'class_name': 'FoundationModel',
                'data_type': '预训练数据'
            },
            'causal_inference': {
                'class_name': 'CausalInference',
                'data_type': '因果推断数据'
            },
            'genomics': {
                'class_name': 'Genomics',
                'data_type': '基因组学'
            }
        }

        config = type_config.get(research_type, type_config['genomics'])

        return DATA_LOADING_TEMPLATE.format(
            project_name=project_name,
            data_type=config['data_type'],
            dataset_class=config['class_name']
        )

    def _generate_model_code(
        self,
        research_type: str,
        paradigm_framework: str,
        project_name: str
    ) -> str:
        """生成模型代码"""

        # 根据研究类型和框架确定模型配置
        if 'graph' in paradigm_framework.lower() or 'gnn' in paradigm_framework.lower():
            model_config = {
                'model_name': 'Graph Attention Network',
                'model_class': 'GATModel',
                'model_description': '基于注意力机制的图神经网络，用于处理基因共表达网络或细胞相互作用网络',
                'architecture_type': 'Graph Attention Network (GAT)',
                'gnn_layers': 'GATConv, GCNConv',
                'gnn_layer_class': 'GATConv'
            }
        elif 'transformer' in paradigm_framework.lower() or 'foundation' in paradigm_framework.lower():
            model_config = {
                'model_name': 'Transformer-based Model',
                'model_class': 'BioTransformer',
                'model_description': '基于Transformer架构的生物学序列/表达模型',
                'architecture_type': 'Transformer',
                'gnn_layers': 'TransformerEncoderLayer',
                'gnn_layer_class': 'TransformerEncoderLayer'
            }
        elif 'causal' in paradigm_framework.lower():
            model_config = {
                'model_name': 'Causal Graph Neural Network',
                'model_class': 'CausalGNN',
                'model_description': '结合因果推断的图神经网络',
                'architecture_type': 'Causal GNN',
                'gnn_layers': 'GATConv, CausalConv',
                'gnn_layer_class': 'GATConv'
            }
        else:
            model_config = {
                'model_name': 'Multi-task Neural Network',
                'model_class': 'MultiTaskModel',
                'model_description': '多任务深度学习模型',
                'architecture_type': 'Multi-layer Perceptron',
                'gnn_layers': 'Linear, Dropout',
                'gnn_layer_class': 'Linear'
            }

        return MODEL_TEMPLATE.format(
            project_name=project_name.replace(' ', '').replace('-', ''),
            **model_config
        )


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    agent = CoderAgent()

    # 测试代码生成
    result = agent.execute({
        'thesis_proposal': '''
        # 基于图神经网络的癌症预后预测模型

        ## 研究背景
        本研究旨在开发一种基于图神经网络的癌症预后预测模型...

        ## 数据集
        - TCGA-BRCA 乳腺癌数据集
        - GEO: GSEXXXXX

        ## 方法
        采用 GAT 架构构建基因共表达网络...
        ''',
        'paradigm_framework': 'Graph Attention Network',
        'datasets': [
            {'name': 'TCGA-BRCA', 'accession': 'TCGA-BRCA', 'description': '乳腺癌数据'}
        ],
        'output_dir': 'reports'
    })

    if result['success']:
        print(f"代码指南生成成功！")
        print(f"保存路径: {result['guide_path']}")
        print(f"研究类型: {result['research_type']}")
