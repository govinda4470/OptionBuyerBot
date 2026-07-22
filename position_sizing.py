"""position_sizing.py - Capital-aware position sizing"""
import math
LOT_SIZES={"NIFTY":75,"BANKNIFTY":15,"FINNIFTY":40,"SENSEX":10,"RELIANCE":250}
def plan_position(symbol, signal, capital, option_chain_data=None):
    try:
        symbol=symbol.upper()
        lot_size=LOT_SIZES.get(symbol,75)
        # Try to get live premium for entry strike
        entry_premium=15.0
        if option_chain_data:
            try:
                records=option_chain_data.get("records",{})
                data_list=records.get("data",[])
                for entry in data_list:
                    if entry.get("strikePrice")==signal.entry_strike:
                        ce=entry.get("CE",{}) if "CALL" in signal.signal_type else entry.get("PE",{})
                        if ce and ce.get("lastPrice"):
                            entry_premium=float(ce.get("lastPrice"))
                            break
            except:
                pass
        # If no live premium, estimate 1% of spot
        if entry_premium==15.0 and hasattr(signal,'entry_strike') and signal.entry_strike:
            entry_premium=round((signal.entry_strike or 24500)*0.01,2)
        # Quantity based on capital: use 90% of capital for entry cost
        max_cost=capital*0.9
        qty_per_lot=lot_size
        # Calculate lots that fit in capital
        cost_per_lot=entry_premium*qty_per_lot
        lots=int(max_cost//cost_per_lot) if cost_per_lot>0 else 1
        lots=max(1,lots)
        total_qty=lots*qty_per_lot
        entry_cost=entry_premium*total_qty
        # Target and SL premium: 1:2 RR, 30% SL
        target_premium=round(entry_premium*1.6,2)  # 60% up
        sl_premium=round(entry_premium*0.7,2)  # 30% down
        total_risk=(entry_premium-sl_premium)*total_qty
        total_reward=(target_premium-entry_premium)*total_qty
        rr_ratio=round(total_reward/max(1,total_risk),1) if total_risk>0 else 2.0
        tradeable=entry_cost<=capital and total_risk<=capital*0.02*5  # allow 2%*5 risk
        return {
            "symbol":symbol,
            "entry_strike":signal.entry_strike,
            "entry_type":signal.entry_type,
            "entry_premium":entry_premium,
            "quantity":total_qty,
            "lots":lots,
            "lot_size":lot_size,
            "entry_cost":round(entry_cost,2),
            "entry_cost_percent":round(entry_cost/max(1,capital)*100,1),
            "target_premium":target_premium,
            "stoploss_premium":sl_premium,
            "total_risk":round(total_risk,2),
            "total_reward":round(total_reward,2),
            "risk_reward":f"1:{rr_ratio}",
            "tradeable":tradeable,
            "win_rate_probability":getattr(signal,'probability',70),
        }
    except Exception as e:
        return {"error":str(e),"tradeable":False}

def format_plan_for_telegram(plan,symbol,capital):
    try:
        if "error" in plan:
            return f"❌ Plan failed for {symbol}: {plan['error']}"
        lines=[
            f"🎯 <b>{symbol} Strategy for ₹{capital:,.0f} Capital</b>",
            "",
            f"<b>Signal:</b> {plan.get('entry_strike','')} {plan.get('entry_type','')} (CE/PE based on signal)",
            f"<b>Win-rate Probability:</b> {plan.get('win_rate_probability','70')}%",
            "",
            f"<b>Entry Strike:</b> {plan.get('entry_strike')} {plan.get('entry_type')}",
            f"<b>Entry Premium:</b> ₹{plan.get('entry_premium')}",
            f"<b>Quantity:</b> {plan.get('quantity')} ({plan.get('lots')} lot(s) x {plan.get('lot_size')})",
            f"<b>Entry Cost:</b> ₹{plan.get('entry_cost'):,.0f} ({plan.get('entry_cost_percent')}% of capital)",
            "",
            f"<b>Target Premium:</b> ₹{plan.get('target_premium')} (+₹{round(plan.get('target_premium',0)-plan.get('entry_premium',0),2)}/unit)",
            f"<b>Stoploss Premium:</b> ₹{plan.get('stoploss_premium')} (-₹{round(plan.get('entry_premium',0)-plan.get('stoploss_premium',0),2)}/unit)",
            "",
            f"<b>Total Risk:</b> ₹{plan.get('total_risk'):,.0f}",
            f"<b>Total Reward:</b> ₹{plan.get('total_reward'):,.0f}",
            f"<b>Risk:Reward:</b> {plan.get('risk_reward')}",
            "",
            f"{'✅ Tradeable within capital' if plan.get('tradeable') else '⚠️ Entry cost may exceed capital, reduce lots'}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Format plan failed: {e}"
