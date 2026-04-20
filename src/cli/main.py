"""
命令行交互界面（Human-in-the-Loop 版本）
实现人在回路的研究假设生成流程
"""
import sys
import os
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import Orchestrator
from core.database import Hypothesis
from core.config_loader import get_config
from core.program_config import get_program_config, reload_program_config
from utils.report_export import ReportExporter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
import questionary
from questionary import Style
import json

# 自定义样式
custom_style = Style([
    ('qmark', 'fg:cyan bold'),
    ('question', 'fg:white bold'),
    ('answer', 'fg:green bold'),
    ('pointer', 'fg:cyan bold'),
    ('highlighted', 'fg:cyan bold'),
    ('selected', 'fg:green'),
    ('separator', 'fg:cyan'),
    ('instruction', 'fg:white'),
    ('text', 'fg:white'),
])


class ResearchCLI:
    """研究假设生成CLI - Human-in-the-Loop 版本"""

    def __init__(self):
        """初始化CLI"""
        self.console = Console()
        self.orchestrator = Orchestrator()
        self.config = get_config()
        self.exporter = ReportExporter()
        self.current_papers = []
        self.selected_papers = []
        self.generated_hypotheses = []
        self.hypothesis_ids = []
        self.proposal_path = None

    def run(self):
        """运行CLI主循环"""
        self.console.print(Panel.fit(
            "[bold cyan]生物医学计算与统计自动化科研引擎[/bold cyan]\n"
            "[bold yellow]Human-in-the-Loop 模式[/bold yellow]\n"
            "[green]四大核心领域：Biomedical Informatics | Computational Biology | Health Data Science | Biostatistics[/green]\n"
            "[dim]专注于PubMed文献的计算/统计Gap挖掘与方法论创新[/dim]\n"
            f"[dim]版本: {self.config.get('system.version')}[/dim]",
            border_style="cyan"
        ))

        while True:
            # 主菜单
            action = questionary.select(
                "请选择操作：",
                choices=[
                    "开始新的研究流程",
                    "🤖 自主循环模式 (Auto-Iterate)",
                    "查看/修改研究策略 (program.md)",
                    "查看历史会话",
                    "查看已保存的假设",
                    "导出研究报告",
                    "退出系统"
                ],
                style=custom_style
            ).ask()

            if action == "开始新的研究流程":
                self.run_workflow_hitl()
            elif action == "🤖 自主循环模式 (Auto-Iterate)":
                self.run_autonomous_mode()
            elif action == "查看/修改研究策略 (program.md)":
                self.view_program_config()
            elif action == "查看历史会话":
                self.view_sessions()
            elif action == "查看已保存的假设":
                self.view_saved_hypotheses()
            elif action == "导出研究报告":
                self.export_report()
            elif action == "退出系统":
                self.console.print("[green]感谢使用！再见[/green]")
                break

    def run_workflow_hitl(self):
        """
        运行 Human-in-the-Loop 工作流程

        流程：
        1. 询问研究方向
        2. 文献侦察员搜索论文
        3. 首席科学家生成假设
        4. 暂停，显示假设，让用户选择
        5. 选中的假设发送给审稿人验证
        6. 输出评审报告
        """
        session_id = None

        try:
            # ============ 步骤 1: 询问研究方向 ============
            self.console.print("\n[bold cyan]========== 步骤 1: 确定研究方向 ==========[/bold cyan]\n")

            query = questionary.text(
                "请输入您的研究方向或关键词：\n"
                "[dim]例如：单细胞图神经网络, 机器学习基因组学, EHR败血症预测[/dim]",
                style=custom_style
            ).ask()

            if not query:
                self.console.print("[red]研究方向不能为空[/red]")
                return

            # 开始会话
            with self.console.status("[bold cyan]启动研究会话...[/bold cyan]"):
                session_result = self.orchestrator.start_session(query)

            if not session_result['success']:
                self.console.print(f"[red]启动会话失败: {session_result.get('error')}[/red]")
                return

            session_id = session_result['session_id']
            self.console.print(f"[green]会话已启动（ID: {session_id}）[/green]")

            # ============ 步骤 2: 文献侦察员工作 ============
            self.console.print("\n[bold cyan]========== 步骤 2: 文献侦察员搜索论文 ==========[/bold cyan]\n")

            max_results_input = questionary.text(
                f"最大搜索论文数量（默认20，建议10-30）：",
                default="20",
                style=custom_style
            ).ask()

            max_results = int(max_results_input) if max_results_input.isdigit() else 20

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("文献侦察员正在搜索 PubMed...", total=None)
                search_result = self.orchestrator.search_papers(
                    query,
                    max_results,
                    enable_filter=False,
                    fetch_full_text=True,
                    max_full_text=5
                )
                progress.remove_task(task)

            if not search_result['success']:
                self.console.print(f"[red]搜索失败: {search_result.get('error')}[/red]")
                return

            self.current_papers = search_result['papers']
            self.selected_papers = self.current_papers

            # 显示搜索结果摘要
            full_text_stats = search_result.get('full_text_stats', {})
            self.console.print(f"\n[green]文献侦察员找到了 {len(self.current_papers)} 篇相关文献[/green]")
            if full_text_stats:
                self.console.print(
                    f"  [dim]全文获取: PDF {full_text_stats.get('pdf', 0)} 篇, "
                    f"摘要 {full_text_stats.get('abstract', 0)} 篇[/dim]"
                )

            # 简要显示论文标题
            if self.current_papers:
                self.console.print("\n[cyan]论文列表（前5篇）：[/cyan]")
                for i, paper in enumerate(self.current_papers[:5], 1):
                    title = paper.get('title', 'N/A')
                    if len(title) > 60:
                        title = title[:60] + "..."
                    self.console.print(f"  {i}. {title}")

            # ============ 步骤 3: 首席科学家生成假设 ============
            self.console.print("\n[bold cyan]========== 步骤 3: 首席科学家生成假设 ==========[/bold cyan]\n")

            research_topic = questionary.text(
                "请确认研究主题（用于生成假设）：",
                default=query,
                style=custom_style
            ).ask()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("首席科学家正在深度分析文献并生成 Nature 级别假设...", total=None)

                hyp_result = self.orchestrator.hypothesis_agent.execute({
                    'literature_report': f"搜索关键词: {query}\n找到 {len(self.selected_papers)} 篇相关文献",
                    'papers': self.selected_papers,
                    'research_topic': research_topic,
                    'output_dir': 'reports'
                })

                progress.remove_task(task)

            if not hyp_result['success']:
                self.console.print(f"[red]假设生成失败: {hyp_result.get('error')}[/red]")
                return

            self.generated_hypotheses = hyp_result['hypotheses']
            self.hypothesis_ids = hyp_result.get('hypothesis_ids', [])
            self.proposal_path = hyp_result.get('proposal_path')

            self.console.print(f"\n[green]首席科学家生成了 {len(self.generated_hypotheses)} 个假设[/green]")
            if self.proposal_path:
                self.console.print(f"[dim]提案文档: {self.proposal_path}[/dim]")

            # ============ 步骤 4: Human-in-the-Loop 选择 ============
            self.console.print("\n[bold yellow]========== Human-in-the-Loop: 假设审核 ==========[/bold yellow]\n")

            # 循环让用户选择，直到选择一个假设或退出
            while True:
                # 显示假设摘要
                self._display_hypotheses_summary()

                # 询问用户选择
                self.console.print("\n[bold white]老板，初步假设已生成。请选择您最看好的一个进入终审阶段：[/bold white]\n")

                choice = questionary.text(
                    "输入 1, 2, 3 选择对应假设，或输�� 0 让他们重新想：",
                    style=custom_style
                ).ask()

                # 验证输入
                if choice == '0':
                    # 重新生成假设
                    self.console.print("\n[yellow]打回给首席科学家重新生成...[/yellow]\n")

                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=self.console
                    ) as progress:
                        task = progress.add_task("首席科学家正在重新构思假设...", total=None)

                        hyp_result = self.orchestrator.hypothesis_agent.execute({
                            'literature_report': f"搜索关键词: {query}\n找到 {len(self.selected_papers)} 篇相关文献\n\n上一轮假设被否决，请生成全新的假设",
                            'papers': self.selected_papers,
                            'research_topic': research_topic,
                            'output_dir': 'reports'
                        })

                        progress.remove_task(task)

                    if hyp_result['success']:
                        self.generated_hypotheses = hyp_result['hypotheses']
                        self.hypothesis_ids = hyp_result.get('hypothesis_ids', [])
                        self.proposal_path = hyp_result.get('proposal_path')
                        self.console.print(f"[green]已重新生成 {len(self.generated_hypotheses)} 个新假设[/green]")
                        continue  # 重新显示选择
                    else:
                        self.console.print(f"[red]重新生成失败: {hyp_result.get('error')}[/red]")
                        continue

                elif choice in ['1', '2', '3']:
                    # 检查索引是否有效
                    hyp_index = int(choice) - 1
                    if hyp_index >= len(self.generated_hypotheses):
                        self.console.print(f"[red]无效选择，只有 {len(self.generated_hypotheses)} 个假设[/red]")
                        continue

                    # 选中的假设
                    selected_hyp = self.generated_hypotheses[hyp_index]
                    selected_hyp_id = self.hypothesis_ids[hyp_index] if hyp_index < len(self.hypothesis_ids) else None

                    self.console.print(f"\n[bold green]您选择了假设 {choice}: {selected_hyp['title'][:50]}...[/bold green]\n")

                    # ============ 步骤 5: 审稿人深度评估 ============
                    self.console.print("[bold cyan]========== 步骤 5: 严苛的审稿人深度评估 ==========[/bold cyan]\n")

                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=self.console
                    ) as progress:
                        task = progress.add_task("Nature 高级编辑正在进行深度可行性与价值评估...", total=None)

                        validation_result = self.orchestrator.validation_agent.execute({
                            'hypothesis_id': selected_hyp_id,
                            'hypothesis_data': {
                                'title': selected_hyp.get('title', ''),
                                'description': selected_hyp.get('description', ''),
                                'rationale': selected_hyp.get('rationale', ''),
                                'novelty': selected_hyp.get('novelty', ''),
                                'expected_value': selected_hyp.get('expected_value', ''),
                                'validation_plan': selected_hyp.get('validation_plan', ''),
                                'paradigm_framework': selected_hyp.get('paradigm_framework', ''),
                                'grand_challenge': selected_hyp.get('grand_challenge', '')
                            },
                            'source_papers': self.selected_papers[:5],
                            'enable_literature_check': True,
                            'output_dir': 'reports'
                        })

                        progress.remove_task(task)

                    if not validation_result['success']:
                        self.console.print(f"[red]评估失败: {validation_result.get('error')}[/red]")
                        return

                    # ============ 步骤 6: 输出评审报告 ============
                    self._display_final_report(selected_hyp, validation_result)

                    # 完成会话
                    self.complete_session(session_id)
                    break

                else:
                    self.console.print("[red]无效输入，请输入 0, 1, 2 或 3[/red]")
                    continue

        except KeyboardInterrupt:
            self.console.print("\n[yellow]流程已中断[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]错误: {str(e)}[/red]")
            import traceback
            traceback.print_exc()

    def _display_hypotheses_summary(self):
        """显示假设摘要供用户选择"""
        self.console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]")
        self.console.print("[bold white]假设提案摘要[/bold white]")
        self.console.print("[bold cyan]" + "=" * 60 + "[/bold cyan]\n")

        for i, hyp in enumerate(self.generated_hypotheses, 1):
            title = hyp.get('title', 'N/A')
            description = hyp.get('description', 'N/A')
            paradigm = hyp.get('paradigm_framework', 'N/A')

            # 截断描述
            if len(description) > 150:
                description = description[:150] + "..."

            panel = Panel(
                f"[bold]假设名称[/bold]: {title}\n\n"
                f"[bold]前沿框架[/bold]: {paradigm}\n\n"
                f"[bold]摘要[/bold]: {description}",
                title=f"[bold yellow]假设 {i}[/bold yellow]",
                border_style="cyan"
            )
            self.console.print(panel)

    def _display_final_report(self, hypothesis: dict, validation_result: dict):
        """显示最终评审报告"""
        validation = validation_result.get('validation', {})
        scores = validation.get('scores', {})

        # 决议
        final_decision = validation.get('final_decision', 'unknown')
        decision_emoji = {
            'accepted': '[green]ACCEPT[/green]',
            'revise': '[yellow]REVISE[/yellow]',
            'rejected': '[red]REJECT[/red]'
        }
        decision_display = decision_emoji.get(final_decision.lower(), f'[white]{final_decision}[/white]')

        self.console.print("\n[bold green]" + "=" * 60 + "[/bold green]")
        self.console.print("[bold white]Nature 级别评审报告[/bold white]")
        self.console.print("[bold green]" + "=" * 60 + "[/bold green]\n")

        # 评分表
        score_table = Table(title="评分详情", show_header=True, header_style="bold cyan")
        score_table.add_column("评估维度", width=30)
        score_table.add_column("得分", width=10)
        score_table.add_column("等级", width=15)

        dimension_names = {
            'transformative_impact': '广度与深度的颠覆性',
            'methodological_originality': '方法论的原创性',
            'poc_feasibility': '验证的可行性'
        }

        for key, score in scores.items():
            name = dimension_names.get(key, key)
            level = self._get_score_level(score)
            score_table.add_row(name, f"{score}/10", level)

        avg_score = sum(scores.values()) / len(scores) if scores else 0
        score_table.add_row("[bold]平均分[/bold]", f"[bold]{avg_score:.1f}/10[/bold]", "")

        self.console.print(score_table)

        # 最终决议
        verdict = validation.get('verdict', {})
        self.console.print(f"\n[bold]最终决议: {decision_display}[/bold]")
        self.console.print(f"[bold]决策理由[/bold]: {verdict.get('rationale', 'N/A')}")

        if final_decision.lower() == 'revise':
            self.console.print(f"[bold]修改条件[/bold]: {verdict.get('conditions', 'N/A')}")

        # 详细分析
        impact = validation.get('impact_analysis', {})
        originality = validation.get('originality_analysis', {})
        feasibility = validation.get('feasibility_analysis', {})

        self.console.print("\n[bold cyan]---------- 详细分析 ----------[/bold cyan]\n")

        self.console.print("[bold]广度与深度的颠覆性[/bold]")
        self.console.print(f"  跨学科影响力: {impact.get('breadth', 'N/A')}")
        self.console.print(f"  颠覆性: {impact.get('depth', 'N/A')}")
        self.console.print(f"  教科书影响: {impact.get('textbook_impact', 'N/A')}")

        self.console.print("\n[bold]方法论的原创性[/bold]")
        self.console.print(f"  核心创新: {originality.get('core_innovation', 'N/A')}")
        self.console.print(f"  与现有方法的区别: {originality.get('comparison', 'N/A')}")

        self.console.print("\n[bold]验证的可行性[/bold]")
        self.console.print(f"  数据规模: {feasibility.get('data_scale', 'N/A')}")
        self.console.print(f"  算力需求: {feasibility.get('computational_needs', 'N/A')}")

        recommended_dbs = feasibility.get('recommended_databases', [])
        if recommended_dbs:
            self.console.print(f"  推荐数据库: {', '.join(recommended_dbs)}")

        # 报告路径
        report_path = validation.get('report_path')
        if report_path:
            self.console.print(f"\n[dim]详细报告已保存: {report_path}[/dim]")

    def _get_score_level(self, score: int) -> str:
        """获取得分等级"""
        if score >= 9:
            return '[green]Nature 级别[/green]'
        elif score >= 7:
            return '[cyan]优秀[/cyan]'
        elif score >= 5:
            return '[yellow]中等[/yellow]'
        elif score >= 3:
            return '[orange]较差[/orange]'
        else:
            return '[red]拒稿[/red]'

    def complete_session(self, session_id):
        """完成会话"""
        complete_result = self.orchestrator.complete_session()

        if complete_result['success']:
            summary = complete_result['summary']
            self.console.print(Panel.fit(
                f"[bold green]会话完成[/bold green]\n"
                f"会话ID: {session_id}\n"
                f"搜索论文: {summary['papers_found']} 篇\n"
                f"生成假设: {summary['hypotheses_generated']} 个\n"
                f"验证假设: {summary['hypotheses_validated']} 个",
                border_style="green"
            ))

    def view_sessions(self):
        """查看历史会话"""
        sessions = self.orchestrator.list_recent_sessions(10)

        if not sessions:
            self.console.print("[yellow]暂无历史会话[/yellow]")
            return

        table = Table(
            title="历史研究会话",
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("ID", width=6)
        table.add_column("搜索关键词", width=30)
        table.add_column("创建时间", width=20)
        table.add_column("状态", width=12)
        table.add_column("论文数", width=8)
        table.add_column("假设数", width=8)

        for session in sessions:
            table.add_row(
                str(session['id']),
                session['query'][:30] + '...' if len(session['query']) > 30 else session['query'],
                session['created_at'][:19],
                session['status'],
                str(session['papers_found']),
                str(session['hypotheses_generated'])
            )

        self.console.print(table)

    def view_saved_hypotheses(self):
        """查看已保存的假设"""
        self.console.print("[yellow]假设查看功能开发中[/yellow]")

    def run_autonomous_mode(self):
        """
        运行自主循环模式

        类似 Karpathy autoresearch 的设计：
        - Agent 自动迭代优化假设
        - 直到达标或超时
        """
        self.console.print(Panel.fit(
            "[bold cyan]🤖 自主循环模式[/bold cyan]\n"
            "[yellow]Agent 将自动迭代优化假设，直到达标或超时[/yellow]\n"
            "[dim]参考: Karpathy autoresearch[/dim]",
            border_style="cyan"
        ))

        # 加载配置
        config = get_program_config()

        # 显示当前配置
        self.console.print(f"\n[cyan]当前配置:[/cyan]")
        self.console.print(f"  目标分数: {config.get_target_score()}")
        self.console.print(f"  最大迭代: {config.get_max_iterations()}")
        self.console.print(f"  时间预算: {config.get_time_budget()} 分钟")
        self.console.print(f"  最低 IF: {config.get_min_if()}")
        self.console.print(f"  日期范围: {config.get_date_range()}")

        # 询问是否修改配置
        modify_config = questionary.confirm(
            "是否修改配置参数？",
            default=False,
            style=custom_style
        ).ask()

        if modify_config:
            self._modify_autonomous_config(config)

        # 输入关键词
        query = questionary.text(
            "请输入研究关键词：\n"
            "[dim]例如：machine learning genomics, Alzheimer MRI[/dim]",
            style=custom_style
        ).ask()

        if not query:
            self.console.print("[red]关键词不能为空[/red]")
            return

        # 确认启动
        confirm = questionary.confirm(
            f"确认启动自主循环？\n"
            f"关键词: {query}\n"
            f"目标分数: {config.get_target_score()}\n"
            f"最大迭代: {config.get_max_iterations()}",
            default=True,
            style=custom_style
        ).ask()

        if not confirm:
            self.console.print("[yellow]已取消[/yellow]")
            return

        # 运行自主模式
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task(
                    "🤖 Agent 正在自主迭代优化...",
                    total=None
                )

                result = self.orchestrator.run_autonomous_mode(
                    query=query,
                    config=config
                )

                progress.remove_task(task)

            # 显示结果
            self._display_autonomous_result(result)

        except KeyboardInterrupt:
            self.console.print("\n[yellow]自主循环已中断[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]错误: {str(e)}[/red]")
            import traceback
            traceback.print_exc()

    def _modify_autonomous_config(self, config):
        """修改自主模式配置"""
        self.console.print("\n[cyan]修改配置参数:[/cyan]")

        # 目标分数
        target_score = questionary.text(
            f"目标分数（当前: {config.get_target_score()}）：",
            default=str(config.get_target_score()),
            style=custom_style
        ).ask()
        try:
            config.update('autonomous_mode.target_score', float(target_score))
        except ValueError:
            pass

        # 最大迭代
        max_iter = questionary.text(
            f"最大迭代次数（当前: {config.get_max_iterations()}）：",
            default=str(config.get_max_iterations()),
            style=custom_style
        ).ask()
        try:
            config.update('autonomous_mode.max_iterations', int(max_iter))
        except ValueError:
            pass

        # 时间预算
        time_budget = questionary.text(
            f"时间预算（分钟，当前: {config.get_time_budget()}）：",
            default=str(config.get_time_budget()),
            style=custom_style
        ).ask()
        try:
            config.update('autonomous_mode.time_budget_minutes', int(time_budget))
        except ValueError:
            pass

        # 最低 IF
        min_if = questionary.text(
            f"最低影响因子（当前: {config.get_min_if()}）：",
            default=str(config.get_min_if()),
            style=custom_style
        ).ask()
        try:
            config.update('paper_search.min_if', float(min_if))
        except ValueError:
            pass

        self.console.print("[green]配置已更新[/green]")

    def _display_autonomous_result(self, result):
        """显示自主循环结果"""
        self.console.print("\n" + "="*60)
        self.console.print("[bold cyan]🤖 自主循环完成[/bold cyan]")
        self.console.print("="*60 + "\n")

        if result.get('success'):
            self.console.print(f"[green]✅ 成功生成假设[/green]")
        else:
            self.console.print(f"[red]❌ 未达标: {result.get('error', '未知错误')}[/red]")

        # 统计信息
        self.console.print(f"\n[cyan]统计信息:[/cyan]")
        self.console.print(f"  总迭代: {result.get('iterations', 0)}")
        self.console.print(f"  总用时: {result.get('time_elapsed', 0)/60:.1f} 分钟")
        self.console.print(f"  最终分数: {result.get('best_score', 0):.1f}")
        self.console.print(f"  论文数: {len(result.get('papers', []))}")

        # 显示最终假设
        final_hypotheses = result.get('final_hypotheses', [])
        if final_hypotheses:
            self.console.print(f"\n[bold cyan]最终假设:[/bold cyan]")
            for i, hyp in enumerate(final_hypotheses, 1):
                title = hyp.get('title', 'N/A')
                score = hyp.get('prevalidation_avg', 0)
                self.console.print(f"\n  [bold yellow]假设 {i}[/bold yellow]: {title[:60]}...")
                self.console.print(f"  综合分数: [green]{score:.1f}/10[/green]")

        # 实验日志路径
        experiment_log = result.get('experiment_log', [])
        if experiment_log:
            self.console.print(f"\n[dim]实验日志已记录，共 {len(experiment_log)} 条[/dim]")

        # 会话 ID
        session_id = result.get('session_id')
        if session_id:
            self.console.print(f"[dim]会话 ID: {session_id}[/dim]")

    def view_program_config(self):
        """查看/修改 program.md 配置"""
        config = get_program_config()

        self.console.print(Panel.fit(
            "[bold cyan]研究策略配置 (program.md)[/bold cyan]\n"
            "[dim]参考 Karpathy autoresearch 的设计理念[/dim]",
            border_style="cyan"
        ))

        # 显示配置文件路径
        self.console.print(f"\n[cyan]配置文件: {config.program_path}[/cyan]")

        # 显示关键配置
        self.console.print(f"\n[bold]研究目标:[/bold]")
        goals = config.get_section('research_goals')
        for key, value in goals.items():
            self.console.print(f"  {key}: {value}")

        self.console.print(f"\n[bold]论文搜索:[/bold]")
        search = config.get_section('paper_search')
        for key, value in search.items():
            self.console.print(f"  {key}: {value}")

        self.console.print(f"\n[bold]假设生成:[/bold]")
        gen = config.get_section('hypothesis_generation')
        for key, value in gen.items():
            self.console.print(f"  {key}: {value}")

        self.console.print(f"\n[bold]自主模式:[/bold]")
        auto = config.get_section('autonomous_mode')
        for key, value in auto.items():
            self.console.print(f"  {key}: {value}")

        # 询问是否编辑
        edit = questionary.confirm(
            "是否编辑 program.md 文件？",
            default=False,
            style=custom_style
        ).ask()

        if edit:
            # 显示文件路径供用户手动编辑
            self.console.print(f"\n[yellow]请手动编辑文件: {config.program_path}[/yellow]")
            self.console.print("[dim]编辑完成后，重启程序以加载新配置[/dim]")

            # 或者提供简单的配置修改选项
            quick_edit = questionary.confirm(
                "是否使用快速配置修改？",
                default=False,
                style=custom_style
            ).ask()

            if quick_edit:
                self._quick_edit_config(config)

        # 重新加载配置
        reload_config = questionary.confirm(
            "是否重新加载配置？",
            default=False,
            style=custom_style
        ).ask()

        if reload_config:
            reload_program_config()
            self.console.print("[green]配置已重新加载[/green]")

    def _quick_edit_config(self, config):
        """快速编辑配置"""
        choices = [
            "修改目标分数",
            "修改最大迭代次数",
            "修改时间预算",
            "开启/关闭自主模式",
            "修改最低影响因子",
            "返回"
        ]

        while True:
            action = questionary.select(
                "选择要修改的配置项：",
                choices=choices,
                style=custom_style
            ).ask()

            if action == "修改目标分数":
                value = questionary.text(
                    f"当前: {config.get_target_score()}，新值:",
                    style=custom_style
                ).ask()
                try:
                    config.update('autonomous_mode.target_score', float(value))
                except ValueError:
                    self.console.print("[red]无效数值[/red]")

            elif action == "修改最大迭代次数":
                value = questionary.text(
                    f"当前: {config.get_max_iterations()}，新值:",
                    style=custom_style
                ).ask()
                try:
                    config.update('autonomous_mode.max_iterations', int(value))
                except ValueError:
                    self.console.print("[red]无效数值[/red]")

            elif action == "修改时间预算":
                value = questionary.text(
                    f"当前: {config.get_time_budget()} 分钟，新值:",
                    style=custom_style
                ).ask()
                try:
                    config.update('autonomous_mode.time_budget_minutes', int(value))
                except ValueError:
                    self.console.print("[red]无效数值[/red]")

            elif action == "开启/关闭自主模式":
                current = config.is_autonomous_enabled()
                new_value = not current
                config.update('autonomous_mode.enabled', new_value)
                status = "开启" if new_value else "关闭"
                self.console.print(f"[green]自主模式已{status}[/green]")

            elif action == "修改最低影响因子":
                value = questionary.text(
                    f"当前: {config.get_min_if()}，新值:",
                    style=custom_style
                ).ask()
                try:
                    config.update('paper_search.min_if', float(value))
                except ValueError:
                    self.console.print("[red]无效数值[/red]")

            elif action == "返回":
                break

    def export_report(self):
        """导出报告菜单"""
        hypothesis_id_input = questionary.text(
            "请输入要导出的假设ID：",
            style=custom_style
        ).ask()

        try:
            hyp_id = int(hypothesis_id_input)
            self.export_single_report(hyp_id)
        except ValueError:
            self.console.print("[red]请输入有效的ID[/red]")

    def export_single_report(self, hypothesis_id):
        """导出单个假设的报告"""
        report = self.orchestrator.get_full_report(hypothesis_id)
        if report:
            filename = self.exporter.export_to_markdown(report)
            self.console.print(f"[green]报告已导出到: {filename}[/green]")


def main():
    """主函数"""
    try:
        cli = ResearchCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n\n程序已退出")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    main()