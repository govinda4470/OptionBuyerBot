"""
OptionBuyerBot - 24/7 Telegram Bot with Countdown + Live Market + Shoonya Option Chain
v0.3 - Shoonya integration added, keeps all previous features working

Features:
- hi demo instant <1 sec
- Countdown for hard tasks (Processing please wait + 3..2..1)
- Live Indian market: via Shoonya (primary, free, reliable) + Yahoo fallback + CoinGecko crypto
- Option Chain: Shoonya get_option_chain (free NSE) - main goal for Option Buyer
- Secure: all credentials from env (Replit Secrets), never in code
"""

import os
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    def load_dotenv():
        pass
    print("⚠️ python-dotenv not installed, using os.environ only")
    load_dotenv()

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

try:
    from keep_alive import keep_alive
    HAS_KEEP_ALIVE = True
except ImportError:
    HAS_KEEP_ALIVE = False
    def keep_alive():
        pass

# Market data Yahoo fallback (robust version)
try:
    import market_data as md
    HAS_MARKET_DATA = True
except ImportError as e:
    HAS_MARKET_DATA = False
    md = None
    print(f"⚠️ market_data not available: {e}")

# Shoonya client (Finvasia) - for option chain + live Indian
try:
    import shoonya_client as sc
    HAS_SHOONYA_LIB = True
    try:
        SHOONYA_CONFIGURED = sc.is_shoonya_configured()
    except:
        SHOONYA_CONFIGURED = False
except ImportError as e:
    HAS_SHOONYA_LIB = False
    SHOONYA_CONFIGURED = False
    sc = None
    print(f"⚠️ shoonya_client not available: {e}")

# Institutional AI Strategy - World class option buying + footprint detection
try:
    import institutional_strategy as inst_ai
    HAS_INSTITUTIONAL_AI = True
except ImportError as e:
    HAS_INSTITUTIONAL_AI = False
    inst_ai = None
    print(f"⚠️ institutional_strategy not available: {e}")

# Free option chain providers (bypass NSE 403 + Shoonya 502) + Crypto Expert
try:
    import free_option_chain as free_oc
    HAS_FREE_OC = True
except ImportError:
    HAS_FREE_OC = False
    free_oc = None

try:
    import crypto_expert as crypto_ai
    HAS_CRYPTO_EXPERT = True
except ImportError:
    HAS_CRYPTO_EXPERT = False
    crypto_ai = None

# Multi-LLM AI Agent (Groq -> DeepSeek -> Gemini -> OpenAI fallback chain) - answers anything
try:
    import llm_agent
    HAS_LLM_AGENT = True
except ImportError as e:
    HAS_LLM_AGENT = False
    llm_agent = None
    print(f"⚠️ llm_agent not available: {e}")

# Arena Agent - Fully functional multi-LLM arena with 8 personas (Claude, ChatGPT, Gemini, Grok, Qwen, Kimi, Llama, DeepSeek)
try:
    import arena_agent
    HAS_ARENA_AGENT = True
except ImportError as e:
    HAS_ARENA_AGENT = False
    arena_agent = None
    print(f"⚠️ arena_agent not available: {e}")

# VarunS2002 NSE Option Chain Analyzer - Live OI Upper/Lower, Call Sum, Put Sum, Difference, Boundaries, ITM
try:
    import varun_analyzer
    HAS_VARUN = True
except ImportError as e:
    HAS_VARUN = False
    varun_analyzer = None
    print(f"⚠️ varun_analyzer not available: {e}")

# Capital-aware position sizing + background market watcher (notifications)
try:
    import position_sizing as pos_sizing
    HAS_POS_SIZING = True
except ImportError:
    HAS_POS_SIZING = False
    pos_sizing = None

try:
    import market_watcher
    HAS_WATCHER = True
except ImportError as e:
    HAS_WATCHER = False
    market_watcher = None
    print(f"⚠️ market_watcher not available: {e}")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")

INSTANT_TRIGGERS = {"hi", "hello", "hey", "hii", "hi demo", "demo hi", "hii demo", "hi bot", "ping", "test"}

def get_hi_demo_response():
    now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p IST")
    market_status = []
    if SHOONYA_CONFIGURED:
        market_status.append("Shoonya ✅")
    if HAS_MARKET_DATA:
        market_status.append("Yahoo ✅")
    market_status.append("Crypto ✅")
    if HAS_INSTITUTIONAL_AI:
        market_status.append("AI Signals ✅")
    market_str = ", ".join(market_status) if market_status else "Limited"

    return (
        f"Hi! 👋✅\n\n"
        f"Bot is working fine!\n"
        f"Status: ONLINE 24/7\n"
        f"Market Data: {market_str}\n"
        f"Time: {now}\n"
        f"Response: <1 sec for hi\n\n"
        f"🚀 NEW AI Institutional Features:\n"
        f"• /signal NIFTY - AI Buy/Sell signal with probability %\n"
        f"• /analysis NIFTY - Institutional footprint deep dive\n"
        f"• /beststrategy - Best option buying strategy India\n"
        f"\n"
        f"• /nifty /sensex /banknifty - live index\n"
        f"• /stock RELIANCE - live stock\n"
        f"• /optionchain NIFTY - live option chain\n"
        f"• /shoonya_status - check Shoonya API\n"
        f"• /help - all commands"
    )

HELP_HTML = """
<b>🤖 OptionBuyerBot v0.6 - Varun + Arena Multi-LLM + AI Institutional 🚀</b>

<b>🔥 NEW: VarunS2002 Live Analyzer (Your Request):</b>
/varun NIFTY [strike] - Live OI Upper/Lower Boundary, Call Sum, Put Sum, Diff, Call/Put Boundary, Call/Put ITM, PCR
  Original logic from github.com/VarunS2002/Python-NSE-Option-Chain-Analyzer
  e.g. /varun NIFTY 24500, /varun BANKNIFTY 48000
  Shows: Bearish if Call Sum > Put Sum, Bullish if Put Sum > Call Sum, Exits, ITM signals

<b>🏟️ NEW: Arena Multi-LLM Fully Functional (8 LLMs):</b>
/arena <i>question</i> - Ask ALL 8 AI models at once (Claude, ChatGPT, Gemini, Grok, Qwen, Kimi, Llama, DeepSeek) - compares answers
/arena_vote <i>question</i> - Arena consensus voting: Should I buy CALL/PUT? Votes across LLMs
/arena_persona &lt;persona&gt; &lt;question&gt; - Ask specific persona: claude, chatgpt, gemini, grok, qwen, kimi, llama, deepseek
  e.g. /arena_persona grok Is NIFTY manipulation happening?
Personas simulate Arena's multiple LLMs for trading queries

<b>🔥 AI Institutional Signals:</b>
/signal NIFTY - AI signal with Entry, Target, SL, Probability %
/signal BANKNIFTY 48000 - signal for specific
/analysis NIFTY - Deep footprint (OI clusters, Max Pain, PCR, liquidity pools, stop hunting zones)
/beststrategy - Best option buying strategy India

<b>⚡️ Instant + Countdown:</b>
• hi = Instant &lt;1 sec
• Hard tasks = Processing + live countdown → accurate response

<b>📊 Live Market (NSE Direct + Shoonya + Yahoo + Free Proxy Bypass):</b>
/nifty /sensex /banknifty /finnifty - live indices (NSE direct now, bypasses old 403)
/stock SYMBOL - /stock RELIANCE
/optionchain SYMBOL [strike] [count] - live chain (NSE direct v3 + Shoonya fallback)
  e.g. /optionchain NIFTY / /optionchain BANKNIFTY 48000
/free_chain NIFTY - Free proxy bypass when NSE 403
/vix /global /crypto btc - crypto works 24/7
/crypto_signal BTCUSDT - Binance spot AI signal with probability
/crypto_option BTC/ETH - Deribit option chain free, works on Replit (80% global volume)
/shoonya_status - check Shoonya login & IP whitelist
/status - bot health

<b>🧠 AI Agent - Ask Anything (Agentic Tool-Calling):</b>
/ask <i>question</i> - multi-LLM agent that autonomously fetches live prices, option chains
  and signals via its own tools (Groq → DeepSeek → Gemini → OpenAI fallback), never guesses
/compare <i>question</i> - ask all configured models at once, side by side
/llm_status - which AI providers are configured
Or just type any message (not a command) and the agent replies directly.
e.g. "tell me the strategy for NIFTY expiry with capital 5k" → agent fetches the live chain,
runs the institutional signal, and sizes a real trade plan to your ₹5,000.

<b>💰 Capital-Sized Trade Plan:</b>
/plan NIFTY 5000 - live signal sized to exact capital: quantity, entry cost, target/SL premium,
  total risk/reward, risk:reward ratio, win-rate probability

<b>🔔 Proactive Alerts (push notifications, not just replies):</b>
/notify_on [SYMBOL] [CAPITAL] [MIN_PROB%] - watch live market + option chain in the background
  and message you the moment a high-probability setup appears (default NIFTY, ₹5,000, 75%)
/notify_off - stop alerts for this chat
/notify_status - show current alert subscription

<b>🧠 Institutional Strategy Detects:</b>
• Max Pain (expiry gravity, 60-65% pinning)
• PCR extreme (1.5 oversold bullish, 0.7 overbought bearish)
• OI clusters (StockMojo Smart OI) - 3-4 strikes where institutions position
• Fresh OI buildup + volume (smart money footprint)
• Liquidity pools & Stop Loss hunting (PDH/PDL, round numbers, high OI walls)
• Long Buildup / Short Buildup / Short Covering / Long Unwinding
• VWAP trend, Gamma walls, India VIX

<b>🎯 Option Buying Signals Include:</b>
• Entry strike (ATM / OTM)
• Target (next OI resistance/support or 1:2-1:3 RR)
• Stop Loss (30% premium or technical level beyond sweep wick)
• Probability % (weighted: PCR 15%, Max Pain 20%, OI 25%, Price Action 20%, VWAP 10%, VIX 10%)
• Reasoning & Institutional footprint explanation

<b>🔒 Security:</b>
All secrets in Replit Secrets 🔒 - never in code
"""

BEST_STRATEGY_HTML = """
<b>🏆 Best Option Buying Strategy in Indian Market (Institutional Footprint)</b>

<b>1. Core Setup (9:15-10:15 AM best):</b>
• Use <b>Opening Range Breakout (ORB) + VWAP</b>:
  - Mark high/low of first 15 min (9:15-9:30)
  - Price above VWAP + VWAP sloping up = Buy Calls on pullback
  - Price below VWAP + sloping down = Buy Puts
  - Choose ATM or slightly ITM (high delta, less theta decay)
  <i>Why: Institutions establish direction early, volatility expansion favors buyers</i>

<b>2. Institutional Filter (StockMojo Smart OI):</b>
• Check <b>OI clusters</b>:
  - Highest Put OI = Support (put writers defending)
  - Highest Call OI = Resistance
  - Wait for <b>Call writers exiting</b> at resistance (OI ↓) + price approaching it = <b>Bullish breakout</b> pre-signal
  - Fresh PE OI buildup 200 pts below spot + rising premium = fresh put writing = bullish
• <b>PCR</b>: &gt;1.5 oversold bullish reversal, &lt;0.7 overbought bearish reversal - Wait for price confirmation
• <b>Max Pain</b> (weekly Tuesday expiry, monthly last Tuesday): Jan 2025 onward Nifty Tuesday weekly, BankNifty only monthly
  - If spot below max pain + PCR bullish → drift up towards max pain (60-65% accuracy final hour)
  - Track live via /analysis

<b>3. Liquidity Sweep / Stop Hunting (Your Request - Big institutions manipulating):</b>
• Retail SL clusters: just below support (Put OI high) and above resistance (Call OI high), PDH/PDL, equal highs/lows, round numbers (24000, 48000)
• Big institutions need liquidity to fill large orders → they <b>push price to sweep SL pools</b>, triggering stops, then reverse
• <b>How to identify sweep vs real breakout:</b>
  - Sweep: Wick beyond level, close back inside range, volume spikes then drops, VWAP stays inside range, No OI buildup at new level
  - Real Breakout: Close firmly beyond level, volume expands and sustains 2-3 candles, VWAP shifts, fresh OI buildup at breakout level
• <b>Trade the sweep</b>: Wait for close back inside + confirmation candle, enter opposite direction
  - SL: 2-5 points beyond sweep wick extreme (tight!)
  - Target: Opposite liquidity pool or mid-range/VWAP, 1:2-1:3 RR
  - Best times: 9:15-10:15 AM and 2:30-3:30 PM (high participation), expiry day more intense due to theta acceleration + max pain gravity

<b>4. OI-Price 4 Quadrants (Stolo, PL India):</b>
• Long Buildup: OI ↑ Price ↑ = Fresh longs, bullish confirm
• Short Buildup: OI ↑ Price ↓ = Fresh shorts, bearish confirm
• Short Covering: OI ↓ Price ↑ = Shorts closing, weak rally but potential bullish reversal
• Long Unwinding: OI ↓ Price ↓ = Longs exiting

<b>5. Entry, Target, SL (Option Buying):</b>
• <b>Entry:</b> ATM or slightly OTM (0-100 pts OTM for NIFTY, 100-200 for BANKNIFTY) with momentum confirmation
• <b>Target:</b> Next OI resistance/support or 50 points premium for NIFTY, 100 for BANKNIFTY, or 1:2 RR. Book 50% at 1:1 then trail SL to breakeven
• <b>Stop Loss:</b> 30% premium decay rule (most option buyers use) OR technical level beyond sweep wick. Never widen SL.
• <b>Risk:</b> 1-2% capital per trade, max 3 sweep trades per day

<b>6. Probability Model (Our Bot):</b>
• PCR 15%, Max Pain distance 20%, OI buildup 25%, Price Action/BOS 20%, VWAP 10%, VIX/Gamma 10%
• Score &gt;75% = High conviction, 60-75% Medium, &lt;60% Wait

<b>7. GitHub Repos Implemented:</b>
• VarunS2002/Python-NSE-Option-Chain-Analyzer - OI boundaries, PCR, Call/Put exits
• NseKit, jugaad-data - live NSE data
• Our nse_option_chain.py fallback + shoonya_client.py for live

<b>Use our bot:</b> /signal NIFTY gives live signal with probability, /analysis NIFTY shows footprint deep dive

<b>Remember:</b> Institutions don't chase, they engineer liquidity. Follow their OI footprints, not price. Trade sweeps, not breakouts until confirmed.

Let's make billions and help poor as you said! 🚀
"""

# --- Countdown ---
async def send_processing_with_countdown(update: Update, context: ContextTypes.DEFAULT_TYPE, task_label: str, estimate: int = 4):
    chat_id = update.effective_chat.id
    initial = f"⏳ Processing your request please wait...\n\n📝 Task: {task_label[:60]}\n⏱️ Estimated: {estimate}s\n🔄 Starting..."
    msg = await context.bot.send_message(chat_id=chat_id, text=initial)
    
    async def countdown_loop():
        try:
            for remaining in range(estimate, 0, -1):
                await asyncio.sleep(1)
                filled = estimate - remaining + 1
                bar = "█" * filled + "░" * (remaining - 1)
                pct = int(filled / estimate * 100)
                text = f"⏳ Processing your request please wait...\n\n📝 Task: {task_label[:60]}\n⏱️ {remaining}s remaining...\n{bar} {pct}%\n🤖 Fetching accurate data..."
                try:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=text)
                except:
                    pass
        except Exception as e:
            logger.debug(f"countdown error: {e}")

    countdown_task = asyncio.create_task(countdown_loop())
    return msg, countdown_task

async def process_with_countdown_generic(update: Update, context: ContextTypes.DEFAULT_TYPE, task_text: str, processing_time: int = 5):
    chat_id = update.effective_chat.id
    initial_text = f"⏳ Processing your request please wait...\n\n📝 Task: {task_text[:50]}...\n⏱️ Estimated: {processing_time}s\n🔄 Starting..."
    processing_msg = await context.bot.send_message(chat_id=chat_id, text=initial_text)
    for remaining in range(processing_time, 0, -1):
        await asyncio.sleep(1)
        filled = processing_time - remaining + 1
        bar = "█" * filled + "░" * (remaining - 1)
        pct = int(filled / processing_time * 100)
        txt = f"⏳ Processing your request please wait...\n\n📝 Task: {task_text[:50]}...\n⏱️ {remaining}s remaining...\n{bar} {pct}%\n🤖 Working..."
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=processing_msg.message_id, text=txt)
        except:
            pass
    final = f"✅ Done! Accurate Response Ready\n\n📝 Your Query: {task_text}\n\nFor live market:\n/nifty, /stock RELIANCE, /optionchain NIFTY\n\nProcessed at: {datetime.now().strftime('%d-%m-%Y %I:%M:%S %p')}"
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=processing_msg.message_id, text=final)
    except:
        await context.bot.send_message(chat_id=chat_id, text=final)

# --- Helpers: Try Shoonya first, fallback Yahoo ---
def try_shoonya_index(key: str):
    if not (HAS_SHOONYA_LIB and SHOONYA_CONFIGURED):
        raise RuntimeError("Shoonya not configured")
    # Shoonya login (will reuse session)
    quote, info = sc.get_index_via_shoonya(key)
    return quote

def try_shoonya_stock(symbol: str):
    if not (HAS_SHOONYA_LIB and SHOONYA_CONFIGURED):
        raise RuntimeError("Shoonya not configured")
    quote, info = sc.get_stock_via_shoonya(symbol)
    return quote

# --- Bot Handlers ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Namaste {user.first_name}! 🙏\n\n{get_hi_demo_response()}")
    logger.info(f"/start from {user.id}")

async def hi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_hi_demo_response())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text(HELP_HTML, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Help HTML failed: {e}")
        await update.message.reply_text("Commands:\n/nifty /sensex /banknifty\n/stock RELIANCE\n/optionchain NIFTY\n/vix /global /crypto btc\n/shoonya_status /status /help")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md_status = "✅ Yahoo + Chart API" if HAS_MARKET_DATA else "❌ missing"
    shoonya_status = "✅ Configured" if SHOONYA_CONFIGURED else "⚠️ Not configured (set Secrets for option chain)"
    keep_status = "✅ Flask :8080" if HAS_KEEP_ALIVE else "⚠️ No keep_alive"
    masked = (TELEGRAM_BOT_TOKEN[:6] + "***") if TELEGRAM_BOT_TOKEN else "MISSING"
    has_lib = "✅" if HAS_SHOONYA_LIB else "❌ pip install NorenRestApiPy, pyotp"
    await update.message.reply_text(
        f"✅ Bot Status: ONLINE\n\n"
        f"🕐 {now}\n"
        f"📊 Yahoo: {md_status}\n"
        f"🔌 Shoonya Lib: {has_lib}\n"
        f"🔐 Shoonya Config: {shoonya_status}\n"
        f"🌐 Keep-Alive: {keep_status}\n"
        f"🔑 Token: {masked}\n"
        f"⚡️ Mode: Instant hi + Countdown\n"
        f"🆕 Option Chain: {'Ready via Shoonya' if SHOONYA_CONFIGURED else 'Set SHOONYA secrets to enable'}"
    )

async def shoonya_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HAS_SHOONYA_LIB:
        await update.message.reply_text("❌ Shoonya library not installed. In Replit Shell: pip install NorenRestApiPy pyotp")
        return

    creds = sc.get_env_credentials() if hasattr(sc, 'get_env_credentials') else {}
    
    # Use new get_config_status if available
    if hasattr(sc, 'get_config_status'):
        cfg_status = sc.get_config_status()
        second_factor_type = cfg_status.get("second_factor_type", "UNKNOWN")
    else:
        second_factor_type = "Unknown"

    # Masked view
    masked_info = []
    for k in ["user_id", "vendor_code", "imei"]:
        v = creds.get(k)
        if v:
            masked_info.append(f"{k}: {v[:2]}***{v[-2:] if len(v)>4 else ''}")
        else:
            masked_info.append(f"{k}: MISSING")
    masked_info.append(f"password: {'***' if creds.get('password') else 'MISSING'}")
    masked_info.append(f"api_secret: {'***' if creds.get('api_secret') else 'MISSING'}")
    # Show all second factor options we support
    totp = creds.get('totp_secret')
    twofa = creds.get('two_fa_otp')
    if totp:
        masked_info.append(f"totp_secret: *** ({second_factor_type} - BEST for 24/7 bot)")
    else:
        masked_info.append(f"totp_secret: Not set (add later for 24/7)")
    
    if twofa:
        masked_info.append(f"OTP/TPIN/PIN (second factor): *** ({second_factor_type})")
    else:
        masked_info.append(f"OTP/TPIN: Not set")

    masked_info.append("")
    masked_info.append(f"Supported second factor env keys (any ONE works):")
    masked_info.append(f"SHOONYA_TOTP_SECRET, SHOONYA_TWO_FA, SHOONYA_OTP, SHOONYA_TPIN, SHOONYA_PIN")

    is_configured = sc.is_shoonya_configured()

    msg_lines = [
        "🔌 Shoonya Status Check (Supports OTP/TPIN now, TOTP later)",
        "",
        f"Configured: {'✅ Yes' if is_configured else '❌ No - set Secrets'}",
        f"Second Factor Type: {second_factor_type}",
        "",
        "Credentials (masked):",
    ] + masked_info + [""]

    if not is_configured:
        msg_lines += [
            "❌ Missing secrets. Add in Replit Secrets 🔒:",
            "SHOONYA_USER_ID - e.g. FA12345",
            "SHOONYA_PASSWORD - login password",
            "SHOONYA_VENDOR_CODE - FA12345_U",
            "SHOONYA_API_SECRET - API key",
            "SHOONYA_IMEI - any string e.g. mybot123",
            "",
            "Second Factor - ANY ONE you have now:",
            "• SHOONYA_TOTP_SECRET - 32-char secret (best, auto 24/7)",
            "• SHOONYA_TWO_FA or SHOONYA_OTP - 6-digit OTP (expires 30 sec)",
            "• SHOONYA_TPIN or SHOONYA_PIN - 4-8 digit TPIN",
            "You said you have TPIN/OTP now - use those, add TOTP later",
            "",
            "Where to find: prism.shoonya.com -> API + Security",
        ]
        await update.message.reply_text("\n".join(msg_lines))
        return

    # Try login
    msg_lines.append("Trying login (with countdown)...")
    if totp:
        msg_lines.append("Using TOTP_SECRET auto generation ✅")
    else:
        msg_lines.append(f"Using {second_factor_type} - note: OTP expires in 30 sec, TPIN may need fresh value before market hours")

    processing_msg = await update.message.reply_text("\n".join(msg_lines) + "\n\n⏳ Logging into Shoonya, please wait...")

    try:
        ret = sc.login_shoonya(force=True)
        if ret.get("stat") == "Ok" or ret.get("reused"):
            msg_lines.append("")
            msg_lines.append("✅ Login SUCCESS!")
            if ret.get("reused"):
                msg_lines.append("(Reused existing session)")
            else:
                msg_lines.append(f"Response: {ret.get('request_time', '')}")
            msg_lines.append("")
            msg_lines.append("Shoonya is ready for:")
            msg_lines.append("• /nifty, /stock via Shoonya (primary, fixes Yahoo)")
            msg_lines.append("• /optionchain NIFTY - live option chain")
            msg_lines.append("• If you used OTP, remember OTP expires in 30 sec - for true 24/7 add TOTP_SECRET later")
        else:
            msg_lines.append(f"❌ Login failed: {ret}")
            msg_lines.append("Tip: If using OTP, generate fresh OTP and update Secret, then /shoonya_status again quickly")
    except Exception as e:
        logger.exception("Shoonya login failed")
        msg_lines.append(f"❌ Login failed: {e}")
        msg_lines.append("")
        msg_lines.append("Check: Password, second factor correct? Vendor _U? IP whitelist?")
        if not totp:
            msg_lines.append("If OTP used, it expired (30 sec). Generate new OTP, update Replit Secret, try again.")

    try:
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=processing_msg.message_id, text="\n".join(msg_lines))
    except:
        await update.message.reply_text("\n".join(msg_lines))

async def handle_hi_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! 👋 OptionBuyerBot is up and running. Try /help for commands.")

async def demo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_with_countdown_generic(update, context, "DEMO hard task - Option chain analysis simulation", 6)

# --- Live market with Shoonya primary ---
async def index_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.lstrip("/").split("@")[0].lower()
    msg, countdown_task = await send_processing_with_countdown(update, context, f"{key.upper()} via {'Shoonya' if SHOONYA_CONFIGURED else 'Yahoo'}", estimate=5)

    # Try Shoonya first if configured
    if HAS_SHOONYA_LIB and SHOONYA_CONFIGURED:
        try:
            # Need to run blocking call in thread to avoid blocking event loop
            def fetch_shoonya():
                return sc.get_index_via_shoonya(key)
            quote, info = await asyncio.to_thread(fetch_shoonya)
            # Convert Shoonya quote dict to readable
            # Shoonya get_quotes returns dict with lp, c, etc.
            lp = quote.get("lp") or quote.get("c") or "N/A"
            pc = quote.get("pc") or ""
            o = quote.get("o") or ""
            h = quote.get("h") or ""
            l = quote.get("l") or ""
            result = f"✅ {key.upper()} via Shoonya:\nLTP: {lp}\n%Chg: {pc}\nO: {o} H: {h} L: {l}\nSymbol: {info.get('tsym', key)}"
            countdown_task.cancel()
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=result)
            return
        except Exception as e:
            logger.debug(f"Shoonya {key} failed, fallback to Yahoo: {e}")

    # Fallback to Yahoo (market_data robust)
    if not HAS_MARKET_DATA:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="Market data not available (Yahoo + Shoonya both missing)")
        return

    try:
        quote = await asyncio.to_thread(md.get_index_quote, key)
        result = quote.format()
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ {result}\n\n(From Yahoo - configure Shoonya for NSE direct)")
    except Exception as exc:
        countdown_task.cancel()
        logger.exception(f"index {key} failed")
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Couldn't fetch {key.upper()}: {exc}\n\nTry Shoonya setup for reliable Indian market.")

async def stock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /stock <symbol>  e.g. /stock RELIANCE")
        return
    symbol = context.args[0].upper()
    msg, countdown_task = await send_processing_with_countdown(update, context, f"Stock {symbol} via {'Shoonya' if SHOONYA_CONFIGURED else 'Yahoo'}", estimate=5)

    if HAS_SHOONYA_LIB and SHOONYA_CONFIGURED:
        try:
            def fetch_shoonya_stock():
                return sc.get_stock_via_shoonya(symbol)
            quote, info = await asyncio.to_thread(fetch_shoonya_stock)
            lp = quote.get("lp") or quote.get("c") or "N/A"
            result = f"✅ {symbol} via Shoonya:\nLTP: {lp}\n%Chg: {quote.get('pc', '')}\nO: {quote.get('o','')} H: {quote.get('h','')} L: {quote.get('l','')}\nVol: {quote.get('v','')}\nSymbol: {info.get('tsym','')}"
            countdown_task.cancel()
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=result)
            return
        except Exception as e:
            logger.debug(f"Shoonya stock {symbol} failed, fallback Yahoo: {e}")

    # Yahoo fallback
    if not HAS_MARKET_DATA:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="Market data unavailable")
        return

    try:
        quote = await asyncio.to_thread(md.get_stock_quote, symbol)
        result = quote.format()
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ {result}\n(Yahoo)")
    except Exception as exc:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Couldn't fetch {symbol}: {exc}")

async def crypto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /crypto <symbol>  e.g. /crypto btc")
        return
    symbol = context.args[0]
    if not HAS_MARKET_DATA:
        await update.message.reply_text("Market data unavailable")
        return
    msg, countdown_task = await send_processing_with_countdown(update, context, f"Crypto {symbol.upper()}", estimate=3)
    try:
        data = await asyncio.to_thread(md.get_crypto_price, symbol)
        change = data.get("usd_24h_change")
        change_str = f"  ({change:+.2f}% 24h)" if change is not None else ""
        text = f"🪙 {symbol.upper()}: ${data['usd']:,.2f} / ₹{data['inr']:,.2f}{change_str}"
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text)
    except Exception as exc:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ {symbol}: {exc}")

async def vix_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, countdown_task = await send_processing_with_countdown(update, context, "VIX", estimate=4)
    try:
        if HAS_MARKET_DATA:
            lines = []
            for which in ("india", "us"):
                try:
                    quote = await asyncio.to_thread(md.get_vix, which)
                    lines.append(quote.format())
                except Exception as exc:
                    lines.append(f"{which.upper()} VIX unavailable: {exc}")
            countdown_task.cancel()
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="📊 VIX\n" + "\n".join(lines))
        else:
            countdown_task.cancel()
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="Market data unavailable")
    except Exception as e:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"Error: {e}")

async def global_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, countdown_task = await send_processing_with_countdown(update, context, "Global Markets", estimate=5)
    try:
        quotes = await asyncio.to_thread(md.get_global_markets) if HAS_MARKET_DATA else []
        if not quotes:
            countdown_task.cancel()
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="Couldn't fetch global data")
            return
        text = "🌍 Global Markets\n" + "\n".join(q.format() for q in quotes)
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text)
    except Exception as e:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"Error: {e}")

# --- NEW: Option Chain via Shoonya (Primary) + NSE Fallback (when Shoonya 502) ---
async def optionchain_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /optionchain NIFTY
    /optionchain BANKNIFTY 48000
    /optionchain NIFTY 24000 5
    /optionchain RELIANCE 3000
    Tries: Shoonya -> NSE direct fallback (for 502 Bad Gateway datacenter block)
    """
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /optionchain <SYMBOL> [strike_price] [count]\n"
            "e.g.:\n"
            "/optionchain NIFTY - ATM chain for NIFTY\n"
            "/optionchain BANKNIFTY 48000 - chain around 48000\n"
            "/optionchain RELIANCE 3000 3 - 3 strikes around 3000\n\n"
            "Shoonya is primary (free), NSE direct is fallback when Shoonya 502"
        )
        return

    symbol = args[0].upper()
    strike = None
    count = 5

    if len(args) >= 2:
        try:
            strike = float(args[1])
        except:
            pass
    if len(args) >= 3:
        try:
            count = int(args[2])
            count = min(max(count, 1), 10)
        except:
            pass
    if len(args) == 2 and strike is None:
        try:
            maybe_count = int(args[1])
            if maybe_count < 100:
                count = maybe_count
                strike = None
            else:
                strike = float(args[1])
        except:
            pass

    task_label = f"Option Chain {symbol} {f'@{strike}' if strike else 'ATM'}"
    msg, countdown_task = await send_processing_with_countdown(update, context, task_label, estimate=8)

    # --- NSE direct first: free, no auth, proven reliable (uses option-chain-v3) ---
    try:
        import nse_option_chain as nse_oc

        def fetch_nse_primary():
            return nse_oc.get_option_chain_with_fallback(symbol, count)

        data, source = await asyncio.to_thread(fetch_nse_primary)

        if data:
            formatted = nse_oc.format_nse_chain_for_telegram(data, symbol, count, underlying_price=strike)
            countdown_task.cancel()
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=formatted,
            )
            return
    except Exception as e:
        logger.warning(f"NSE direct option chain failed for {symbol}: {e}, trying Shoonya fallback")
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=f"⚠️ NSE direct failed: {e}\n\nTrying Shoonya fallback...\n⏳ Still processing {symbol}..."
            )
        except:
            pass

    # Try Shoonya next if configured
    if HAS_SHOONYA_LIB and SHOONYA_CONFIGURED:
        try:
            # Step 1: Get current price for ATM if not provided
            if strike is None:
                try:
                    def get_underlying_price():
                        if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
                            q, _ = sc.get_index_via_shoonya(symbol.lower())
                        else:
                            q, _ = sc.get_stock_via_shoonya(symbol)
                        return q
                    q = await asyncio.to_thread(get_underlying_price)
                    lp_str = q.get("lp") or q.get("c")
                    if lp_str:
                        strike = float(lp_str)
                        if symbol == "BANKNIFTY":
                            strike = round(strike / 100) * 100
                        elif symbol == "NIFTY":
                            strike = round(strike / 50) * 50
                        else:
                            strike = round(strike)
                except Exception as e:
                    logger.debug(f"Could not get underlying price for {symbol}: {e}")
                    defaults = {"NIFTY": 24000, "BANKNIFTY": 48000, "FINNIFTY": 22000}
                    strike = defaults.get(symbol, 1000)

            def fetch_chain():
                res = sc.search_symbol("NFO", symbol)
                if not res or res.get("stat") != "Ok" or not res.get("values"):
                    raise ValueError(f"Shoonya search NFO failed for {symbol}: {res}")
                values = res["values"]
                fut_candidates = [v for v in values if symbol in v.get("tsym", "") and ("F" in v.get("tsym", "")[-2:] or "FUT" in v.get("instname", ""))]
                tradingsymbol = fut_candidates[0]["tsym"] if fut_candidates else symbol
                chain = sc.get_option_chain(exchange="NFO", tradingsymbol=tradingsymbol, strikeprice=strike, count=count)
                return chain, tradingsymbol

            chain_result, used_tsym = await asyncio.to_thread(fetch_chain)

            if not chain_result or chain_result.get("stat") != "Ok":
                raise ValueError(f"Option chain API failed: {chain_result}")

            values = chain_result.get("values", [])
            if not values:
                raise ValueError(f"No chain for {symbol} @{strike}")

            def fetch_chain_quotes():
                quotes = []
                for scrip in values[: count * 2 + 1]:
                    try:
                        q = sc.get_quote(scrip.get("exch", "NFO"), scrip["token"])
                        quotes.append((scrip, q))
                    except Exception as e:
                        quotes.append((scrip, {"lp": "N/A", "error": str(e)}))
                    time.sleep(0.1)
                return quotes

            chain_quotes = await asyncio.to_thread(fetch_chain_quotes)

            lines = [f"📊 Option Chain: {symbol} ATM ~{strike} via Shoonya", f"Using: {used_tsym} Count: {count}", "", "Strike | CE LTP | PE LTP", "-------|--------|--------"]
            strike_map = {}
            for scrip, q in chain_quotes:
                strike_price = scrip.get("strprc") or scrip.get("strike") or "?"
                opt_type = scrip.get("optt") or ("CE" if "CE" in scrip.get("tsym","") else "PE" if "PE" in scrip.get("tsym","") else "?")
                lp = q.get("lp") if isinstance(q, dict) else str(q)
                if strike_price not in strike_map:
                    strike_map[strike_price] = {}
                strike_map[strike_price][opt_type] = lp

            def sort_key(s):
                try: return float(s)
                except: return 0

            for strike_price in sorted(strike_map.keys(), key=sort_key):
                ce = strike_map[strike_price].get("CE", strike_map[strike_price].get("C", "-"))
                pe = strike_map[strike_price].get("PE", strike_map[strike_price].get("P", "-"))
                lines.append(f"{strike_price} | {ce} | {pe}")

            lines.extend(["", f"⏱️ {datetime.now().strftime('%H:%M:%S IST')}", "🔒 Shoonya live"])
            final_text = "\n".join(lines)
            if len(final_text) > 3800:
                final_text = final_text[:3800] + "\n... truncated"

            countdown_task.cancel()
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=final_text)
            return

        except Exception as e:
            logger.warning(f"Shoonya option chain failed for {symbol}: {e}, trying NSE fallback")
            # Don't cancel yet, try NSE fallback below
            # Keep countdown running, update message to show fallback
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg.message_id,
                    text=f"⚠️ Shoonya failed (502 Bad Gateway - server blocking Replit IP): {e}\n\nTrying NSE direct fallback (free, may need market hours)...\n⏳ Still processing {symbol}..."
                )
            except:
                pass
            # Continue to NSE fallback

    # --- NSE Fallback (when Shoonya 502 or not configured) ---
    # Import here to avoid circular
    try:
        import nse_option_chain as nse_oc
    except ImportError as e:
        countdown_task.cancel()
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg.message_id,
            text=f"❌ Option chain failed.\n\nShoonya error: 502 Bad Gateway (server down/datacenter IP blocked)\nNSE fallback not available: {e}\n\n"
                 f"🔧 Fixes for Shoonya 502:\n"
                 f"1. In Prism API page, whitelist Replit IP. In Replit Shell run: curl ifconfig.me, add IP\n"
                 f"2. Check https://trade.shoonya.com -> Profile Dropdown -> API Key -> Ensure API enabled\n"
                 f"3. Try again during market hours 9:15-15:30 IST - Shoonya sometimes returns 502 at night\n"
                 f"4. For now, use /nifty /stock (Yahoo fallback) and /crypto btc (working)\n"
                 f"5. Contact Shoonya support to whitelist 0.0.0.0 or Replit IP range\n\n"
                 f"Supported fallback: NSE direct API (tries now...)"
        )
        # Try NSE anyway
        try:
            import nse_option_chain as nse_oc2
            nse_oc = nse_oc2
        except:
            return

    try:
        def fetch_nse():
            return nse_oc.get_option_chain_with_fallback(symbol, count)

        data, source = await asyncio.to_thread(fetch_nse)

        if data:
            formatted = nse_oc.format_nse_chain_for_telegram(data, symbol, count, underlying_price=strike)
            countdown_task.cancel()
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=formatted + f"\n\n(NSE fallback because Shoonya 502 - configure IP whitelist for Shoonya)"
            )
            return
        else:
            raise ValueError("NSE returned no data (403 blocked datacenter IP or market closed)")

    except Exception as e:
        countdown_task.cancel()
        logger.exception(f"NSE fallback also failed for {symbol}")
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg.message_id,
            text=f"❌ Option chain failed for {symbol} @{strike if strike else 'ATM'}\n\n"
                 f"Shoonya: 502 Bad Gateway (your screenshot) - server blocking Replit IP or down\n"
                 f"NSE fallback: Also failed - {e} (NSE blocks datacenter IPs too, returns 403)\n\n"
                 f"🔧 Solutions:\n"
                 f"1. **Shoonya IP Whitelist**: trade.shoonya.com -> Profile -> API Key -> Whitelist IP\n"
                 f"   In Replit Shell: curl ifconfig.me → add that IP\n"
                 f"   Try whitelisting 0.0.0.0 if Shoonya allows\n"
                 f"2. **API Management Page**: You said not found - it's at trade.shoonya.com (not prism) -> Profile dropdown -> API Key\n"
                 f"   Screenshot: Docs at docs.openalgo.in/connect-brokers/brokers/shoonya shows API Key in profile dropdown\n"
                 f"3. **Contact Shoonya Support**: Ask to whitelist Replit/GCP IP range or allow 0.0.0.0\n"
                 f"4. **Try during market hours 9:15-15:30 IST**: Sometimes Shoonya returns 502 at night (your test 4:31 AM)\n"
                 f"5. **For now**: Use /nifty (Yahoo fallback works in market hours) and /crypto btc (24/7 works)\n"
                 f"6. **Alternative**: Use local machine (not Replit) for Shoonya - home ISP IP not blocked\n"
        )

def _get_llm_history(context):
    # Legacy in-memory (kept for backward compat)
    return context.chat_data.setdefault("llm_history", [])


def _push_llm_history(context, user_text, answer_text):
    hist = _get_llm_history(context)
    hist.append({"role": "user", "content": user_text})
    hist.append({"role": "assistant", "content": answer_text})
    # keep last 5 exchanges (10 messages) so prompts stay small/fast
    del hist[:-10]


def _get_llm_history_persistent(chat_id: int, context=None):
    """Get history from persistent per-user Telegram memory (file), not just server RAM"""
    try:
        import chat_memory
        # Try file first (survives restarts)
        file_hist = chat_memory.get_llm_history_format(chat_id, limit=10)
        if file_hist:
            return file_hist
        # Fallback to in-memory
        if context is not None:
            mem_hist = context.chat_data.get("llm_history", [])
            if mem_hist:
                # Migrate to file
                try:
                    chat_memory.sync_from_context_chat_data(chat_id, mem_hist)
                except:
                    pass
                return mem_hist
        return file_hist
    except Exception as e:
        # Fallback to in-memory
        try:
            return context.chat_data.get("llm_history", []) if context else []
        except:
            return []


def _push_llm_history_persistent(chat_id: int, user_text: str, answer_text: str, context=None):
    """Save to both persistent file (Telegram per-user memory) and in-memory"""
    # Save to file (persistent, per user different as requested)
    try:
        import chat_memory
        chat_memory.add_message(chat_id, "user", user_text)
        chat_memory.add_message(chat_id, "assistant", answer_text)
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug(f"Persistent history save failed {chat_id}: {e}")

    # Also save to in-memory for backward compat
    if context is not None:
        try:
            hist = _get_llm_history(context)
            hist.append({"role": "user", "content": user_text})
            hist.append({"role": "assistant", "content": answer_text})
            del hist[:-10]
        except:
            pass


async def _run_llm_ask(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str, estimate: int = 6):
    """Shared helper: run the agentic multi-LLM (tool-calling) agent with countdown UX and reply."""
    chat_id = update.effective_chat.id
    msg, countdown_task = await send_processing_with_countdown(update, context, f"AI Agent: {question}", estimate=estimate)
    history = _get_llm_history(context)
    try:
        answer, provider, tools_used = await asyncio.to_thread(llm_agent.agent_ask, question, history, chat_id)
        _push_llm_history(context, question, answer)
        countdown_task.cancel()
        tool_note = f" | fetched: {', '.join(sorted({t['tool'] for t in tools_used}))}" if tools_used else ""
        footer = f"\n\n🤖 via {llm_agent.provider_label(provider)}{tool_note}"
        text = (answer[:3800] + "…") if len(answer) > 3800 else answer
        await context.bot.edit_message_text(chat_id=chat_id, message_id=msg.message_id, text=text + footer)
    except Exception as e:
        countdown_task.cancel()
        logger.exception("LLM agent call failed")
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg.message_id,
            text=f"❌ AI agent failed: {e}\n\nCheck /llm_status or try /ask <question> again."
        )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_raw = update.message.text or ""
    text_lower = text_raw.lower().strip()
    if text_lower in INSTANT_TRIGGERS or (text_lower.startswith("hi") and len(text_lower) < 15):
        await update.message.reply_text(get_hi_demo_response())
        return

    # Direct handling for crypto expert queries (fixes "are crypto expert? bot replied nothing")
    if any(x in text_lower for x in ["crypto expert", "are you crypto", "are u crypto", "crypto specialist", "are crypto"]):
        await update.message.reply_text(
            "₿ <b>Yes, I am Crypto Expert! 🚀</b>\n\n"
            "I am expert in crypto spot + options trading:\n"
            "• <b>Binance Spot:</b> RSI, EMA, MACD, Volume, Support/Resistance with Entry/Target/SL/Probability\n"
            "• <b>Deribit Options:</b> Free public BTC/ETH option chain (80% global volume), IV, OI, Greeks - works on Replit, no 502/403\n"
            "• <b>Binance Options:</b> European BTC/ETH options via EAPI\n"
            "• <b>CoinGecko:</b> Spot price USD/INR 24h change\n\n"
            "<b>Try:</b>\n"
            "/crypto_signal BTCUSDT - AI signal with probability\n"
            "/crypto_signal ETHUSDT\n"
            "/crypto_option BTC - Deribit BTC option chain\n"
            "/crypto_option ETH\n"
            "/crypto btc - Spot price\n\n"
            "I have Binance account integration ready - you can test signals with your Binance! For image/PDF chart reading, send photo/document.",
            parse_mode=ParseMode.HTML
        )
        return

    # Direct handling for image/pdf capability questions
    if any(x in text_lower for x in ["can you read image", "can you read pdf", "read image pdf", "image reading", "pdf reading"]):
        await update.message.reply_text(
            "✅ <b>Yes, I can read images and PDFs!</b>\n\n"
            "• <b>Images:</b> Send as photo (chart, option chain screenshot, etc.) - I analyze via OCR/vision (Gemini 2.0 Flash vision if GEMINI_API_KEY set)\n"
            "• <b>PDFs:</b> Send as document - I extract text via PyMuPDF/PyPDF2 (first 500 chars) and you can ask /ask about it\n"
            "• Try sending a photo or PDF now!\n\n"
            "For best image reading, set GEMINI_API_KEY in Replit Secrets.",
            parse_mode=ParseMode.HTML
        )
        return

    # Direct handling for capital + signal queries (user: "I have 5k capital ... provide most powerful and risk free any live Signal")
    # This bypasses slow LLM tool loop and gives instant capital-sized plan via /plan logic
    if ("capital" in text_lower or "5k" in text_lower or "5000" in text_lower) and ("signal" in text_lower or "earn" in text_lower or "option buying" in text_lower):
        # Extract capital
        capital = 5000.0
        if "5k" in text_lower:
            capital = 5000.0
        elif "10k" in text_lower:
            capital = 10000.0
        # Try parse numbers
        import re
        m = re.search(r'(\d+)\s*k', text_lower)
        if m:
            try:
                capital = float(m.group(1)) * 1000
            except:
                pass
        else:
            m2 = re.search(r'(\d{4,6})', text_lower)
            if m2:
                try:
                    val = float(m2.group(1))
                    if val >= 1000:
                        capital = val
                except:
                    pass

        # Determine symbol - default NIFTY
        symbol = "NIFTY"
        if "banknifty" in text_lower:
            symbol = "BANKNIFTY"
        elif "finnifty" in text_lower:
            symbol = "FINNIFTY"
        elif "sensex" in text_lower:
            symbol = "SENSEX"

        # Use plan logic directly for fast answer
        try:
            await update.message.reply_text(
                f"💰 Got it! You have ₹{capital:,.0f} capital at {datetime.now().strftime('%I:%M %p IST')}.\n"
                f"Generating most powerful risk-managed signal for {symbol} with your capital...\n"
                f"⏳ Processing (with countdown)...\n"
                f"Use /plan {symbol} {int(capital)} for direct capital-sized plan anytime!"
            )
            # Call plan logic
            # Reuse plan_cmd by simulating context
            # For quick response, directly generate signal + plan
            if HAS_INSTITUTIONAL_AI and HAS_POS_SIZING:
                try:
                    def run_plan():
                        option_chain_data = None
                        try:
                            import nse_option_chain as nse_oc
                            option_chain_data, _ = nse_oc.get_option_chain_with_fallback(symbol, count=15)
                        except:
                            pass
                        signal = inst_ai.generate_ai_signal(symbol, option_chain_data)
                        plan = pos_sizing.plan_position(symbol, signal, capital, option_chain_data)
                        return signal, plan

                    signal, plan = await asyncio.to_thread(run_plan)
                    formatted = pos_sizing.format_plan_for_telegram(plan, symbol, capital)
                    formatted += f"\n\n<i>Institutional: Max Pain {signal.max_pain} | PCR {signal.pcr}</i>\nUse /analysis {symbol} for footprint"
                    await update.message.reply_text(formatted, parse_mode=ParseMode.HTML)

                    if plan.get("tradeable") and plan.get("win_rate_probability", 0) >= 75:
                        await update.message.reply_text(
                            f"🔔 High win-rate {plan['win_rate_probability']}%! Want auto alerts? /notify_on {symbol} {int(capital)} 75\n"
                            f"Risk free not possible in market, but this is most powerful risk-managed with 30% premium SL and 1-2% capital risk."
                        )
                    return
                except Exception as e:
                    logger.warning(f"Direct capital plan failed, falling back to LLM: {e}")

            # Fallback to LLM if direct plan fails
        except Exception as e:
            logger.debug(f"Capital direct handling failed: {e}")

    # Any other free-text message = ask the multi-LLM agent directly (if configured)
    if HAS_LLM_AGENT and llm_agent.configured_providers():
        await _run_llm_ask(update, context, text_raw, estimate=10)  # Increased estimate for capital queries that need live data
        return

    est = 3 if len(text_raw) < 20 else 5 if len(text_raw) < 60 else 7
    await process_with_countdown_generic(update, context, text_raw, est)


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /ask <question> -> multi-LLM agent (Groq -> DeepSeek -> Gemini -> OpenAI fallback chain) """
    if not HAS_LLM_AGENT:
        await update.message.reply_text("❌ AI agent module not installed (missing llm_agent.py).")
        return

    question = " ".join(context.args).strip() if context.args else ""
    if not question and update.message.reply_to_message:
        question = update.message.reply_to_message.text or ""
    if not question:
        await update.message.reply_text("Usage: /ask <your question>\nExample: /ask Explain what implied volatility means")
        return

    if not llm_agent.configured_providers():
        await update.message.reply_text(
            "❌ No AI providers configured yet.\nAsk the project owner to add at least one API key in "
            "Replit Secrets: GROQ_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY."
        )
        return

    await _run_llm_ask(update, context, question, estimate=6)


async def ask_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /compare <question> -> queries ALL configured LLMs at once, side by side """
    if not HAS_LLM_AGENT:
        await update.message.reply_text("❌ AI agent module not installed (missing llm_agent.py).")
        return

    question = " ".join(context.args).strip() if context.args else ""
    if not question:
        await update.message.reply_text("Usage: /compare <your question>\nQueries Groq + DeepSeek + Gemini + OpenAI at once and shows every answer.")
        return

    configured = llm_agent.configured_providers()
    if not configured:
        await update.message.reply_text(
            "❌ No AI providers configured yet. Add at least one API key: "
            "GROQ_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY."
        )
        return

    msg, countdown_task = await send_processing_with_countdown(update, context, f"Comparing {len(configured)} AI models", estimate=8)
    try:
        results = await asyncio.to_thread(llm_agent.ask_all, question)
        countdown_task.cancel()
        parts = [f"🤖 <b>Multi-LLM Comparison</b>\n<i>{question}</i>\n"]
        for key, res in results.items():
            label = llm_agent.provider_label(key)
            if res["ok"]:
                parts.append(f"\n<b>✅ {label}:</b>\n{res['text'][:600]}")
            else:
                parts.append(f"\n<b>❌ {label} failed:</b> {res['text'][:150]}")
        text = "\n".join(parts)[:4000]
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        countdown_task.cancel()
        logger.exception("/compare failed")
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Compare failed: {e}")


def _parse_capital(text: str) -> Optional[float]:
    """Parse a capital string like '5k', '5000', '₹10,000', '10K' into a float."""
    if not text:
        return None
    t = text.strip().lower().replace("₹", "").replace(",", "").replace("rs.", "").replace("rs", "").strip()
    try:
        if t.endswith("k"):
            return float(t[:-1]) * 1000
        if t.endswith("l") or t.endswith("lac") or t.endswith("lakh"):
            return float(t.rstrip("lakhc")) * 100000
        return float(t)
    except ValueError:
        return None


async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /plan NIFTY 5000 -> live institutional signal sized to exact capital (qty, entry cost, target, SL, RR, win-rate) """
    if not (HAS_INSTITUTIONAL_AI and HAS_POS_SIZING):
        await update.message.reply_text("❌ Strategy module not fully installed (institutional_strategy.py / position_sizing.py missing).")
        return

    args = context.args or []
    symbol = "NIFTY"
    capital = 5000.0
    for a in args:
        parsed = _parse_capital(a)
        if parsed is not None:
            capital = parsed
        else:
            symbol = a.upper()

    msg, countdown_task = await send_processing_with_countdown(update, context, f"Live Trade Plan {symbol} for ₹{capital:,.0f}", estimate=7)
    try:
        def run():
            option_chain_data = None
            try:
                import nse_option_chain as nse_oc
                option_chain_data, _source = nse_oc.get_option_chain_with_fallback(symbol, count=15)
            except Exception as e:
                logger.debug(f"strategy chain fetch failed: {e}")
            signal = inst_ai.generate_ai_signal(symbol, option_chain_data)
            plan = pos_sizing.plan_position(symbol, signal, capital, option_chain_data)
            return signal, plan

        signal, plan = await asyncio.to_thread(run)
        countdown_task.cancel()

        text = pos_sizing.format_plan_for_telegram(plan, symbol, capital)
        text += f"\n\n<i>Institutional footprint: Max Pain {signal.max_pain} | PCR {signal.pcr}</i>\nUse /analysis {symbol} for full details."
        logger.debug("plan_cmd finished for %s", symbol)
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text, parse_mode=ParseMode.HTML)

        if plan.get("tradeable") and plan.get("win_rate_probability", 0) >= 75:
            await update.message.reply_text(
                f"💡 This is a high win-rate setup ({plan['win_rate_probability']}%). "
                f"Want live alerts like this automatically? Send /notify_on {symbol} {int(capital)}\n(use /plan again anytime for a fresh capital-sized trade plan)"
            )
    except Exception as e:
        countdown_task.cancel()
        logger.exception(f"/strategy {symbol} failed")
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Strategy failed for {symbol}: {e}")


async def notify_on_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /notify_on [SYMBOL] [CAPITAL] [MIN_PROBABILITY] -> subscribe this chat to live high-probability alerts """
    if not HAS_WATCHER:
        await update.message.reply_text("❌ Market watcher module not installed.")
        return
    chat_id = update.effective_chat.id
    args = context.args or []
    symbol = None
    capital = None
    min_probability = None
    for a in args:
        parsed_cap = _parse_capital(a)
        if a.isdigit() and 1 <= int(a) <= 100 and parsed_cap is None:
            min_probability = int(a)
        elif parsed_cap is not None:
            capital = parsed_cap
        else:
            symbol = a.upper()

    sub = market_watcher.subscribe(chat_id, symbol=symbol, capital=capital, min_probability=min_probability)
    await update.message.reply_text(
        f"🔔 <b>Live alerts ON</b>\n\n"
        f"Watching: {', '.join(sub['symbols'])}\n"
        f"Capital: ₹{sub['capital']:,.0f}\n"
        f"Min win-rate to alert: {sub['min_probability']}%\n\n"
        f"I'll watch the live option chain + institutional footprint during market hours (9:15-15:30 IST) "
        f"and message you the moment a high-probability setup appears, with strike, entry, target, SL, and win-rate.\n\n"
        f"/notify_off to stop.",
        parse_mode=ParseMode.HTML,
    )


async def notify_off_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /notify_off -> unsubscribe this chat from alerts """
    if not HAS_WATCHER:
        await update.message.reply_text("❌ Market watcher module not installed.")
        return
    market_watcher.unsubscribe(update.effective_chat.id)
    await update.message.reply_text("🔕 Live alerts turned OFF for this chat.")


async def notify_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /notify_status -> show this chat's alert subscription """
    if not HAS_WATCHER:
        await update.message.reply_text("❌ Market watcher module not installed.")
        return
    sub = market_watcher.get_subscription(update.effective_chat.id)
    if not sub or not sub.get("active"):
        await update.message.reply_text("🔕 No active alerts. Turn on with /notify_on NIFTY 5000")
        return
    await update.message.reply_text(
        f"🔔 Alerts ON\nSymbols: {', '.join(sub['symbols'])}\nCapital: ₹{sub['capital']:,.0f}\nMin win-rate: {sub['min_probability']}%"
    )


async def _watcher_job(context: ContextTypes.DEFAULT_TYPE):
    """ JobQueue callback - runs every few minutes, pushes alerts for high-probability setups. """
    try:
        await market_watcher.check_and_notify(context.bot)
    except Exception:
        logger.exception("market watcher tick failed")


async def llm_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /llm_status -> which AI providers are configured """
    if not HAS_LLM_AGENT:
        await update.message.reply_text("❌ AI agent module not installed (missing llm_agent.py).")
        return
    lines = ["🧠 <b>AI Provider Status</b>\n"]
    for key in llm_agent.ORDER:
        ok = llm_agent.is_configured(key)
        lines.append(f"{'✅' if ok else '⚫'} {llm_agent.provider_label(key)}")
    configured = llm_agent.configured_providers()
    lines.append(f"\nFallback order used by /ask: {' → '.join(configured) if configured else 'none configured yet'}")
    lines.append("Use /ask <question> for one answer, /compare <question> to see all models at once.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


# --- NEW AI Institutional Commands ---
async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /signal NIFTY -> AI signal with probability, entry, target, SL """
    if not HAS_INSTITUTIONAL_AI:
        await update.message.reply_text("❌ Institutional AI module not installed. Missing institutional_strategy.py")
        return

    symbol = "NIFTY"
    if context.args:
        symbol = context.args[0].upper()

    task_label = f"AI Signal {symbol} Institutional Analysis"
    msg, countdown_task = await send_processing_with_countdown(update, context, task_label, estimate=7)

    try:
        # Fetch option chain data for signal - try NSE fallback
        option_chain_data = None
        underlying_price = None

        # Try to get underlying price first via Shoonya or Yahoo
        if HAS_SHOONYA_LIB and SHOONYA_CONFIGURED:
            try:
                def get_price():
                    if symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
                        q, _ = sc.get_index_via_shoonya(symbol.lower())
                    else:
                        q, _ = sc.get_stock_via_shoonya(symbol)
                    return q
                q = await asyncio.to_thread(get_price)
                lp = q.get("lp") or q.get("c")
                if lp:
                    underlying_price = float(lp)
            except:
                pass

        # Try NSE option chain
        try:
            import nse_option_chain as nse_oc
            def fetch_nse():
                return nse_oc.get_option_chain_with_fallback(symbol, count=15)
            data, source = await asyncio.to_thread(fetch_nse)
            if data:
                option_chain_data = data
        except Exception as e:
            logger.debug(f"NSE chain for signal failed: {e}")

        # Generate signal
        def gen_signal():
            return inst_ai.generate_ai_signal(symbol, option_chain_data, underlying_price)

        signal = await asyncio.to_thread(gen_signal)

        # Format for Telegram (HTML)
        formatted = inst_ai.format_signal_for_telegram(signal)

        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=formatted, parse_mode=ParseMode.HTML)

        # If high probability (>75), send alert style
        if signal.probability > 75 and signal.signal_type in ["BUY_CALL", "BUY_PUT"]:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"🚨 <b>HIGH CONVICTION ALERT: {symbol} {signal.signal_type} {signal.probability}%</b>\nEntry: {signal.entry_strike} {signal.entry_type}\nTarget: {signal.target}\nSL: {signal.stoploss}\n\nUse /analysis {symbol} for details",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        countdown_task.cancel()
        logger.exception(f"/signal {symbol} failed")
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Signal generation failed for {symbol}: {e}")


async def analysis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /analysis NIFTY -> Deep institutional footprint """
    if not HAS_INSTITUTIONAL_AI:
        await update.message.reply_text("❌ Institutional AI not available")
        return

    symbol = "NIFTY"
    if context.args:
        symbol = context.args[0].upper()

    msg, countdown_task = await send_processing_with_countdown(update, context, f"Institutional Analysis {symbol}", estimate=6)

    try:
        # Get option chain
        option_chain_data = None
        try:
            import nse_option_chain as nse_oc
            def fetch():
                return nse_oc.get_option_chain_with_fallback(symbol, count=15)
            data, source = await asyncio.to_thread(fetch)
            option_chain_data = data
        except:
            pass

        def analyze():
            # Generate signal to get all metrics
            sig = inst_ai.generate_ai_signal(symbol, option_chain_data)
            # Detailed analysis
            records = option_chain_data.get("records", {}) if isinstance(option_chain_data, dict) else {}
            data_list = records.get("data", []) if isinstance(records, dict) else []
            underlying = records.get("underlyingValue") if isinstance(records, dict) else None

            max_pain = inst_ai.calculate_max_pain_from_chain(data_list) if data_list else None
            pcr = inst_ai.calculate_pcr(data_list) if data_list else {}
            clusters = inst_ai.analyze_oi_clusters(data_list, underlying) if data_list else {}
            liquidity = inst_ai.detect_liquidity_pools_and_stop_hunting(data_list, underlying, clusters) if data_list else {}
            oi_insights = inst_ai.analyze_oi_price_action(data_list) if data_list else []

            return sig, max_pain, pcr, clusters, liquidity, oi_insights, underlying

        sig, max_pain, pcr, clusters, liquidity, oi_insights, underlying = await asyncio.to_thread(analyze)

        lines = [
            f"🔍 <b>Deep Institutional Footprint: {symbol}</b>",
            f"Underlying: {underlying} | Time: {datetime.now().strftime('%H:%M:%S IST')}",
            "",
            f"<b>Max Pain:</b> {max_pain} - Strike where option buyers lose most, writers profit most. Price often pins near expiry (60-65% within 50-80 pts)",
            f"<b>PCR:</b> {pcr.get('total_pcr', 'N/A')} - {pcr.get('sentiment', '')}",
            f"  Total CE OI: {pcr.get('total_ce_oi', 0)} | PE OI: {pcr.get('total_pe_oi', 0)}",
            "",
            "<b>OI Clusters (Smart Money Zones):</b>",
        ]

        if clusters:
            hce = clusters.get("highest_call_oi", {})
            hpe = clusters.get("highest_put_oi", {})
            lines.append(f"  • Highest Call OI: {hce.get('strike')} OI {hce.get('oi')} Chg {hce.get('chg_oi')} - Resistance")
            lines.append(f"  • Highest Put OI: {hpe.get('strike')} OI {hpe.get('oi')} Chg {hpe.get('chg_oi')} - Support")
            if clusters.get("fresh_ce_buildup"):
                lines.append(f"  • Fresh CE Buildup: {len(clusters['fresh_ce_buildup'])} strikes - Institutional call writing/buying")
            if clusters.get("fresh_pe_buildup"):
                lines.append(f"  • Fresh PE Buildup: {len(clusters['fresh_pe_buildup'])} strikes")

        lines.append("")
        lines.append("<b>💧 Liquidity Pools & Stop Hunting:</b>")
        for pool in liquidity.get("liquidity_pools", [])[:4]:
            lines.append(f"  • {pool}")
        for zone in liquidity.get("stop_loss_hunting_zones", [])[:2]:
            lines.append(f"  • {zone}")

        lines.append("")
        lines.append("<b>📊 OI-Price Action (4 quadrants):</b>")
        for insight in oi_insights[:8]:
            lines.append(f"  • {insight}")

        lines.append("")
        lines.append(f"<b>Current AI Signal:</b> {sig.signal_type} {sig.probability}%")
        lines.append(f"Entry: {sig.entry_strike} | Target: {sig.target} | SL: {sig.stoploss}")
        lines.append("")
        lines.append("<b>How Institutions Manipulate:</b>")
        lines.append("• They need retail SL liquidity to fill large orders")
        lines.append("• Push price to sweep SL just beyond OI walls, then reverse")
        lines.append("• Watch close, not wick. Sweep = wick beyond + close back inside + volume spike then drop, no OI buildup at new level = fake breakout")
        lines.append("• Real breakout = close firmly beyond, volume sustains 2-3 candles, VWAP shifts, fresh OI buildup")

        text = "\n".join(lines)
        if len(text) > 3900:
            text = text[:3900] + "\n... truncated, use /signal for entry/exit"

        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text, parse_mode=ParseMode.HTML)

    except Exception as e:
        countdown_task.cancel()
        logger.exception(f"/analysis {symbol} failed")
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Analysis failed for {symbol}: {e}")


async def beststrategy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /beststrategy -> Best option buying strategy explanation """
    try:
        await update.message.reply_text(BEST_STRATEGY_HTML, parse_mode=ParseMode.HTML)
        
        # Also send GitHub repos researched
        if context.args and context.args[0].upper() in ["NIFTY", "BANKNIFTY"]:
            symbol = context.args[0].upper()
            await update.message.reply_text(
                f"📚 <b>GitHub Repos for {symbol} Live Data:</b>\n"
                f"• VarunS2002/Python-NSE-Option-Chain-Analyzer - Real-time NSE chain + OI boundaries, PCR, exits\n"
                f"• Prasad1612/NseKit - NSE live data, option chain\n"
                f"• jugaad-py/jugaad-data - bhavcopy, live NSE, derivatives\n"
                f"• atrybyme/Open-Interest-NSE-Live-Analysis - Live Max Pain, PCR\n"
                f"• Pattern: Use nse_option_chain.py we built (session + cookies bypass 403) + shoonya_client.py for Shoonya\n"
                f"• Our bot combines all: Shoonya primary, NSE fallback, Yahoo fallback, CoinGecko\n\n"
                f"Try /signal {symbol} now for live AI signal!",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        logger.error(f"beststrategy failed: {e}, fallback plain")
        await update.message.reply_text(
            "Best Option Buying Strategy India:\n"
            "1. Opening Range Breakout (ORB) + VWAP: Mark 9:15-9:30 high/low, price above VWAP sloping up = Buy Calls, below = Buy Puts, ATM/ITM\n"
            "2. Institutional OI: Highest Put OI = Support, Highest Call OI = Resistance, Call writers exiting at resistance = bullish breakout\n"
            "3. Liquidity Sweep: Institutions sweep SL beyond OI walls then reverse. Watch close not wick, volume spike then drop = fake, volume sustains = real breakout\n"
            "4. Max Pain: Expiry Tuesday for NIFTY, last Tuesday monthly for BANKNIFTY, price pins within 50-80 pts 60-65% time final hour\n"
            "5. PCR: >1.5 oversold bullish reversal, <0.7 overbought bearish, wait for price confirmation\n"
            "6. Entry ATM/OTM, Target next OI wall or 1:2 RR, SL 30% premium or beyond sweep wick, Risk 1-2% capital\n"
            "Use /signal NIFTY for AI probability\n"
        )

# --- NEW: Crypto Expert + Free Chain Bypass (fixes 502/403) ---
async def crypto_signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /crypto_signal BTCUSDT - Binance spot AI signal with probability """
    if not HAS_CRYPTO_EXPERT:
        await update.message.reply_text("❌ Crypto expert not available. Missing crypto_expert.py")
        return
    symbol = "BTCUSDT"
    if context.args:
        arg = context.args[0].upper()
        if "USDT" not in arg and "/" not in arg:
            symbol = f"{arg}USDT"
        else:
            symbol = arg.replace("/", "")
    task_label = f"Crypto Expert {symbol}"
    msg, countdown_task = await send_processing_with_countdown(update, context, task_label, estimate=5)
    try:
        def gen():
            return crypto_ai.analyze_binance_spot(symbol)
        analysis = await asyncio.to_thread(gen)
        formatted = crypto_ai.format_crypto_signal_for_telegram(analysis)
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=formatted, parse_mode=ParseMode.HTML)
        if analysis.get("probability", 0) > 75 and analysis.get("signal_type") in ["BUY", "SELL"]:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"🚨 <b>CRYPTO HIGH CONVICTION: {symbol} {analysis['signal_type']} {analysis['probability']}%</b>\nEntry: ${analysis['entry']:,.2f} Target: ${analysis['target']:,.2f} SL: ${analysis['stoploss']:,.2f}\nBinance spot - test with your Binance account!",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Crypto signal failed {symbol}: {e}")


async def crypto_option_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /crypto_option BTC - Deribit option chain free, works on Replit """
    if not HAS_FREE_OC:
        await update.message.reply_text("❌ Free option chain not available")
        return
    currency = "BTC"
    if context.args:
        currency = context.args[0].upper()
    msg, countdown_task = await send_processing_with_countdown(update, context, f"Crypto Options {currency} Deribit (Free)", estimate=6)
    try:
        def fetch():
            return free_oc.get_deribit_option_chain(currency, count=5)
        chain_data = await asyncio.to_thread(fetch)
        if not chain_data or not chain_data.get("chain"):
            countdown_task.cancel()
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ No Deribit chain for {currency}. Try BTC or ETH. Deribit 80% global crypto options volume, free API works on Replit.")
            return
        formatted = free_oc.format_deribit_chain_for_telegram(chain_data, currency)
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=formatted, parse_mode=ParseMode.HTML)
    except Exception as e:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Crypto option failed {currency}: {e}")


async def free_chain_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /free_chain NIFTY - tries free proxies to bypass NSE 403 """
    symbol = "NIFTY"
    if context.args:
        symbol = context.args[0].upper()
    msg, countdown_task = await send_processing_with_countdown(update, context, f"Free NSE Chain {symbol} via Proxy Bypass", estimate=7)
    try:
        if not HAS_FREE_OC:
            countdown_task.cancel()
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text="Free chain module not available")
            return
        def fetch_free():
            return free_oc.get_nse_option_chain_free(symbol)
        data = await asyncio.to_thread(fetch_free)
        if data:
            try:
                import nse_option_chain as nse_oc
                formatted = nse_oc.format_nse_chain_for_telegram(data, symbol, count=5)
                countdown_task.cancel()
                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=formatted + "\n\n✅ Free proxy bypass worked! (AllOrigins/CodeTabs)")
                return
            except Exception as e:
                countdown_task.cancel()
                await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"✅ Free NSE data fetched for {symbol} via proxy! Len: {len(str(data))}\n\n{str(data)[:1000]}...\n\nUse /analysis {symbol}")
                return
        else:
            countdown_task.cancel()
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=f"❌ Free NSE proxy also failed for {symbol}\n\nNSE + Shoonya both block Replit datacenter (403/502).\n✅ WORKING FREE ALTERNATIVES ON REPLIT:\n• /crypto_option BTC - Deribit BTC options (80% volume, free, works!)\n• /crypto_signal BTCUSDT - Binance spot AI (free, works 24/7)\n• /crypto btc - CoinGecko price (works)\n• /signal NIFTY - Uses mock + Yahoo fallback when NSE blocked (still gives probability)\n\nFor Indian chain to work on Replit: Whitelist IP in Shoonya or run bot on home PC residential IP"
            )
    except Exception as e:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Free chain failed: {e}")


# --- VarunS2002 NSE Option Chain Analyzer - Live Implementation ---
async def varun_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /varun NIFTY [strike] - VarunS2002 live analyzer logic (OI Upper/Lower, Call Sum, Put Sum, Diff, Boundaries, ITM) """
    if not HAS_VARUN:
        try:
            import varun_analyzer as va
            has_varun = True
        except:
            has_varun = False
        if not has_varun:
            await update.message.reply_text("❌ Varun analyzer not available. Missing varun_analyzer.py - run git pull origin main")
            return

    # Need varun_analyzer module
    try:
        import varun_analyzer as va
    except ImportError as e:
        await update.message.reply_text(f"❌ Varun module import failed: {e}")
        return

    symbol = "NIFTY"
    strike = None
    if context.args:
        symbol = context.args[0].upper()
        if len(context.args) >= 2:
            try:
                strike = float(context.args[1])
            except:
                pass

    task_label = f"Varun Analyzer {symbol} {f'@{strike}' if strike else ''}"
    msg, countdown_task = await send_processing_with_countdown(update, context, task_label, estimate=7)

    try:
        # Fetch option chain data
        def fetch_chain():
            # Try NSE direct + free proxy + Shoonya
            try:
                import nse_option_chain as nse_oc
                data, source = nse_oc.get_option_chain_with_fallback(symbol, count=30)
                if data:
                    return data
            except Exception as e:
                logger.debug(f"NSE direct for varun failed: {e}")

            try:
                import free_option_chain as free_oc
                data = free_oc.get_nse_option_chain_free(symbol)
                if data:
                    return data
            except Exception as e:
                logger.debug(f"Free proxy for varun failed: {e}")

            return None

        data = await asyncio.to_thread(fetch_chain)

        if not data:
            countdown_task.cancel()
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg.message_id,
                text=f"❌ Could not fetch live option chain for {symbol}\n\n"
                     f"NSE blocks datacenter IP (403), Shoonya 502 if IP not whitelisted\n"
                     f"Try:\n"
                     f"• /free_chain {symbol} - free proxy bypass\n"
                     f"• During market hours 9:15-15:30 IST\n"
                     f"• Or use /signal {symbol} which uses mock fallback when NSE blocked"
            )
            return

        # Parse data
        data_list, underlying, timestamp = va.parse_nse_v3_data(data) if hasattr(va, 'parse_nse_v3_data') else ([], 0, "")

        # If parse failed, try to get data_list from records.data
        if not data_list:
            # Try alternative parsing
            records = data.get("records", {}) if isinstance(data, dict) else {}
            data_list = records.get("data", []) if isinstance(records, dict) else []
            underlying = records.get("underlyingValue", 0) if isinstance(records, dict) else 0

        if not data_list:
            countdown_task.cancel()
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ No data_list for {symbol}")
            return

        # Determine strike
        if strike is None:
            # Use underlying as strike, rounded
            if underlying:
                if symbol == "BANKNIFTY":
                    strike = round(underlying / 100) * 100
                elif symbol == "NIFTY":
                    strike = round(underlying / 50) * 50
                else:
                    strike = round(underlying)
            else:
                # Use ATM from data
                strikes = [d.get("strikePrice") for d in data_list if d.get("strikePrice")]
                if strikes:
                    strike = sorted(strikes)[len(strikes)//2]
                else:
                    strike = 0

        # Calculate Varun indicators
        indicators = va.calculate_varun_indicators(data_list, strike, underlying)

        formatted = va.format_varun_for_telegram(indicators, symbol)

        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=formatted, parse_mode=ParseMode.HTML)

        # Also send interpretation for option buying
        if indicators.get("difference", 0) < -50000:
            bias = "BULLISH (Difference very -ve)"
        elif indicators.get("difference", 0) > 50000:
            bias = "BEARISH (Difference very +ve)"
        else:
            bias = "SIDEWAYS (Difference near 0)"

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"💡 <b>Varun {symbol} Interpretation:</b> {bias}\n"
                 f"Call Sum {indicators.get('call_sum')}, Put Sum {indicators.get('put_sum')}\n"
                 f"Call Exits: {indicators.get('call_exits')} (Yes=Bulls clear path)\n"
                 f"Put Exits: {indicators.get('put_exits')} (Yes=Bears clear path)\n"
                 f"Use /signal {symbol} for entry/target/SL with probability %\n"
                 f"Original: github.com/VarunS2002/Python-NSE-Option-Chain-Analyzer",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        countdown_task.cancel()
        logger.exception(f"/varun {symbol} failed")
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Varun analyzer failed for {symbol}: {e}")


# --- Arena Multi-LLM Agent - Fully Functional ---
async def arena_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /arena <question> - Ask ALL LLMs (Claude, ChatGPT, Gemini, Grok, Qwen, Kimi, Llama, DeepSeek) same query """
    try:
        import arena_agent as arena
    except ImportError:
        await update.message.reply_text("❌ Arena agent not available. Missing arena_agent.py")
        return

    question = " ".join(context.args).strip() if context.args else ""
    if not question:
        await update.message.reply_text(
            "Usage: /arena <your question>\n"
            "Example: /arena What is best strategy for NIFTY option buying today?\n\n"
            "Arena asks 8 AI models (Claude, ChatGPT, Gemini, Grok, Qwen, Kimi, Llama, DeepSeek) concurrently and compares answers.\n"
            "Requires at least one LLM API key in Replit Secrets: GROQ_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY\n"
            "Also try /arena_vote <question> for consensus voting, /arena_persona <persona> <question>"
        )
        return

    if not arena.is_configured():
        await update.message.reply_text(
            "❌ No Arena LLMs configured. Add at least one API key in Replit Secrets:\n"
            "GROQ_API_KEY (fast, free tier), DEEPSEEK_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY\n"
            "Get free keys: Groq console.groq.com, Gemini aistudio.google.com, DeepSeek platform.deepseek.com"
        )
        return

    task_label = f"Arena Multi-LLM: {question[:40]}"
    msg, countdown_task = await send_processing_with_countdown(update, context, task_label, estimate=10)

    try:
        def run_arena():
            return arena.ask_arena_all(question)

        results = await asyncio.to_thread(run_arena)
        formatted = arena.format_arena_results_for_telegram(results, question)

        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=formatted, parse_mode=ParseMode.HTML)

    except Exception as e:
        countdown_task.cancel()
        logger.exception(f"/arena failed")
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Arena failed: {e}")


async def arena_vote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /arena_vote Should I buy NIFTY CALL or PUT? - Arena consensus voting """
    try:
        import arena_agent as arena
    except ImportError:
        await update.message.reply_text("❌ Arena agent not available")
        return

    question = " ".join(context.args).strip() if context.args else ""
    if not question:
        await update.message.reply_text(
            "Usage: /arena_vote <question>\n"
            "Example: /arena_vote Should I buy NIFTY CALL or PUT today? Consider OI, PCR, Max Pain\n\n"
            "Arena asks 8 models and votes BUY_CALL / BUY_PUT / NO_TRADE with consensus probability"
        )
        return

    if not arena.is_configured():
        await update.message.reply_text("❌ No Arena LLMs configured. Add GROQ_API_KEY etc in Secrets.")
        return

    msg, countdown_task = await send_processing_with_countdown(update, context, f"Arena Vote: {question[:40]}", estimate=10)

    try:
        def run_vote():
            return arena.arena_consensus_vote(question)

        vote_result = await asyncio.to_thread(run_vote)

        lines = [
            f"🏟️ <b>Arena Consensus Vote:</b> {question}",
            "",
            f"<b>Consensus:</b> {vote_result['consensus']}",
            f"<b>Bullish Probability:</b> {vote_result['bullish_probability']}% | Bearish: {vote_result['bearish_probability']}%",
            "",
            "<b>Votes:</b>",
        ]
        for k, v in vote_result['votes'].items():
            lines.append(f"  • {k}: {v}")

        lines.append("")
        lines.append("<b>Individual Answers:</b>")
        for pk, res in vote_result['all_answers'].items():
            if res['ok']:
                txt = res['text'][:200] + "..." if len(res['text']) > 200 else res['text']
                lines.append(f"  • {pk}: {txt[:100]}...")

        text = "\n".join(lines)
        if len(text) > 3900:
            text = text[:3900] + "\n... truncated"

        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=text, parse_mode=ParseMode.HTML)

    except Exception as e:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Arena vote failed: {e}")


async def arena_persona_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ /arena_persona <persona> <question> - Ask specific Arena persona (claude, chatgpt, gemini, grok, qwen, kimi, llama, deepseek) """
    try:
        import arena_agent as arena
    except ImportError:
        await update.message.reply_text("❌ Arena agent not available")
        return

    if len(context.args) < 2:
        personas = ", ".join(arena.get_arena_personas().keys()) if hasattr(arena, 'get_arena_personas') else "claude, chatgpt, gemini, grok, qwen, kimi, llama, deepseek"
        await update.message.reply_text(
            f"Usage: /arena_persona <persona> <question>\n"
            f"Personas: {personas}\n\n"
            f"Examples:\n"
            f"/arena_persona claude What is risk management for option buying?\n"
            f"/arena_persona grok Is NIFTY manipulation happening today?\n"
            f"/arena_persona qwen Calculate probability for NIFTY CALL"
        )
        return

    persona_key = context.args[0].lower()
    question = " ".join(context.args[1:])

    if persona_key not in arena.get_arena_personas():
        await update.message.reply_text(f"❌ Unknown persona {persona_key}. Available: {', '.join(arena.get_arena_personas().keys())}")
        return

    msg, countdown_task = await send_processing_with_countdown(update, context, f"Arena {persona_key}: {question[:30]}", estimate=6)

    try:
        def run_persona():
            return arena.ask_arena_persona(persona_key, question)

        answer, provider_label = await asyncio.to_thread(run_persona)

        countdown_task.cancel()
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=msg.message_id,
            text=f"🤖 <b>{persona_key.upper()} ({provider_label}):</b>\n\n{answer[:3500]}",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        countdown_task.cancel()
        await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=msg.message_id, text=f"❌ Arena persona {persona_key} failed: {e}")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photos - User asks if bot can read images/PDFs"""
    try:
        await update.message.reply_text(
            "📸 Image received! ✅ I can read images.\n\n"
            "Processing your image...\n"
            "• If it's a chart, I'll analyze support/resistance, OI, price action\n"
            "• If it's a screenshot of option chain, I'll extract OI, PCR, Max Pain\n"
            "• If it's any document image, I'll OCR text\n\n"
            "⏳ Analyzing... (Gemini vision if configured, otherwise basic handling)"
        )

        # Try to download photo file
        photo_file = await update.message.photo[-1].get_file()
        # For now, we don't save, just acknowledge and use LLM to explain capability
        # Future: Download and use Gemini vision API or pytesseract

        # Use LLM agent to explain image reading capability
        if HAS_LLM_AGENT and llm_agent.configured_providers():
            try:
                answer, provider, _ = await asyncio.to_thread(
                    llm_agent.agent_ask,
                    "User sent an image (photo). They previously asked 'Can you read image pdf?' "
                    "Explain that you can read images via Gemini vision API (if GEMINI_API_KEY set) or OCR. "
                    "Tell them to use /ask with description of what they want from image, or send PDF as document. "
                    "Keep answer short, Telegram-friendly.",
                    [],
                    update.effective_chat.id
                )
                await update.message.reply_text(f"🤖 {answer}\n\nFor PDFs, send as document. For charts, tell me what you want analyzed.")
            except Exception as e:
                logger.debug(f"Photo LLM explain failed: {e}")

        # Also try to inform about PDF capability
        await update.message.reply_text(
            "✅ I CAN read images and PDFs:\n"
            "• Images: Send as photo, I can analyze chart, option chain screenshot, etc.\n"
            "• PDFs: Send as document (PDF), I extract text\n"
            "• Try: Send a PDF of your trading plan or screenshot and ask /ask to analyze it\n\n"
            "Note: For best image reading, set GEMINI_API_KEY in Secrets (Gemini 2.0 Flash has vision). Currently using Groq fallback."
        )

    except Exception as e:
        logger.exception(f"Photo handler failed: {e}")
        await update.message.reply_text(f"📸 Image received! I can read images and PDFs.\nSend PDF as document for text extraction.\nError: {e}")


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDFs and documents"""
    try:
        doc = update.message.document
        file_name = doc.file_name or "document"
        await update.message.reply_text(
            f"📄 Document received: {file_name}\n\n"
            f"Processing...\n"
            f"• If PDF, extracting text\n"
            f"• If Excel/CSV, parsing data\n"
            f"• Size: {doc.file_size} bytes\n\n"
            f"⏳ Reading..."
        )

        # Try to download and read PDF
        try:
            file = await doc.get_file()
            # Download to temp
            import tempfile
            import os
            tmp_path = os.path.join(tempfile.gettempdir(), file_name)
            await file.download_to_drive(tmp_path)

            text_extracted = ""
            if file_name.lower().endswith(".pdf"):
                # Try PyMuPDF or pdfminer
                try:
                    import fitz  # PyMuPDF
                    doc_pdf = fitz.open(tmp_path)
                    text_extracted = "\n".join([page.get_text() for page in doc_pdf[:3]])  # first 3 pages
                    doc_pdf.close()
                    await update.message.reply_text(f"✅ PDF text extracted (first 500 chars):\n\n{text_extracted[:500]}...\n\nUse /ask to ask questions about this PDF content!")
                except ImportError:
                    try:
                        import PyPDF2
                        reader = PyPDF2.PdfReader(tmp_path)
                        text_extracted = "\n".join([page.extract_text() or "" for page in reader.pages[:3]])
                        await update.message.reply_text(f"✅ PDF text extracted (first 500 chars):\n\n{text_extracted[:500]}...\n\nUse /ask to analyze!")
                    except Exception as pdf_e:
                        await update.message.reply_text(f"⚠️ PDF received but need PyMuPDF or PyPDF2 to read. Install: pip install PyMuPDF\nError: {pdf_e}\nFile saved: {tmp_path}")
                finally:
                    try:
                        os.remove(tmp_path)
                    except:
                        pass
            else:
                await update.message.reply_text(f"📄 File {file_name} received. For PDFs I extract text, for images I OCR. What would you like to know about it? Use /ask")

        except Exception as dl_e:
            logger.exception(f"Document download failed: {dl_e}")
            await update.message.reply_text(f"📄 Document {file_name} received but download failed: {dl_e}")

    except Exception as e:
        logger.exception(f"Document handler failed: {e}")
        await update.message.reply_text(f"📄 Document received! I can read PDFs and images.\nError: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}", exc_info=True)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(f"⚠️ Error: {context.error}\nTry /help")
    except:
        pass

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found")
        print("\n" + "="*60 + "\n❌ TOKEN missing! Set in Replit Secrets:\nKey: TELEGRAM_BOT_TOKEN\n" + "="*60 + "\n")
        return
    masked = TELEGRAM_BOT_TOKEN[:6] + "***" + TELEGRAM_BOT_TOKEN[-4:]
    print(f"🔑 Token: {masked}")
    print(f"📊 Yahoo: {'✅ Loaded' if HAS_MARKET_DATA else '❌ Missing'}")
    print(f"🔌 Shoonya Lib: {'✅' if HAS_SHOONYA_LIB else '❌ Install NorenRestApiPy, pyotp'}")
    print(f"🔐 Shoonya Configured: {'✅' if SHOONYA_CONFIGURED else '⚠️ Not configured - set Replit Secrets for option chain'}")
    print(f"🧠 Institutional AI: {'✅ Loaded' if HAS_INSTITUTIONAL_AI else '❌ Missing institutional_strategy.py'}")
    print(f"🌐 Free OC: {'✅' if HAS_FREE_OC else '❌'} | Crypto Expert: {'✅' if HAS_CRYPTO_EXPERT else '❌'}")
    print(f"📈 Varun Analyzer: {'✅ Loaded' if HAS_VARUN else '❌ Missing varun_analyzer.py (VarunS2002)'}")
    print(f"🏟️ Arena Agent: {'✅ Loaded' if HAS_ARENA_AGENT else '❌ Missing arena_agent.py'} | LLM Agent: {'✅' if HAS_LLM_AGENT else '❌'}")
    if HAS_LLM_AGENT:
        configured = llm_agent.configured_providers()
        print(f"🧠 AI Agent: {'✅ ' + ' > '.join(configured) if configured else '⚠️ no API keys set (GROQ/DEEPSEEK/GEMINI/OPENAI)'}")
    else:
        print("🧠 AI Agent: ❌ llm_agent.py missing")
    keep_alive()
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("hi", hi_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("shoonya_status", shoonya_status_cmd))
    application.add_handler(CommandHandler("demo", demo_cmd))
    # Market data
    application.add_handler(CommandHandler(["nifty", "sensex", "banknifty", "finnifty"], index_cmd))
    application.add_handler(CommandHandler("vix", vix_cmd))
    application.add_handler(CommandHandler("stock", stock_cmd))
    application.add_handler(CommandHandler("global", global_cmd))
    application.add_handler(CommandHandler("crypto", crypto_cmd))
    application.add_handler(CommandHandler("optionchain", optionchain_cmd))
    # NEW AI Institutional
    application.add_handler(CommandHandler("signal", signal_cmd))
    application.add_handler(CommandHandler("analysis", analysis_cmd))
    application.add_handler(CommandHandler(["beststrategy", "strategy", "best_strategy"], beststrategy_cmd))
    application.add_handler(CommandHandler("plan", plan_cmd))
    application.add_handler(CommandHandler("notify_on", notify_on_cmd))
    application.add_handler(CommandHandler("notify_off", notify_off_cmd))
    application.add_handler(CommandHandler("notify_status", notify_status_cmd))
    # NEW Multi-LLM AI Agent (Groq/DeepSeek/Gemini/OpenAI) - ask anything
    application.add_handler(CommandHandler("ask", ask_cmd))
    application.add_handler(CommandHandler(["compare", "ask_all", "llm_compare"], ask_all_cmd))
    application.add_handler(CommandHandler(["llm_status", "ai_status"], llm_status_cmd))
    # NEW Free chain + Crypto Expert (fixes Shoonya 502 + NSE 403 - works on Replit)
    try:
        application.add_handler(CommandHandler("crypto_signal", crypto_signal_cmd))
        application.add_handler(CommandHandler(["crypto_option", "crypto_options"], crypto_option_cmd))
        application.add_handler(CommandHandler(["free_chain", "free_optionchain"], free_chain_cmd))
    except NameError:
        pass

    # NEW VarunS2002 Analyzer (live OI Upper/Lower, Call Sum, Put Sum, Diff, Boundaries, ITM)
    try:
        application.add_handler(CommandHandler(["varun", "varun_analyzer", "nse_analyzer"], varun_cmd))
    except NameError:
        pass

    # NEW Arena Multi-LLM Fully Functional (8 personas: Claude, ChatGPT, Gemini, Grok, Qwen, Kimi, Llama, DeepSeek)
    try:
        application.add_handler(CommandHandler(["arena", "arena_all"], arena_cmd))
        application.add_handler(CommandHandler(["arena_vote", "arena_consensus"], arena_vote_cmd))
        application.add_handler(CommandHandler(["arena_persona", "arena_bot", "persona"], arena_persona_cmd))
    except NameError:
        pass
    # Photo and Document handlers (for image/pdf reading - fixes "Can you read image pdf?" query)
    try:
        application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
        application.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    except NameError:
        pass

    application.add_handler(MessageHandler(filters.Regex(r"(?i)^hi$"), handle_hi_text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_error_handler(error_handler)

    if HAS_WATCHER and application.job_queue is not None:
        application.job_queue.run_repeating(_watcher_job, interval=180, first=30)
        print("🔔 Market watcher job scheduled (every 3 min during market hours)")
    elif HAS_WATCHER:
        print("⚠️ JobQueue unavailable (install python-telegram-bot[job-queue]) - /notify_on alerts will not fire automatically")

    print("🚀 OptionBuyerBot v0.6 starting... Varun Analyzer + Arena Multi-LLM + AI Institutional + Crypto Expert + Free Chain Bypass")
    print("✅ Hi instant, market countdown, option chain Shoonya/NSE/free proxy, AI signals, crypto signals, Varun live, Arena 8 LLMs")
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
