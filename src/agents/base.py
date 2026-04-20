"""
智能体基础类
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import os
import sys
from dotenv import load_dotenv, dotenv_values

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.db_manager import get_db_manager
from src.core.config_loader import get_config

# 加载环境变量（使用更可靠的方式）
def _load_env():
    """加载环境变量"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    env_path = os.path.join(project_root, '.env')

    # 先尝试 load_dotenv
    loaded = load_dotenv(env_path, encoding='utf-8', override=True)

    # 检查关键变量是否加载成功
    if not os.getenv('ANTHROPIC_API_KEY'):
        # 使用 dotenv_values 作为备用方案
        try:
            config = dotenv_values(env_path)
            os.environ.update(config)
        except:
            pass

_load_env()


class BaseAgent(ABC):
    """智能体基类"""

    def __init__(self, name: str, agent_type: str = None):
        """
        初始化智能体

        Args:
            name: 智能体名称
            agent_type: 智能体类型（用于从配置读取模型）
        """
        self.name = name
        # 从配置读取模型
        self.config = get_config()
        if agent_type:
            self.model = self.config.get_agent_model(agent_type)
        else:
            self.model = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")

        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("未找到ANTHROPIC_API_KEY环境变量，请检查.env文件")

        # 使用统一的数据库管理器
        self.db_manager = get_db_manager()

    @abstractmethod
    def execute(self, input_data: Any) -> Dict:
        """
        执行智能体任务（抽象方法，子类必须实现）

        Args:
            input_data: 输入数据

        Returns:
            执行结果
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}(name={self.name}, model={self.model})>"


if __name__ == '__main__':
    print("智能体基础模块加载成功")