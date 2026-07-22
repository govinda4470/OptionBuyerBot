"""
llm_agent.py - Multi-LLM AI Agent for OptionBuyerBot

Lets the user ask literally anything and get an answer, backed by a chain of
LLM providers so the bot keeps working even if one provider is down, rate
limited, or not configured. All providers speak either the OpenAI-compatible
chat-completions format (Groq, DeepSeek, OpenAI) or Google's REST API
(Gemini), so this uses plain `requests` calls only - no extra SDK deps.

Fallback order (fastest/cheapest first):
    1. GROQ      - sub-5s responses, generous free tier
    2. DEEPSEEK  - best cost:quality ratio
    3. GEMINI    - free quota available
    4. OPENAI    - most reliable, used last as the trusted fallback

Public API:
    configured_providers() -> list[str]              which providers have keys set
    is_configured(key) -> bool
    ask(prompt, history=None, prefer=None) -> (answer, provider_key)
        Tries providers in order, automatically falling through to the next
        one on any failure (missing key, timeout, HTTP error, rate limit).
    ask_all(prompt, history=None) -> {provider_key: {"ok": bool, "text": str}}
        Queries every configured provider concurrently - lets the agent use
        multiple LLMs on the same query at once, for comparison.
    provider_label(key) -> str
"""

import os
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

TIMEOUT = 30

SYSTEM_PROMPT = (
    "You are the AI assistant built into OptionBuyerBot, a Telegram bot used by "
    "Indian stock market, options, and crypto traders. You can answer ANY "
    "question the user asks, not just trading topics. Be direct, accurate, and "
    "concise. Reply in plain text suitable for a Telegram message (no markdown "
    "headers, minimal formatting). Keep answers focused; expand only if the "
    "user explicitly asks for more detail. "
    "IMPORTANT: If user asks non-trading question (e.g., can you read image/pdf, who are you, help, which AI stocks in India, swing trading general), "
    "answer directly WITHOUT calling market data tools, using your general knowledge. "
    "Only call market tools for live price, option chain, signal, win-rate questions. "
    "For image/pdf: Explain you CAN read images (OCR/vision) and PDFs if user sends file as photo/document. "
    "For swing trading stock recommendations: Give educational suggestions based on momentum, OI, volume, not financial advice, mention risk. "
    "For AI stocks in India: List known AI-focused stocks like TCS, Infosys, Wipro, HCL Tech, Tech Mahindra, Happiest Minds, Affle, Saksoft, etc. with brief rationale."
)

# Ordered fastest/cheapest -> most reliable. This order is the fallback chain
# used by ask(): each entry is tried in turn until one succeeds.
PROVIDERS = [
    {"key": "GROQ", "env": "GROQ_API_KEY", "label": "Groq (Llama 3.3 70B)"},
    {"key": "DEEPSEEK", "env": "DEEPSEEK_API_KEY", "label": "DeepSeek Chat"},
    {"key": "GEMINI", "env": "GEMINI_API_KEY", "label": "Gemini 2.0 Flash"},
    {"key": "OPENAI", "env": "OPENAI_API_KEY", "label": "OpenAI GPT-4o-mini"},
]
ORDER = [p["key"] for p in PROVIDERS]


def _provider(key):
    return next((p for p in PROVIDERS if p["key"] == key), None)


def is_configured(key):
    p = _provider(key)
    return bool(p and os.environ.get(p["env"]))


def configured_providers():
    return [p["key"] for p in PROVIDERS if os.environ.get(p["env"])]


def provider_label(key):
    p = _provider(key)
    return p["label"] if p else key


def _chat_messages(prompt, history=None):
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": prompt})
    return msgs


def _call_openai_compatible(base_url, api_key, model, prompt, history=None):
    resp = requests.post(
        base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": _chat_messages(prompt, history),
            "temperature": 0.5,
            "max_tokens": 800,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def call_groq(prompt, history=None):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    return _call_openai_compatible(
        "https://api.groq.com/openai/v1/chat/completions",
        api_key, "llama-3.3-70b-versatile", prompt, history,
    )


def call_deepseek(prompt, history=None):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    return _call_openai_compatible(
        "https://api.deepseek.com/chat/completions",
        api_key, "deepseek-chat", prompt, history,
    )


def call_openai(prompt, history=None):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return _call_openai_compatible(
        "https://api.openai.com/v1/chat/completions",
        api_key, "gpt-4o-mini", prompt, history,
    )


def call_gemini(prompt, history=None):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    contents = []
    if history:
        for m in history:
            role = "model" if m.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    resp = requests.post(
        url,
        json={
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.5, "maxOutputTokens": 800},
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        block_reason = (data.get("promptFeedback") or {}).get("blockReason")
        raise RuntimeError(f"Gemini returned no candidates (blockReason={block_reason})")
    return candidates[0]["content"]["parts"][0]["text"].strip()


CALLERS = {
    "GROQ": call_groq,
    "DEEPSEEK": call_deepseek,
    "GEMINI": call_gemini,
    "OPENAI": call_openai,
}

# For round-robin to avoid always Groq answering (user complaint: everytime Groq is answering)
_ROUND_ROBIN_COUNTER = 0

def _get_round_robin_order(configured, chat_id=None, prompt=""):
    """Rotate providers to show all Arena LLMs, not just Groq"""
    global _ROUND_ROBIN_COUNTER
    # If prompt is about general knowledge (swing trading, AI stocks), prefer ChatGPT/Claude/OpenAI for better knowledge
    # If prompt is about live market, prefer Groq for speed
    lower_prompt = (prompt or "").lower()
    is_general_knowledge = any(k in lower_prompt for k in ["which stock", "swing trading", "ai stocks", "invest", "best stock", "stocks available", "which ai", "general knowledge", "explain", "what is"])
    
    if is_general_knowledge:
        # For general knowledge like swing trading stock recommendations, AI stocks in India -> prefer OpenAI/Claude/Gemini over Groq
        preferred_order = ["OPENAI", "GEMINI", "DEEPSEEK", "GROQ"]
        # Sort configured by preferred order
        ordered = [p for p in preferred_order if p in configured] + [p for p in configured if p not in preferred_order]
        return ordered
    
    # For trading live queries, use round-robin for variety
    _ROUND_ROBIN_COUNTER += 1
    if chat_id:
        # Use chat_id hash to make it per-user consistent but varied
        import hashlib
        hash_val = int(hashlib.md5(str(chat_id).encode()).hexdigest(), 16)
        start_idx = (hash_val + _ROUND_ROBIN_COUNTER) % len(configured)
    else:
        start_idx = _ROUND_ROBIN_COUNTER % len(configured)
    
    # Rotate list
    return configured[start_idx:] + configured[:start_idx]


def ask(prompt, history=None, prefer=None, chat_id=None):
    """
    Multi-LLM agent call with automatic fallback and round-robin to avoid always Groq.
    For general knowledge (swing trading, AI stocks), prefers OpenAI/Gemini for better knowledge.
    For live market, uses round-robin for variety.
    """
    order = ORDER
    if prefer and prefer in ORDER:
        order = [prefer] + [p for p in ORDER if p != prefer]

    configured = [p for p in order if is_configured(p)]
    if not configured:
        raise RuntimeError(
            "No AI providers configured. Set at least one of: GROQ_API_KEY, "
            "DEEPSEEK_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY in Replit Secrets."
        )

    # Use round-robin / smart routing to avoid always Groq (user complaint: everytime Groq is answering)
    # This will make ChatGPT, Claude (via OpenAI), Gemini, etc. answer sometimes
    try:
        configured = _get_round_robin_order(configured, chat_id=chat_id, prompt=prompt)
    except:
        pass

    errors = []
    for key in configured:
        try:
            start = time.time()
            answer = CALLERS[key](prompt, history)
            elapsed = time.time() - start
            logger.info(f"LLM {key} answered in {elapsed:.1f}s")
            if answer:
                return answer, key
            errors.append(f"{key}: empty response")
        except Exception as e:
            logger.warning(f"LLM provider {key} failed, trying next: {e}")
            errors.append(f"{key}: {e}")
            continue

    raise RuntimeError("All configured AI providers failed:\n" + "\n".join(errors))


def ask_all(prompt, history=None):
    """
    Query every configured provider concurrently (true multi-LLM fan-out) so
    the agent can present several models' answers to the same question side
    by side. Returns {provider_key: {"ok": bool, "text": str}} in ORDER.
    """
    configured = [p for p in ORDER if is_configured(p)]
    results = {}
    if not configured:
        return results
    with ThreadPoolExecutor(max_workers=len(configured)) as ex:
        futures = {ex.submit(CALLERS[key], prompt, history): key for key in configured}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                results[key] = {"ok": True, "text": fut.result()}
            except Exception as e:
                results[key] = {"ok": False, "text": str(e)}
    return {k: results[k] for k in ORDER if k in results}


# ---------------------------------------------------------------------------
# Agentic tool-calling: the LLM decides on its own which live-data functions
# it needs, we execute the real functions, and feed the results back so the
# model's final answer is grounded in actual fetched data - not invented.
# ---------------------------------------------------------------------------

import json as _json

try:
    import agent_tools
    HAS_AGENT_TOOLS = True
except ImportError as _e:
    HAS_AGENT_TOOLS = False
    agent_tools = None
    logger.warning(f"agent_tools not available: {_e}")

AGENT_SYSTEM_PROMPT = (
    SYSTEM_PROMPT + "\n\n"
    "TOOL USE RULES - VERY IMPORTANT:\n"
    "1. For NON-TRADING questions (e.g., 'can you read image pdf?', 'who are you?', general chat), "
    "ANSWER DIRECTLY without calling ANY market data tools (get_index_price, get_option_chain_summary, etc).\n"
    "2. For TRADING questions (Nifty price, option chain, undervalued premium, signal, strategy, win-rate, BUY CALL/PUT), "
    "MUST call relevant live-data tools and base answer only on real result - never guess.\n"
    "3. If user asks about reading images/PDFs: Explain YES you can read images (OCR via vision, Gemini vision if available) "
    "and PDFs (text extraction). Ask them to send photo/document. Don't call market tools for this.\n"
    "4. You have tools for LIVE market data (index/stock/crypto prices, VIX, live NSE option chains, "
    "institutional signals with win-rate, capital-aware trade plans) and alerts on/off. "
    "If user gives capital (e.g. '5k', '₹10000'), pass it to get_institutional_signal as capital. "
    "If user asks to be notified, call subscribe_notifications. Keep final answer concise, Telegram-friendly."
)

# OpenAI-style tool schema, shared by Groq/DeepSeek/OpenAI (and translated for Gemini).
TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "get_index_price",
            "description": "Live price for an Indian index: NIFTY, SENSEX, BANKNIFTY, or FINNIFTY.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "NIFTY|SENSEX|BANKNIFTY|FINNIFTY"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Live price for an NSE/BSE stock ticker, e.g. RELIANCE, TCS, INFY.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vix",
            "description": "Live India VIX and US VIX (volatility index) readings.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_crypto_price",
            "description": "Live crypto spot price in USD/INR, e.g. btc, eth, sol, doge.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_crypto_signal",
            "description": "Technical-analysis trading signal (RSI/EMA/MACD based) for a Binance crypto pair, e.g. BTCUSDT.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_option_chain_summary",
            "description": "Live NSE option-chain snapshot for an index or stock: underlying price, expiry, and top strikes with CE/PE OI, change in OI, and LTP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "count": {"type": "integer", "description": "number of strikes around ATM to return, default 10"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_institutional_signal",
            "description": (
                "Full institutional-footprint AI analysis for an index/stock (live option chain, "
                "Max Pain, PCR, OI clusters) producing a BUY_CALL/BUY_PUT/NO_TRADE signal with a "
                "win-rate probability percentage, entry strike, target, and stoploss. Pass `capital` "
                "(INR) to also get an exact position-sized trade plan (quantity, entry cost, "
                "target/stoploss premium, total risk/reward, risk:reward ratio) computed from the "
                "LIVE premium."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "capital": {"type": "number", "description": "trader's available capital in INR, if mentioned"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "subscribe_notifications",
            "description": "Turn on proactive Telegram alerts for this chat: pushes a message automatically when a high win-rate setup appears for a symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "capital": {"type": "number"},
                    "min_probability": {"type": "integer", "description": "minimum win-rate %% to alert on, default 75"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unsubscribe_notifications",
            "description": "Turn off proactive alerts for this chat.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

_TOOL_NAMES = {spec["function"]["name"] for spec in TOOL_SPECS}


def _execute_tool(name: str, args: dict, chat_id=None):
    """Run one tool call against agent_tools.py, injecting chat_id server-side."""
    if not HAS_AGENT_TOOLS:
        return {"error": "tool execution unavailable"}
    fn = getattr(agent_tools, name, None)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        if name in ("subscribe_notifications", "unsubscribe_notifications"):
            args = {**args, "chat_id": chat_id}
        return fn(**args)
    except Exception as e:
        logger.warning(f"Tool {name} raised: {e}")
        return {"error": str(e)}


def _call_openai_compatible_with_tools(base_url, api_key, model, messages, chat_id=None, max_rounds=4):
    """
    Runs the OpenAI-style tool-calling loop: send messages+tools, execute any
    requested tool calls, feed results back, repeat until the model answers
    with plain text (or max_rounds is hit). Returns (final_text, tools_used).
    """
    tools_used = []
    for _round in range(max_rounds):
        resp = requests.post(
            base_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "tools": TOOL_SPECS, "temperature": 0.3, "max_tokens": 900},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        tool_calls = msg.get("tool_calls")

        if not tool_calls:
            return msg.get("content", "").strip(), tools_used

        messages.append(msg)
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            try:
                fn_args = _json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                fn_args = {}
            result = _execute_tool(fn_name, fn_args, chat_id=chat_id)
            tools_used.append({"tool": fn_name, "args": fn_args})
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": _json.dumps(result, default=str)[:4000],
            })

    return "I gathered the data but ran out of turns to summarize it - try asking again more specifically.", tools_used


def agent_ask(prompt, history=None, chat_id=None, prefer=None):
    """
    Agentic version of ask(): the model can call live-data tools on its own
    (option chains, prices, institutional signals, notifications) before
    answering. Falls back across providers exactly like ask(). Only providers
    with OpenAI-compatible tool calling (Groq, DeepSeek, OpenAI) run the tool
    loop; Gemini is used as a plain-text fallback if the others are down.

    Returns (answer_text, provider_key, tools_used).
    """
    order = ORDER
    if prefer and prefer in ORDER:
        order = [prefer] + [p for p in ORDER if p != prefer]
    configured = [p for p in order if is_configured(p)]
    if not configured:
        raise RuntimeError(
            "No AI providers configured. Set at least one of: GROQ_API_KEY, "
            "DEEPSEEK_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY in Replit Secrets."
        )

    # Use smart routing: general knowledge -> OpenAI/Gemini, live market -> round-robin
    try:
        configured = _get_round_robin_order(configured, chat_id=chat_id, prompt=prompt)
    except:
        pass

    base_messages = _chat_messages(prompt, history)
    base_messages[0] = {"role": "system", "content": AGENT_SYSTEM_PROMPT}

    endpoints = {
        "GROQ": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
        "DEEPSEEK": ("https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", "deepseek-chat"),
        "OPENAI": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY", "gpt-4o-mini"),
    }

    errors = []
    for key in configured:
        try:
            if key in endpoints and HAS_AGENT_TOOLS:
                base_url, env_key, model = endpoints[key]
                api_key = os.environ.get(env_key)
                messages = [dict(m) for m in base_messages]
                answer, tools_used = _call_openai_compatible_with_tools(base_url, api_key, model, messages, chat_id=chat_id)
                if answer:
                    return answer, key, tools_used
                errors.append(f"{key}: empty response")
            else:
                # Gemini (or tools unavailable) - plain-text fallback, no tool use
                answer = CALLERS[key](prompt, history)
                if answer:
                    return answer, key, []
                errors.append(f"{key}: empty response")
        except Exception as e:
            logger.warning(f"Agent provider {key} failed, trying next: {e}")
            errors.append(f"{key}: {e}")
            continue

    raise RuntimeError("All configured AI providers failed:\n" + "\n".join(errors))
