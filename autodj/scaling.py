"""
Dynamic Concurrency & Scaling Module (v8.1.0).
Intelligently adjusts parallel worker counts based on system load.
"""
import os
import psutil
import config

class DynamicConcurrencyManager:
    def __init__(self):
        self.system_cores = os.cpu_count() or 1
        self.min_cores = 1
        self.max_cores = self.system_cores

    def get_optimal_worker_count(self):
        """
        Calculates optimal worker count based on CPU and RAM headroom.
        Rules:
        1. If CPU > 85%, scale down to 50% capacity.
        2. If RAM > 90%, scale down to 25% capacity.
        3. Otherwise, use full system capacity.
        """
        cpu_usage = psutil.cpu_percent(interval=None)
        ram_usage = psutil.virtual_memory().percent

        scaling_factor = 1.0

        if cpu_usage > 85.0:
            scaling_factor = 0.5
        if ram_usage > 90.0:
            scaling_factor = 0.25

        optimal = int(self.max_cores * scaling_factor)
        return max(self.min_cores, optimal)

    def get_status(self):
        return {
            "current_limit": self.get_optimal_worker_count(),
            "system_cores": self.system_cores,
            "scaling_factor": self.get_optimal_worker_count() / self.system_cores
        }

concurrency = DynamicConcurrencyManager()
