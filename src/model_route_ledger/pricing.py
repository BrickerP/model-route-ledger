"""Claude 5.5-family list prices (USD per 1M tokens).

Sources (checked 2026-10-13):
  https://www.anthropic.com/claude-haiku-5-5
  https://platform.claude.com/docs/en/about-claude/pricing
Haiku 5.5 is priced by prompt length: a request whose prompt (input + cache
reads + cache writes) is over 100,000 tokens pays the higher tier for the
whole request.
"""

HAIKU_CLIFF = 100_000

PRICES = {
    # model: (input, cache_read, output)
    "opus-5.5": {"input": 4.00, "cache_read": 0.40, "output": 20.00},  # cache_read assumed 0.1x input
    "sonnet-5.5": {"input": 2.00, "cache_read": 0.10, "output": 10.00},
    "haiku-5.5": {"input": 0.10, "cache_read": 0.01, "output": 0.50},
    "haiku-5.5>100k": {"input": 0.50, "cache_read": 0.05, "output": 2.50},
}

# Haiku 5.5 ships a new tokenizer; the same text counts as more tokens than
# on the previous tokenizer. Configurable; default 1.30 per Anthropic's
# migration notes as summarized publicly. Set 1.0 if your logs already
# count Haiku 5.5 tokens.
DEFAULT_HAIKU_TOKEN_INFLATION = 1.30


def price_key(model: str, prompt_tokens: int) -> str:
    if model == "haiku-5.5" and prompt_tokens > HAIKU_CLIFF:
        return "haiku-5.5>100k"
    return model


def cost(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> tuple[float, str]:
    prompt = input_tokens + cached_tokens
    key = price_key(model, prompt)
    p = PRICES[key]
    usd = (input_tokens * p["input"] + cached_tokens * p["cache_read"] + output_tokens * p["output"]) / 1_000_000
    return usd, key
