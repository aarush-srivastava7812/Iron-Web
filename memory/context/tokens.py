"""Explicit consumer-tokenizer accounting; no character/token approximation."""


class ContextCapacity(ValueError):
    pass


class TokenBudget:
    def __init__(self, tokenizer, identity, prefix="", suffix=""):
        if not identity or not callable(getattr(tokenizer, "encode", None)):
            raise ValueError(
                "Supply the consumer tokenizer and its versioned identity."
            )
        self.tokenizer, self.identity = tokenizer, identity
        self.prefix, self.suffix = prefix, suffix
        # Prevent a tokenizer's preconfigured truncation from hiding overflow.
        no_truncation = getattr(tokenizer, "no_truncation", None)
        if no_truncation:
            no_truncation()
        no_padding = getattr(tokenizer, "no_padding", None)
        if no_padding:
            no_padding()

    @classmethod
    def from_file(cls, path, identity, prefix="", suffix=""):
        import hashlib
        from pathlib import Path
        from tokenizers import Tokenizer

        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        return cls(
            Tokenizer.from_file(str(path)), identity + ":" + digest, prefix, suffix
        )

    def wrap(self, text):
        return self.prefix + text + self.suffix

    def count(self, text):
        encoded = self.tokenizer.encode(text)
        return len(encoded.ids if hasattr(encoded, "ids") else encoded)

    def require(self, text, limit, block):
        count = self.count(text)
        if count > limit:
            raise ContextCapacity(
                f"{block} needs {count} tokens; limit is {limit}. Narrow the task."
            )
        return count

    def prompt(self, text, context_limit, reserved_output):
        return self.require(text, context_limit - reserved_output, "Complete prompt")
