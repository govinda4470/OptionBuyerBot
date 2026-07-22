"""Arena AI Agent - 8 personas"""
import os, logging
from typing import Dict, List, Tuple
logger = logging.getLogger(__name__)
try:
    import llm_agent
    HAS_LLM_AGENT=True
except:
    HAS_LLM_AGENT=False
    llm_agent=None
ARENA_PERSONAS={
    "claude":{"name":"Claude (Anthropic) - Careful Analyst","style":"Thoughtful, risk-aware","system_extra":"You are Claude, careful, ethical, risk-aware."},
    "chatgpt":{"name":"ChatGPT (OpenAI) - Versatile Trader","style":"Versatile, clear","system_extra":"You are ChatGPT, versatile helpful."},
    "gemini":{"name":"Gemini (Google) - Data Driven","style":"Data-driven","system_extra":"You are Gemini, data-driven."},
    "grok":{"name":"Grok (xAI) - Contrarian","style":"Contrarian, witty","system_extra":"You are Grok, contrarian, look for manipulation."},
    "qwen":{"name":"Qwen (Alibaba) - Quantitative","style":"Quantitative","system_extra":"You are Qwen, quantitative expert."},
    "kimi":{"name":"Kimi (Moonshot) - Long Context","style":"Long context","system_extra":"You are Kimi, long context holistic."},
    "llama":{"name":"Llama (Meta) - Open Source","style":"Open source, practical","system_extra":"You are Llama, practical open source."},
    "deepseek":{"name":"DeepSeek - Cost Efficient","style":"Efficient","system_extra":"You are DeepSeek, efficient direct."},
}
PERSONA_TO_PROVIDER={"claude":"OPENAI","chatgpt":"OPENAI","gemini":"GEMINI","grok":"GROQ","qwen":"DEEPSEEK","kimi":"GEMINI","llama":"GROQ","deepseek":"DEEPSEEK"}
def get_arena_personas():
    return ARENA_PERSONAS
def ask_arena_persona(persona_key: str, prompt: str, history: List[Dict]=None) -> Tuple[str, str]:
    if not HAS_LLM_AGENT:
        raise RuntimeError("llm_agent not available")
    persona=ARENA_PERSONAS.get(persona_key.lower())
    if not persona:
        raise ValueError(f"Unknown persona {persona_key}")
    provider=PERSONA_TO_PROVIDER.get(persona_key.lower(),"GROQ")
    enhanced=f"{persona['system_extra']}\n\nUser: {prompt}\n\nStyle: {persona['style']}"
    try:
        answer,used=llm_agent.ask(enhanced,history=history,prefer=provider)
        return answer, f"{persona['name']} via {llm_agent.provider_label(used)}"
    except Exception as e:
        answer,used=llm_agent.ask(enhanced,history=history)
        return answer, f"{persona['name']} via {llm_agent.provider_label(used)} (fallback)"
def ask_arena_all(prompt: str, history: List[Dict]=None) -> Dict[str, Dict]:
    results={}
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        def ask_one(pk):
            try:
                ans,prov=ask_arena_persona(pk,prompt,history)
                return pk,{"ok":True,"text":ans,"provider":prov}
            except Exception as e:
                return pk,{"ok":False,"text":str(e),"provider":"Failed"}
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures={ex.submit(ask_one,pk):pk for pk in ARENA_PERSONAS.keys()}
            for fut in as_completed(futures):
                pk,res=fut.result()
                results[pk]=res
    except Exception as e:
        for pk in ARENA_PERSONAS.keys():
            try:
                ans,prov=ask_arena_persona(pk,prompt,history)
                results[pk]={"ok":True,"text":ans,"provider":prov}
            except Exception as ex:
                results[pk]={"ok":False,"text":str(ex),"provider":"Failed"}
    return results
def arena_consensus_vote(prompt: str, history: List[Dict]=None) -> Dict:
    all_answers=ask_arena_all(prompt,history)
    votes={"BUY_CALL":0,"BUY_PUT":0,"NO_TRADE":0,"BULLISH":0,"BEARISH":0}
    for pk,res in all_answers.items():
        if not res["ok"]:
            continue
        text=res["text"].upper()
        if "BUY CALL" in text or "BUY_CALL" in text:
            votes["BUY_CALL"]+=1
        if "BUY PUT" in text or "BUY_PUT" in text:
            votes["BUY_PUT"]+=1
        if "NO TRADE" in text or "WAIT" in text:
            votes["NO_TRADE"]+=1
        if "BULLISH" in text:
            votes["BULLISH"]+=1
        if "BEARISH" in text:
            votes["BEARISH"]+=1
    if votes["BUY_CALL"]>votes["BUY_PUT"] and votes["BUY_CALL"]>votes["NO_TRADE"]:
        consensus="BUY_CALL"
    elif votes["BUY_PUT"]>votes["BUY_CALL"] and votes["BUY_PUT"]>votes["NO_TRADE"]:
        consensus="BUY_PUT"
    else:
        consensus="NO_TRADE"
    bullish_prob=int((votes["BULLISH"]/max(1,votes["BULLISH"]+votes["BEARISH"]))*100) if (votes["BULLISH"]+votes["BEARISH"])>0 else 50
    return {"consensus":consensus,"votes":votes,"bullish_probability":bullish_prob,"bearish_probability":100-bullish_prob,"all_answers":all_answers}
def format_arena_results_for_telegram(results: Dict[str, Dict], prompt: str) -> str:
    lines=[f"🏟️ <b>Arena - Multi-LLM Answers for:</b> {prompt}","",f"Asked {len(results)} AI models",""]
    for pk,res in results.items():
        name=ARENA_PERSONAS.get(pk,{}).get("name",pk)
        if res["ok"]:
            txt=res["text"]
            if len(txt)>500:
                txt=txt[:500]+"..."
            lines.append(f"<b>{name}:</b> ({res['provider']})")
            lines.append(txt)
            lines.append("")
        else:
            lines.append(f"<b>{name}:</b> ❌ Failed - {res['text'][:100]}")
            lines.append("")
    lines.append("Arena voting gives multiple perspectives.")
    text="\n".join(lines)
    if len(text)>3800:
        text=text[:3800]+"... truncated"
    return text
def is_configured():
    if not HAS_LLM_AGENT:
        return False
    return len(llm_agent.configured_providers())>0
def configured_providers():
    if not HAS_LLM_AGENT:
        return []
    return llm_agent.configured_providers()
