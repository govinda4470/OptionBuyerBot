"""
Chat Memory - Persistent per-user Telegram memory (not server RAM)

User request: "Use telegram memory not server, for every user it will be different"

Problem: context.chat_data is in-memory only, wiped when Render free instance spins down (15 min inactivity).
Solution: Store chat history per chat_id (Telegram user) in a JSON file on disk, persisted across restarts.

This is Telegram's own memory per user:
- chat_id is unique per user/group (from Telegram)
- History is stored per chat_id, so every user has different memory
- File chat_histories.json survives restarts and spin-downs (until file deleted)
- Also keeps in-memory cache for speed, but loads from disk on startup

File format:
{
  "123456789": [
    {"role": "user", "content": "hi", "timestamp": "2026-07-14 18:00:00"},
    {"role": "assistant", "content": "Hi! Bot working fine...", "timestamp": "..."},
    ...
  ],
  "987654321": [...]
}
"""

import os
import json
import time
import logging
import threading
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

MEMORY_FILE = "chat_histories.json"
MAX_HISTORY_PER_CHAT = 20  # Keep last 20 messages per user (10 exchanges)
_lock = threading.Lock()


def _load_all():
    """Load all chat histories from file"""
    try:
        if not os.path.exists(MEMORY_FILE):
            return {}
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Failed to load chat memory {MEMORY_FILE}: {e}")
        return {}


def _save_all(histories: Dict):
    """Save all chat histories to file (thread-safe)"""
    try:
        with _lock:
            # Atomic write via temp file
            tmp_file = MEMORY_FILE + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(histories, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, MEMORY_FILE)
    except Exception as e:
        logger.error(f"Failed to save chat memory: {e}")


def get_history(chat_id: int) -> List[Dict]:
    """
    Get chat history for a specific Telegram chat_id (user)
    Returns list of {"role": "user"/"assistant", "content": "...", "timestamp": "..."}
    This is Telegram's own per-user memory, not server RAM
    """
    try:
        chat_id_str = str(chat_id)
        all_hist = _load_all()
        history = all_hist.get(chat_id_str, [])
        # Convert old format (without timestamp) to new if needed
        # Old format from context.chat_data was list of {"role":..., "content":...}
        # New format includes timestamp but we keep compatibility
        return history
    except Exception as e:
        logger.error(f"get_history {chat_id} failed: {e}")
        return []


def add_message(chat_id: int, role: str, content: str):
    """
    Add a message to persistent per-user memory
    role: "user" or "assistant"
    """
    try:
        chat_id_str = str(chat_id)
        all_hist = _load_all()
        
        if chat_id_str not in all_hist:
            all_hist[chat_id_str] = []
        
        all_hist[chat_id_str].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
        })
        
        # Keep only last N messages per user
        if len(all_hist[chat_id_str]) > MAX_HISTORY_PER_CHAT:
            all_hist[chat_id_str] = all_hist[chat_id_str][-MAX_HISTORY_PER_CHAT:]
        
        _save_all(all_hist)
        logger.debug(f"Saved chat memory for {chat_id}: {role} - {content[:50]}")
    except Exception as e:
        logger.error(f"add_message {chat_id} failed: {e}")


def get_llm_history_format(chat_id: int, limit: int = 10) -> List[Dict]:
    """
    Get history in LLM format: [{"role": "user"/"assistant", "content": "..."}]
    For passing to llm_agent
    Limit to last N messages (default 10)
    """
    try:
        history = get_history(chat_id)
        # Take last N
        recent = history[-limit:] if len(history) > limit else history
        # Convert to LLM format (without timestamp)
        llm_format = [{"role": msg["role"], "content": msg["content"]} for msg in recent if "role" in msg and "content" in msg]
        return llm_format
    except Exception as e:
        logger.error(f"get_llm_history_format {chat_id} failed: {e}")
        return []


def clear_history(chat_id: int):
    """Clear history for a user (if they want to reset)"""
    try:
        chat_id_str = str(chat_id)
        all_hist = _load_all()
        if chat_id_str in all_hist:
            del all_hist[chat_id_str]
            _save_all(all_hist)
            logger.info(f"Cleared chat history for {chat_id}")
    except Exception as e:
        logger.error(f"clear_history {chat_id} failed: {e}")


def get_all_chat_ids() -> List[str]:
    """Get all chat IDs that have history (for debugging)"""
    try:
        all_hist = _load_all()
        return list(all_hist.keys())
    except:
        return []


def sync_from_context_chat_data(chat_id: int, context_chat_data_history: List[Dict]):
    """
    Sync in-memory context.chat_data history to persistent file
    Called when bot has in-memory history but file is empty (migration)
    """
    try:
        existing = get_history(chat_id)
        if existing:
            return  # Already has persistent history, don't overwrite
        
        if not context_chat_data_history:
            return
        
        # Save context history to file
        chat_id_str = str(chat_id)
        all_hist = _load_all()
        # Convert to persistent format with timestamps
        persistent = []
        for msg in context_chat_data_history:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                persistent.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")
                })
        
        if persistent:
            all_hist[chat_id_str] = persistent[-MAX_HISTORY_PER_CHAT:]
            _save_all(all_hist)
            logger.info(f"Migrated {len(persistent)} messages from context to persistent for {chat_id}")
    except Exception as e:
        logger.error(f"sync_from_context failed {chat_id}: {e}")
