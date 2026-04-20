# -*- coding: utf-8 -*-
"""
科研审计与快照复刻引擎
确保系统的绝对可复现性（Absolute Reproducibility）

五大核心功能：
1. 锁死大模型随机性
2. 全链路溯源日志
3. 冻结生信代码环境
4. 时间锁与本地数据快照
5. 打包导出
"""
import os
import json
import hashlib
import zipfile
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, List
from pathlib import Path


class DeterminismLock:
    """模块1: 锁死大模型随机性"""

    # 强制使用的确定性参数
    DEFAULT_TEMPERATURE = 0.0
    DEFAULT_TOP_P = 1.0
    DEFAULT_SEED = 42  # 固定随机种子

    # 模型版本映射（确保使用具体版本）
    MODEL_VERSIONS = {
        'claude-opus-4-6': 'claude-opus-4-6',  # 已是具体版本
        'claude-sonnet-4-6': 'claude-sonnet-4-6',
        'gpt-4': 'gpt-4-0613',
        'gpt-4-turbo': 'gpt-4-0125-preview',
        'gpt-4o': 'gpt-4o-2024-05-13',
    }

    @classmethod
    def get_deterministic_params(cls, model: str) -> Dict[str, Any]:
        """获取确定性模型参数"""
        return {
            'model': cls.MODEL_VERSIONS.get(model, model),
            'temperature': cls.DEFAULT_TEMPERATURE,
            'top_p': cls.DEFAULT_TOP_P,
            'seed': cls.DEFAULT_SEED,
        }

    @classmethod
    def enforce_determinism(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """强制执行确定性参数"""
        if 'temperature' not in params or params['temperature'] > 0.1:
            params['temperature'] = cls.DEFAULT_TEMPERATURE
        if 'model' in params:
            params['model'] = cls.MODEL_VERSIONS.get(params['model'], params['model'])
        return params


class AuditTrailLogger:
    """模块2: 全链路溯源日志"""

    def __init__(self, experiment_id: str = None, output_dir: str = 'logs/audit'):
        self.experiment_id = experiment_id or self._generate_experiment_id()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.output_dir / f'experiment_provenance_log_{self.experiment_id}.json'
        self.data = {
            'experiment_id': self.experiment_id,
            'start_time': datetime.now().isoformat(),
            'system_info': self._get_system_info(),
            'stages': []
        }

    @staticmethod
    def _generate_experiment_id() -> str:
        """生成唯一实验ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        hash_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f'exp_{timestamp}_{hash_part}'

    @staticmethod
    def _get_system_info() -> Dict:
        """获取系统信息"""
        import platform
        import sys

        return {
            'platform': platform.platform(),
            'python_version': sys.version,
            'working_directory': os.getcwd(),
        }

    def log_stage(self, stage_name: str, stage_data: Dict) -> None:
        """记录一个阶段"""
        stage_record = {
            'stage': stage_name,
            'timestamp': datetime.now().isoformat(),
            'data': stage_data
        }
        self.data['stages'].append(stage_record)
        self._save()

    def log_input(self, user_input: str, search_params: Dict) -> None:
        """记录用户输入"""
        self.data['user_input'] = user_input
        self.data['search_params'] = search_params
        self._save()

    def log_model_call(self, model: str, prompt_length: int, response_length: int) -> None:
        """记录模型调用"""
        if 'model_calls' not in self.data:
            self.data['model_calls'] = []

        self.data['model_calls'].append({
            'timestamp': datetime.now().isoformat(),
            'model': model,
            'prompt_length': prompt_length,
            'response_length': response_length
        })
        self._save()

    def log_snapshot(self, snapshot_path: str, record_count: int) -> None:
        """记录数据快照"""
        if 'snapshots' not in self.data:
            self.data['snapshots'] = []

        self.data['snapshots'].append({
            'timestamp': datetime.now().isoformat(),
            'path': snapshot_path,
            'record_count': record_count
        })
        self._save()

    def finalize(self, final_output: Dict = None) -> str:
        """完成日志记录"""
        self.data['end_time'] = datetime.now().isoformat()
        self.data['duration_seconds'] = (
            datetime.fromisoformat(self.data['end_time']) -
            datetime.fromisoformat(self.data['start_time'])
        ).total_seconds()

        if final_output:
            self.data['final_output_summary'] = {
                'hypotheses_count': len(final_output.get('hypotheses', [])),
                'papers_count': len(final_output.get('papers', [])),
            }

        self._save()
        return str(self.log_file)

    def _save(self) -> None:
        """保存日志到文件"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_log(cls, log_path: str) -> Dict:
        """加载现有日志"""
        with open(log_path, 'r', encoding='utf-8') as f:
            return json.load(f)


class DataSnapshotManager:
    """模块4: 时间锁与本地数据快照"""

    SNAPSHOT_DIR = Path('data/snapshots')
    SNAPSHOT_VERSION = '1.0'

    def __init__(self):
        self.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_cutoff_date() -> date:
        """获取当前日期作为截止日期（时间锁）"""
        return date.today()

    @staticmethod
    def format_cutoff_date_for_pubmed(cutoff_date: date) -> str:
        """格式化日期为 PubMed 查询格式"""
        return cutoff_date.strftime('%Y/%m/%d')

    def _serialize_paper(self, paper: Dict) -> Dict:
        """将论文数据序列化为JSON可序列化的格式"""
        serialized = {}
        for key, value in paper.items():
            if isinstance(value, datetime):
                serialized[key] = value.isoformat()
            elif isinstance(value, date):
                serialized[key] = value.isoformat()
            elif isinstance(value, dict):
                serialized[key] = self._serialize_paper(value)
            elif isinstance(value, list):
                serialized[key] = [
                    self._serialize_paper(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                serialized[key] = value
        return serialized

    def create_snapshot(self, papers: List[Dict], metadata: Dict = None) -> str:
        """创建数据快照"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        snapshot_file = self.SNAPSHOT_DIR / f'data_snapshot_{timestamp}.json'

        # 序列化论文数据（处理datetime等不可序列化的对象）
        serialized_papers = [self._serialize_paper(paper) for paper in papers]

        snapshot_data = {
            'version': self.SNAPSHOT_VERSION,
            'timestamp': datetime.now().isoformat(),
            'cutoff_date': self.get_cutoff_date().isoformat(),
            'metadata': metadata or {},
            'record_count': len(papers),
            'papers': serialized_papers
        }

        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot_data, f, ensure_ascii=False, indent=2)

        return str(snapshot_file)

    def load_snapshot(self, snapshot_path: str) -> Dict:
        """加载现有快照"""
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_snapshots(self) -> List[Dict]:
        """列出所有可用快照"""
        snapshots = []
        for file in self.SNAPSHOT_DIR.glob('data_snapshot_*.json'):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    snapshots.append({
                        'path': str(file),
                        'timestamp': data.get('timestamp'),
                        'record_count': data.get('record_count', 0),
                        'cutoff_date': data.get('cutoff_date')
                    })
            except:
                continue
        return sorted(snapshots, key=lambda x: x['timestamp'], reverse=True)

    def verify_snapshot_integrity(self, snapshot_path: str) -> bool:
        """验证快照完整性"""
        try:
            data = self.load_snapshot(snapshot_path)
            required_keys = ['version', 'timestamp', 'papers']
            return all(key in data for key in required_keys)
        except:
            return False


class EnvironmentFreezer:
    """模块3: 冻结生信代码环境"""

    # 常见生信包的推荐版本（2024年稳定版）
    RECOMMENDED_VERSIONS = {
        'numpy': '1.24.3',
        'pandas': '2.0.3',
        'scanpy': '1.9.3',
        'anndata': '0.8.0',
        'scikit-learn': '1.3.0',
        'scipy': '1.11.1',
        'matplotlib': '3.7.2',
        'seaborn': '0.12.2',
        'plotly': '5.15.0',
        'torch': '2.0.1',
        'tensorflow': '2.13.0',
        'xgboost': '1.7.6',
        'lightgbm': '4.1.0',
        'lifelines': '0.27.8',
        'statsmodels': '0.14.0',
        'biopython': '1.81',
        'pysam': '0.22.0',
        'pysam': '0.22.0',
        'cell2location': '0.1',
        'scvi-tools': '0.21.0',
    }

    @classmethod
    def freeze_requirements(cls, requirements: List[str]) -> List[str]:
        """将包名转换为带版本号的格式"""
        frozen = []
        for req in requirements:
            # 提取包名（去除版本说明符和空格）
            package_name = req.lower()
            for sep in ['>=', '<=', '==', '~=', '>', '<', ' ', '[', ';']:
                package_name = package_name.split(sep)[0].strip()

            # 查找推荐版本
            if package_name in cls.RECOMMENDED_VERSIONS:
                version = cls.RECOMMENDED_VERSIONS[package_name]
                frozen.append(f'{package_name}=={version}')
            else:
                # 如果没有推荐版本，添加警告注释
                if req.strip() and not req.strip().startswith('#'):
                    frozen.append(f'{req}  # TODO: 请指定具体版本号')

        return frozen

    @classmethod
    def get_frozen_prompt_addendum(cls) -> str:
        """获取用于 Prompt 的补充说明"""
        return """

【重要】依赖包版本锁定要求：
生成的 requirements.txt 必须为每个包指定精确版本号，格式：package_name==x.y.z
例如：
- scanpy==1.9.3（正确）
- scanpy>=1.9（错误）
- scanpy（错误）

请使用以下已知稳定版本（2024年）：
- numpy==1.24.3
- pandas==2.0.3
- scanpy==1.9.3
- scikit-learn==1.3.0
- torch==2.0.1
- tensorflow==2.13.0
- xgboost==1.7.6
- lifelines==0.27.8
"""


class ReproducibilityPackager:
    """模块5: 打包导出"""

    def __init__(self, audit_log: AuditTrailLogger, output_dir: str = 'exports'):
        self.audit_log = audit_log
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_package(self, components: Dict[str, Any]) -> str:
        """
        创建可复刻数据包

        Args:
            components: 包含以下键的字典
                - report_path: 开题报告路径
                - code_path: 核心代码路径
                - requirements_path: requirements.txt 路径
                - snapshot_path: 数据快照路径
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        package_name = f'reproducible_package_{timestamp}'
        zip_path = self.output_dir / f'{package_name}.zip'

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加溯源日志
            zipf.write(self.audit_log.log_file, 'audit_log.json')

            # 添加各个组件
            for component_name, component_path in components.items():
                if component_path and Path(component_path).exists():
                    zipf.write(component_path, f'{component_name}_{Path(component_path).name}')

            # 添加元数据
            metadata = {
                'package_version': '1.0',
                'created_at': datetime.now().isoformat(),
                'experiment_id': self.audit_log.experiment_id,
                'components': {k: str(v) for k, v in components.items()}
            }
            metadata_path = self.output_dir / 'temp_metadata.json'
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            zipf.write(metadata_path, 'metadata.json')
            metadata_path.unlink()

        return str(zip_path)


# 全局单例实例
_audit_logger: Optional[AuditTrailLogger] = None
_snapshot_manager: Optional[DataSnapshotManager] = None


def get_audit_logger() -> AuditTrailLogger:
    """获取全局审计日志器"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditTrailLogger()
    return _audit_logger


def get_snapshot_manager() -> DataSnapshotManager:
    """获取全局快照管理器"""
    global _snapshot_manager
    if _snapshot_manager is None:
        _snapshot_manager = DataSnapshotManager()
    return _snapshot_manager


def reset_audit_logger(experiment_id: str = None) -> AuditTrailLogger:
    """重置审计日志器（开始新实验时调用）"""
    global _audit_logger
    _audit_logger = AuditTrailLogger(experiment_id)
    return _audit_logger
