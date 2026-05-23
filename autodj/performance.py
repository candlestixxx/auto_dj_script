"""
Granular Performance Analytics for Auto DJ (v8.1.0).
Tracks task-level execution timings and manages performance history.
"""
import time
import json
import os
from datetime import datetime
from typing import Dict, List

class PerformanceTracker:
    def __init__(self, history_file: str = "logs/performance_history.json"):
        self.history_file = history_file
        self.current_session = {
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "tasks": [],
            "totals": {
                "analysis_ms": 0.0,
                "warping_ms": 0.0,
                "mixing_ms": 0.0,
                "total_ms": 0.0
            }
        }
        os.makedirs("logs", exist_ok=True)

    def start_task(self, task_name: str, task_type: str, metadata: Dict = None):
        return {
            "name": task_name,
            "type": task_type,
            "start": time.time(),
            "metadata": metadata or {}
        }

    def end_task(self, task_obj: Dict):
        duration = (time.time() - task_obj["start"]) * 1000
        task_entry = {
            "name": task_obj["name"],
            "type": task_obj["type"],
            "duration_ms": float(round(duration, 2)),
            "metadata": task_obj["metadata"],
            "timestamp": datetime.now().isoformat()
        }
        self.current_session["tasks"].append(task_entry)

        # Update totals
        key = f"{task_obj['type']}_ms"
        if key in self.current_session["totals"]:
            self.current_session["totals"][key] = float(self.current_session["totals"][key] + duration)

        return duration

    def save_session(self):
        self.current_session["totals"]["total_ms"] = float(sum(
            t["duration_ms"] for t in self.current_session["tasks"]
        ))

        history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    history = json.load(f)
            except Exception:
                pass

        history.append(self.current_session)
        # Keep last 10 sessions
        history = history[-10:]

        with open(self.history_file, "w") as f:
            json.dump(history, f, indent=2)

# Global Performance Tracker
perf = PerformanceTracker()
