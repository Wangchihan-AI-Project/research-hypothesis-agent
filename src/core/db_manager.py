"""
数据库连接池管理器
统一管理所有智能体的数据库连接，避免资源浪费
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from contextlib import contextmanager
import os


class DatabaseManager:
    """数据库连接池管理器（单例模式）"""

    _instance = None
    _engine = None
    _session_factory = None

    def __new__(cls):
        """单例模式：确保只有一个实例"""
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, db_url=None):
        """初始化数据库连接池"""
        if self._engine is None:
            # 默认数据库路径
            if db_url is None:
                db_url = os.getenv('DATABASE_URL', 'sqlite:///./data/research.db')

            # 确保数据目录存在
            db_path = db_url.replace('sqlite:///', '')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

            # 创建引擎（使用连接池）
            self._engine = create_engine(
                db_url,
                echo=False,
                pool_size=5,  # 连接池大小
                max_overflow=10,  # 最大溢出连接数
                pool_pre_ping=True,  # 自动检测连接是否有效
                pool_recycle=3600  # 1小时回收连接
            )

            # 创建会话工厂（线程安全）
            self._session_factory = scoped_session(
                sessionmaker(bind=self._engine)
            )

            # 初始化数据库表
            from .database import Base
            Base.metadata.create_all(self._engine)

    @contextmanager
    def get_session(self):
        """
        获取数据库会话（上下文管理器）

        用法：
            with db_manager.get_session() as session:
                papers = session.query(Paper).all()

        Returns:
            数据库会话
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_engine(self):
        """获取数据库引擎"""
        return self._engine

    def close_all(self):
        """关闭所有连接"""
        if self._session_factory:
            self._session_factory.remove()
        if self._engine:
            self._engine.dispose()


# 全局数据库管理器实例
db_manager = DatabaseManager()


def get_db_manager():
    """获取全局数据库管理器"""
    return db_manager


if __name__ == '__main__':
    # 测试
    from dotenv import load_dotenv
    load_dotenv()

    db = get_db_manager()

    # 测试获取会话
    with db.get_session() as session:
        print("数据库连接成功！")

    print("数据库管理器测试完成")