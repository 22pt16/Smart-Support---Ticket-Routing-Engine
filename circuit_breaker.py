# circuit_breaker.py

import time

class CircuitBreaker:
    def __init__(self):
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = None

    def record(self, latency):
        if latency > 500:
            self.failure_count += 1
            self.last_failure_time = time.time()
        else:
            # Successful request
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
            self.failure_count = 0

        if self.failure_count >= 3:
            self.state = "OPEN"

    def allow(self):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > 60:
                self.state = "HALF_OPEN"
                return True
            return False
        return True

breaker = CircuitBreaker()