# -*- coding: utf-8 -*-
"""
Test Web UI Backend Logic
Simulate Streamlit workflow
"""
import sys
import os
from pathlib import Path

# Add project paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', encoding='utf-8')

from src.core.orchestrator import Orchestrator
from memory_manager import MemoryManager

print("=" * 70)
print("Web UI Backend Logic Test")
print("Keyword: machine learning")
print("=" * 70)

# Test 1: Initialize components
print("\n[Test 1] Initialize components...")

try:
    orchestrator = Orchestrator()
    print("  [OK] Orchestrator initialized")
except Exception as e:
    print(f"  [FAIL] Orchestrator: {e}")
    sys.exit(1)

try:
    memory_manager = MemoryManager()
    print("  [OK] MemoryManager initialized")
except Exception as e:
    print(f"  [FAIL] MemoryManager: {e}")

# Test 2: Memory stats
print("\n[Test 2] Memory library stats...")

try:
    stats = memory_manager.get_memory_stats()
    print(f"  Papers: {stats.get('unique_dois', 0)}")
    print(f"  Chunks: {stats.get('total_chunks', 0)}")
    print(f"  DB: {stats.get('collection_name', 'N/A')}")
    print("  [OK] Memory stats retrieved")
except Exception as e:
    print(f"  [FAIL] Memory stats: {e}")

# Test 3: Start session
print("\n[Test 3] Start research session...")

query = "machine learning"
session_result = orchestrator.start_session(query)

if session_result['success']:
    session_id = session_result['session_id']
    print(f"  [OK] Session #{session_id} started")
else:
    print(f"  [FAIL] Session: {session_result.get('error')}")
    sys.exit(1)

# Test 4: Search papers
print("\n[Test 4] Paper agent searching...")

search_result = orchestrator.search_papers(
    query,
    max_results=10,
    enable_filter=False,
    fetch_full_text=True,
    max_full_text=3
)

if search_result['success']:
    papers = search_result['papers']
    full_text_stats = search_result.get('full_text_stats', {})
    print(f"  [OK] Found {len(papers)} papers")
    print(f"       PDF: {full_text_stats.get('pdf', 0)} papers")

    print("\n  Top 5 papers:")
    for i, paper in enumerate(papers[:5], 1):
        title = paper.get('title', 'N/A')
        if len(title) > 60:
            title = title[:60] + "..."
        print(f"    {i}. {title}")
else:
    print(f"  [FAIL] Search: {search_result.get('error')}")
    sys.exit(1)

# Test 5: Generate hypotheses
print("\n[Test 5] Chief Scientist generating hypotheses...")
print("  (This may take several minutes...)")

hyp_result = orchestrator.hypothesis_agent.execute({
    'literature_report': f"Query: {query}\nFound {len(papers)} papers",
    'papers': papers,
    'research_topic': query,
    'output_dir': 'reports'
})

if hyp_result['success']:
    hypotheses = hyp_result['hypotheses']
    hypothesis_ids = hyp_result.get('hypothesis_ids', [])
    print(f"  [OK] Generated {len(hypotheses)} hypotheses")

    print("\n  Hypothesis summary:")
    for i, hyp in enumerate(hypotheses, 1):
        title = hyp.get('title', 'N/A')
        paradigm = hyp.get('paradigm_framework', 'N/A')
        print(f"\n  [Hypothesis {i}]")
        print(f"    Title: {title[:70]}...")
        print(f"    Framework: {paradigm}")
else:
    print(f"  [FAIL] Hypothesis generation: {hyp_result.get('error')}")
    sys.exit(1)

# Test 6: Select and validate
print("\n[Test 6] HITL: Select hypothesis 1 and validate...")

# Auto-select hypothesis 1
selected_idx = 0
selected_hyp = hypotheses[selected_idx]
selected_hyp_id = hypothesis_ids[selected_idx] if selected_idx < len(hypothesis_ids) else None

print(f"  Selected: Hypothesis 1")
print(f"  Title: {selected_hyp.get('title', 'N/A')[:60]}...")

print("\n  Nature Editor evaluating...")
validation_result = orchestrator.validation_agent.execute({
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
    'source_papers': papers[:5],
    'enable_literature_check': True,
    'output_dir': 'reports'
})

if validation_result['success']:
    validation = validation_result.get('validation', {})
    scores = validation.get('scores', {})
    final_decision = validation.get('final_decision', 'unknown')

    avg = sum(scores.values()) / len(scores) if scores else 0

    print(f"  [OK] Evaluation complete")
    print(f"\n  [Scores]")
    print(f"    Transformative Impact: {scores.get('transformative_impact', 'N/A')}/10")
    print(f"    Methodological Originality: {scores.get('methodological_originality', 'N/A')}/10")
    print(f"    PoC Feasibility: {scores.get('poc_feasibility', 'N/A')}/10")
    print(f"    Average: {avg:.1f}/10")
    print(f"\n  [Decision]: {final_decision.upper()}")

    report_path = validation.get('report_path')
    if report_path:
        print(f"  Report: {report_path}")
else:
    print(f"  [FAIL] Validation: {validation_result.get('error')}")

# Test 7: Memory search
print("\n[Test 7] Test memory search...")

search_result = memory_manager.search_past_literature("machine learning", n_results=3)

if search_result.get('success'):
    results = search_result.get('results', [])
    print(f"  [OK] Found {len(results)} related records")
    for i, r in enumerate(results[:2], 1):
        print(f"    {i}. {r.get('title', 'N/A')[:50]}...")
else:
    print(f"  [INFO] {search_result.get('message', 'No results')}")

# Complete
print("\n" + "=" * 70)
print("All tests completed!")
print("=" * 70)

print(f"""
Summary:
  - Session ID: {session_id}
  - Papers found: {len(papers)}
  - Hypotheses generated: {len(hypotheses)}
  - Validation result: {final_decision.upper()}
  - Average score: {avg:.1f}/10

Web UI is running at http://localhost:8503
Open in browser for interactive testing
""")