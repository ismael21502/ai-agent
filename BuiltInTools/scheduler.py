import time
import json
from datetime import datetime, timezone
from enum import Enum
from smolagents import tool 
import asyncio
import threading

ACTIONS = {
    "print": print,
}

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Scheduler:
    def __init__(self):
        self.tasks = []
        self.ACTIONS = {}
    def addTask(self, type: str, payload: dict, scheduled_at: str = None):
        self.loadTasks()
        task = {
            "id": str(len(self.tasks) + 1),
            "type": type,
            "scheduled_at": scheduled_at or datetime.now(timezone.utc).isoformat(),
            "status": TaskStatus.PENDING.value,
            "payload": payload,
            "result": None,
            }
        print("adding task", task)
        self.tasks.append(task)
        self.saveTasks()
        return task
    def cancelTask(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = TaskStatus.CANCELLED.value
                self.saveTasks()
                return True
        return False
    def getPendingTasks(self):
        return [task for task in self.tasks if task["status"] == TaskStatus.PENDING.value]
    def getNextTask(self):
        pendingTasks = self.getPendingTasks()
        if not pendingTasks:
            return None
        return min(pendingTasks, key=lambda x: x["scheduled_at"])
    def run(self):
        try:
            while True:
                nextTask = self.getNextTask()
                print("Scheduler:", nextTask)
                if nextTask is None:
                    time.sleep(5)
                    continue
                scheduledAt = datetime.fromisoformat(
                    nextTask["scheduled_at"]
                )
                now = datetime.now(timezone.utc)
                if scheduledAt <= now:
                    self.execute(nextTask)
                time.sleep(5)
        except Exception as e:
            print("SCHEDULER ERROR:", repr(e))
    def execute(self, task):
        action = self.ACTIONS[task["payload"]["action"]]
        result = action(*task["payload"]["args"])
        task["status"] = TaskStatus.COMPLETED.value
        task["result"] = result
        self.saveTasks()
    def loadTasks(self):
        with open("schedule.json", "r") as f:
            self.tasks = json.load(f)
    def saveTasks(self):
        with open("schedule.json", "w") as f:
            json.dump(self.tasks, f, indent=4)
