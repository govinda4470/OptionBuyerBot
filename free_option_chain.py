import requests, logging
logger = logging.getLogger(__name__)
PROXY_TEMPLATES=["https://api.allorigins.win/raw?url={url}","https://api.codetabs.com/v1/proxy?quest={url}"]
def _fetch_via_proxy(nse_url):
    for tmpl in PROXY_TEMPLATES:
        try:
            proxy_url=tmpl.format(url=nse_url)
            resp=requests.get(proxy_url,headers={"User-Agent":"Mozilla/5.0"},timeout=15)
            if resp.status_code==200 and len(resp.text)>100:
                try:
                    data=resp.json()
                    if isinstance(data, dict) and ("records" in data or "data" in str(data)[:100]):
                        return data
                    if isinstance(data, dict) and "contents" in data:
                        import json
                        inner=data["contents"]
                        return json.loads(inner) if isinstance(inner,str) else inner
                except:
                    try:
                        import json
                        return json.loads(resp.text)
                    except:
                        continue
        except Exception as e:
            continue
    return None
def get_nse_option_chain_free(symbol="NIFTY"):
    try:
        import nse_option_chain as nse_oc
        data,src=nse_oc.get_option_chain_with_fallback(symbol,count=15)
        if data:
            return data
    except:
        pass
    nse_url=f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}" if symbol in ["NIFTY","BANKNIFTY","FINNIFTY"] else f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
    return _fetch_via_proxy(nse_url)
DERIBIT_BASE="https://www.deribit.com/api/v2"
def get_deribit_book_summary(currency="BTC", kind="option"):
    try:
        url=f"{DERIBIT_BASE}/public/get_book_summary_by_currency"
        resp=requests.get(url,params={"currency":currency,"kind":kind},timeout=15)
        if resp.status_code==200:
            return resp.json().get("result",[])
    except Exception as e:
        logger.error(f"Deribit book summary failed: {e}")
    return []
def get_deribit_option_chain(currency="BTC", count=10):
    try:
        summary=get_deribit_book_summary(currency,"option")
        if not summary:
            return {}
        from collections import defaultdict
        import re
        chain_by_expiry=defaultdict(list)
        for item in summary:
            inst=item.get("instrument_name","")
            m=re.match(r"(\w+)-(\d+\w+\d+)-(\d+)-([CP])",inst)
            if m:
                expiry=m.group(2)
                strike=int(m.group(3))
                opt_type=m.group(4)
                chain_by_expiry[expiry].append({"instrument":inst,"strike":strike,"type":opt_type,"mark_price":item.get("mark_price",0),"last_price":item.get("last_price",0),"open_interest":item.get("open_interest",0),"volume":item.get("volume",0),"iv":item.get("mark_iv",0),"bid":item.get("bid_price",0),"ask":item.get("ask_price",0)})
        if not chain_by_expiry:
            return {}
        nearest_expiry=sorted(chain_by_expiry.keys())[0]
        options=chain_by_expiry[nearest_expiry]
        strike_map=defaultdict(dict)
        for opt in options:
            strike_map[opt["strike"]][opt["type"]]=opt
        strikes=sorted(strike_map.keys())
        # Find ATM
        try:
            idx_resp=requests.get(f"{DERIBIT_BASE}/public/get_index_price",params={"index_name":f"{currency.lower()}_usd"},timeout=5)
            btc_price=idx_resp.json().get("result",{}).get("index_price",64000) if idx_resp.status_code==200 else 64000
        except:
            btc_price=64000
        atm=min(strikes,key=lambda x: abs(x-btc_price)) if strikes else 0
        atm_idx=strikes.index(atm) if atm in strikes else len(strikes)//2
        start=max(0,atm_idx-count)
        end=min(len(strikes),atm_idx+count+1)
        selected=strikes[start:end]
        return {"currency":currency,"expiry":nearest_expiry,"underlying_price":btc_price,"strikes":selected,"chain":{s:strike_map[s] for s in selected},"atm":atm}
    except Exception as e:
        logger.exception(f"Deribit chain {currency} failed: {e}")
        return {}
def format_deribit_chain_for_telegram(chain_data, currency="BTC"):
    try:
        if not chain_data or not chain_data.get("chain"):
            return f"❌ No Deribit chain for {currency}"
        atm=chain_data.get("atm",0)
        underlying=chain_data.get("underlying_price",0)
        expiry=chain_data.get("expiry","N/A")
        chain=chain_data.get("chain",{})
        lines=[f"₿ <b>Deribit {currency} Options (Free, Works on Replit)</b>",f"Underlying: ${underlying:,.2f} | ATM: {atm} | Expiry: {expiry}","","Strike | C Mark | C IV | C OI | P Mark | P IV | P OI","-------|--------|------|------|--------|------|------"]
        for strike in sorted(chain.keys()):
            c=chain[strike].get("C",{})
            p=chain[strike].get("P",{})
            lines.append(f"{strike} | {c.get('mark_price',0):.4f} | {c.get('iv',0):.1f}% | {c.get('open_interest',0):.1f} | {p.get('mark_price',0):.4f} | {p.get('iv',0):.1f}% | {p.get('open_interest',0):.1f}")
        lines.append("")
        lines.append("💡 Deribit 80% global crypto options volume")
        return "\n".join(lines)
    except Exception as e:
        return f"Format error: {e}"
def get_binance_option_chain(symbol="BTC"):
    try:
        url="https://eapi.binance.com/eapi/v1/exchangeInfo"
        resp=requests.get(url,timeout=10)
        if resp.status_code!=200:
            return None
        data=resp.json()
        symbols=[s for s in data.get("optionSymbols",[]) if symbol in s.get("symbol","")]
        return {"symbols":symbols[:20],"source":"Binance EAPI"}
    except Exception as e:
        logger.error(f"Binance chain {symbol} failed: {e}")
        return None
