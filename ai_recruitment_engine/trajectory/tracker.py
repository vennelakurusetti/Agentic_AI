"""
Trajectory Recorder
Records every step with Thought, Tool Used, Arguments, Observation, State Changes, Decision.
"""

import json
from typing import Any


class TrajectoryStep:
    """A single step record in the trajectory."""
    
    def __init__(self):
        self.thought: str = ""
        self.tool_used: str = ""
        self.arguments: dict = {}
        self.observation: str = ""
        self.state_changes: dict = {}
        self.decision: str = ""
    
    def to_dict(self) -> dict:
        return {
            "thought": self.thought,
            "tool_used": self.tool_used,
            "arguments": self.arguments,
            "observation": self.observation,
            "state_changes": self.state_changes,
            "decision": self.decision,
        }
    
    def __str__(self) -> str:
        return f"{self.tool_used}: {self.observation[:60]}" if self.observation else self.tool_used


class TrajectoryRecorder:
    """Records chronological trajectory of the recruitment pipeline."""
    
    def __init__(self):
        self.steps: list[TrajectoryStep] = []
        self._prev_state: dict = {}
    
    def start(self, initial_state: dict):
        """Record the starting state."""
        self._prev_state = self._capture_state(initial_state)
    
    def _capture_state(self, state: dict) -> dict:
        """Capture key state values for change tracking."""
        captured = {}
        for key in ["jd_parsed", "resume_parsed", "score_card", "decision", 
                     "interview_slot", "candidate_name", "rubric", "plan",
                     "available_slots", "error"]:
            val = state.get(key)
            if val is not None:
                if hasattr(val, "model_dump"):
                    captured[key] = val.model_dump()
                elif isinstance(val, str) and len(val) > 200:
                    captured[key] = val[:200] + "..."
                elif isinstance(val, list) and len(val) > 10:
                    captured[key] = f"list[{len(val)} items]"
                else:
                    captured[key] = val
        return captured
    
    def record(self, thought: str, tool_used: str, arguments: dict, 
               observation: str, new_state: dict, decision: str = ""):
        """Record a step in the trajectory."""
        step = TrajectoryStep()
        step.thought = thought
        step.tool_used = tool_used
        step.arguments = arguments
        step.observation = observation
        step.decision = decision
        
        # Compute state changes
        curr_state = self._capture_state(new_state)
        changes = {}
        for key, new_val in curr_state.items():
            old_val = self._prev_state.get(key)
            if new_val != old_val:
                changes[key] = {"from": str(old_val)[:80], "to": str(new_val)[:80]}
        step.state_changes = changes
        self._prev_state = curr_state
        
        self.steps.append(step)
        return step
    
    def to_json(self) -> str:
        """Export trajectory as chronological JSON."""
        return json.dumps([s.to_dict() for s in self.steps], indent=2, default=str)
    
    def print_trajectory(self):
        """Print a human-readable trajectory summary."""
        print(f"\n--- Trajectory ({len(self.steps)} steps) ---")
        for i, step in enumerate(self.steps, 1):
            print(f"  Step {i}:")
            print(f"    Thought: {step.thought[:80]}")
            print(f"    Tool: {step.tool_used}")
            if step.arguments:
                args_str = json.dumps(step.arguments)[:80]
                print(f"    Args: {args_str}")
            print(f"    Observation: {step.observation[:80]}")
            if step.state_changes:
                changes = list(step.state_changes.keys())
                print(f"    State Changes: {', '.join(changes)}")
            if step.decision:
                print(f"    Decision: {step.decision}")