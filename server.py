"""
MultiTrans - Backend Server
Deploy lên Render.com (free, không cần thẻ)
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import base64
import time
import threading
import hashlib
import re
import os

app = Flask(__name__, static_folder='static')
CORS(app)

# ============================================================
# IN-MEMORY CACHE
# ============================================================
cache = {}
cache_lock = threading.Lock()

def make_cache_key(text, src, tgt):
    return hashlib.md5(f"{src}:{tgt}:{text}".encode()).hexdigest()

def from_cache(text, src, tgt):
    k = make_cache_key(text, src, tgt)
    with cache_lock:
        return cache.get(k)

def to_cache(text, src, tgt, result):
    k = make_cache_key(text, src, tgt)
    with cache_lock:
        if len(cache) > 5000:   # giới hạn 5000 entries
            oldest = list(cache.keys())[:500]
            for key in oldest:
                del cache[key]
        cache[k] = result

# ============================================================
# RUNTIME CONFIG (được cập nhật từ UI)
# ============================================================
CONFIG = {
    "mymemory":       {"enabled": True,  "emails": [], "key_idx": 0},
    "libretranslate": {"enabled": True,  "servers": ["https://libretranslate.com", "https://translate.argosopentech.com"], "api_key": "", "key_idx": 0},
    "lingva":         {"enabled": True,  "servers": ["https://lingva.ml", "https://lingva.thedaviddelta.com", "https://translate.plausibility.cloud"], "key_idx": 0},
    "smartcat":       {"enabled": False, "accounts": [], "key_idx": 0},
    "argos":          {"enabled": True,  "servers": ["https://translate.argosopentech.com"], "key_idx": 0},
}

cfg_lock = threading.Lock()

def rotate(api, items):
    if not items:
        return None
    with cfg_lock:
        idx = CONFIG[api]["key_idx"] % len(items)
        CONFIG[api]["key_idx"] = (idx + 1) % len(items)
    return items[idx]

# ============================================================
# API CALLERS
# ============================================================
TIMEOUT = 12

def call_mymemory(text, src, tgt):
    emails = CONFIG["mymemory"].get("emails", [])
    email  = rotate("mymemory", emails)
    params = {"q": text, "langpair": f"{'en' if src=='auto' else src}|{tgt}"}
    if email:
        params["de"] = email
    r = requests.get("https://api.mymemory.translated.net/get", params=params, timeout=TIMEOUT)
    d = r.json()
    if d.get("responseStatus") != 200:
        raise Exception(d.get("responseDetails", "MyMemory error"))
    result = d["responseData"]["translatedText"]
    # MyMemory trả lỗi dưới dạng text đôi khi
    if "MYMEMORY WARNING" in result.upper():
        raise Exception("MyMemory quota exceeded")
    return result

def call_libretranslate(text, src, tgt):
    servers = CONFIG["libretranslate"].get("servers", [])
    server  = rotate("libretranslate", servers) or "https://libretranslate.com"
    payload = {"q": text, "source": "en" if src == "auto" else src, "target": tgt, "format": "text"}
    ak = CONFIG["libretranslate"].get("api_key", "")
    if ak:
        payload["api_key"] = ak
    r = requests.post(f"{server}/translate", json=payload, timeout=TIMEOUT)
    d = r.json()
    if "translatedText" not in d:
        raise Exception(d.get("error", "LibreTranslate error"))
    return d["translatedText"]

def call_lingva(text, src, tgt):
    servers = CONFIG["lingva"].get("servers", [])
    server  = rotate("lingva", servers) or "https://lingva.ml"
    from urllib.parse import quote
    r = requests.get(f"{server}/api/v1/{'en' if src=='auto' else src}/{tgt}/{quote(text)}", timeout=TIMEOUT)
    d = r.json()
    if "translation" not in d:
        raise Exception("Lingva: no result")
    return d["translation"]

def call_smartcat(text, src, tgt):
    accounts = CONFIG["smartcat"].get("accounts", [])
    acct     = rotate("smartcat", accounts)
    if not acct:
        raise Exception("Smartcat: chưa cấu hình")
    token = base64.b64encode(f"{acct['account_id']}:{acct['api_key']}".encode()).decode()
    r = requests.post(
        "https://smartcat.com/api/integration/v1/translate/text",
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        json={"text": [text], "sourceLanguage": "en" if src=="auto" else src, "targetLanguages": [tgt]},
        timeout=TIMEOUT
    )
    d = r.json()
    if not d or not d[0].get("translation"):
        raise Exception("Smartcat: no result")
    return d[0]["translation"]

def call_argos(text, src, tgt):
    servers = CONFIG["argos"].get("servers", [])
    server  = rotate("argos", servers) or "https://translate.argosopentech.com"
    r = requests.post(f"{server}/translate",
        json={"q": text, "source": "en" if src=="auto" else src, "target": tgt},
        headers={"Content-Type": "application/json"}, timeout=TIMEOUT)
    d = r.json()
    if "translatedText" not in d:
        raise Exception("Argos: no result")
    return d["translatedText"]

# ============================================================
# FALLBACK CHAIN
# ============================================================
API_CHAIN = [
    ("mymemory",       call_mymemory),
    ("libretranslate", call_libretranslate),
    ("lingva",         call_lingva),
    ("argos",          call_argos),
    ("smartcat",       call_smartcat),
]

def translate_one(text, src, tgt, use_cache=True):
    if use_cache:
        cached = from_cache(text, src, tgt)
        if cached:
            return {"result": cached, "api": "CACHE", "from_cache": True}

    errors = []
    for name, fn in API_CHAIN:
        if not CONFIG.get(name, {}).get("enabled", False):
            continue
        try:
            result = fn(text, src, tgt)
            if use_cache:
                to_cache(text, src, tgt, result)
            return {"result": result, "api": name, "from_cache": False}
        except Exception as e:
            errors.append(f"{name}: {e}")

    raise Exception("Tất cả API thất bại: " + " | ".join(errors))

def split_text(text, max_len=500):
    if len(text) <= max_len:
        return [text]
    parts = re.split(r'(?<=[.!?\n])\s+', text)
    chunks, cur = [], ""
    for p in parts:
        if len(cur) + len(p) > max_len and cur:
            chunks.append(cur.strip())
            cur = p
        else:
            cur += " " + p
    if cur.strip():
        chunks.append(cur.strip())
    return chunks or [text]

# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/ping')
def ping():
    return jsonify({"status": "ok", "time": time.time()})

@app.route('/api/translate', methods=['POST'])
def translate():
    data      = request.json or {}
    text      = data.get('text', '').strip()
    src       = data.get('source', 'auto')
    tgt       = data.get('target', 'vi')
    max_chunk = int(data.get('max_chunk', 500))
    use_cache = bool(data.get('cache', True))

    if not text:
        return jsonify({"error": "Không có văn bản"}), 400

    chunks  = split_text(text, max_chunk)
    results = [None] * len(chunks)
    errors  = []
    lock    = threading.Lock()

    def do(chunk, idx):
        try:
            results[idx] = translate_one(chunk, src, tgt, use_cache)
        except Exception as e:
            with lock:
                errors.append(str(e))
            results[idx] = {"result": f"[LỖI]", "api": "error", "from_cache": False}

    threads = [threading.Thread(target=do, args=(c, i)) for i, c in enumerate(chunks)]
    for t in threads: t.start()
    for t in threads: t.join()

    translated = " ".join(r["result"] for r in results)
    apis_used  = list(dict.fromkeys(r["api"] for r in results))
    from_cache_all = all(r.get("from_cache") for r in results)

    return jsonify({
        "translated": translated,
        "apis_used":  apis_used,
        "chunks":     len(chunks),
        "from_cache": from_cache_all,
        "errors":     errors
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    safe = {}
    for api, cfg in CONFIG.items():
        safe[api] = {"enabled": cfg.get("enabled", False)}
        if "emails"   in cfg: safe[api]["email_count"]   = len(cfg["emails"])
        if "servers"  in cfg: safe[api]["servers"]       = cfg["servers"]
        if "accounts" in cfg: safe[api]["account_count"] = len(cfg["accounts"])
    return jsonify(safe)

@app.route('/api/config', methods=['POST'])
def set_config():
    data = request.json or {}
    with cfg_lock:
        for api in CONFIG:
            if api not in data:
                continue
            inc = data[api]
            CONFIG[api]["enabled"] = bool(inc.get("enabled", False))
            if "emails"   in inc: CONFIG[api]["emails"]   = inc["emails"]
            if "servers"  in inc: CONFIG[api]["servers"]  = inc["servers"]
            if "api_key"  in inc: CONFIG[api]["api_key"]  = inc["api_key"]
            if "accounts" in inc: CONFIG[api]["accounts"] = inc["accounts"]
    return jsonify({"ok": True})

@app.route('/api/cache/clear', methods=['POST'])
def cache_clear():
    with cache_lock:
        n = len(cache); cache.clear()
    return jsonify({"cleared": n})

@app.route('/api/cache/stats')
def cache_stats():
    with cache_lock:
        return jsonify({"size": len(cache)})

# ============================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n🚀 MultiTrans chạy tại http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
