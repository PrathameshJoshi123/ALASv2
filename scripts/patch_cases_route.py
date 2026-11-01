with open('backend/routes/cases.py', 'r', encoding='utf-8') as f:
    code = f.read()

target = """from backend.agents.trial_debate_langgraph import (
    build_trial_debate_graph,
    autonomous_kanoon_research,
    TrialDebateState,
)"""

replacement = """from backend.agents.trial_debate_langgraph import (
    build_trial_debate_graph,
    autonomous_kanoon_research,
    TrialDebateState,
    _call_resilient_llm_text,
)"""

if target in code:
    code = code.replace(target, replacement, 1)

old_turn = """    counter_turn = {
        "id": f"turn_pivot_{int(datetime.now().timestamp())}",
        "turn_number": len(state.get("debate_turns", [])) + 2,
        "round_number": state.get("current_round", 2),
        "speaker": opposing_side,
        "title": f"Autonomous Counter-Rebuttal ({opposing_side.capitalize()})",
        "argument_text": (
            f"Responding directly to lead counsel's submission: The proposition cannot stand. "
            f"Under {citations[0]['title'] if citations else 'settled Supreme Court precedent'}, "
            "the judicial inquiry at this preliminary threshold is strictly bounded by the four corners of the record. "
            "Counsel's argument introduces factual disputes that can only be resolved through cross-examination."
        ),
        "citations": citations,
        "doctrine_tags": ["Autonomous Counter-Pivot", "Indian Kanoon Real-Time Grounding"],
        "timestamp": datetime.now().strftime("%I:%M %p"),
    }"""

new_turn = """    # Dynamic Opponent LLM Counter-Pivot
    matter_title = state.get("matter_title", "Litigation Matter")
    cit_meta = citations[0] if citations else {}
    pivot_prompt = (
        f"You are the Senior Advocate representing the {opposing_side.capitalize()} before the High Court of Delhi in '{matter_title}'.\\n"
        f"Human Lead Counsel representing the {side.capitalize()} has just made the following submission:\\n"
        f"\\\"{custom_arg}\\\"\\n\\n"
        f"Your retrieved legal authority from Indian Kanoon:\\n"
        f"Title: {cit_meta.get('title', 'Supreme Court Precedent')}\\n"
        f"Ratio Decidendi: {cit_meta.get('ratio_decidendi', 'Preliminary inquiries are strictly governed by statutory thresholds.')}\\n"
        f"Statutory Sections: {cit_meta.get('statutory_sections', ['Section 482 CrPC', 'Section 65B Evidence Act'])}\\n\\n"
        f"Deliver a direct, highly intelligent, aggressive oral counter-rebuttal (100-150 words). "
        f"Directly dismantle lead counsel's specific proposition, expose its procedural or factual flaw under Indian law, "
        f"anchor in {cit_meta.get('title', 'settled Supreme Court precedent')}, and demand that the court rule in your favor."
    )
    fallback_counter = (
        f"Responding directly to lead counsel's submission: The proposition cannot stand. "
        f"Under {cit_meta.get('title', 'settled Supreme Court authority')}, "
        "the judicial inquiry at this preliminary threshold is strictly bounded by the four corners of the record. "
        "Counsel's argument introduces factual disputes that can only be resolved through cross-examination."
    )
    counter_arg_text = _call_resilient_llm_text(pivot_prompt, fallback=fallback_counter)

    counter_turn = {
        "id": f"turn_pivot_{int(datetime.now().timestamp())}",
        "turn_number": len(state.get("debate_turns", [])) + 2,
        "round_number": state.get("current_round", 2),
        "speaker": opposing_side,
        "title": f"Autonomous Counter-Rebuttal ({opposing_side.capitalize()})",
        "argument_text": counter_arg_text,
        "citations": citations,
        "doctrine_tags": ["Autonomous Counter-Pivot", "Indian Kanoon Real-Time Grounding"],
        "timestamp": datetime.now().strftime("%I:%M %p"),
    }"""

if old_turn in code:
    code = code.replace(old_turn, new_turn, 1)

with open('backend/routes/cases.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("backend/routes/cases.py updated successfully!")
