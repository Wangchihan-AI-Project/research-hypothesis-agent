# -*- coding: utf-8 -*-
"""文献检索页两阶段状态流回归测试。"""
import os
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAGE_PATH = PROJECT_ROOT / 'pages' / '04_文献检索.py'


if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')

sys.path.insert(0, str(PROJECT_ROOT))
os.environ['PYTHONPATH'] = str(PROJECT_ROOT) + os.pathsep + os.environ.get('PYTHONPATH', '')
os.chdir(PROJECT_ROOT)


def build_paper(*, fallback: bool, source: str = 'PubMed', retrieved_via: str = 'pubmed'):
    return {
        'title': 'Demo Paper',
        'authors': 'A, B',
        'year': 2025,
        'journal': 'Nature',
        'pmid': '123456',
        'impact_factor': 10.0,
        'citations': 42,
        'abstract': 'demo abstract',
        'source': source,
        'doi': '10.1/demo',
        'retrieved_via': retrieved_via,
        'requested_source': 'semantic_scholar',
        'llm_score': 5.4 if fallback else 7.8,
        'llm_reason': 'LLM调用失败(APITimeoutError)，使用启发式回退' if fallback else '真实 LLM 评分',
        'llm_research_type': '原创研究',
        'llm_fallback': fallback,
        'llm_error_type': 'APITimeoutError' if fallback else '',
    }


def get_metric_map(at: AppTest):
    return {metric.label: metric.value for metric in at.metric}


def run_preliminary_state_test():
    at = AppTest.from_file(str(PAGE_PATH), default_timeout=30)
    at.run(timeout=60)

    at.session_state['search_query'] = 'demo'
    at.session_state['search_status'] = 'preliminary'
    at.session_state['search_result_level'] = 'preliminary'
    at.session_state['search_running'] = True
    at.session_state['search_preliminary_elapsed'] = 4.1
    at.session_state['search_final_elapsed'] = None
    at.session_state['search_results'] = [build_paper(fallback=False)]
    at.run(timeout=60)

    metrics = get_metric_map(at)
    assert metrics['候选耗时'] == '4.1 s', metrics
    assert metrics['最终耗时'] == '- s', metrics
    assert metrics['回退评分数'] == '0', metrics
    assert metrics['实际数据源'] == 'pubmed', metrics
    assert len(at.warning) >= 1, 'preliminary 状态未显示 warning'



def run_final_fallback_test():
    at = AppTest.from_file(str(PAGE_PATH), default_timeout=30)
    at.run(timeout=60)

    at.session_state['search_query'] = 'demo'
    at.session_state['search_status'] = 'success'
    at.session_state['search_result_level'] = 'final'
    at.session_state['search_running'] = False
    at.session_state['search_preliminary_elapsed'] = 4.1
    at.session_state['search_final_elapsed'] = 10.2
    at.session_state['search_results'] = [build_paper(fallback=True)]
    at.run(timeout=60)

    metrics = get_metric_map(at)
    captions = [caption.value for caption in at.caption]
    assert metrics['候选耗时'] == '4.1 s', metrics
    assert metrics['最终耗时'] == '10.2 s', metrics
    assert metrics['回退评分数'] == '1', metrics
    assert metrics['实际数据源'] == 'pubmed', metrics
    assert len(at.success) >= 1, 'final 状态未显示 success'
    assert any('启发式回退' in caption for caption in captions), captions
    assert any('评分依据' in caption for caption in captions), captions


if __name__ == '__main__':
    run_preliminary_state_test()
    run_final_fallback_test()
    print('PASS: 文献检索页状态流回归测试通过')
