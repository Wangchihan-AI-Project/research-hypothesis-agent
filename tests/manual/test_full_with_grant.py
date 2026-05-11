# -*- coding: utf-8 -*-
"""
Full Workflow Test with Grant Writer
Keyword: machine learning
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', encoding='utf-8')

from src.core.orchestrator import Orchestrator
from src.agents.grant_writer_agent import GrantWriterAgent
from memory_manager import MemoryManager

print("=" * 70)
print("Full Workflow Test with Grant Writer")
print("Keyword: machine learning")
print("=" * 70)

# Initialize
orchestrator = Orchestrator()
memory_manager = MemoryManager()
grant_writer = GrantWriterAgent()

print("\n[Step 1] Initialize components")
print("  [OK] All agents initialized")

# Step 2: Start session
print("\n[Step 2] Start research session")
query = "machine learning"
session_result = orchestrator.start_session(query)
if session_result['success']:
    session_id = session_result['session_id']
    print(f"  [OK] Session #{session_id} started")
else:
    print(f"  [FAIL] {session_result.get('error')}")
    sys.exit(1)

# Step 3: Search papers
print("\n[Step 3] Paper agent searching...")
search_result = orchestrator.search_papers(
    query,
    max_results=10,
    enable_filter=False,
    fetch_full_text=True,
    max_full_text=3
)

if not search_result['success']:
    print(f"  [FAIL] {search_result.get('error')}")
    sys.exit(1)

papers = search_result['papers']
print(f"  [OK] Found {len(papers)} papers")

# Show paper titles
print("\n  Paper titles (first 5):")
for i, paper in enumerate(papers[:5], 1):
    title = paper.get('title', 'N/A')
    if len(title) > 60:
        title = title[:60] + "..."
    print(f"    {i}. {title}")

# Step 4: Generate hypotheses
print("\n[Step 4] Chief Scientist generating hypotheses...")
print("  (This may take several minutes...)")

hyp_result = orchestrator.hypothesis_agent.execute({
    'literature_report': f"Query: {query}\nFound {len(papers)} papers",
    'papers': papers,
    'research_topic': query,
    'output_dir': 'reports'
})

if not hyp_result['success']:
    print(f"  [FAIL] {hyp_result.get('error')}")
    sys.exit(1)

hypotheses = hyp_result['hypotheses']
hypothesis_ids = hyp_result.get('hypothesis_ids', [])

print(f"  [OK] Generated {len(hypotheses)} hypotheses")

# Show hypotheses summary
print("\n  Hypotheses:")
for i, hyp in enumerate(hypotheses, 1):
    title = hyp.get('title', 'N/A')
    paradigm = hyp.get('paradigm_framework', 'N/A')
    if len(title) > 70:
        title = title[:70] + "..."
    print(f"    {i}. {title}")
    print(f"       Framework: {paradigm}")

# Step 5: Auto-select hypothesis 1
print("\n[Step 5] Auto-select Hypothesis 1")
selected_idx = 0
selected_hyp = hypotheses[selected_idx]
selected_hyp_id = hypothesis_ids[selected_idx] if selected_idx < len(hypothesis_ids) else None

title = selected_hyp.get('title', 'N/A')
if len(title) > 60:
    title = title[:60] + "..."
print(f"  [OK] Selected: {title}")

# Step 6: Validate hypothesis
print("\n[Step 6] Nature Editor validating...")
print("  (This may take several minutes...)")

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

if not validation_result['success']:
    print(f"  [FAIL] {validation_result.get('error')}")
    sys.exit(1)

validation = validation_result.get('validation', {})
scores = validation.get('scores', {})
final_decision = validation.get('final_decision', 'unknown')

avg = sum(scores.values()) / len(scores) if scores else 0

print(f"  [OK] Validation complete")
print(f"\n  [Scores]")
print(f"    Transformative Impact: {scores.get('transformative_impact', 'N/A')}/10")
print(f"    Methodological Originality: {scores.get('methodological_originality', 'N/A')}/10")
print(f"    PoC Feasibility: {scores.get('poc_feasibility', 'N/A')}/10")
print(f"    Average: {avg:.1f}/10")
print(f"\n  [Decision]: {final_decision.upper()}")

report_path = validation.get('report_path')
if report_path:
    print(f"  Report saved: {report_path}")

# Step 7: Grant Writer - Generate grant proposal
print("\n[Step 7] Grant Writer generating proposal...")
print("  (This may take several minutes...)")

grant_result = grant_writer.execute({
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
    'validation_result': validation_result,
    'papers': papers,
    'output_dir': 'reports'
})

if grant_result['success']:
    proposal = grant_result['grant_proposal']
    proposal_path = grant_result.get('proposal_path', '')

    print(f"\n  [OK] Grant proposal generated")
    print(f"    Length: {len(proposal)} characters")
    print(f"    Saved: {proposal_path}")

    # Show preview
    print("\n  [Preview - First 800 characters]")
    print("-" * 70)
    print(proposal[:800])
    print("...")
    print("-" * 70)
else:
    print(f"\n  [FAIL] {grant_result.get('error')}")

# Complete session
print("\n" + "=" * 70)
print("WORKFLOW COMPLETE")
print("=" * 70)

orchestrator.complete_session()

print(f"""
Summary:
  - Session ID: {session_id}
  - Papers found: {len(papers)}
  - Hypotheses generated: {len(hypotheses)}
  - Selected hypothesis: {selected_idx + 1}
  - Validation decision: {final_decision.upper()}
  - Average score: {avg:.1f}/10
  - Grant proposal: {'Generated' if grant_result['success'] else 'Failed'}
""")