from langgraph.graph import StateGraph, END
from graph.state import RecruitmentState
from graph.nodes import (
    node_parse_jd,
    node_generate_rubric,
    node_create_plan,
    node_parse_resume,
    node_score_candidate,
    node_make_decision,
    node_check_availability,
    node_schedule_interview,
    node_guardrail_check,
    should_schedule,
)
from typing import Callable


def build_recruitment_graph(llm_call: Callable) -> StateGraph:
    """Build the recruitment agent state graph."""
    
    # Define the graph builder
    builder = StateGraph(RecruitmentState)
    
    # Add nodes
    builder.add_node("parse_jd", lambda state: node_parse_jd(state, llm_call))
    builder.add_node("generate_rubric", lambda state: node_generate_rubric(state, llm_call))
    builder.add_node("create_plan", lambda state: node_create_plan(state, llm_call))
    builder.add_node("parse_resume", lambda state: node_parse_resume(state, llm_call))
    builder.add_node("score_candidate", lambda state: node_score_candidate(state, llm_call))
    builder.add_node("make_decision", lambda state: node_make_decision(state, llm_call))
    builder.add_node("check_availability", lambda state: node_check_availability(state, llm_call))
    builder.add_node("schedule_interview", lambda state: node_schedule_interview(state, llm_call))
    builder.add_node("guardrail_check", lambda state: node_guardrail_check(state, llm_call))
    
    # Add edges
    builder.set_entry_point("parse_jd")
    
    builder.add_edge("parse_jd", "generate_rubric")
    builder.add_edge("generate_rubric", "create_plan")
    builder.add_edge("create_plan", "parse_resume")
    builder.add_edge("parse_resume", "score_candidate")
    builder.add_edge("score_candidate", "make_decision")
    builder.add_edge("make_decision", "guardrail_check")
    
    # Conditional edge: schedule only if selected
    builder.add_conditional_edges(
        "guardrail_check",
        should_schedule,
        {
            "schedule": "check_availability",
            "skip": END,
        }
    )
    
    builder.add_edge("check_availability", "schedule_interview")
    builder.add_edge("schedule_interview", END)
    
    # Compile graph
    graph = builder.compile()
    
    return graph