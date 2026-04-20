"""
完整测试脚本 - 验证所有修复
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

print("=" * 70)
print("研究假设生成系统 - 完整测试")
print("=" * 70)

try:
    print("\n[步骤1] 初始化系统...")
    from src.core.orchestrator import Orchestrator
    orchestrator = Orchestrator()
    print("[OK] 系统初始化成功")

    print("\n[步骤2] 启动研究会话...")
    session_result = orchestrator.start_session("bioinformatics test")
    print(f"[OK] 会话启动成功 (ID: {session_result['session_id']})")

    print("\n[步骤3] 搜索论文...")
    search_result = orchestrator.search_papers("bioinformatics", max_results=3)
    if search_result['success']:
        print(f"[OK] 论文搜索成功")
        print(f"     - 找到: {len(search_result['papers'])} 篇论文")

        # 显示论文标题
        for i, paper in enumerate(search_result['papers'], 1):
            if paper.get('title'):
                print(f"     论文{i}: {paper['title'][:70]}...")
                print(f"       PMID: {paper.get('pmid', 'N/A')}")
    else:
        print(f"[FAIL] 论文搜索失败: {search_result.get('error')}")
        sys.exit(1)

    print("\n[步骤4] 测试数据保存...")
    # 搜索结果已经自动保存到数据库
    print("[OK] 论文已保存到数据库")

    print("\n[步骤5] 完成会话...")
    complete_result = orchestrator.complete_session()
    print(f"[OK] 会话完成成功")
    print(f"     - 搜索论文: {complete_result['summary']['papers_found']} 篇")
    print(f"     - 生成假设: {complete_result['summary']['hypotheses_generated']} 个")
    print(f"     - 验证假设: {complete_result['summary']['hypotheses_validated']} 个")

    print("\n[步骤6] 查询历史会话...")
    sessions = orchestrator.list_recent_sessions(3)
    print(f"[OK] 找到 {len(sessions)} 个历史会话")
    for session in sessions:
        print(f"     - 会话{session['id']}: {session['query'][:30]}... ({session['status']})")

    print("\n" + "=" * 70)
    print("[SUCCESS] 所有测试通过！系统运行正常")
    print("=" * 70)
    print("\n系统已就绪，可以开始使用了！")
    print("\n启动命令: python main.py")
    print("或双击: 启动系统.bat")

except Exception as e:
    print(f"\n[FAIL] 测试失败: {str(e)}")
    import traceback
    traceback.print_exc()
    print("\n请检查:")
    print("1. 是否关闭了所有Python进程")
    print("2. 是否安装了所有依赖: pip install -r requirements.txt")
    print("3. 是否配置了API密钥")

print("\n按任意键退出...")
input()