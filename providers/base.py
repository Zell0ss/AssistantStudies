"""Base provider class with retry logic and logging"""
from abc import ABC, abstractmethod
from typing import Any, Callable, TypeVar
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)
import requests.exceptions

# Type for retry wrapper
T = TypeVar('T')

# Transient errors that should be retried
TRANSIENT_ERRORS = (
    requests.exceptions.RequestException,
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    ConnectionResetError,
    TimeoutError,
)


class BaseProvider(ABC):
    """
    Base class for all providers with retry logic and structured logging.

    Providers should inherit from this and implement:
    - __init__: Initialize provider with config
    - health_check: Verify provider is working
    """

    def __init__(self, config):
        """Initialize provider with configuration"""
        self.config = config
        self.config.validate()
        logger.info(f"Initialized {self.__class__.__name__}")

    def _call_with_retry(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with automatic retry for transient errors.

        Retries 3 times with exponential backoff (2s → 4s → 8s) for:
        - Network errors
        - Connection timeouts
        - Temporary API failures

        Fails immediately for:
        - Authentication errors
        - Validation errors
        - Configuration errors

        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            Original exception if retries exhausted or non-transient error
        """
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(TRANSIENT_ERRORS),
            reraise=True
        )
        def _retry_wrapper():
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{self.__class__.__name__}.{func.__name__}: Call successful")
                return result
            except TRANSIENT_ERRORS as e:
                logger.warning(
                    f"{self.__class__.__name__}.{func.__name__}: "
                    f"Transient error (will retry): {type(e).__name__}: {e}"
                )
                raise  # Let tenacity handle retry
            except Exception as e:
                logger.error(
                    f"{self.__class__.__name__}.{func.__name__}: "
                    f"Non-transient error (failing fast): {type(e).__name__}: {e}"
                )
                raise  # Don't retry, fail immediately

        try:
            return _retry_wrapper()
        except RetryError as e:
            logger.error(
                f"{self.__class__.__name__}.{func.__name__}: "
                f"Failed after 3 retries: {e.last_attempt.exception()}"
            )
            raise e.last_attempt.exception()

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if provider is healthy and properly configured.

        Returns:
            True if provider is working

        Raises:
            Exception if provider is unhealthy
        """
        pass
