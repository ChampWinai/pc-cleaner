"""Retry logic and operation context for reliable execution."""
import logging
import time
import threading
from typing import Callable, Any, Optional
from functools import wraps

log = logging.getLogger(__name__)


class OperationCancelled(Exception):
    """Raised when an operation is cancelled."""
    pass


class OperationContext:
    """Thread-safe context for managing long-running operations."""

    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        self.cancelled = False
        self._lock = threading.Lock()
        self.progress = 0
        self.total_steps = 0
        self.current_step_name = ""

    def cancel(self):
        """Request cancellation of the operation."""
        with self._lock:
            self.cancelled = True
        log.info(f"Operation {self.operation_id} cancellation requested")

    def is_cancelled(self):
        """Check if operation is cancelled."""
        with self._lock:
            return self.cancelled

    def check_cancelled(self):
        """Raise OperationCancelled if cancelled."""
        if self.is_cancelled():
            raise OperationCancelled(f"Operation {self.operation_id} was cancelled")

    def set_progress(self, current: int, total: int, step_name: str = ""):
        """Update progress."""
        with self._lock:
            self.progress = current
            self.total_steps = total
            self.current_step_name = step_name

    def get_progress(self):
        """Get current progress state."""
        with self._lock:
            return {
                'progress': self.progress,
                'total': self.total_steps,
                'step': self.current_step_name,
                'percentage': int((self.progress / max(self.total_steps, 1)) * 100),
            }


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts=3,
        initial_delay=1,
        max_delay=30,
        backoff_factor=2,
        exceptions=(Exception,),
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.exceptions = exceptions


def retry(config: Optional[RetryConfig] = None):
    """
    Decorator for retrying operations with exponential backoff.
    
    Args:
        config: RetryConfig instance. Defaults to 3 attempts with exponential backoff.
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            context = kwargs.get('_operation_context')
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    if context:
                        context.check_cancelled()
                    
                    log.debug(f"Attempt {attempt}/{config.max_attempts} for {func.__name__}")
                    result = func(*args, **kwargs)
                    
                    if attempt > 1:
                        log.info(f"{func.__name__} succeeded on attempt {attempt}")
                    
                    return result
                
                except OperationCancelled:
                    raise
                except config.exceptions as e:
                    last_exception = e
                    
                    if attempt >= config.max_attempts:
                        log.error(f"{func.__name__} failed after {config.max_attempts} attempts: {e}")
                        raise
                    
                    delay = min(
                        config.initial_delay * (config.backoff_factor ** (attempt - 1)),
                        config.max_delay
                    )
                    log.warning(
                        f"{func.__name__} failed (attempt {attempt}/{config.max_attempts}), "
                        f"retrying in {delay}s: {e}"
                    )
                    time.sleep(delay)
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def cancellable(func: Callable) -> Callable:
    """
    Decorator to make a function cancellable via _operation_context kwarg.
    Function should check context via context.check_cancelled() periodically.
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        context = kwargs.get('_operation_context')
        if context:
            context.check_cancelled()
        return func(*args, **kwargs)
    return wrapper


__all__ = ['OperationContext', 'OperationCancelled', 'RetryConfig', 'retry', 'cancellable']
