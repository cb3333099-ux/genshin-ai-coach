"""
Farming scheduler for daily/weekly tasks
"""
from datetime import datetime, timedelta

class FarmingScheduler:
    """Manages farming schedules"""
    
    DAILY_TASKS = [
        "Commission rewards (40 Primogems)",
        "Daily ore farming",
        "Talent materials",
    ]
    
    @staticmethod
    def get_daily_reset_time():
        now = datetime.now()
        reset_time = now.replace(hour=4, minute=0, second=0)
        
        if now >= reset_time:
            reset_time += timedelta(days=1)
        
        hours_until = (reset_time - now).seconds // 3600
        
        return {
            "hours_until_reset": hours_until,
            "daily_tasks": FarmingScheduler.DAILY_TASKS
        }
    
    @staticmethod
    def get_daily_farming(day=None):
        return {
            "talent": "Check calendar",
            "artifact": "Check calendar"
        }