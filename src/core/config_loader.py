"""
配置加载器
从config.yaml读取系统配置，让配置文件真正生效
"""
import yaml
import os
from typing import Dict, Any


class ConfigLoader:
    """配置加载器（单例模式）"""

    _instance = None
    _config = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_path=None):
        """加载配置文件"""
        if self._config is None:
            # 默认配置路径
            if config_path is None:
                # 获取项目根目录
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                config_path = os.path.join(project_root, 'config.yaml')

            # 加载配置
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f)
            else:
                # 使用默认配置
                self._config = self._default_config()

    def _default_config(self) -> Dict:
        """默认配置（V3.4 支持异构模型）"""
        return {
            'system': {
                'name': 'Research Hypothesis Generator',
                'version': '3.4.0'
            },
            'agents': {
                'paper_search': {
                    'model': os.getenv('PAPER_SEARCH_MODEL', os.getenv('CLAUDE_MODEL', 'claude-opus-4-6')),
                    'screening_model': os.getenv('PAPER_SCREENING_MODEL', 'claude-sonnet-4-6'),
                    'max_results': 50
                },
                'hypothesis': {
                    # 首席科学家 PI 使用 Model A
                    'model': os.getenv('PI_MODEL', os.getenv('CLAUDE_MODEL', 'claude-opus-4-6'))
                },
                'red_team': {
                    # 红方审计员强制使用 Model B（与 PI 不同，防止认知塌缩）
                    'model': os.getenv('RED_TEAM_MODEL', os.getenv('CLAUDE_MODEL_ALT', 'claude-haiku-4-5-20251001'))
                },
                'validation': {
                    'model': os.getenv('VALIDATION_MODEL', os.getenv('CLAUDE_MODEL', 'claude-opus-4-6'))
                },
                'tech_analysis': {
                    'model': os.getenv('TECH_ANALYSIS_MODEL', os.getenv('CLAUDE_MODEL', 'claude-opus-4-6'))
                }
            },
            'pubmed': {
                'retmax': 50,
                'retmode': 'json'
            },
            'database': {
                'type': 'sqlite',
                'path': './data/research.db'
            },
            'cli': {
                'page_size': 10,
                'hypothesis_display_limit': 5
            }
        }

    def get(self, key: str, default=None) -> Any:
        """
        获取配置值（支持点号分隔的路径）

        Args:
            key: 配置键（例如 'agents.hypothesis.model'）
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_agent_config(self, agent_name: str) -> Dict:
        """
        获取智能体配置

        Args:
            agent_name: 智能体名称（例如 'hypothesis'）

        Returns:
            智能体配置字典
        """
        return self._config.get('agents', {}).get(agent_name, {})

    def get_agent_model(self, agent_name: str) -> str:
        """
        获取智能体使用的模型

        Args:
            agent_name: 智能体名称

        Returns:
            模型名称
        """
        agent_config = self.get_agent_config(agent_name)
        return agent_config.get('model', os.getenv('CLAUDE_MODEL', 'claude-opus-4-6'))

    def get_pubmed_config(self) -> Dict:
        """获取PubMed配置"""
        return self._config.get('pubmed', {})

    def get_cli_config(self) -> Dict:
        """获取CLI配置"""
        return self._config.get('cli', {})

    def get_all(self) -> Dict:
        """获取完整配置"""
        return self._config


# 全局配置实例
config_loader = ConfigLoader()


def get_config():
    """获取全局配置实例"""
    return config_loader


if __name__ == '__main__':
    # 测试
    config = get_config()

    print("系统配置:")
    print(f"  名称: {config.get('system.name')}")
    print(f"  版本: {config.get('system.version')}")

    print("\n智能体配置:")
    print(f"  论文搜索模型: {config.get_agent_model('paper_search')}")
    print(f"  假设生成模型: {config.get_agent_model('hypothesis')}")

    print("\nPubMed配置:")
    pubmed_config = config.get_pubmed_config()
    print(f"  最大返回数: {pubmed_config.get('retmax')}")

    print("\n配置加载测试完成")