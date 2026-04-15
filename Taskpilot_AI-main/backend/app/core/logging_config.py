"""
Advanced Logging and Monitoring System for TaskPilot AI

Provides:
- Structured logging with context
- Performance tracking
- Real-time monitoring
- Error tracking and analysis
"""

import logging
import time
import json
from datetime import datetime
from typing import Any, Optional
from pathlib import Path
import io
import sys


class TaskPilotLogger:
    """
    Centralized logging system for TaskPilot AI.
    
    Features:
    - Structured JSON logging
    - Performance metrics
    - Agent-specific logging
    - Real-time monitoring support
    """
    
    def __init__(self, name: str = "taskpilot"):
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Configure logger with handlers."""
        if self.logger.handlers:
            return  # Already configured

        # Windows consoles often default to a legacy code page; use UTF-8 so
        # diagnostic symbols and structured output do not crash logging.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        elif hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        elif hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Console handler with color support
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        # File handler for structured logs
        file_handler = logging.FileHandler(
            log_dir / f"taskpilot_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Error file handler
        error_handler = logging.FileHandler(
            log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with exception details."""
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_message'] = str(error)
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """Log message with structured context."""
        if kwargs:
            context = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            message = f"{message} | {context}"
        self.logger.log(level, message)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)


class PerformanceMonitor:
    """
    Performance monitoring for agents and tasks.
    
    Tracks:
    - Execution time
    - Success/failure rates
    - Resource usage
    """
    
    def __init__(self):
        self.metrics = {}
        self.logger = TaskPilotLogger("performance")
    
    def start_task(self, task_id: str, task_type: str) -> str:
        """Start tracking a task."""
        self.metrics[task_id] = {
            'task_type': task_type,
            'start_time': time.time(),
            'status': 'running'
        }
        self.logger.info(f"Task started", task_id=task_id, task_type=task_type)
        return task_id
    
    def end_task(self, task_id: str, status: str = 'success', details: Optional[dict] = None):
        """End tracking a task."""
        if task_id not in self.metrics:
            return
        
        metric = self.metrics[task_id]
        metric['end_time'] = time.time()
        metric['duration'] = metric['end_time'] - metric['start_time']
        metric['status'] = status
        
        if details:
            metric.update(details)
        
        self.logger.info(
            f"Task completed",
            task_id=task_id,
            duration=f"{metric['duration']:.2f}s",
            status=status
        )
        
        return metric
    
    def get_metrics(self, task_id: Optional[str] = None) -> dict:
        """Get performance metrics."""
        if task_id:
            return self.metrics.get(task_id, {})
        return self.metrics
    
    def get_summary(self) -> dict:
        """Get performance summary."""
        total_tasks = len(self.metrics)
        if total_tasks == 0:
            return {'total_tasks': 0}
        
        successful = sum(1 for m in self.metrics.values() if m.get('status') == 'success')
        failed = sum(1 for m in self.metrics.values() if m.get('status') == 'failed')
        
        durations = [m['duration'] for m in self.metrics.values() if 'duration' in m]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            'total_tasks': total_tasks,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total_tasks) * 100 if total_tasks > 0 else 0,
            'avg_duration': avg_duration,
            'total_time': sum(durations)
        }


class AgentMonitor:
    """
    Agent-specific monitoring system.
    
    Tracks each agent's performance and outputs.
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = TaskPilotLogger(f"agent.{agent_name}")
        self.executions = []
    
    def log_start(self, context: dict):
        """Log agent execution start."""
        execution = {
            'agent': self.agent_name,
            'start_time': time.time(),
            'context': context,
            'status': 'running'
        }
        self.executions.append(execution)
        
        self.logger.info(
            f"Agent {self.agent_name} started",
            context_keys=list(context.keys())
        )
        
        return len(self.executions) - 1  # Return execution index
    
    def log_end(self, execution_idx: int, status: str, output: Any, details: Optional[dict] = None):
        """Log agent execution end."""
        if execution_idx >= len(self.executions):
            return
        
        execution = self.executions[execution_idx]
        execution['end_time'] = time.time()
        execution['duration'] = execution['end_time'] - execution['start_time']
        execution['status'] = status
        execution['output_length'] = len(str(output)) if output else 0
        
        if details:
            execution['details'] = details
        
        self.logger.info(
            f"Agent {self.agent_name} completed",
            duration=f"{execution['duration']:.2f}s",
            status=status,
            output_length=execution['output_length']
        )
    
    def log_error(self, execution_idx: int, error: Exception):
        """Log agent error."""
        if execution_idx >= len(self.executions):
            return
        
        execution = self.executions[execution_idx]
        execution['status'] = 'error'
        execution['error'] = str(error)
        execution['error_type'] = type(error).__name__
        
        self.logger.error(
            f"Agent {self.agent_name} error",
            error=error,
            error_type=type(error).__name__
        )
    
    def get_stats(self) -> dict:
        """Get agent statistics."""
        total = len(self.executions)
        if total == 0:
            return {'total_executions': 0}
        
        successful = sum(1 for e in self.executions if e.get('status') == 'complete')
        errors = sum(1 for e in self.executions if e.get('status') == 'error')
        
        durations = [e['duration'] for e in self.executions if 'duration' in e]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            'agent': self.agent_name,
            'total_executions': total,
            'successful': successful,
            'errors': errors,
            'success_rate': (successful / total) * 100 if total > 0 else 0,
            'avg_duration': avg_duration
        }


# Global instances
_performance_monitor = None
_loggers = {}


def get_logger(name: str = "taskpilot") -> TaskPilotLogger:
    """Get or create a logger instance."""
    if name not in _loggers:
        _loggers[name] = TaskPilotLogger(name)
    return _loggers[name]


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def get_agent_monitor(agent_name: str) -> AgentMonitor:
    """Get or create an agent monitor."""
    key = f"agent_monitor_{agent_name}"
    if key not in _loggers:
        _loggers[key] = AgentMonitor(agent_name)
    return _loggers[key]
