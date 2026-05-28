"""
Token Budget Manager — controls how many tokens each context layer gets.
Enforces a total cap and allocates by priority.
"""


class TokenBudget:
    def __init__(self, max_tokens=10000):
        self.max_tokens = max_tokens
        self.used = 0
        self.allocations = {}

    @property
    def remaining(self):
        return max(0, self.max_tokens - self.used)

    def allocate(self, category, requested):
        """Try to allocate tokens for a category.
        Returns the actual amount allocated (may be less than requested).
        """
        allowed = min(requested, self.remaining)
        self.used += allowed
        self.allocations[category] = allowed
        return allowed

    def to_dict(self):
        return {
            "max_tokens": self.max_tokens,
            "used": self.used,
            "remaining": self.remaining,
            "allocations": self.allocations,
        }
