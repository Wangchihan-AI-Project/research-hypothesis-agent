# -*- coding: utf-8 -*-
"""
Human-in-the-Loop 全流程测试
关键词: machine learning
"""
import sys
import os
import json

sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent')
sys.path.insert(0, 'C:/Users/PC/research-hypothesis-agent/src')

print("=" * 70)
print("Human-in-the-Loop Full Workflow Test")
print("Keyword: machine learning")
print("=" * 70)

# Import components
from core.orchestrator import Orchestrator
from agents.hypothesis_agent import ChiefScientistAgent
from agents.validation_agent import ValidationAgent

# Initialize
print("\n[Step 1] Initializing system...")
orchestrator = Orchestrator()
hypothesis_agent = ChiefScientistAgent()
validation_agent = ValidationAgent()
print("  [OK] All agents initialized")

# Step 2: Start session
print("\n[Step 2] Starting research session...")
query = "machine learning"
session_result = orchestrator.start_session(query)
if session_result['success']:
    session_id = session_result['session_id']
    print(f"  [OK] Session started (ID: {session_id})")
else:
    print(f"  [FAIL] {session_result.get('error')}")
    sys.exit(1)

# Step 3: Search papers
print("\n[Step 3] Paper Agent searching PubMed...")
print("  (This may take a minute...)")

search_result = orchestrator.search_papers(
    query,
    max_results=15,
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
print("\n[Step 4] Chief Scientist generating Nature-level hypotheses...")
print("  (This will take a few minutes with Claude API...)")

hyp_result = hypothesis_agent.execute({
    'literature_report': f"Search keyword: {query}\nFound {len(papers)} related papers",
    'papers': papers,
    'research_topic': query,
    'output_dir': 'reports'
})

if not hyp_result['success']:
    print(f"  [FAIL] {hyp_result.get('error')}")
    sys.exit(1)

hypotheses = hyp_result['hypotheses']
hypothesis_ids = hyp_result.get('hypothesis_ids', [])
proposal_path = hyp_result.get('proposal_path')

print(f"  [OK] Generated {len(hypotheses)} hypotheses")
if proposal_path:
    print(f"  [OK] Proposal saved: {proposal_path}")

# Step 5: Display hypotheses for user selection
print("\n" + "=" * 70)
print("[Step 5] HYPOTHESIS SUMMARY - Human-in-the-Loop Decision Point")
print("=" * 70)

for i, hyp in enumerate(hypotheses, 1):
    title = hyp.get('title', 'N/A')
    paradigm = hyp.get('paradigm_framework', 'N/A')
    description = hyp.get('description', 'N/A')
    if len(description) > 120:
        description = description[:120] + "..."

    print(f"\n[ Hypothesis {i} ]")
    print(f"  Title: {title}")
    print(f"  Framework: {paradigm}")
    print(f"  Summary: {description}")

print("\n" + "-" * 70)
print("Boss, preliminary hypotheses generated.")
print("Select the one you think has the most potential for final review.")
print("-" * 70)

# Simulate user selection (auto-select hypothesis 1 for testing)
user_choice = 1
print(f"\n[Simulated User Input: {user_choice}]")

selected_hyp = hypotheses[user_choice - 1]
selected_hyp_id = hypothesis_ids[user_choice - 1] if user_choice - 1 < len(hypothesis_ids) else None

print(f"\n  You selected Hypothesis {user_choice}:")
print(f"  {selected_hyp.get('title', 'N/A')[:60]}...")

# Step 6: Validation by Nature Editor
print("\n" + "=" * 70)
print("[Step 6] Nature Senior Editor - Deep Evaluation")
print("=" * 70)
print("  (This will take a few minutes...)")

validation_result = validation_agent.execute({
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

validation = validation_result['validation']
scores = validation.get('scores', {})

# Display final report
print("\n" + "=" * 70)
print("FINAL REVIEW REPORT")
print("=" * 70)

print("\n[ Scores ]")
print(f"  Transformative Impact:      {scores.get('transformative_impact', 'N/A')}/10")
print(f"  Methodological Originality: {scores.get('methodological_originality', 'N/A')}/10")
print(f"  PoC Feasibility:            {scores.get('poc_feasibility', 'N/A')}/10")

avg = sum(scores.values()) / len(scores) if scores else 0
print(f"  Average Score:              {avg:.1f}/10")

final_decision = validation.get('final_decision', 'unknown')
decision_display = {
    'accepted': '[ACCEPT]',
    'revise': '[REVISE]',
    'rejected': '[REJECT]'
}.get(final_decision.lower(), f'[{final_decision.upper()}]')

print(f"\n[ Final Decision: {decision_display} ]")

verdict = validation.get('verdict', {})
print(f"\nRationale: {verdict.get('rationale', 'N/A')}")

if final_decision.lower() == 'revise':
    print(f"Conditions: {verdict.get('conditions', 'N/A')}")

# Impact analysis
impact = validation.get('impact_analysis', {})
print(f"\n[ Impact Analysis ]")
print(f"  Interdisciplinary impact: {impact.get('breadth', 'N/A')}")
print(f"  Disruptive potential: {impact.get('depth', 'N/A')}")

# Originality analysis
originality = validation.get('originality_analysis', {})
print(f"\n[ Originality Analysis ]")
print(f"  Core innovation: {originality.get('core_innovation', 'N/A')}")

# Feasibility analysis
feasibility = validation.get('feasibility_analysis', {})
print(f"\n[ Feasibility Analysis ]")
print(f"  Data scale: {feasibility.get('data_scale', 'N/A')}")

recommended_dbs = feasibility.get('recommended_databases', [])
if recommended_dbs:
    print(f"  Recommended databases: {', '.join(recommended_dbs[:3])}")

# Report path
report_path = validation.get('report_path')
if report_path:
    print(f"\n[ Detailed report saved: {report_path} ]")

# Complete session
print("\n" + "=" * 70)
print("WORKFLOW COMPLETE")
print("=" * 70)

orchestrator.complete_session()

print(f"""
Summary:
  - Papers found: {len(papers)}
  - Hypotheses generated: {len(hypotheses)}
  - Selected hypothesis: {user_choice}
  - Final decision: {final_decision.upper()}
  - Average score: {avg:.1f}/10
""")