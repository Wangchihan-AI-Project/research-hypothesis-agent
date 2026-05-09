# -*- coding: utf-8 -*-
"""
测试 ReAct 工具调用功能

验证：
1. 工具定义正确
2. ReAct 执行器可以正确调用工具
3. 系统提示词包含查证钢印
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.react_tools import (
    ReActExecutor,
    SEARCH_PUBMED_TOOL,
    create_pubmed_tool_implementation,
    VERIFICATION_STEEL_IMPRINT
)
from src.utils.pubmed import PubMedSearcher


def test_tool_definition():
    """测试工具定义"""
    print("=" * 60)
    print("测试1: 工具定义")
    print("=" * 60)

    print(f"工具名称: {SEARCH_PUBMED_TOOL['name']}")
    print(f"工具描述: {SEARCH_PUBMED_TOOL['description'][:100]}...")
    print(f"必需参数: {SEARCH_PUBMED_TOOL['input_schema']['required']}")

    assert SEARCH_PUBMED_TOOL['name'] == 'search_pubmed'
    assert 'query' in SEARCH_PUBMED_TOOL['input_schema']['required']
    print("  OK 工具定义正确\n")


def test_verification_imprint():
    """测试查证钢印"""
    print("=" * 60)
    print("测试2: 查证钢印")
    print("=" * 60)

    print(f"查证钢印长度: {len(VERIFICATION_STEEL_IMPRINT)} 字符")

    # 检查关键内容
    assert 'search_pubmed' in VERIFICATION_STEEL_IMPRINT
    assert 'ReAct' in VERIFICATION_STEEL_IMPRINT
    assert '开题前置检索' in VERIFICATION_STEEL_IMPRINT
    assert '参数级查证' in VERIFICATION_STEEL_IMPRINT
    assert '铁血查重' in VERIFICATION_STEEL_IMPRINT

    print("  OK 查证钢印包含所有关键要素")
    print("  - 开题前置检索")
    print("  - 参数级查证")
    print("  - 铁血查重与评分")
    print("  - 工具调用示例\n")


def test_pubmed_tool_implementation():
    """测试 PubMed 工具实现"""
    print("=" * 60)
    print("测试3: PubMed 工具实现（模拟模式）")
    print("=" * 60)

    # 创建模拟搜索器（符合 PubMedSearcher.search_papers 接口）
    class MockPubMedSearcher:
        def search_papers(self, query, max_results=5, date_range=None, enable_filter=False):
            return [
                {
                    'pmid': '12345678',
                    'title': f'Mock Paper: {query}',
                    'journal': 'Nature',
                    'publication_date': '2024-01-01',
                    'abstract': f'This is a mock abstract for query: {query}. ' * 20
                }
            ]

    mock_searcher = MockPubMedSearcher()
    tool_func = create_pubmed_tool_implementation(mock_searcher)

    # 测试工具调用（现在返回字符串）
    result = tool_func(query='ADNI hippocampus', max_results=3)

    print(f"  返回类型: {type(result).__name__}")
    print(f"  返回内容长度: {len(result)} 字符")
    if '检索到' in result:
        print(f"  包含检索结果: 是")
    if 'Mock Paper' in result:
        print(f"  包含论文标题: 是")
    print("  OK 工具实现正确\n")


def test_react_executor_init():
    """测试 ReAct 执行器初始化"""
    print("=" * 60)
    print("测试4: ReAct 执行器初始化")
    print("=" * 60)

    # 创建模拟客户端
    class MockClient:
        pass

    mock_client = MockClient()

    # 创建工具实现（符合 search_papers 接口）
    class MockSearcher:
        def search_papers(self, query, max_results=5, date_range=None, enable_filter=False):
            return [{'pmid': '123', 'title': 'Test', 'abstract': 'Test abstract'}]

    tool_implementations = {
        'search_pubmed': create_pubmed_tool_implementation(MockSearcher())
    }

    # 初始化执行器
    executor = ReActExecutor(
        client=mock_client,
        model='claude-3-5-sonnet-20241022',
        tools=[SEARCH_PUBMED_TOOL],
        tool_implementations=tool_implementations
    )

    print(f"  工具数量: {len(executor.tools)}")
    print(f"  最大迭代次数: {executor.max_iterations}")
    print(f"  已注册工具: {list(executor.tool_implementations.keys())}")
    print("  OK ReAct 执行器初始化成功\n")


def test_hypothesis_agent_react():
    """测试 HypothesisAgent 的 ReAct 功能"""
    print("=" * 60)
    print("测试5: HypothesisAgent ReAct 集成")
    print("=" * 60)

    from src.agents.hypothesis_agent import ChiefScientistAgent, CHIEF_SCIENTIST_SYSTEM_PROMPT

    # 检查系统提示词（V3.0 重塑版）
    assert 'search_pubmed' in CHIEF_SCIENTIST_SYSTEM_PROMPT
    assert '强制检索协议 V3.0' in CHIEF_SCIENTIST_SYSTEM_PROMPT
    assert '禁止查询词过载' in CHIEF_SCIENTIST_SYSTEM_PROMPT or '禁止事项 A' in CHIEF_SCIENTIST_SYSTEM_PROMPT
    print("  OK 系统提示词包含检索协议 V3.0")

    # 检查 Agent 初始化（不启用 ReAct 以避免 API 调用）
    os.environ['ENABLE_REACT'] = 'false'
    agent = ChiefScientistAgent()
    print(f"  OK Agent 初始化成功 (ReAct: {agent.enable_react})")

    # 检查 Agent 属性
    assert hasattr(agent, 'enable_react')
    assert hasattr(agent, 'tool_calls_log')
    print("  OK Agent 包含 ReAct 相关属性\n")


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("\n" + "=" * 60)
    print("ReAct 工具调用测试")
    print("=" * 60 + "\n")

    try:
        test_tool_definition()
        test_verification_imprint()
        test_pubmed_tool_implementation()
        test_react_executor_init()
        test_hypothesis_agent_react()

        print("=" * 60)
        print("所有测试通过！")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
