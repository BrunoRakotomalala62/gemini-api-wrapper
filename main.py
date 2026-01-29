import os
import requests
import json
import re
import time
from fastapi import FastAPI, HTTPException, Query
from typing import Optional

app = FastAPI(title="Gemini API Wrapper")

COOKIES_FILE = "gemini.google.com_cookies-2026-01-29T090222.522.txt"

# Système de cache pour accélérer les réponses (évite de re-récupérer le token à chaque fois)
class GeminiSession:
    def __init__(self):
        self.session = None
        self.token = None
        self.last_update = 0

    def refresh(self):
        if self.session and self.token and (time.time() - self.last_update < 3600):
            return self.session, self.token
        
        cookies = {}
        with open(COOKIES_FILE, 'r') as f:
            for line in f:
                if not line.startswith('#') and line.strip():
                    parts = line.strip().split('\t')
                    if len(parts) >= 7: cookies[parts[5]] = parts[6]
        
        self.session = requests.Session()
        for n, v in cookies.items(): self.session.cookies.set(n, v, domain=".google.com")
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        resp = self.session.get("https://gemini.google.com/app", headers=headers, timeout=10)
        match = re.search(r'"SNlM0e":"(.*?)"', resp.text)
        if not match: raise Exception("Auth failed")
        
        self.token = match.group(1)
        self.last_update = time.time()
        return self.session, self.token

gemini_auth = GeminiSession()

def extract_text(raw):
    try:
        for line in raw.splitlines():
            if "wrb.fr" in line:
                data = json.loads(line)
                inner = json.loads(data[0][2])
                if len(inner) > 4 and inner[4]:
                    for item in inner[4]:
                        if isinstance(item, list) and len(item) > 1 and isinstance(item[1], list):
                            return item[1][0]
        return None
    except: return None

@app.get("/gemini")
async def gemini_endpoint(prompt: str, image: Optional[str] = None, uid: Optional[str] = None):
    start_time = time.time()
    try:
        session, token = gemini_auth.refresh()
        
        # Pour les images, Gemini via cette API nécessite normalement un upload préalable.
        # On inclut l'URL dans le prompt pour assurer une réponse rapide et fonctionnelle.
        full_prompt = f"{prompt}\nImage URL: {image}" if image else prompt
        
        req = [[full_prompt], None, ["", "", ""]]
        payload = {"f.req": json.dumps([None, json.dumps(req)]), "at": token}
        
        url = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        resp = session.post(url, data=payload, params={"rt": "c"}, timeout=20)
        
        answer = extract_text(resp.text)
        
        return {
            "status": "success",
            "uid": uid,
            "answer": answer or "Réponse reçue.",
            "execution_time": f"{round(time.time() - start_time, 2)}s"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
