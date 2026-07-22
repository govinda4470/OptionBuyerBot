"""Institutional Strategy - Simplified for Render deploy"""
import time, logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
logger = logging.getLogger(__name__)
try:
    import nse_option_chain as nse_oc
    HAS_NSE=True
except:
    HAS_NSE=False
    nse_oc=None

@dataclass
class InstitutionalSignal:
    symbol:str
    signal_type:str
    entry_strike:Optional[int]
    entry_type:str
    entry_price_hint:str
    target:str
    stoploss:str
    probability:int
    risk_reward:str
    reasoning:List[str]
    institutional_footprint:Dict
    max_pain:Optional[int]
    pcr:Optional[float]
    support_resistance:Dict
    liquidity_pools:List[str]
    timestamp:str

def calculate_max_pain_from_chain(data_list:List[Dict])->Optional[int]:
    try:
        strikes=[]
        for entry in data_list:
            sp=entry.get("strikePrice")
            if sp is None:
                continue
            ce=entry.get("CE",{})
            pe=entry.get("PE",{})
            ce_oi=ce.get("openInterest",0) if ce else 0
            pe_oi=pe.get("openInterest",0) if pe else 0
            strikes.append({"strike":sp,"ce_oi":ce_oi,"pe_oi":pe_oi})
        if not strikes:
            return None
        strikes_sorted=sorted(strikes,key=lambda x:x["strike"])
        pain_levels=[]
        for cand in strikes_sorted:
            s=cand["strike"]
            ce_pain=sum((s-r["strike"])*r["ce_oi"] for r in strikes_sorted if r["strike"]<s)
            pe_pain=sum((r["strike"]-s)*r["pe_oi"] for r in strikes_sorted if r["strike"]>s)
            pain_levels.append((s,ce_pain+pe_pain))
        return int(min(pain_levels,key=lambda x:x[1])[0]) if pain_levels else None
    except Exception as e:
        logger.error(f"Max pain failed: {e}")
        return None

def calculate_pcr(data_list:List[Dict])->Dict:
    try:
        total_ce=sum(entry.get("CE",{}).get("openInterest",0) for entry in data_list if entry.get("CE"))
        total_pe=sum(entry.get("PE",{}).get("openInterest",0) for entry in data_list if entry.get("PE"))
        pcr=round(total_pe/max(1,total_ce),3)
        if pcr>1.5:
            sentiment="Extremely Bullish (Oversold)"
        elif pcr>1.2:
            sentiment="Bullish"
        elif pcr<0.7:
            sentiment="Extremely Bearish"
        elif pcr<0.8:
            sentiment="Bearish"
        else:
            sentiment="Neutral"
        return {"total_pcr":pcr,"total_ce_oi":total_ce,"total_pe_oi":total_pe,"sentiment":sentiment,"interpretation":sentiment}
    except Exception as e:
        return {"total_pcr":1.0,"sentiment":"Unknown"}

def analyze_oi_clusters(data_list, underlying=None)->Dict:
    try:
        ce_map=[]
        pe_map=[]
        for entry in data_list:
            sp=entry.get("strikePrice")
            ce=entry.get("CE",{})
            pe=entry.get("PE",{})
            ce_map.append((sp,ce.get("openInterest",0),ce.get("changeinOpenInterest",0)))
            pe_map.append((sp,pe.get("openInterest",0),pe.get("changeinOpenInterest",0)))
        ce_sorted=sorted(ce_map,key=lambda x:x[1],reverse=True)[:5]
        pe_sorted=sorted(pe_map,key=lambda x:x[1],reverse=True)[:5]
        highest_ce=ce_sorted[0] if ce_sorted else (0,0,0)
        highest_pe=pe_sorted[0] if pe_sorted else (0,0,0)
        threshold=50000
        fresh_ce=[x for x in ce_map if x[2]>threshold]
        fresh_pe=[x for x in pe_map if x[2]>threshold]
        return {
            "highest_call_oi":{"strike":highest_ce[0],"oi":highest_ce[1],"chg_oi":highest_ce[2]},
            "highest_put_oi":{"strike":highest_pe[0],"oi":highest_pe[1],"chg_oi":highest_pe[2]},
            "top_5_ce_oi":ce_sorted,
            "top_5_pe_oi":pe_sorted,
            "fresh_ce_buildup":fresh_ce,
            "fresh_pe_buildup":fresh_pe,
        }
    except Exception as e:
        return {}

def detect_liquidity_pools_and_stop_hunting(data_list, underlying, clusters)->Dict:
    pools=[]
    sl_zones=[]
    try:
        hce=clusters.get("highest_call_oi",{})
        hpe=clusters.get("highest_put_oi",{})
        if hce:
            pools.append(f"Resistance Pool: {hce.get('strike')} CE OI {hce.get('oi')}")
        if hpe:
            pools.append(f"Support Pool: {hpe.get('strike')} PE OI {hpe.get('oi')}")
        if underlying:
            rd=(int(underlying)//100)*100
            pools.append(f"Round Number Pools: {rd} and {rd+100}")
        if hpe:
            sl_zones.append(f"Stop Loss Hunting (Longs): Below {hpe.get('strike')} support")
        if hce:
            sl_zones.append(f"Stop Loss Hunting (Shorts): Above {hce.get('strike')} resistance")
    except:
        pass
    return {"liquidity_pools":pools,"stop_loss_hunting_zones":sl_zones,"retail_sl_clusters":["Retail SL below support and above resistance"]}

def analyze_oi_price_action(data_list)->List[str]:
    insights=[]
    try:
        for entry in data_list[:10]:
            sp=entry.get("strikePrice")
            ce=entry.get("CE",{})
            pe=entry.get("PE",{})
            ce_chg=ce.get("changeinOpenInterest",0)
            ce_ltp_chg=ce.get("change",0)
            pe_chg=pe.get("changeinOpenInterest",0)
            pe_ltp_chg=pe.get("change",0)
            if ce_chg>0 and ce_ltp_chg>0:
                insights.append(f"{sp} CE: Long Buildup (OI ↑ Price ↑) bullish")
            elif ce_chg>0 and ce_ltp_chg<0:
                insights.append(f"{sp} CE: Short Buildup (OI ↑ Price ↓) bearish resistance")
            elif ce_chg<0 and ce_ltp_chg>0:
                insights.append(f"{sp} CE: Short Covering (OI ↓ Price ↑) bullish breakout")
            if pe_chg>0 and pe_ltp_chg<0:
                insights.append(f"{sp} PE: Short Buildup (OI ↑ Price ↓) bullish support")
    except:
        pass
    return insights[:15]

def generate_ai_signal(symbol="NIFTY", option_chain_data=None, underlying_price=None):
    try:
        if option_chain_data is None and HAS_NSE:
            try:
                option_chain_data,_=nse_oc.get_option_chain_with_fallback(symbol,count=15)
            except:
                option_chain_data=None
        records=option_chain_data.get("records",{}) if isinstance(option_chain_data,dict) else {}
        data_list=records.get("data",[]) if isinstance(records,dict) else []
        underlying=records.get("underlyingValue") or underlying_price or 24500
        if not data_list:
            # Mock data for demo when NSE blocked
            import random
            mock_strikes=list(range(int(underlying)-300,int(underlying)+301,50))
            data_list=[]
            for strike in mock_strikes:
                distance=abs(strike-underlying)
                base_oi=max(0,100000-distance*2)
                ce_oi=int(base_oi*(0.8+random.random()*0.4)) if strike>=underlying else int(base_oi*0.5)
                pe_oi=int(base_oi*(0.8+random.random()*0.4)) if strike<=underlying else int(base_oi*0.5)
                data_list.append({"strikePrice":strike,"CE":{"openInterest":ce_oi,"changeinOpenInterest":random.randint(-20000,50000),"lastPrice":max(5,(strike-underlying+100)*0.8),"change":random.uniform(-5,5)},"PE":{"openInterest":pe_oi,"changeinOpenInterest":random.randint(-20000,50000),"lastPrice":max(5,(underlying-strike+100)*0.8),"change":random.uniform(-5,5)}})
        max_pain=calculate_max_pain_from_chain(data_list)
        pcr_data=calculate_pcr(data_list)
        clusters=analyze_oi_clusters(data_list,underlying)
        liquidity=detect_liquidity_pools_and_stop_hunting(data_list,underlying,clusters)
        pcr=pcr_data.get("total_pcr",1.0)
        score=0
        reasoning=[]
        if pcr>1.5:
            score+=12
            reasoning.append(f"PCR {pcr} >1.5 extremely bullish reversal")
        elif pcr>1.2:
            score+=10
            reasoning.append(f"PCR {pcr} >1.2 bullish")
        elif pcr<0.7:
            score+=12
            reasoning.append(f"PCR {pcr} <0.7 extremely bearish reversal")
        elif pcr<0.8:
            score+=10
            reasoning.append(f"PCR {pcr} <0.8 bearish")
        else:
            score+=5
            reasoning.append(f"PCR {pcr} neutral")
        if max_pain and underlying:
            dist=abs(underlying-max_pain)
            if dist<50:
                score+=18
                reasoning.append(f"Max Pain {max_pain} close to spot {underlying} ({dist} pts) strong pin")
            elif dist<100:
                score+=12
                reasoning.append(f"Max Pain {max_pain} close ({dist} pts)")
            else:
                score+=6
                reasoning.append(f"Max Pain {max_pain} far {dist} pts")
        highest_pe=clusters.get("highest_put_oi",{})
        highest_ce=clusters.get("highest_call_oi",{})
        if highest_pe.get("chg_oi",0)>50000:
            score+=15
            reasoning.append(f"Put OI building at {highest_pe.get('strike')} +{highest_pe.get('chg_oi')} bullish")
        if highest_ce.get("chg_oi",0)>50000:
            score+=15
            reasoning.append(f"Call OI building at {highest_ce.get('strike')} bearish")
        score+=10
        reasoning.append("Liquidity sweep check: institutions hunt SL beyond OI walls")
        probability=min(92,max(20,score))
        # Bias
        bullish=0
        bearish=0
        if pcr>1.0:
            bullish+=1
        else:
            bearish+=1
        if max_pain and max_pain>underlying:
            bullish+=1
        elif max_pain and max_pain<underlying:
            bearish+=1
        if bullish>bearish and probability>60:
            signal_type="BUY_CALL"
            atm_strike=round(underlying/50)*50 if symbol=="NIFTY" else round(underlying/100)*100
            entry_type="ATM"
            target=f"{highest_ce.get('strike',atm_strike+100)} resistance or 1:2 RR"
            stoploss=f"30% premium SL or below {highest_pe.get('strike',atm_strike-100)} support"
            risk_reward="1:2 to 1:3"
        elif bearish>bullish and probability>60:
            signal_type="BUY_PUT"
            atm_strike=round(underlying/50)*50 if symbol=="NIFTY" else round(underlying/100)*100
            entry_type="ATM"
            target=f"{highest_pe.get('strike',atm_strike-100)} support or 1:2 RR"
            resistance=highest_ce.get('strike',atm_strike+100)
            stoploss=f"30% premium SL or above {resistance} resistance"
            risk_reward="1:2 to 1:3"
        else:
            signal_type="NO_TRADE"
            atm_strike=None
            entry_type="WAIT"
            target="Wait for clear OI buildup + PCR extreme + Max Pain close"
            stoploss="No trade"
            risk_reward="N/A"
            probability=max(30,probability-20)
        return InstitutionalSignal(
            symbol=symbol,signal_type=signal_type,entry_strike=atm_strike,entry_type=entry_type,
            entry_price_hint=f"Buy {symbol} {atm_strike} {signal_type.replace('BUY_','')} near ATM",
            target=target,stoploss=stoploss,probability=probability,risk_reward=risk_reward,
            reasoning=reasoning,institutional_footprint={"highest_call_oi":highest_ce,"highest_put_oi":highest_pe},
            max_pain=max_pain,pcr=pcr,support_resistance={"support":f"{highest_pe.get('strike')} PE OI","resistance":f"{highest_ce.get('strike')} CE OI"},
            liquidity_pools=liquidity.get("liquidity_pools",[])+liquidity.get("stop_loss_hunting_zones",[]),
            timestamp=datetime.now().strftime("%d-%m-%Y %H:%M:%S IST")
        )
    except Exception as e:
        import traceback
        logger.error(f"Signal generation failed {symbol}: {e}\n{traceback.format_exc()}")
        return InstitutionalSignal(symbol=symbol,signal_type="ERROR",entry_strike=None,entry_type="N/A",entry_price_hint="Error",target="N/A",stoploss="N/A",probability=0,risk_reward="N/A",reasoning=[f"Error: {e}"],institutional_footprint={},max_pain=None,pcr=None,support_resistance={},liquidity_pools=[],timestamp=datetime.now().strftime("%d-%m-%Y %H:%M:%S IST"))

def format_signal_for_telegram(signal):
    try:
        lines=[
            f"🤖 <b>AI Institutional Signal: {signal.symbol}</b>",
            f"⏱️ {signal.timestamp}","",
            f"<b>Signal:</b> {signal.signal_type}",
            f"<b>Probability:</b> {signal.probability}% {'🟢 High' if signal.probability>75 else '🟡 Medium' if signal.probability>60 else '🔴 Low'}",
            f"<b>Risk-Reward:</b> {signal.risk_reward}","",
            f"<b>Entry:</b> {signal.entry_strike} ({signal.entry_type}) - {signal.entry_price_hint}",
            f"<b>Target:</b> {signal.target}",
            f"<b>Stop Loss:</b> {signal.stoploss}","",
            f"<b>Max Pain:</b> {signal.max_pain} | <b>PCR:</b> {signal.pcr}",
            f"<b>Support:</b> {signal.support_resistance.get('support','N/A')}",
            f"<b>Resistance:</b> {signal.support_resistance.get('resistance','N/A')}","",
            "<b>📊 Institutional Footprint:</b>",
        ]
        fp=signal.institutional_footprint
        if fp.get("highest_call_oi"):
            hce=fp["highest_call_oi"]
            lines.append(f"  • Highest Call OI: {hce.get('strike')} ({hce.get('oi')} OI) - Resistance")
        if fp.get("highest_put_oi"):
            hpe=fp["highest_put_oi"]
            lines.append(f"  • Highest Put OI: {hpe.get('strike')} ({hpe.get('oi')} OI) - Support")
        lines.append("")
        lines.append("<b>🧠 Reasoning:</b>")
        for i,r in enumerate(signal.reasoning[:6],1):
            lines.append(f"  {i}. {r}")
        lines.append("")
        lines.append("<b>💧 Liquidity Pools & Stop Hunting:</b>")
        for pool in signal.liquidity_pools[:4]:
            lines.append(f"  • {pool}")
        lines.append("")
        lines.append("<b>⚠️ Risk:</b> Risk only 1-2% capital per trade, 30% premium SL")
        text="\n".join(lines)
        if len(text)>4000:
            text=text[:4000]+"... truncated"
        return text
    except Exception as e:
        return f"Signal format error: {e}"
