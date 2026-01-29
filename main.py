import os
import requests
import json
import re
from fastapi import FastAPI, HTTPException, Query
from typing import Optional

app = FastAPI(title="Gemini API Wrapper")

COOKIES_FILE = "gemini.google.com_cookies-2026-01-29T090222.522.txt"

def get_cookies_from_file(file_path):
    cookies = {}
    if not os.path.exists(file_path):
        return cookies
    with open(file_path, 'r') as f:
        for line in f:
            if not line.startswith('#') and line.strip():
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    cookies[parts[5]] = parts[6]
    return cookies

def get_gemini_response_real(prompt: str):
    cookies = get_cookies_from_file(COOKIES_FILE)
    if not cookies:
        return {"error": "Fichier de cookies introuvable ou vide."}

    url = "https://gemini.google.com/app"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Origin": "https://gemini.google.com",
        "Referer": "https://gemini.google.com/",
    }

    session = requests.Session()
    # Ajout des cookies à la session
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".google.com")

    try:
        # 1. Récupérer le token SNlM0e
        resp = session.get(url, headers=headers, timeout=15)
        snlm0e = re.search(r'"SNlM0e":"(.*?)"', resp.text)
        if not snlm0e:
            return {"error": "Impossible de trouver le token SNlM0e. Les cookies sont peut-être expirés ou invalides."}
        token = snlm0e.group(1)

        # 2. Envoyer la requête de chat
        chat_url = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        
        # Format de données spécifique à l'API interne de Gemini (basé sur reverse engineering courant)
        req_inner = [[prompt], None, ["", "", ""]]
        req_outer = [None, json.dumps(req_inner)]
        
        post_data = {
            "f.req": json.dumps([None, json.dumps(req_outer)]),
            "at": token
        }
        
        params = {
            "bl": "boq_assistant-bard-web-server_20240124.11_p0",
            "_reqid": "12345",
            "rt": "c"
        }

        chat_resp = session.post(chat_url, params=params, data=post_data, headers=headers, timeout=30)
        
        # Tentative d'extraction du texte de la réponse
        lines = chat_resp.text.splitlines()
        for line in lines:
            if "wrb.fr" in line:
                try:
                    data = json.loads(line)
                    inner_data = json.loads(data[0][2])
                    # La réponse textuelle se trouve souvent à cet index
                    response_text = inner_data[4][0][1][0]
                    return {"status": "success", "prompt": prompt, "answer": response_text}
                except:
                    continue

        return {"status": "partial", "prompt": prompt, "raw_sample": chat_resp.text[:500]}

    except Exception as e:
        return {"error": str(e)}

@app.get("/gemini")
async def gemini_endpoint(prompt: str, uid: Optional[str] = None):
    result = get_gemini_response_real(prompt)
    
    if "error" in result:
        return {
            "status": "error",
            "uid": uid,
            "prompt": prompt,
            "error_detail": result["error"]
        }
    
    return {
        "status": "success",
        "uid": uid,
        "prompt": prompt,
        "answer": result.get("answer", "Réponse reçue mais le format d'extraction a échoué."),
        "raw_data_preview": result.get("raw_sample")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
