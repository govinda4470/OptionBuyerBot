"""Market data - Robust Yahoo fallback"""
import time, logging, requests
import yfinance as yf
from dataclasses import dataclass
from typing import Optional
logger = logging.getLogger(__name__)
INDEX_TICKERS = {"nifty": ("^NSEI", "NIFTY 50"), "sensex": ("^BSESN", "SENSEX"), "banknifty": ("^NSEBANK", "BANK NIFTY"), "finnifty": ("^CNXFIN", "FIN NIFTY")}
VIX_TICKERS = {"india": ("^INDIAVIX", "INDIA VIX"), "us": ("^VIX", "CBOE VIX")}
GLOBAL_TICKERS = [("^DJI", "Dow"), ("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq")]
CRYPTO_IDS = {"btc":"bitcoin","eth":"ethereum","sol":"solana"}
_CACHE={}
_CACHE_TTL=20
def _cached(k,f):
    now=time.time()
    if k in _CACHE:
        ts,v=_CACHE[k]
        if now-ts<_CACHE_TTL:
            return v
    v=f()
    _CACHE[k]=(now,v)
    return v
@dataclass
class Quote:
    name:str; symbol:str; price:float; previous_close:Optional[float]=None; source:str="yfinance"; is_market_closed:bool=False
    @property
    def change(self):
        return None if self.previous_close in (None,0) else self.price-self.previous_close
    @property
    def change_pct(self):
        return None if self.previous_close in (None,0) else (self.change/self.previous_close)*100
    def format(self):
        line=f"{self.name} ({self.symbol}): {self.price:,.2f}"
        if self.change is not None:
            arrow="🟢" if self.change>=0 else "🔴"
            line+=f"  {arrow} {self.change:+,.2f} ({self.change_pct:+.2f}%)"
        return line
def _fetch_quote_robust(ticker,name):
    def fetch():
        try:
            t=yf.Ticker(ticker)
            fi=t.fast_info
            if fi and getattr(fi,"last_price",None) is not None:
                return Quote(name=name,symbol=ticker,price=float(fi.last_price),previous_close=float(getattr(fi,"previous_close",0) or 0) or None,source="yfinance fast_info")
        except Exception as e:
            logger.debug(f"fast_info {ticker} failed: {e}")
        for period in ["1d","5d","1mo"]:
            try:
                t=yf.Ticker(ticker)
                hist=t.history(period=period,auto_adjust=False,timeout=10)
                if hist is not None and not hist.empty:
                    price=float(hist["Close"].iloc[-1])
                    prev=float(hist["Close"].iloc[-2]) if len(hist)>=2 else None
                    return Quote(name=name,symbol=ticker,price=price,previous_close=prev,source=f"history {period}",is_market_closed=True)
            except:
                continue
        # Yahoo chart API fallback
        try:
            url=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            resp=requests.get(url,params={"range":"5d","interval":"1d"},headers={"User-Agent":"Mozilla/5.0"},timeout=12)
            if resp.status_code==200:
                data=resp.json()
                result=data.get("chart",{}).get("result",[])
                if result:
                    meta=result[0].get("meta",{})
                    price=meta.get("regularMarketPrice") or meta.get("previousClose")
                    prev=meta.get("previousClose")
                    if price:
                        return Quote(name=name,symbol=ticker,price=float(price),previous_close=float(prev) if prev else None,source="Yahoo Chart API")
        except Exception as e:
            logger.debug(f"Chart API {ticker} failed: {e}")
        raise ValueError(f"No price for {ticker}")
    return _cached(f"quote:{ticker}",fetch)
def get_index_quote(key):
    key=key.lower().strip()
    ticker,name=INDEX_TICKERS[key]
    return _fetch_quote_robust(ticker,name)
def get_vix(which="india"):
    which=which.lower().strip()
    ticker,name=VIX_TICKERS[which]
    return _fetch_quote_robust(ticker,name)
def get_stock_quote(symbol):
    symbol=symbol.upper().strip()
    cands=[symbol] if "." in symbol else [f"{symbol}.NS",f"{symbol}.BO",symbol]
    def fetch():
        last=None
        for cand in cands:
            try:
                return _fetch_quote_robust(cand,symbol)
            except Exception as e:
                last=e
                continue
        raise ValueError(f"Could not find {symbol}: {last}")
    return _cached(f"stock:{symbol}",fetch)
def get_global_markets():
    def fetch():
        quotes=[]
        for ticker,name in GLOBAL_TICKERS:
            try:
                quotes.append(_fetch_quote_robust(ticker,name))
            except:
                continue
        if not quotes:
            raise ValueError("No global markets")
        return quotes
    return _cached("global",fetch)
def get_crypto_price(symbol):
    symbol=symbol.lower().strip()
    coin_id=CRYPTO_IDS.get(symbol,symbol)
    def fetch():
        resp=requests.get("https://api.coingecko.com/api/v3/simple/price",params={"ids":coin_id,"vs_currencies":"usd,inr","include_24hr_change":"true"},timeout=12,headers={"User-Agent":"Mozilla/5.0"})
        resp.raise_for_status()
        data=resp.json()
        if coin_id not in data:
            raise KeyError(f"Unknown crypto {symbol}")
        return data[coin_id]
    return _cached(f"crypto:{coin_id}",fetch)
OPTION_CHAIN_UNAVAILABLE_NOTE="📊 Option Chain: NSE blocks datacenter IPs. Use /free_chain NIFTY proxy bypass or /crypto_option BTC (free, works)."
