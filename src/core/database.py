"""
数据库模型定义
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Table, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# 论文与假设的多对多关联表
paper_hypothesis_association = Table(
    'paper_hypothesis_links',
    Base.metadata,
    Column('paper_id', Integer, ForeignKey('papers.id'), primary_key=True),
    Column('hypothesis_id', Integer, ForeignKey('hypotheses.id'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Paper(Base):
    """论文表"""
    __tablename__ = 'papers'

    id = Column(Integer, primary_key=True)
    pmid = Column(String(20), unique=True, nullable=False)  # PubMed ID
    title = Column(Text)  # 允许为空
    abstract = Column(Text)
    authors = Column(Text)  # JSON格式存储作者列表
    journal = Column(String(255))
    publication_date = Column(String(50))
    doi = Column(String(100))
    keywords = Column(Text)  # JSON格式存储关键词列表

    # 搜索元数据
    search_query = Column(Text)  # 搜索关键词
    search_date = Column(DateTime, default=datetime.utcnow)

    # 状态标记
    status = Column(String(20), default='pending')  # pending, reviewed, used

    # LLM 评分字段 - 摘要精读漏斗
    llm_score = Column(Float, default=0.0)  # LLM评分 0-10
    llm_reason = Column(Text)  # LLM评分理由
    llm_innovation = Column(String(500))  # 方法论创新性评价
    llm_data_quality = Column(String(500))  # 数据质量评价
    llm_research_type = Column(String(100))  # 研究类型：原创研究/方法论文/综述/病例报告
    screening_date = Column(DateTime)  # LLM筛选日期

    # 关联
    hypotheses = relationship(
        'Hypothesis',
        secondary=paper_hypothesis_association,
        back_populates='papers'
    )

    def __repr__(self):
        return f"<Paper(pmid={self.pmid}, title={self.title[:50]}...)>"


class Hypothesis(Base):
    """研究假设表"""
    __tablename__ = 'hypotheses'

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    rationale = Column(Text)  # 假设的理论依据
    novelty = Column(Text)  # 新颖性说明
    expected_value = Column(Text)  # 预期价值

    # 生成元数据
    created_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String(50))  # 使用的模型

    # 验证结果
    validation_status = Column(String(20), default='pending')  # pending, approved, rejected, needs_revision
    feasibility_score = Column(Integer)  # 可行性评分 1-10
    novelty_score = Column(Integer)  # 新颖性评分 1-10
    technical_score = Column(Integer)  # 技术难度评分 1-10
    validation_notes = Column(Text)  # 验证笔记
    feasibility_notes = Column(Text)  # 可行性详细说明
    novelty_notes = Column(Text)  # 新颖性详细说明
    technical_notes = Column(Text)  # 技术性详细说明

    # 技术分析
    technical_analysis = Column(Text)  # JSON格式存储技术分析
    required_techniques = Column(Text)  # JSON格式存储所需技术列表
    estimated_timeline = Column(String(100))  # 预计时间线

    # 关联
    papers = relationship(
        'Paper',
        secondary=paper_hypothesis_association,
        back_populates='hypotheses'
    )

    def __repr__(self):
        return f"<Hypothesis(id={self.id}, title={self.title[:50]}...)>"


class ResearchSession(Base):
    """研究会话表 - 记录每次完整的研究流程"""
    __tablename__ = 'research_sessions'

    id = Column(Integer, primary_key=True)
    query = Column(Text, nullable=False)  # 初始搜索关键词
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(20), default='in_progress')  # in_progress, completed, cancelled

    # 结果统计
    papers_found = Column(Integer, default=0)
    hypotheses_generated = Column(Integer, default=0)
    hypotheses_validated = Column(Integer, default=0)

    def __repr__(self):
        return f"<ResearchSession(id={self.id}, query={self.query[:30]}...)>"


def init_database(db_url='sqlite:///./data/research.db'):
    """初始化数据库"""
    import os
    # 确保数据目录存在
    os.makedirs('data', exist_ok=True)

    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


if __name__ == '__main__':
    # 测试数据库初始化
    engine = init_database()
    print("数据库初始化成功！")