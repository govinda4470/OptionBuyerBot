"""
NSE Option Chain - Robust version with v3 API + Proxy Bypass + Session Cookies
Fixes:
- NSE deprecated old endpoints /api/option-chain-indices and /api/option-chain-equities (now 404)
- New v3 endpoint: /api/option-chain-v3?type=Indices&symbol=NIFTY&expiry=12-Dec-2024
- Requires: First get cookies from /option-chain, then get contract-info for expiry dates
- Works with session handling, and fallback to free proxies (AllOrigins, CodeTabs, corsproxy.io) to bypass 403 datacenter block
"""

import requests
import time
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Cache for cookies and data
_NSE_COOKIES = None
_NSE_COOKIE_TIME = 0
_CACHE = {}
_CACHE_TTL = 30

def _get_nse_session():
    global _NSE_COOKIES, _NSE_COOKIE_TIME
    now = time.time()
    if _NSE_COOKIES is None or (now - _NSE_COOKIE_TIME > 300):
        try:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            # Get main page and option-chain page for cookies
            session.get("https://www.nseindia.com", headers=headers, timeout=15)
            session.get("https://www.nseindia.com/option-chain", headers=headers, timeout=15)
            _NSE_COOKIES = session.cookies
            _NSE_COOKIE_TIME = now
            logger.info("NSE cookies refreshed")
            return session
        except Exception as e:
            logger.error(f"NSE cookie fetch failed: {e}")
            return requests.Session()
    else:
        session = requests.Session()
        session.cookies = _NSE_COOKIES
        return session


def _fetch_nse_api(url: str, params: Dict = None, use_proxy: bool = False) -> Optional[Dict]:
    """Fetch NSE API with session, with optional proxy fallback"""
    # Try direct first
    try:
        session = _get_nse_session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/option-chain",
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive",
        }
        resp = session.get(url, headers=headers, params=params, timeout=15, cookies=_NSE_COOKIES)
        logger.info(f"NSE direct {url} params {params} status {resp.status_code} len {len(resp.text)}")
        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception as e:
                logger.error(f"NSE JSON parse failed: {e}, body preview: {resp.text[:500]}")
                return None
        elif resp.status_code in [401, 403, 404]:
            # Need fresh cookies or endpoint deprecated, try proxy
            if not use_proxy:
                # Try with proxy
                return _fetch_via_proxy(url, params)
            return None
        else:
            logger.error(f"NSE API {resp.status_code}: {resp.text[:500]}")
            if not use_proxy:
                return _fetch_via_proxy(url, params)
            return None
    except Exception as e:
        logger.error(f"NSE direct fetch error {url}: {e}")
        if not use_proxy:
            return _fetch_via_proxy(url, params)
        return None


def _fetch_via_proxy(nse_url: str, params: Dict = None) -> Optional[Dict]:
    """Try free proxies to bypass NSE 403 datacenter block"""
    # Build full URL with params
    full_url = nse_url
    if params:
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{nse_url}?{query}" if "?" not in nse_url else f"{nse_url}&{query}"

    proxy_templates = [
        "https://api.allorigins.win/raw?url={url}",
        "https://api.codetabs.com/v1/proxy?quest={url}",
        "https://corsproxy.io/?{url}",
        "https://thingproxy.freeboard.io/fetch/{url}",
    ]

    for tmpl in proxy_templates:
        try:
            proxy_url = tmpl.format(url=full_url)
            logger.info(f"Trying proxy {tmpl[:30]} for {full_url[:60]}")
            resp = requests.get(proxy_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            if resp.status_code == 200 and len(resp.text) > 200:
                try:
                    # AllOrigins raw returns JSON directly
                    # CodeTabs returns JSON
                    # Some proxies wrap in JSON with contents field
                    import json
                    try:
                        data = resp.json()
                    except:
                        data = json.loads(resp.text)

                    # Handle AllOrigins wrapper
                    if isinstance(data, dict) and "contents" in data:
                        inner = data["contents"]
                        if isinstance(inner, str):
                            data = json.loads(inner)
                        else:
                            data = inner

                    if isinstance(data, dict) and ("records" in data or "data" in data or "filtered" in data or "expiryDates" in data):
                        logger.info(f"Proxy success {tmpl[:30]} for {full_url[:60]}")
                        return data
                except Exception as e:
                    logger.debug(f"Proxy {tmpl[:30]} parse failed: {e}")
                    continue
        except Exception as e:
            logger.debug(f"Proxy {tmpl[:30]} failed: {e}")
            continue
    logger.warning(f"All proxies failed for {full_url}")
    return None


def get_expiry_dates(symbol: str = "NIFTY", is_index: bool = True) -> list:
    """Get expiry dates for symbol via contract-info API"""
    try:
        # Endpoint: https://www.nseindia.com/api/option-chain-contract-info?symbol=NIFTY
        url = f"https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol}"
        data = _fetch_nse_api(url, use_proxy=False)
        if data is None:
            data = _fetch_nse_api(url, use_proxy=True)
        if data:
            # Try different keys for expiry dates
            if "expiryDates" in data:
                return data["expiryDates"]
            if "records" in data and "expiryDates" in data["records"]:
                return data["records"]["expiryDates"]
        return []
    except Exception as e:
        logger.error(f"Get expiry dates {symbol} failed: {e}")
        return []


def get_option_chain_v3(symbol: str = "NIFTY", expiry: str = None, is_index: bool = True) -> Optional[Dict]:
    """
    Get option chain via new v3 API (replaces deprecated v2)
    URL: https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=NIFTY&expiry=12-Dec-2024
    For stocks: type=Equity
    """
    try:
        if not expiry:
            # Get nearest expiry
            expiries = get_expiry_dates(symbol, is_index)
            if not expiries:
                # Try direct without expiry? Some endpoints work without expiry for nearest?
                logger.warning(f"No expiry found for {symbol}, trying without expiry param")
                # Fallback to old v2 for indices (might still work for some symbols)
                return None
            expiry = expiries[0]

        type_param = "Indices" if is_index else "Equity"
        url = "https://www.nseindia.com/api/option-chain-v3"
        params = {"type": type_param, "symbol": symbol, "expiry": expiry}

        # Try direct
        data = _fetch_nse_api(url, params=params, use_proxy=False)
        if data is None:
            # Try proxy
            data = _fetch_nse_api(url, params=params, use_proxy=True)

        return data
    except Exception as e:
        logger.error(f"v3 chain {symbol} expiry {expiry} failed: {e}")
        return None


# Legacy functions for backward compatibility - now use v3 internally
def get_nse_option_chain_indices(symbol: str = "NIFTY", count: int = 10) -> Optional[Dict]:
    """Legacy - now uses v3"""
    return get_option_chain_v3(symbol, expiry=None, is_index=True)

def get_nse_option_chain_equities(symbol: str = "RELIANCE", count: int = 10) -> Optional[Dict]:
    """Legacy - now uses v3 for equities"""
    return get_option_chain_v3(symbol, expiry=None, is_index=False)


def format_nse_chain_for_telegram(data, symbol, count=5, underlying_price=None):
    try:
        if not data:
            return f"❌ No data for {symbol}"

        # Handle v3 structure
        records = data.get("records", {}) if isinstance(data, dict) else {}
        # v3 has filtered data? Let's try to parse
        # v3 structure may have data.filtered.data or records.data
        data_list = []
        if "filtered" in data:
            # v3 filtered
            filtered = data["filtered"]
            data_list = filtered.get("data", []) if isinstance(filtered, dict) else []
            underlying = filtered.get("underlyingValue") or records.get("underlyingValue") or underlying_price
        else:
            data_list = records.get("data", []) if isinstance(records, dict) else []
            underlying = records.get("underlyingValue") or underlying_price

        if not data_list and "data" in data:
            # Sometimes data is directly list
            data_list = data["data"] if isinstance(data["data"], list) else []

        if not data_list:
            # Try alternative: data may have CE/PE directly?
            return f"📊 Option Chain raw for {symbol}: {str(data)[:1000]}... (parsing v3)"

        # Sort by strike proximity to underlying if available
        if underlying:
            data_list_sorted = sorted(data_list, key=lambda x: abs(x.get("strikePrice", 0) - underlying))
            selected = data_list_sorted[:count*2+1]
            selected_sorted = sorted(selected, key=lambda x: x.get("strikePrice", 0))
        else:
            selected_sorted = data_list[:count*2+1]

        lines = [f"📊 Option Chain: {symbol} (NSE v3 Direct)", f"Underlying: {underlying if underlying else 'N/A'}", "", "Strike | CE LTP | PE LTP", "-------|--------|--------"]
        for entry in selected_sorted:
            sp = entry.get("strikePrice", "?")
            ce = entry.get("CE", {}).get("lastPrice", "-") if isinstance(entry.get("CE"), dict) else "-"
            pe = entry.get("PE", {}).get("lastPrice", "-") if isinstance(entry.get("PE"), dict) else "-"
            # v3 may have CE/PE as direct?
            if ce == "-" and "CE" in entry:
                ce_data = entry["CE"]
                if isinstance(ce_data, dict):
                    ce = ce_data.get("lastPrice", ce_data.get("last_price", "-"))
            if pe == "-" and "PE" in entry:
                pe_data = entry["PE"]
                if isinstance(pe_data, dict):
                    pe = pe_data.get("lastPrice", pe_data.get("last_price", "-"))
            lines.append(f"{sp} | {ce} | {pe}")

        lines.append("")
        lines.append(f"⏱️ {records.get('timestamp','') if isinstance(records, dict) else ''}")
        lines.append("✅ NSE v3 direct (bypasses deprecated v2 404)")

        return "\n".join(lines)
    except Exception as e:
        import traceback
        logger.error(f"Format NSE chain failed {symbol}: {e}\n{traceback.format_exc()}")
        return f"❌ Format failed {symbol}: {e}"


def get_option_chain_with_fallback(symbol="NIFTY", count=10):
    """
    Try v3 first, then free proxy, then old endpoints
    """
    symbol = symbol.upper()
    is_index = symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX", "MIDCPNIFTY"]

    # Try v3 direct
    data = get_option_chain_v3(symbol, expiry=None, is_index=is_index)
    if data:
        return data, "NSE v3 Direct"

    # Try via proxy (free bypass)
    try:
        from free_option_chain import get_nse_option_chain_free
        data = get_nse_option_chain_free(symbol)
        if data:
            return data, "NSE via Free Proxy"
    except Exception as e:
        logger.debug(f"Free proxy fallback failed for {symbol}: {e}")

    # Try old v2 via proxy as last resort
    try:
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}" if is_index else f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
        data = _fetch_via_proxy(url)
        if data:
            return data, "NSE v2 via Proxy"
    except:
        pass

    return None, "None"
