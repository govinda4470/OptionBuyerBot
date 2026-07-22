"""VarunS2002 Ported"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
logger = logging.getLogger(__name__)
try:
    import nse_option_chain as nse_oc
    HAS_NSE=True
except:
    HAS_NSE=False
def fetch_option_chain_dataframe(symbol="NIFTY", expiry=None):
    return None
def parse_nse_v3_data(data):
    try:
        if not data:
            return [],0,""
        records=data.get("records",{}) if isinstance(data,dict) else {}
        data_list=records.get("data",[]) if isinstance(records,dict) else []
        underlying=records.get("underlyingValue",0) if isinstance(records,dict) else 0
        timestamp=records.get("timestamp","") if isinstance(records,dict) else ""
        return data_list,float(underlying) if underlying else 0,timestamp
    except Exception as e:
        logger.error(f"Parse failed: {e}")
        return [],0,""
def calculate_varun_indicators(data_list, strike_price, underlying=0):
    try:
        if not data_list:
            return {"error":"No data"}
        strikes=[]
        ce_oi=[]
        pe_oi=[]
        ce_chg=[]
        pe_chg=[]
        for entry in sorted(data_list,key=lambda x: x.get("strikePrice",0)):
            sp=entry.get("strikePrice")
            if sp is None:
                continue
            ce=entry.get("CE",{})
            pe=entry.get("PE",{})
            strikes.append(float(sp))
            ce_oi.append(int(ce.get("openInterest",0) if ce else 0))
            pe_oi.append(int(pe.get("openInterest",0) if pe else 0))
            ce_chg.append(int(ce.get("changeinOpenInterest",0) if ce else 0))
            pe_chg.append(int(pe.get("changeinOpenInterest",0) if pe else 0))
        if not strikes:
            return {"error":"No strikes"}
        max_call_oi=max(ce_oi) if ce_oi else 0
        max_call_idx=ce_oi.index(max_call_oi) if ce_oi else 0
        max_call_sp=strikes[max_call_idx] if max_call_idx < len(strikes) else 0
        max_put_oi=max(pe_oi) if pe_oi else 0
        max_put_idx=pe_oi.index(max_put_oi) if pe_oi else 0
        max_put_sp=strikes[max_put_idx] if max_put_idx < len(strikes) else 0
        total_call=sum(ce_oi)
        total_put=sum(pe_oi)
        pcr=round(total_put/max(1,total_call),2)
        try:
            idx=strikes.index(float(strike_price))
        except ValueError:
            idx=min(range(len(strikes)),key=lambda i: abs(strikes[i]-float(strike_price)))
        def get_ce(i):
            return ce_chg[i] if 0<=i<len(ce_chg) else 0
        def get_pe(i):
            return pe_chg[i] if 0<=i<len(pe_chg) else 0
        c1=get_ce(idx)
        c2=get_ce(idx+1)
        c3=get_ce(idx+2)
        call_sum=c1+c2+c3
        call_boundary=c3
        p1=get_pe(idx)
        p2=get_pe(idx+1)
        p3=get_pe(idx+2)
        p4=get_pe(idx+4)
        p5=get_ce(idx+4)
        p6=get_ce(idx-2)
        p7=get_pe(idx-2)
        put_sum=p1+p2+p3
        put_boundary=p1
        difference=call_sum-put_sum
        def set_itm_labels(call_change,put_change):
            label="No"
            if put_change>call_change:
                if put_change>=0:
                    if call_change<=0:
                        label="Yes"
                    elif call_change!=0 and put_change/call_change>1.5:
                        label="Yes"
                else:
                    if call_change!=0 and put_change/call_change<0.5:
                        label="Yes"
            if call_change<=0:
                label="Yes"
            return label
        call_itm=set_itm_labels(call_change=p5,put_change=p4)
        put_itm=set_itm_labels(call_change=p7,put_change=p6)
        if call_sum>=put_sum:
            oi_label="Bearish"
        else:
            oi_label="Bullish"
        call_exits="Yes" if (call_boundary<=0 or call_sum<=0) else "No"
        put_exits="Yes" if (put_boundary<=0 or put_sum<=0) else "No"
        return {
            "strike_price":float(strike_price),
            "underlying":underlying,
            "max_call_oi":max_call_oi,
            "max_call_oi_sp":max_call_sp,
            "max_call_oi_2":0,
            "max_call_oi_sp_2":0,
            "max_put_oi":max_put_oi,
            "max_put_oi_sp":max_put_sp,
            "max_put_oi_2":0,
            "max_put_oi_sp_2":0,
            "total_call_oi":total_call,
            "total_put_oi":total_put,
            "pcr":pcr,
            "call_sum":call_sum,
            "put_sum":put_sum,
            "difference":difference,
            "call_boundary":call_boundary,
            "put_boundary":put_boundary,
            "call_itm":call_itm,
            "put_itm":put_itm,
            "oi_label":oi_label,
            "call_exits":call_exits,
            "put_exits":put_exits,
            "p4":p4,"p5":p5,"p6":p6,"p7":p7,
        }
    except Exception as e:
        import traceback
        logger.error(f"Varun calc failed: {e}\n{traceback.format_exc()}")
        return {"error":str(e)}

def format_varun_for_telegram(indicators,symbol="NIFTY"):
    if "error" in indicators:
        return f"❌ Varun error {symbol}: {indicators['error']}"
    is_index=symbol.upper() in ["NIFTY","BANKNIFTY","FINNIFTY","SENSEX"]
    divisor=1000 if is_index else 10
    unit="in K" if is_index else "in 10s"
    def fmt_k(v):
        return f"{round(v/divisor,1)} {unit}" if v!=0 else f"0 {unit}"
    lines=[
        f"📊 <b>Varun NSE Analyzer: {symbol} @ {indicators['strike_price']}</b>",
        f"Underlying: {indicators['underlying']} | PCR: {indicators['pcr']} | OI: {indicators['oi_label']}","",
        f"<b>OI Upper Boundary (Resistance):</b>",
        f"  • Strike 1: {indicators['max_call_oi_sp']} - OI {fmt_k(indicators['max_call_oi'])}",
        f"",
        f"<b>OI Lower Boundary (Support):</b>",
        f"  • Strike 1: {indicators['max_put_oi_sp']} - OI {fmt_k(indicators['max_put_oi'])}","",
        f"<b>Varun Core (Strike {indicators['strike_price']}):</b>",
        f"  • Call Sum ({unit}) [SP+next2]: {fmt_k(indicators['call_sum'])}",
        f"  • Put Sum ({unit}) [SP+next2]: {fmt_k(indicators['put_sum'])}",
        f"  • Difference: {fmt_k(indicators['difference'])} | {indicators['oi_label']}",
        f"  • Call Boundary ({unit}) [2 above]: {fmt_k(indicators['call_boundary'])}",
        f"  • Put Boundary ({unit}) [at SP]: {fmt_k(indicators['put_boundary'])}","",
        f"<b>ITM Signals:</b>",
        f"  • Call ITM: {indicators['call_itm']}",
        f"  • Put ITM: {indicators['put_itm']}","",
        f"<b>Exits:</b>",
        f"  • Call Exits: {indicators['call_exits']}",
        f"  • Put Exits: {indicators['put_exits']}","",
        f"⏱️ {datetime.now().strftime('%H:%M:%S IST')} | Varun v5.8 ported"
    ]
    text="\n".join(lines)
    if len(text)>3900:
        text=text[:3900]+"... truncated"
    return text
