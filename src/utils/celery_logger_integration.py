# -*- coding: utf-8 -*-
"""
V7.1 Celery Task 日志集成示例

展示如何在 Celery 异步任务中使用集中式日志系统：
1. Task ID 自动注入
2. Agent 名称标记
3. 深水区异常堆栈捕获
4. 业务审计日志分离
"""

# ==================== 方式一：上下文管理器注入（推荐） ====================

from celery import Task
from src.utils.logger import (
    get_central_logger,
    TaskLogContext,
    log_exceptions,
    AUDIT_LEVEL
)


class LoggedTask(Task):
    """
    V7.1 增强版 Celery Task 基类

    自动注入 Task ID 和 Agent 名称到所有日志
    """

    def __call__(self, *args, **kwargs):
        """任务执行入口"""
        logger = get_central_logger()

        # 获取 Task ID
        task_id = self.request.id if hasattr(self, 'request') else 'unknown'
        agent_name = self.name.split('.')[-1] if self.name else 'CeleryWorker'

        # 进入 Task 日志上下文
        with TaskLogContext(task_id=str(task_id), agent_name=agent_name):
            logger.info(f"[Celery] 任务开始执行: {self.name}")

            try:
                result = super().__call__(*args, **kwargs)
                logger.info(f"[Celery] 任务成功完成: {self.name}")
                return result

            except SoftTimeLimitExceeded:
                logger.warning(f"[Celery] 任务软超时: {self.name}")
                raise

            except TimeLimitExceeded:
                logger.critical(f"[Celery] 任务硬超时: {self.name}")
                raise

            except Exception as e:
                # 自动捕获异常堆栈和关键变量
                logger.exception(
                    f"[Celery] 任务执行异常: {self.name}",
                    extra_vars={
                        'task_args': str(args)[:200],
                        'task_kwargs': str(kwargs)[:200],
                        'exception_type': type(e).__name__
                    }
                )
                raise


# ==================== 方式二：装饰器注入（灵活控制） ====================

def celery_task_with_logging(agent_name: str = None):
    """
    Celery Task 日志装饰器

    用于需要精细控制日志上下文的任务

    Args:
        agent_name: Agent 名称（可选，默认使用函数名）

    Usage:
        @celery_task_with_logging(agent_name='RAGRouter')
        def fetch_pubmed_task(query: str):
            # ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_central_logger()

            # 从 Celery request 获取 Task ID（如果有）
            try:
                from celery import current_task
                task_id = current_task.request.id if current_task else 'standalone'
            except:
                task_id = 'standalone'

            agent = agent_name or func.__name__

            with TaskLogContext(task_id=str(task_id), agent_name=agent):
                logger.debug(f"[{agent}] 任务参数: args={args[:2]}, kwargs={kwargs}")

                try:
                    result = func(*args, **kwargs)
                    logger.info(f"[{agent}] 任务完成")
                    return result

                except Exception as e:
                    logger.exception(
                        f"[{agent}] 执行异常",
                        extra_vars={'args': str(args)[:100], 'kwargs': str(kwargs)[:100]}
                    )
                    raise

        return wrapper
    return decorator


# ==================== 方式三：深水区异常捕获（关键代码段） ====================

class RAGRouterTaskExample:
    """
    RAG Router 任务示例 - 展示深水区异常捕获
    """

    @log_exceptions(agent_name='RAGRouter', capture_vars=True)
    def fetch_from_pubmed(self, query: str, timeout: int = 15) -> dict:
        """
        PubMed 检索 - 深水区代码

        使用 @log_exceptions 装饰器自动捕获异常堆栈和关键变量
        """
        logger = get_central_logger()

        logger.debug(f"[RAGRouter] PubMed API 调用: query={query}")

        # 模拟网络请求（深水区）
        import requests
        response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={'term': query, 'retmax': 50},
            timeout=timeout
        )

        if response.status_code != 200:
            # 这里抛出的异常会被装饰器自动捕获
            raise ValueError(f"PubMed API 返回错误: {response.status_code}")

        return {'papers': response.json()}


class HybridFitnessTaskExample:
    """
    混合打分器任务示例 - 展示复杂变量捕获
    """

    def calculate_fitness_score(self, hypothesis: dict) -> float:
        """
        计算假设的适应性评分 - 深水区计算逻辑
        """
        logger = get_central_logger()

        try:
            # 提取评分维度
            feasibility = hypothesis.get('feasibility_score', 0)
            novelty = hypothesis.get('novelty_score', 0)
            technical = hypothesis.get('technical_score', 0)

            # 混合计算（可能出错）
            weights = hypothesis.get('weights', {'feasibility': 0.4, 'novelty': 0.3, 'technical': 0.3})

            score = (
                feasibility * weights['feasibility'] +
                novelty * weights['novelty'] +
                technical * weights['technical']
            )

            logger.info(f"[HybridFitness] 计算完成: score={score:.2f}")
            return score

        except Exception as e:
            # 深水区异常：捕获完整堆栈和导致报错的原始变量值
            logger.exception(
                "[HybridFitness] 混合打分计算失败",
                extra_vars={
                    'hypothesis_id': hypothesis.get('id'),
                    'feasibility': feasibility,
                    'novelty': novelty,
                    'technical': technical,
                    'weights': weights,
                    'hypothesis_keys': list(hypothesis.keys())
                }
            )
            raise


class PhysicalValidatorTaskExample:
    """
    物理验证器任务示例 - 展示业务审计日志
    """

    def validate_hypothesis(self, hypothesis: dict, threshold: float = 5.0) -> dict:
        """
        假设物理验证 - 展示 AUDIT 级别用于业务驳回记录
        """
        logger = get_central_logger()

        # 计算评分
        score = hypothesis.get('physical_score', 0)

        # 判断是否达标
        if score < threshold:
            # AUDIT 级别：业务驳回记录（科研人员查阅）
            logger.audit(
                f"[驳回] 假设 #{hypothesis.get('id')} 物理验证不达标\n"
                f"  评分: {score}/10 (阈值: {threshold}/10)\n"
                f"  原因: {hypothesis.get('rejection_reason', '评分不足')}\n"
                f"  建议: {hypothesis.get('suggestion', '需要更强的实验支撑')}"
            )

            return {
                'valid': False,
                'score': score,
                'threshold': threshold,
                'reason': 'physical_validation_failed'
            }

        # 通过验证
        logger.info(f"[通过] 假设 #{hypothesis.get('id')} 物理验证达标: score={score}/10")

        return {
            'valid': True,
            'score': score,
            'threshold': threshold
        }


# ==================== 完整 Celery Task 示例 ====================

def example_celery_task_integration():
    """
    完整 Celery Task 集成示例

    展示如何在真实 Celery 任务中使用日志系统
    """
    from celery import Celery

    # 获取 Celery App（从项目配置）
    from src.core.celery_tasks import get_celery_app
    app = get_celery_app()

    logger = get_central_logger()

    # ==================== 定义任务 ====================

    @app.task(base=LoggedTask, bind=True)
    def research_pipeline_task(self, query: str, config: dict):
        """
        研究管线任务 - 使用 LoggedTask 基类自动注入日志上下文

        LoggedTask 会自动：
        1. 在所有日志中注入 [TaskID: xxx]
        2. 在所有日志中注入 [Agent: research_pipeline_task]
        3. 捕获任务执行异常的完整堆栈
        """
        # Task ID 和 Agent 已自动注入，直接使用 logger
        logger.info(f"[Pipeline] 开始处理查询: {query}")

        # Step 1: RAG 检索（深水区）
        rag_router = RAGRouterTaskExample()

        @log_exceptions(agent_name='RAGRouter', capture_vars=True)
        def fetch_papers(query: str):
            return rag_router.fetch_from_pubmed(query, timeout=config.get('timeout', 15))

        papers = fetch_papers(query)
        logger.info(f"[Pipeline] 检索完成: 找到 {len(papers.get('papers', []))} 篇论文")

        # Step 2: 假设生成
        hypotheses = generate_hypotheses(papers)
        logger.audit(f"[Audit] 生成假设: {len(hypotheses)} 个")

        # Step 3: 物理验证（业务审计）
        validator = PhysicalValidatorTaskExample()
        valid_hypotheses = []

        for hyp in hypotheses:
            result = validator.validate_hypothesis(hyp, threshold=5.0)
            if result['valid']:
                valid_hypotheses.append(hyp)

        # AUDIT 级别记录验证结果
        logger.audit(
            f"[Audit] 验证结果:\n"
            f"  输入假设: {len(hypotheses)} 个\n"
            f"  通过验证: {len(valid_hypotheses)} 个\n"
            f"  驳回率: {(len(hypotheses) - len(valid_hypotheses)) / len(hypotheses) * 100:.1f}%"
        )

        return {
            'query': query,
            'papers_count': len(papers.get('papers', [])),
            'hypotheses_count': len(hypotheses),
            'valid_count': len(valid_hypotheses),
            'valid_hypotheses': valid_hypotheses
        }

    @app.task(base=LoggedTask, bind=True)
    def hypothesis_scoring_task(self, hypothesis_id: str, papers: list):
        """
        假设打分任务 - 展示深水区计算异常捕获
        """
        logger.info(f"[Scoring] 开始打分: hypothesis_id={hypothesis_id}")

        scorer = HybridFitnessTaskExample()

        hypothesis = {'id': hypothesis_id, 'papers': papers}

        # 获取各维度评分
        try:
            feasibility = calculate_feasibility(papers)
            novelty = calculate_novelty(papers)
            technical = calculate_technical(papers)

            hypothesis.update({
                'feasibility_score': feasibility,
                'novelty_score': novelty,
                'technical_score': technical,
                'weights': {'feasibility': 0.4, 'novelty': 0.3, 'technical': 0.3}
            })

            score = scorer.calculate_fitness_score(hypothesis)

            logger.info(f"[Scoring] 打分完成: {hypothesis_id} -> {score:.2f}")

            return {'hypothesis_id': hypothesis_id, 'score': score}

        except Exception as e:
            # 深水区异常：完整堆栈 + 关键变量
            logger.exception(
                f"[Scoring] 打分计算异常",
                extra_vars={
                    'hypothesis_id': hypothesis_id,
                    'papers_count': len(papers),
                    'feasibility': feasibility if 'feasibility' in dir() else 'N/A',
                    'novelty': novelty if 'novelty' in dir() else 'N/A',
                    'technical': technical if 'technical' in dir() else 'N/A',
                    'papers_sample': papers[:3] if papers else []
                }
            )
            raise


# ==================== 日志检索示例 ====================

def search_logs_by_task_id(task_id: str):
    """
    按 Task ID 检索日志（排查静默崩溃）

    使用 grep 命令搜索：
    grep -E "\[TaskID: {task_id}\]" logs/system_v7.log

    返回该任务在执行期间的所有日志记录
    """
    import subprocess

    log_file = "logs/system_v7.log"

    # 使用 grep 搜索 Task ID
    result = subprocess.run(
        ['grep', '-E', f'\[TaskID: {task_id}\]', log_file],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"=== Task {task_id} 的日志记录 ===")
        print(result.stdout)
    else:
        print(f"未找到 Task {task_id} 的日志记录")


def search_error_logs(hours: int = 24):
    """
    搜索最近 N 小时的错误日志（研发排查）

    查看 logs/error_v7.log 获取所有 ERROR 级别日志
    """
    log_file = "logs/error_v7.log"

    print(f"=== 最近 {hours} 小时的错误日志 ===")

    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            # 简单的时间过滤（根据实际需要调整）
            print(line)


def search_audit_logs(hours: int = 24):
    """
    搜索最近 N 小时的审计日志（科研人员查阅）

    查看 logs/audit_v7.log 获取所有业务驳回记录
    """
    log_file = "logs/audit_v7.log"

    print(f"=== 最近 {hours} 小时的业务驳回记录 ===")

    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            print(line)


# ==================== 测试入口 ====================

if __name__ == '__main__':
    print("=== V7.1 Celery Task 日志集成测试 ===\n")

    logger = get_central_logger()

    # 测试 LoggedTask 模拟
    print("--- 测试 LoggedTask 基类 ---")
    with TaskLogContext(task_id='task_test_001', agent_name='LoggedTaskExample'):
        logger.info("[测试] LoggedTask 自动注入 Task ID")

    # 测试深水区异常捕获
    print("\n--- 测试深水区异常捕获 ---")
    scorer = HybridFitnessTaskExample()

    with TaskLogContext(task_id='task_error_001', agent_name='HybridFitness'):
        try:
            # 模拟错误数据
            bad_hypothesis = {
                'id': 'hyp_001',
                'feasibility_score': 8,
                'novelty_score': 'invalid',  # 类型错误
                'technical_score': 7,
                'weights': {'feasibility': 0.4, 'novelty': 0.3, 'technical': 0.3}
            }
            scorer.calculate_fitness_score(bad_hypothesis)
        except:
            pass

    # 测试业务审计日志
    print("\n--- 测试 AUDIT 级别 ---")
    validator = PhysicalValidatorTaskExample()

    with TaskLogContext(task_id='task_audit_001', agent_name='PhysicalValidator'):
        result = validator.validate_hypothesis(
            {'id': 'hyp_002', 'physical_score': 3, 'rejection_reason': '实验设计不完整'},
            threshold=5.0
        )

    print("\n=== 测试完成 ===")
    print("请检查日志文件:\n"
          "  - logs/system_v7.log (所有日志)\n"
          "  - logs/audit_v7.log (业务驳回)\n"
          "  - logs/error_v7.log (系统异常)")