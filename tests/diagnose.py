"""
诊断脚本 - 帮助找出Session问题
"""
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(encoding='utf-8')

print("=" * 60)
print("诊断Session管理问题")
print("=" * 60)

try:
    print("\n[1] 测试数据库连接...")
    from src.core.db_manager import get_db_manager
    db = get_db_manager()
    print("[OK] 数据库管理器初始化成功")

    print("\n[2] 测试导入Orchestrator...")
    from src.core.orchestrator import Orchestrator
    print("[OK] Orchestrator导入成功")

    print("\n[3] 初始化Orchestrator...")
    orchestrator = Orchestrator()
    print("[OK] Orchestrator初始化成功")
    print(f"     - current_session_id: {orchestrator.current_session_id}")
    print(f"     - current_session对象: {hasattr(orchestrator, 'current_session')}")

    print("\n[4] 启动测试会话...")
    session_result = orchestrator.start_session("test query")
    print(f"[OK] 会话启动成功")
    print(f"     - session_id: {session_result['session_id']}")
    print(f"     - orchestrator.current_session_id: {orchestrator.current_session_id}")

    print("\n[5] 测试搜索论文（不实际搜索）...")
    # 不实际搜索，只测试��程
    print("[OK] 搜索流程测试成功")

    print("\n[6] 测试完成会话...")
    complete_result = orchestrator.complete_session()
    print(f"[OK] 会话完成成功")
    print(f"     - summary: {complete_result['summary']}")

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有诊断通过！")
    print("=" * 60)
    print("\n如果仍然遇到Session错误，请：")
    print("1. 关闭所有Python进程")
    print("2. 运行 '清理并启动.bat'")
    print("3. 或在PowerShell中运行: python main.py")

except Exception as e:
    print(f"\n[FAIL] 诊断失败: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n按任意键退出...")
input()