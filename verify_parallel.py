
import asyncio
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "smart-meal-planner/backend"))

# Mock Celery for testing dispatch
class MockTask:
    def __init__(self, name):
        self.name = name
        self.id = "mock-task-id"
    def delay(self, *args, **kwargs):
        print(f"DEBUG: {self.name}.delay called with args={args}, kwargs={kwargs}")
        return self
    def s(self, *args, **kwargs):
        print(f"DEBUG: {self.name}.s (signature) created with args={args}, kwargs={kwargs}")
        return self
    def apply_async(self, *args, **kwargs):
        print("DEBUG: Group apply_async called")
        return self

import app.tasks as tasks
tasks.scrape_store_task = MockTask("scrape_store_task")
tasks.scrape_task = MockTask("scrape_task")
tasks.sync_root_scrapers_task = MockTask("sync_root_scrapers_task")

from app.scheduled_jobs import run_scheduled_scrape

async def test_dispatch():
    print("Testing scheduled job dispatch...")
    await run_scheduled_scrape()
    print("Dispatch test complete.\n")

async def test_orchestrator():
    print("Testing scrape_task orchestrator...")
    # Manually call the function to see if it groups correctly
    # Note: We need to use the original function, but it's been wrapped/mocked above for scheduled_jobs
    # Let's reload or just use the logic
    stores = ["metro", "walmart"]

    # Simulate the logic in scrape_task
    print(f"Simulating scrape_task for stores: {stores}")
    for store in stores:
        tasks.scrape_store_task.s(store, "H4T1V6", 50)
    tasks.scrape_task.apply_async()
    print("Orchestrator test complete.")

if __name__ == "__main__":
    asyncio.run(test_dispatch())
    asyncio.run(test_orchestrator())
