"""Task Scheduler integration for auto-clean scheduling."""
import subprocess
import logging
from pathlib import Path
import os
import sys

log = logging.getLogger(__name__)


class TaskSchedulerManager:
    """Manage Windows Task Scheduler tasks for auto-clean."""

    TASK_NAME = r"\PCCleaner\AutoClean"
    
    @staticmethod
    def _get_executable_path():
        """Get path to the current executable."""
        if getattr(sys, 'frozen', False):
            return sys.executable
        else:
            # Development: assume PyInstaller will create PCCleaner.exe
            return str(Path(__file__).parent / 'dist' / 'PCCleaner' / 'PCCleaner.exe')

    @staticmethod
    def create_task(hour=2, minute=0, frequency='daily'):
        """
        Create a scheduled task in Windows Task Scheduler.
        
        Args:
            hour: Hour to run (0-23)
            minute: Minute to run (0-59)
            frequency: 'daily', 'weekly', or 'monthly'
        """
        try:
            exe_path = TaskSchedulerManager._get_executable_path()
            
            if frequency == 'daily':
                schedule = f'DAILY /ST {hour:02d}:{minute:02d}'
            elif frequency == 'weekly':
                schedule = f'WEEKLY /D MON /ST {hour:02d}:{minute:02d}'
            elif frequency == 'monthly':
                schedule = f'MONTHLY /D 1 /ST {hour:02d}:{minute:02d}'
            else:
                log.error(f"Unknown frequency: {frequency}")
                return False

            cmd = [
                'schtasks', '/create',
                '/tn', TaskSchedulerManager.TASK_NAME,
                '/tr', f'"{exe_path}" --auto-clean',
                '/sc', schedule,
                '/f',  # Force create (overwrite if exists)
                '/rl', 'HIGHEST',  # Run with highest privileges
                '/ru', 'SYSTEM',  # Run as system
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                log.info(f"Task scheduled: {TaskSchedulerManager.TASK_NAME}")
                return True
            else:
                log.error(f"Failed to create task: {result.stderr}")
                return False
        except Exception as e:
            log.error(f"Error creating task: {e}")
            return False

    @staticmethod
    def delete_task():
        """Delete the auto-clean task from Task Scheduler."""
        try:
            cmd = [
                'schtasks', '/delete',
                '/tn', TaskSchedulerManager.TASK_NAME,
                '/f',  # Force delete without confirmation
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                log.info(f"Task deleted: {TaskSchedulerManager.TASK_NAME}")
                return True
            else:
                log.error(f"Failed to delete task: {result.stderr}")
                return False
        except Exception as e:
            log.error(f"Error deleting task: {e}")
            return False

    @staticmethod
    def task_exists():
        """Check if auto-clean task exists."""
        try:
            cmd = ['schtasks', '/query', '/tn', TaskSchedulerManager.TASK_NAME]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            log.debug(f"Error checking task existence: {e}")
            return False

    @staticmethod
    def update_task(hour=2, minute=0, frequency='daily'):
        """Update existing task with new schedule."""
        if TaskSchedulerManager.task_exists():
            TaskSchedulerManager.delete_task()
        return TaskSchedulerManager.create_task(hour, minute, frequency)

    @staticmethod
    def run_task_now():
        """Manually trigger the scheduled task immediately."""
        try:
            cmd = ['schtasks', '/run', '/tn', TaskSchedulerManager.TASK_NAME]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                log.info("Auto-clean task triggered")
                return True
            else:
                log.error(f"Failed to run task: {result.stderr}")
                return False
        except Exception as e:
            log.error(f"Error running task: {e}")
            return False

    @staticmethod
    def get_task_status():
        """Get the status of the auto-clean task."""
        try:
            cmd = ['schtasks', '/query', '/tn', TaskSchedulerManager.TASK_NAME, '/v', '/fo', 'csv']
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return {
                        'exists': True,
                        'status': 'Configured',
                        'raw_output': result.stdout
                    }
            return {'exists': False, 'status': 'Not configured'}
        except Exception as e:
            log.debug(f"Error getting task status: {e}")
            return {'exists': False, 'status': 'Error checking'}


__all__ = ['TaskSchedulerManager']
