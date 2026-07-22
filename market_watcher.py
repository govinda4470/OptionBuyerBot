"""market_watcher.py - Background watcher for proactive alerts"""
import json, os, time, logging
logger = logging.getLogger(__name__)
SUB_FILE="subscriptions.json"
try:
    import threading
    _lock=threading.Lock()
except:
    _lock=None

def _load():
    try:
        if not os.path.exists(SUB_FILE):
            return {}
        with open(SUB_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def _save(data):
    try:
        if _lock:
            with _lock:
                tmp=SUB_FILE+".tmp"
                with open(tmp,"w",encoding="utf-8") as f:
                    json.dump(data,f,indent=2)
                os.replace(tmp,SUB_FILE)
        else:
            with open(SUB_FILE,"w",encoding="utf-8") as f:
                json.dump(data,f,indent=2)
    except Exception as e:
        logger.error(f"Save subs failed: {e}")

def subscribe(chat_id,symbol=None,capital=None,min_probability=None):
    data=_load()
    chat_id_str=str(chat_id)
    symbols=[symbol.upper()] if symbol else ["NIFTY"]
    capital=float(capital) if capital else 5000.0
    min_prob=int(min_probability) if min_probability else 75
    data[chat_id_str]={"symbols":symbols,"capital":capital,"min_probability":min_prob,"active":True,"created":time.time()}
    _save(data)
    return data[chat_id_str]

def unsubscribe(chat_id):
    data=_load()
    chat_id_str=str(chat_id)
    if chat_id_str in data:
        del data[chat_id_str]
        _save(data)

def get_subscription(chat_id):
    data=_load()
    return data.get(str(chat_id))

async def check_and_notify(bot):
    try:
        data=_load()
        now=time.time()
        for chat_id_str, sub in list(data.items()):
            if not sub.get("active"):
                continue
            last_notified=sub.get("last_notified",0)
            if now-last_notified<1800:
                continue
            try:
                symbol=sub["symbols"][0] if sub["symbols"] else "NIFTY"
                capital=sub.get("capital",5000)
                min_prob=sub.get("min_probability",75)
                import institutional_strategy as inst_ai
                import nse_option_chain as nse_oc
                option_chain_data,_=nse_oc.get_option_chain_with_fallback(symbol,count=15)
                signal=inst_ai.generate_ai_signal(symbol,option_chain_data)
                if signal.probability>=min_prob and signal.signal_type in ["BUY_CALL","BUY_PUT"]:
                    sub["last_notified"]=now
                    data[chat_id_str]=sub
                    _save(data)
                    try:
                        text=inst_ai.format_signal_for_telegram(signal)
                        await bot.send_message(chat_id=int(chat_id_str), text=f"🔔 Auto Alert: {symbol} {signal.signal_type} {signal.probability}%\n\n"+text[:3000], parse_mode="HTML")
                    except Exception as e:
                        logger.error(f"Notify {chat_id_str} failed: {e}")
            except Exception as e:
                logger.debug(f"Watcher check {chat_id_str} failed: {e}")
                continue
    except Exception as e:
        logger.exception(f"Watcher job failed: {e}")
