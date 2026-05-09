# -*- coding: utf-8 -*-
"""
多源文献检索 - PubMed / ArXiv / Semantic Scholar

直接调用 Orchestrator 同步检索，支持过滤、排序、导出

作者: V8.1
日期: 2026-05-03
"""
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

import streamlit as st
import pandas as pd

from src.ui.page_base import setup_page, get_orchestrator

project_root = setup_page("文献检索", "🔍")

# ==================== Session State ====================
def init_search_state():
    defaults = {
        'search_results': [],
        'search_query': '',
        'search_source': 'pubmed',
        'search_running': False,
        'search_selected_papers': set(),
        'search_future_id': None,
        'search_status': 'idle',
        'search_error': None,
        'search_started_at': None,
        'search_params_snapshot': None,
        'search_result_level': None,
        'search_job_id': None,
        'search_preliminary_elapsed': None,
        'search_final_elapsed': None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_search_state()

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False


@st.cache_resource
def get_search_executor():
    return ThreadPoolExecutor(max_workers=3, thread_name_prefix="paper_search")


@st.cache_resource
def get_search_futures():
    return {}


def submit_search_future(params):
    future_id = str(uuid4())
    get_search_futures()[future_id] = get_search_executor().submit(run_search_task, params)
    return future_id


def get_elapsed_seconds(started_at):
    if not started_at:
        return None
    return round((datetime.now() - datetime.fromisoformat(started_at)).total_seconds(), 1)


def normalize_pubmed_progressive_result(result, retrieved_via, requested_source=None):
    papers = result.get('papers', [])
    output = []
    normalized_requested_source = requested_source or retrieved_via
    for p in papers:
        output.append({
            'title': p.get('title', 'N/A'),
            'authors': p.get('authors', p.get('first_author', '')),
            'year': p.get('year', ''),
            'journal': p.get('journal', ''),
            'pmid': p.get('pmid', ''),
            'impact_factor': p.get('impact_factor', p.get('if', 0)),
            'citations': p.get('citations', p.get('citation_count', 0)),
            'abstract': p.get('abstract', '')[:300] if p.get('abstract') else '',
            'source': 'PubMed',
            'doi': p.get('doi', ''),
            'retrieved_via': retrieved_via,
            'requested_source': normalized_requested_source,
            'selection_stage': p.get('selection_stage'),
        })
    return output


def run_search_task(params):
    source = params['source']
    fallback_orders = {
        'pubmed': ['pubmed', 'semantic_scholar', 'arxiv'],
        'arxiv': ['arxiv', 'semantic_scholar', 'pubmed'],
        'semantic_scholar': ['semantic_scholar', 'pubmed', 'arxiv'],
    }

    search_errors = []
    for candidate in fallback_orders.get(source, [source]):
        try:
            if candidate == 'pubmed':
                result = do_pubmed_search(
                    params['query'],
                    params['max_results'],
                    params['min_if'],
                    params['start_year'],
                    params['end_year'],
                    requested_source=source,
                    retrieved_via=candidate,
                )
                if not result.get('success', False):
                    raise RuntimeError(result.get('error', '未知错误'))
                papers = normalize_pubmed_progressive_result(result, candidate, source)
                return {
                    'papers': papers,
                    'result_level': result.get('result_level', 'preliminary'),
                    'job_id': result.get('job_id'),
                    'stage1_stats': result.get('stage1_stats'),
                    'retrieved_via': candidate,
                    'requested_source': source,
                }
            elif candidate == 'arxiv':
                papers = do_arxiv_search(params['query'], params['max_results'])
            elif candidate == 'semantic_scholar':
                papers = do_semantic_scholar_search(params['query'], params['max_results'])
            else:
                continue

            for paper in papers:
                paper.setdefault('retrieved_via', candidate)
                paper.setdefault('requested_source', source)
                paper.setdefault('selection_stage', 'stage1')
                paper.setdefault('llm_fallback', False)
                paper.setdefault('llm_error_type', '')
            if not papers:
                search_errors.append(f"{candidate}: 未返回结果")
                continue
            return {
                'papers': papers,
                'result_level': 'final',
                'job_id': None,
                'stage1_stats': {'total_fetched': len(papers), 'query': params['query']},
                'retrieved_via': candidate,
                'requested_source': source,
            }
        except Exception as e:
            search_errors.append(f"{candidate}: {e}")

    raise RuntimeError('；'.join(search_errors) if search_errors else '所有数据源均不可用')


def sync_final_job():
    job_id = st.session_state.get('search_job_id')
    if st.session_state.get('search_status') != 'preliminary' or not job_id:
        return

    from src.core.orchestrator import get_progressive_search_job

    job = get_progressive_search_job(job_id)
    if not job.get('success'):
        st.session_state.search_status = 'error'
        st.session_state.search_error = job.get('error', '最终精选任务不存在')
        st.session_state.search_running = False
        st.session_state.search_job_id = None
        st.rerun()

    if job['status'] == 'running' and not job.get('final_result'):
        return

    if job['status'] == 'error':
        st.session_state.search_status = 'error'
        st.session_state.search_error = job.get('error', '最终精选失败')
        st.session_state.search_running = False
        st.session_state.search_job_id = None
        st.rerun()

    final_result = job.get('final_result') or {}
    final_retrieved_via = final_result.get('retrieved_via') or st.session_state.search_source
    requested_source = final_result.get('requested_source') or st.session_state.search_source
    st.session_state.search_results = normalize_pubmed_progressive_result(final_result, final_retrieved_via, requested_source)
    st.session_state.search_status = 'success'
    st.session_state.search_result_level = 'final'
    st.session_state.search_final_elapsed = get_elapsed_seconds(st.session_state.get('search_started_at'))
    st.session_state.search_error = None
    st.session_state.search_running = False
    st.session_state.search_job_id = None
    st.rerun()


def sync_search_future():
    future_id = st.session_state.get('search_future_id')
    future = get_search_futures().get(future_id) if future_id else None
    if st.session_state.get('search_status') != 'running' or not isinstance(future, Future):
        return

    if not future.done():
        return

    try:
        result = future.result()
        st.session_state.search_results = result['papers']
        st.session_state.search_result_level = result.get('result_level')
        st.session_state.search_job_id = result.get('job_id')
        st.session_state.search_error = None
        if result.get('result_level') == 'preliminary' and result.get('job_id'):
            st.session_state.search_status = 'preliminary'
            st.session_state.search_running = True
            st.session_state.search_preliminary_elapsed = get_elapsed_seconds(st.session_state.get('search_started_at'))
        else:
            st.session_state.search_status = 'success'
            st.session_state.search_running = False
            st.session_state.search_final_elapsed = get_elapsed_seconds(st.session_state.get('search_started_at'))
    except Exception as e:
        st.session_state.search_status = 'error'
        st.session_state.search_error = str(e)
        st.session_state.search_running = False
    finally:
        st.session_state.search_future_id = None
        if future_id:
            get_search_futures().pop(future_id, None)
        st.rerun()


sync_search_future()
sync_final_job()

# ==================== 检索逻辑 ====================

current_year = datetime.now().year

def do_pubmed_search(query, max_results, min_if, start_year, end_year, requested_source='pubmed', retrieved_via='pubmed'):
    orch = get_orchestrator(search_only=True)
    return orch.search_papers(
        query,
        max_results=max_results,
        enable_filter=True,
        fetch_full_text=False,
        min_if=min_if,
        start_year=start_year,
        end_year=end_year,
        progressive=True,
        requested_source=requested_source,
        retrieved_via=retrieved_via,
    )

def do_arxiv_search(query, max_results):
    try:
        from src.data_sources.arxiv_searcher import ArXivSearcher
        searcher = ArXivSearcher(delay=0.3)
        # 候选阶段优先快速失败，尽快回退到高质量漏斗链路。
        searcher.MAX_RETRIES = 1
        searcher.TIMEOUT = 8
        searcher.BASE_DELAY = 0.3
        result = searcher.search(query, max_results=max_results)
        if isinstance(result, dict):
            if not result.get('success', False):
                raise RuntimeError(result.get('error', '未知错误'))
            papers = result.get('papers', [])
        else:
            papers = result
        output = []
        for p in papers:
            output.append({
                'title': p.get('title', 'N/A'),
                'authors': p.get('authors', ''),
                'year': p.get('year', ''),
                'journal': 'arXiv',
                'pmid': '',
                'impact_factor': 0,
                'citations': p.get('citation_count', 0),
                'abstract': (p.get('abstract', '') or '')[:300],
                'source': 'arXiv',
                'doi': p.get('doi', p.get('id', '')),
                'arxiv_id': p.get('id', ''),
            })
        return output
    except ImportError as e:
        raise RuntimeError("ArXiv 搜索模块不可用") from e
    except Exception as e:
        raise RuntimeError(f"ArXiv 搜索失败: {e}") from e

def do_semantic_scholar_search(query, max_results):
    try:
        from src.data_sources.semantic_scholar_searcher import SemanticScholarSearcher
        searcher = SemanticScholarSearcher(enable_retry=False)
        # 候选阶段优先快速失败，尽快回退到高质量漏斗链路。
        searcher.MAX_RETRIES = 1
        searcher.TIMEOUT = 8
        searcher.BASE_DELAY = 0.3
        searcher.RATE_LIMIT_DELAY = 0.2
        result = searcher.search(query, max_results=max_results)
        if isinstance(result, dict):
            if not result.get('success', False):
                raise RuntimeError(result.get('error', '未知错误'))
            papers = result.get('papers', [])
        else:
            papers = result
        output = []
        for p in papers:
            output.append({
                'title': p.get('title', 'N/A'),
                'authors': p.get('authors', ''),
                'year': p.get('year', ''),
                'journal': p.get('journal', p.get('venue', '')),
                'pmid': '',
                'impact_factor': 0,
                'citations': p.get('citationCount', p.get('citations', 0)),
                'abstract': (p.get('abstract', '') or '')[:300],
                'source': 'Semantic Scholar',
                'doi': p.get('doi', ''),
                'ss_id': p.get('paperId', ''),
            })
        return output
    except ImportError as e:
        raise RuntimeError("Semantic Scholar 搜索模块不可用") from e
    except Exception as e:
        raise RuntimeError(f"Semantic Scholar 搜索失败: {e}") from e

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown('<div class="sidebar-config-header">🔍 检索参数</div>', unsafe_allow_html=True)

    query = st.text_area("搜索关键词", value=st.session_state.search_query, height=80, key="search_query_input",
                          placeholder="例如: CRISPR gene editing T-cell immunotherapy")

    source = st.selectbox("数据源", ["pubmed", "arxiv", "semantic_scholar"],
                          format_func=lambda x: {"pubmed": "PubMed", "arxiv": "arXiv", "semantic_scholar": "Semantic Scholar"}.get(x, x),
                          key="search_source_select")

    max_results = st.slider("最大结果数", 5, 100, 20, 5)

    col1, col2 = st.columns(2)
    min_if = col1.number_input("最小 IF", 0.0, 50.0, 3.0, 0.5)
    min_citations = col2.number_input("最小引用", 0, 1000, 0, 10)

    col3, col4 = st.columns(2)
    start_year = col3.number_input("起始年份", 1990, current_year, 2020)
    end_year = col4.number_input("截止年份", 1990, current_year + 2, current_year)

    is_search_running = st.session_state.search_status in ('running', 'preliminary')
    do_search = st.button("🔍 搜索", type="primary", use_container_width=True,
                          disabled=not query.strip() or is_search_running)

    if is_search_running:
        snapshot = st.session_state.get('search_params_snapshot') or {}
        st.caption(f"正在检索: {snapshot.get('query', query)[:40]}")

    st.divider()
    results_count = len(st.session_state.search_results)
    if results_count:
        st.caption(f"共 {results_count} 条结果")

    # 导出按钮
    if results_count and st.button("📥 导出 CSV", use_container_width=True):
        df = pd.DataFrame(st.session_state.search_results)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("下载 CSV", csv, "search_results.csv", "text/csv", use_container_width=True)

# ==================== 主区域 ====================
st.markdown("""
<div class="v75-header">
    <h1>🔍 多源文献检索</h1>
    <div class="subtitle">PubMed · arXiv · Semantic Scholar 三源并行检索</div>
</div>
""", unsafe_allow_html=True)

# 提交搜索任务
if do_search:
    params = {
        'query': query,
        'source': source,
        'max_results': max_results,
        'min_if': min_if,
        'min_citations': min_citations,
        'start_year': start_year,
        'end_year': end_year,
    }
    st.session_state.search_query = query
    st.session_state.search_source = source
    st.session_state.search_status = 'running'
    st.session_state.search_running = True
    st.session_state.search_error = None
    st.session_state.search_result_level = None
    st.session_state.search_job_id = None
    st.session_state.search_preliminary_elapsed = None
    st.session_state.search_final_elapsed = None
    st.session_state.search_started_at = datetime.now().isoformat()
    st.session_state.search_params_snapshot = params
    st.session_state.search_future_id = submit_search_future(params)
    st.rerun()

# 搜索运行中
if st.session_state.search_status in ('running', 'preliminary'):
    snapshot = st.session_state.get('search_params_snapshot') or {}
    started_at = st.session_state.get('search_started_at')
    elapsed = 0
    if started_at:
        elapsed = int((datetime.now() - datetime.fromisoformat(started_at)).total_seconds())

    if st.session_state.search_status == 'preliminary':
        st.info(
            f"已返回初步候选，正在继续精选最终结果。\n\n"
            f"查询: {snapshot.get('query', query)}\n"
            f"已耗时 {elapsed} 秒，页面会自动升级为最终高质量结果。"
        )
    else:
        st.info(
            f"正在从 {snapshot.get('source', source).upper()} 检索: "
            f"{snapshot.get('query', query)}\n\n已耗时 {elapsed} 秒，页面会自动更新结果。"
        )
    if AUTOREFRESH_AVAILABLE:
        st_autorefresh(interval=2000, key="paper_search_poll")
    elif st.button("检查搜索状态"):
        st.rerun()

if st.session_state.search_status == 'error' and st.session_state.search_error:
    st.error(st.session_state.search_error)

# 显示结果
papers = st.session_state.search_results
if papers:
    actual_source = papers[0].get('retrieved_via')
    requested_source = papers[0].get('requested_source')
    result_level = st.session_state.get('search_result_level')
    if result_level == 'preliminary':
        st.warning("当前展示的是初步候选结果，后台正在执行 LLM 精读精选。")
    elif result_level == 'final':
        st.success("当前展示的是最终高质量精选结果。")
    if actual_source and requested_source and actual_source != requested_source:
        st.warning(f"首选数据源 {requested_source} 不可用，候选阶段已自动切换到 {actual_source}")

    fallback_count = sum(1 for p in papers if p.get('llm_fallback'))
    diag_col1, diag_col2, diag_col3, diag_col4 = st.columns(4)
    diag_col1.metric("候选耗时", f"{st.session_state.get('search_preliminary_elapsed') or '-'} s")
    diag_col2.metric("最终耗时", f"{st.session_state.get('search_final_elapsed') or '-'} s")
    diag_col3.metric("回退评分数", str(fallback_count))
    diag_col4.metric("实际数据源", actual_source or requested_source or '-')

    # 过滤控件
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    if_filter = filter_col1.number_input("IF ≥", 0.0, 50.0, 0.0, 0.5, key="filter_if")
    cite_filter = filter_col2.number_input("引用 ≥", 0, 1000, 0, 10, key="filter_cite")
    year_filter = filter_col3.number_input("年份 ≥", 1990, current_year, 1990, key="filter_year")

    filtered = [p for p in papers
                if p['impact_factor'] >= if_filter
                and p['citations'] >= cite_filter
                and (not p['year'] or int(p['year']) >= year_filter)]

    st.caption(f"显示 {len(filtered)}/{len(papers)} 条（过滤后）")

    for i, paper in enumerate(filtered):
        with st.container():
            cols = st.columns([8, 1, 1])
            title = paper['title']
            cols[0].markdown(f"**{i+1}. {title}**")

            source_badge = {"PubMed": "🟢", "arXiv": "🟠", "Semantic Scholar": "🔵"}.get(paper['source'], '⚪')
            cols[1].caption(f"{source_badge} {paper['source']}")

            if paper['impact_factor']:
                cols[2].caption(f"IF: {paper['impact_factor']:.1f}")

            meta_parts = []
            if paper['authors']:
                meta_parts.append(str(paper['authors'])[:100])
            if paper['journal']:
                meta_parts.append(f"*{paper['journal']}*")
            if paper['year']:
                meta_parts.append(str(paper['year']))
            if paper['citations']:
                meta_parts.append(f"引用: {paper['citations']}")
            if paper['pmid']:
                meta_parts.append(f"PMID: {paper['pmid']}")
            if paper.get('doi'):
                meta_parts.append(f"DOI: {paper['doi']}")

            st.caption(" · ".join(meta_parts))

            if paper.get('llm_fallback'):
                fallback_error = paper.get('llm_error_type') or '未知原因'
                st.caption(f"评分: 启发式回退 · 原因: {fallback_error}")
            elif paper.get('llm_score'):
                st.caption(f"评分: LLM {paper['llm_score']:.1f}/10 · 类型: {paper.get('llm_research_type') or 'N/A'}")

            if paper['abstract']:
                with st.expander("摘要"):
                    st.write(paper['abstract'])
                    if paper.get('llm_reason'):
                        st.caption(f"评分依据: {paper['llm_reason']}")

            st.divider()

elif st.session_state.search_query and st.session_state.search_status == 'success':
    st.info(f"未找到匹配结果: 「{st.session_state.search_query}」")
else:
    st.markdown("""
    <div style="text-align:center; color:#64748b; padding:3rem 0;">
        <p style="font-size:1.2rem;">🔍 输入关键词开始检索</p>
        <p>支持 PubMed、arXiv、Semantic Scholar 三个数据源</p>
        <p style="font-size:0.85rem;">提示：可使用 IF、引用数、年份过滤器精炼结果</p>
    </div>
    """, unsafe_allow_html=True)
