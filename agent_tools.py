"""agent_tools.py - Tools for LLM agent"""
import logging
logger = logging.getLogger(__name__)
try:
    import market_data as md
    HAS_MD=True
except:
    HAS_MD=False
    md=None
try:
    import nse_option_chain as nse_oc
    HAS_NSE=True
except:
    HAS_NSE=False
    nse_oc=None
try:
    import institutional_strategy as inst_ai
    HAS_INST=True
except:
    HAS_INST=False
    inst_ai=None
try:
    import position_sizing as pos_sizing
    HAS_POS=True
except:
    HAS_POS=False
    pos_sizing=None
try:
    import crypto_expert as crypto_ai
    HAS_CRYPTO=True
except:
    HAS_CRYPTO=False
    crypto_ai=None
try:
    import market_watcher
    HAS_WATCHER=True
except:
    HAS_WATCHER=False
    market_watcher=None

def get_index_price(symbol):
    if not HAS_MD:
        return {"error":"market data unavailable"}
    try:
        q=md.get_index_quote(symbol.lower())
        return {"symbol":symbol.upper(),"text":q.format()}
    except Exception as e:
        return {"error":str(e)}

def get_stock_price(symbol):
    if not HAS_MD:
        return {"error":"market data unavailable"}
    try:
        q=md.get_stock_quote(symbol.upper())
        return {"symbol":symbol.upper(),"text":q.format()}
    except Exception as e:
        return {"error":str(e)}

def get_vix():
    if not HAS_MD:
        return {"error":"market data unavailable"}
    out={}
    for which in ("india","us"):
        try:
            out[which]=md.get_vix(which).format()
        except Exception as e:
            out[which]=f"unavailable: {e}"
    return out

def get_crypto_price(symbol):
    if not HAS_MD:
        return {"error":"market data unavailable"}
    try:
        data=md.get_crypto_price(symbol.lower())
        return {"symbol":symbol.upper(),**data}
    except Exception as e:
        return {"error":str(e)}

def get_crypto_signal(symbol):
    if not HAS_CRYPTO:
        return {"error":"crypto_expert unavailable"}
    try:
        return crypto_ai.analyze_binance_spot(symbol.upper())
    except Exception as e:
        return {"error":str(e)}

def get_option_chain_summary(symbol,count=10):
    if not HAS_NSE:
        return {"error":"nse_option_chain unavailable"}
    try:
        data,source=nse_oc.get_option_chain_with_fallback(symbol.upper(),count=count)
        if not data:
            return {"error":f"Option chain unavailable for {symbol}"}
        records=data.get("records",{})
        data_list=records.get("data",[])[:count]
        rows=[]
        for entry in data_list:
            ce=entry.get("CE") or {}
            pe=entry.get("PE") or {}
            rows.append({"strike":entry.get("strikePrice"),"ce_oi":ce.get("openInterest"),"ce_chg_oi":ce.get("changeinOpenInterest"),"ce_ltp":ce.get("lastPrice"),"pe_oi":pe.get("openInterest"),"pe_chg_oi":pe.get("changeinOpenInterest"),"pe_ltp":pe.get("lastPrice")})
        return {"symbol":symbol.upper(),"source":source,"underlying_price":records.get("underlyingValue"),"expiry":records.get("expiryDate"),"strikes":rows}
    except Exception as e:
        return {"error":str(e)}

def get_institutional_signal(symbol,capital=None):
    if not HAS_INST:
        return {"error":"institutional_strategy unavailable"}
    try:
        option_chain_data=None
        if HAS_NSE:
            try:
                option_chain_data,_=nse_oc.get_option_chain_with_fallback(symbol,count=15)
            except:
                pass
        signal=inst_ai.generate_ai_signal(symbol,option_chain_data)
        result={"symbol":symbol.upper(),"signal_type":signal.signal_type,"entry_strike":signal.entry_strike,"entry_type":signal.entry_type,"entry_price_hint":signal.entry_price_hint,"target":signal.target,"stoploss":signal.stoploss,"probability":signal.probability,"risk_reward":signal.risk_reward,"max_pain":signal.max_pain,"pcr":signal.pcr,"support_resistance":signal.support_resistance,"reasoning":signal.reasoning[:6]}
        if capital and HAS_POS:
            try:
                plan=pos_sizing.plan_position(symbol,signal,float(capital),option_chain_data)
                result["capital_plan"]=plan
            except Exception as e:
                result["capital_plan_error"]=str(e)
        return result
    except Exception as e:
        return {"error":f"Signal failed: {e}"}

def subscribe_notifications(chat_id,symbol=None,capital=None,min_probability=None):
    if not HAS_WATCHER:
        return {"error":"market_watcher unavailable"}
    try:
        sub=market_watcher.subscribe(chat_id,symbol=symbol,capital=capital,min_probability=min_probability)
        return {"status":"subscribed",**sub}
    except Exception as e:
        return {"error":str(e)}

def unsubscribe_notifications(chat_id):
    if not HAS_WATCHER:
        return {"error":"market_watcher unavailable"}
    try:
        market_watcher.unsubscribe(chat_id)
        return {"status":"unsubscribed"}
    except Exception as e:
        return {"error":str(e)}
