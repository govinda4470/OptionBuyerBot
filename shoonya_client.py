import os, time, json, hashlib, logging, threading
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)
try:
    import pyotp
    HAS_PYOTP=True
except:
    HAS_PYOTP=False
try:
    import requests
    HAS_REQUESTS=True
except:
    HAS_REQUESTS=False
try:
    from NorenRestApiPy.NorenApi import NorenApi
    class ShoonyaApiPy(NorenApi):
        def __init__(self):
            NorenApi.__init__(self, host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')
    HAS_SHOONYA_LIB=True
except:
    HAS_SHOONYA_LIB=False
_api_instance=None
_login_time=0
_lock=threading.Lock()
_TTL=3600*6
def get_env_credentials():
    return {
        "user_id": os.getenv("SHOONYA_USER_ID") or os.getenv("SHOONYA_CLIENT_ID"),
        "password": os.getenv("SHOONYA_PASSWORD"),
        "vendor_code": os.getenv("SHOONYA_VENDOR_CODE") or os.getenv("SHOONYA_VC"),
        "api_secret": os.getenv("SHOONYA_API_SECRET") or os.getenv("SHOONYA_API_KEY"),
        "imei": os.getenv("SHOONYA_IMEI") or "optionbuyerbot123",
        "totp_secret": os.getenv("SHOONYA_TOTP_SECRET") or os.getenv("SHOONYA_TOTP"),
        "two_fa_otp": os.getenv("SHOONYA_TWO_FA") or os.getenv("SHOONYA_OTP") or os.getenv("SHOONYA_TPIN") or os.getenv("SHOONYA_PIN"),
    }
def is_shoonya_configured():
    c=get_env_credentials()
    return all([c["user_id"],c["password"],c["vendor_code"],c["api_secret"],(c["totp_secret"] or c["two_fa_otp"])])
def get_config_status():
    c=get_env_credentials()
    st={}
    for k in ["user_id","password","vendor_code","api_secret","imei"]:
        st[k]=bool(c.get(k))
    if c.get("totp_secret"):
        st["second_factor_type"]="TOTP_SECRET (auto 24/7 ✅ best)"
        st["second_factor_present"]=True
    elif c.get("two_fa_otp"):
        st["second_factor_type"]=f"OTP/TPIN {len(c['two_fa_otp'])}-digit"
        st["second_factor_present"]=True
    else:
        st["second_factor_type"]="MISSING"
        st["second_factor_present"]=False
    st["configured"]=is_shoonya_configured()
    return st
def _generate_second_factor():
    c=get_env_credentials()
    if c["totp_secret"]:
        s=c["totp_secret"].strip().replace(" ","")
        if len(s)<=8 and s.isdigit():
            return s
        if not HAS_PYOTP:
            raise RuntimeError("pyotp missing")
        try:
            import pyotp
            totp=pyotp.TOTP(s)
            return totp.now()
        except:
            return s
    if c["two_fa_otp"]:
        return c["two_fa_otp"].strip().replace(" ","")
    raise ValueError("No second factor")
def _direct_login_http(user_id,password,factor2,vendor_code,api_secret,imei):
    def _sha256(s): return hashlib.sha256(s.encode()).hexdigest()
    appkey=hashlib.sha256(f"{user_id}|{api_secret}".encode()).hexdigest()
    payloads=[
        {"apkversion":"1.0.0","uid":user_id,"pwd":password,"factor2":factor2,"vc":vendor_code,"appkey":appkey,"imei":imei,"source":"API"},
        {"apkversion":"1.0.0","uid":user_id,"pwd":_sha256(password),"factor2":factor2,"vc":vendor_code,"appkey":appkey,"imei":imei,"source":"API"},
    ]
    last_err=None
    for jdata in payloads:
        try:
            url="https://api.shoonya.com/NorenWClientTP/QuickAuth"
            data={"jData":json.dumps(jdata),"jKey":""}
            headers={"Content-Type":"application/x-www-form-urlencoded","User-Agent":"ShoonyaBot/1.0"}
            resp=requests.post(url,data=data,headers=headers,timeout=15)
            raw=resp.text
            if not raw.strip():
                last_err=f"Empty response HTTP {resp.status_code} - IP not whitelisted?"
                continue
            try:
                return resp.json()
            except Exception as je:
                last_err=f"Non-JSON HTTP {resp.status_code}: {raw[:500]} err {je}"
                continue
        except Exception as e:
            last_err=str(e)
            continue
    raise RuntimeError(last_err or "Direct login failed")
def login_shoonya(force=False):
    global _api_instance,_login_time
    with _lock:
        if not force and _api_instance is not None and (time.time()-_login_time<_TTL):
            return {"stat":"Ok","reused":True}
        if not HAS_SHOONYA_LIB:
            raise RuntimeError("NorenRestApiPy not installed")
        if not is_shoonya_configured():
            raise RuntimeError("Shoonya not configured")
        creds=get_env_credentials()
        factor2=_generate_second_factor()
        api=ShoonyaApiPy()
        ret=api.login(userid=creds["user_id"],password=creds["password"],twoFA=factor2,vendor_code=creds["vendor_code"],api_secret=creds["api_secret"],imei=creds["imei"])
        if ret is None:
            raise RuntimeError("Login returned None")
        if ret.get("stat")!="Ok":
            raise RuntimeError(f"Login failed: {ret.get('emsg') or ret}")
        _api_instance=api
        _login_time=time.time()
        return ret
def get_api():
    global _api_instance
    if _api_instance is None or (time.time()-_login_time>_TTL):
        login_shoonya()
    return _api_instance
def search_symbol(exchange,search_text):
    api=get_api()
    try:
        return api.searchscrip(exchange=exchange,searchtext=search_text)
    except:
        login_shoonya(force=True)
        return get_api().searchscrip(exchange=exchange,searchtext=search_text)
def get_quote(exchange,token):
    api=get_api()
    try:
        return api.get_quotes(exchange=exchange,token=token)
    except:
        login_shoonya(force=True)
        return get_api().get_quotes(exchange=exchange,token=token)
def get_option_chain(exchange,tradingsymbol,strikeprice,count=5):
    api=get_api()
    try:
        return api.get_option_chain(exchange=exchange,tradingsymbol=tradingsymbol,strikeprice=strikeprice,count=count)
    except:
        login_shoonya(force=True)
        return get_api().get_option_chain(exchange=exchange,tradingsymbol=tradingsymbol,strikeprice=strikeprice,count=count)
def get_index_via_shoonya(key):
    mapping={"nifty":"Nifty 50","sensex":"Sensex","banknifty":"Nifty Bank","finnifty":"Nifty Fin Service"}
    query=mapping.get(key.lower(),key)
    res=search_symbol("NSE",query)
    if not res or res.get("stat")!="Ok":
        raise ValueError(f"Search failed {query}: {res}")
    vals=res.get("values",[])
    if not vals:
        raise ValueError(f"No symbol for {query}")
    info=vals[0]
    q=get_quote(info.get("exch","NSE"),info["token"])
    return q,info
def get_stock_via_shoonya(symbol):
    for q in [f"{symbol}-EQ",symbol]:
        res=search_symbol("NSE",q)
        if res and res.get("stat")=="Ok" and res.get("values"):
            info=res["values"][0]
            qq=get_quote("NSE",info["token"])
            return qq,info
    raise ValueError(f"Could not find {symbol}")
