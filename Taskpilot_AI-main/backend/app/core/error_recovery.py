"""
Error Recovery and Retry System for TaskPilot AI

Features:
- Intelligent retry with exponential backoff
- Circuit breaker pattern
- Error classification
- Graceful degradation
"""

import time
import asyncio
from typing import Callable, Any, Optional, Type
from functools import wraps
from enum import Enum
import random


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"          # Minor issues, can continue
    MEDIUM = "medium"    # Significant issues, retry recommended
    HIGH = "high"        # Critical issues, immediate attention needed
    FATAL = "fatal"      # System-breaking, cannot recover


class ErrorCategory(Enum):
    """Error categories for classification."""
    NETWORK = "network"          # API calls, web requests
    TIMEOUT = "timeout"          # Operation timeout
    VALIDATION = "validation"    # Data validation errors
    PROCESSING = "processing"    # Data processing errors
    EXTERNAL_API = "external_api"  # External service errors
    RESOURCE = "resource"        # Resource limits (memory, disk)
    UNKNOWN = "unknown"          # Unclassified errors


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt."""
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            # Add random jitter to prevent thundering herd
            delay = delay * (0.5 + random.random())
        
        return delay


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by stopping calls to failing services.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise Exception(f"Circuit breaker is OPEN. Service unavailable.")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        if self.state == "half-open":
            self.state = "closed"
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self.last_failure_time is not None and
            (time.time() - self.last_failure_time) >= self.recovery_timeout
        )
    
    def reset(self):
        """Manually reset circuit breaker."""
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None


class ErrorClassifier:
    """Classify errors and determine recovery strategy."""
    
    @staticmethod
    def classify(error: Exception) -> tuple[ErrorCategory, ErrorSeverity]:
        """Classify error by category and severity."""
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # Network errors
        if any(term in error_type.lower() for term in ['connection', 'network', 'http']):
            return ErrorCategory.NETWORK, ErrorSeverity.MEDIUM
        
        # Timeout errors
        if 'timeout' in error_type.lower() or 'timeout' in error_msg:
            return ErrorCategory.TIMEOUT, ErrorSeverity.MEDIUM
        
        # Validation errors
        if any(term in error_type.lower() for term in ['validation', 'value', 'type']):
            return ErrorCategory.VALIDATION, ErrorSeverity.LOW
        
        # External API errors
        if any(term in error_msg for term in ['api', 'rate limit', 'quota']):
            return ErrorCategory.EXTERNAL_API, ErrorSeverity.MEDIUM
        
        # Resource errors
        if any(term in error_msg for term in ['memory', 'disk', 'resource']):
            return ErrorCategory.RESOURCE, ErrorSeverity.HIGH
        
        # Default
        return ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM
    
    @staticmethod
    def is_retryable(error: Exception) -> bool:
        """Determine if error is retryable."""
        category, severity = ErrorClassifier.classify(error)
        
        # Don't retry fatal errors or validation errors
        if severity == ErrorSeverity.FATAL:
            return False
        
        if category == ErrorCategory.VALIDATION:
            return False
        
        # Retry network, timeout, and external API errors
        return category in [
            ErrorCategory.NETWORK,
            ErrorCategory.TIMEOUT,
            ErrorCategory.EXTERNAL_API
        ]


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable] = None,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator for automatic retry with exponential backoff.
    
    Usage:
        @retry_with_backoff(config=RetryConfig(max_retries=3))
        async def my_function():
            # ... code that might fail
    """
    config = config or RetryConfig()
    
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Check if error is retryable
                    if not ErrorClassifier.is_retryable(e):
                        raise
                    
                    # Last attempt - raise error
                    if attempt == config.max_retries:
                        raise
                    
                    # Calculate delay and wait
                    delay = config.get_delay(attempt)
                    
                    if on_retry:
                        on_retry(attempt, delay, e)
                    
                    await asyncio.sleep(delay)
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if not ErrorClassifier.is_retryable(e):
                        raise
                    
                    if attempt == config.max_retries:
                        raise
                    
                    delay = config.get_delay(attempt)
                    
                    if on_retry:
                        on_retry(attempt, delay, e)
                    
                    time.sleep(delay)
            
            if last_exception:
                raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class ErrorRecoveryManager:
    """
    Centralized error recovery management.
    
    Tracks errors, recovery attempts, and success rates.
    """
    
    def __init__(self):
        self.error_history = []
        self.recovery_stats = {
            'total_errors': 0,
            'recovered': 0,
            'failed': 0
        }
    
    def record_error(
        self,
        error: Exception,
        context: dict,
        recovered: bool = False
    ):
        """Record an error occurrence."""
        category, severity = ErrorClassifier.classify(error)
        
        error_record = {
            'timestamp': time.time(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'category': category.value,
            'severity': severity.value,
            'context': context,
            'recovered': recovered
        }
        
        self.error_history.append(error_record)
        self.error_history = self.error_history[-1000:]  # Keep last 1000
        
        self.recovery_stats['total_errors'] += 1
        if recovered:
            self.recovery_stats['recovered'] += 1
        else:
            self.recovery_stats['failed'] += 1
    
    def get_error_summary(self) -> dict:
        """Get summary of errors."""
        if not self.error_history:
            return {'total_errors': 0}
        
        # Count by category
        by_category = {}
        by_severity = {}
        
        for record in self.error_history:
            cat = record['category']
            sev = record['severity']
            
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        recovery_rate = (
            self.recovery_stats['recovered'] / self.recovery_stats['total_errors'] * 100
            if self.recovery_stats['total_errors'] > 0 else 0
        )
        
        return {
            'total_errors': len(self.error_history),
            'by_category': by_category,
            'by_severity': by_severity,
            'recovery_rate': round(recovery_rate, 2),
            **self.recovery_stats
        }
    
    def get_recent_errors(self, limit: int = 10) -> list:
        """Get most recent errors."""
        return self.error_history[-limit:]


# Global instance
_error_recovery_manager = None


def get_error_recovery_manager() -> ErrorRecoveryManager:
    """Get the global error recovery manager."""
    global _error_recovery_manager
    if _error_recovery_manager is None:
        _error_recovery_manager = ErrorRecoveryManager()
    return _error_recovery_manager
