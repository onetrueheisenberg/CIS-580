"""Rate limiter for API calls to respect Gemini API rate limits.

This module provides rate limiting functionality to prevent exceeding
API rate limits when making parallel requests.
"""

import time
from threading import Lock
from typing import Optional
from collections import deque


class RateLimiter:
    """Thread-safe rate limiter for API calls.
    
    Implements token bucket algorithm to respect rate limits:
    - RPM: Requests Per Minute
    - TPM: Tokens Per Minute (estimated)
    - RPD: Requests Per Day
    """
    
    def __init__(
        self,
        rpm: int = 15,
        tpm: int = 250000,
        rpd: int = 1000,
        tokens_per_request: int = 10000  # Estimated tokens per request
    ):
        """Initialize rate limiter.
        
        Args:
            rpm: Requests per minute limit
            tpm: Tokens per minute limit
            rpd: Requests per day limit
            tokens_per_request: Estimated tokens per API request
        """
        self.rpm = rpm
        self.tpm = tpm
        self.rpd = rpd
        self.tokens_per_request = tokens_per_request
        
        # Request tracking
        self.request_times = deque()  # Track request timestamps for RPM
        self.daily_requests = 0  # Track daily requests
        self.daily_reset_time = time.time() + (24 * 60 * 60)  # Reset in 24 hours
        
        # Token tracking
        self.available_tokens = tpm
        self.token_refill_rate = tpm / 60.0  # Tokens per second
        self.last_token_refill = time.time()
        
        # Thread safety
        self.lock = Lock()
    
    def _refill_tokens(self):
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_token_refill
        
        if elapsed > 0:
            tokens_to_add = elapsed * self.token_refill_rate
            self.available_tokens = min(
                self.tpm,
                self.available_tokens + tokens_to_add
            )
            self.last_token_refill = now
    
    def _cleanup_old_requests(self):
        """Remove requests older than 1 minute."""
        now = time.time()
        cutoff = now - 60.0  # 1 minute ago
        
        while self.request_times and self.request_times[0] < cutoff:
            self.request_times.popleft()
    
    def _reset_daily_counter_if_needed(self):
        """Reset daily counter if 24 hours have passed."""
        now = time.time()
        if now >= self.daily_reset_time:
            self.daily_requests = 0
            self.daily_reset_time = now + (24 * 60 * 60)
    
    def wait_if_needed(self, estimated_tokens: Optional[int] = None) -> float:
        """Wait if necessary to respect rate limits.
        
        Args:
            estimated_tokens: Estimated tokens for this request (uses default if None)
            
        Returns:
            Time waited in seconds
        """
        if estimated_tokens is None:
            estimated_tokens = self.tokens_per_request
        
        wait_time = 0.0
        start_time = time.time()
        
        with self.lock:
            # Reset daily counter if needed
            self._reset_daily_counter_if_needed()
            
            # Check daily limit
            if self.daily_requests >= self.rpd:
                # Calculate wait time until next day reset
                wait_until = self.daily_reset_time - time.time()
                if wait_until > 0:
                    wait_time = wait_until
                    time.sleep(wait_time)
                    self._reset_daily_counter_if_needed()
            
            # Clean up old requests
            self._cleanup_old_requests()
            
            # Check RPM limit
            if len(self.request_times) >= self.rpm:
                # Wait until oldest request is 1 minute old
                oldest_request = self.request_times[0]
                wait_until = (oldest_request + 60.0) - time.time()
                if wait_until > 0:
                    wait_time += wait_until
                    time.sleep(wait_until)
                    self._cleanup_old_requests()
            
            # Refill tokens
            self._refill_tokens()
            
            # Check TPM limit
            if self.available_tokens < estimated_tokens:
                # Calculate wait time to get enough tokens
                tokens_needed = estimated_tokens - self.available_tokens
                wait_until = tokens_needed / self.token_refill_rate
                if wait_until > 0:
                    wait_time += wait_until
                    time.sleep(wait_until)
                    self._refill_tokens()
            
            # Record this request
            now = time.time()
            self.request_times.append(now)
            self.daily_requests += 1
            self.available_tokens -= estimated_tokens
        
        return wait_time
    
    def get_status(self) -> dict:
        """Get current rate limit status.
        
        Returns:
            Dictionary with current usage and limits
        """
        with self.lock:
            self._cleanup_old_requests()
            self._refill_tokens()
            self._reset_daily_counter_if_needed()
            
            return {
                "rpm_used": len(self.request_times),
                "rpm_limit": self.rpm,
                "rpm_percent": (len(self.request_times) / self.rpm * 100) if self.rpm > 0 else 0,
                "tpm_used": self.tpm - self.available_tokens,
                "tpm_limit": self.tpm,
                "tpm_percent": ((self.tpm - self.available_tokens) / self.tpm * 100) if self.tpm > 0 else 0,
                "rpd_used": self.daily_requests,
                "rpd_limit": self.rpd,
                "rpd_percent": (self.daily_requests / self.rpd * 100) if self.rpd > 0 else 0
            }


# Global rate limiter instance (shared across all workers)
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(
    rpm: int = 15,
    tpm: int = 250000,
    rpd: int = 1000,
    tokens_per_request: int = 10000
) -> RateLimiter:
    """Get or create global rate limiter instance.
    
    Args:
        rpm: Requests per minute limit
        tpm: Tokens per minute limit
        rpd: Requests per day limit
        tokens_per_request: Estimated tokens per request
        
    Returns:
        Global RateLimiter instance
    """
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(
            rpm=rpm,
            tpm=tpm,
            rpd=rpd,
            tokens_per_request=tokens_per_request
        )
    
    return _global_rate_limiter


def reset_rate_limiter():
    """Reset the global rate limiter (useful for testing)."""
    global _global_rate_limiter
    _global_rate_limiter = None

