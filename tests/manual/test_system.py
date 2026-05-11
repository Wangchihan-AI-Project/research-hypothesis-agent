"""
快速测试脚本 - 验证系统是否正常工作
"""
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

from src.core.orchestrator import Orchestrator

def test_system():
    """测试系统基本功能"""
    print("=" * 50)
    print("系统功能测试")
    print("=" * 50)

    try:
        # 初始化协调器
        print("\n[1/5] 初始化工作流协调器...")
        orchestrator = Orchestrator()
        print("[OK] 协调器初始化成功")

        # 启动会话
        print("\n[2/5] 启动研究会话...")
        session_result = orchestrator.start_session("machine learning test")
        if session_result['success']:
            print(f"[OK] 会话启动成功 (ID: {session_result['session_id']})")
        else:
            print(f"[FAIL] 会话启动失败: {session_result.get('error')}")
            return False

        # 搜索论文（小规模测试）
        print("\n[3/5] 搜索论文（最多5篇）...")
        search_result = orchestrator.search_papers("bioinformatics", max_results=5)
        if search_result['success']:
            print(f"[OK] 论文搜索成功，找到 {len(search_result['papers'])} 篇论文")
        else:
            print(f"[FAIL] 论文搜索失败: {search_result.get('error')}")
            return False

        # 完成会话
        print("\n[4/5] 完成会话...")
        complete_result = orchestrator.complete_session()
        if complete_result['success']:
            print("[OK] 会话完成成功")
            print(f"  - 搜索论文: {complete_result['summary']['papers_found']} 篇")
            print(f"  - 生成假设: {complete_result['summary']['hypotheses_generated']} 个")
            print(f"  - 验证假设: {complete_result['summary']['hypotheses_validated']} 个")
        else:
            print(f"[FAIL] 会话完成失败: {complete_result.get('error')}")
            return False

        # 列出历史会话
        print("\n[5/5] 查询历史会话...")
        sessions = orchestrator.list_recent_sessions(5)
        print(f"[OK] 查询成功，共有 {len(sessions)} 个历史会话")

        print("\n" + "=" * 50)
        print("[SUCCESS] 所有测试通过！系统运行正常")
        print("=" * 50)
        return True

    except Exception as e:
        print(f"\n[FAIL] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_system()
    sys.exit(0 if success else 1)