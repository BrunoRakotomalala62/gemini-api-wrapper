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

def extract_gemini_text(raw_response: str):
    """Extrait proprement le texte de la réponse de Gemini depuis le flux JSON."""
    try:
        for line in raw_response.splitlines():
            if "wrb.fr" in line:
                data = json.loads(line)
                # Les données de réponse sont dans le 3ème élément (index 2) et sont encodées en JSON
                inner_json_str = data[0][2]
                if not inner_json_str: continue
                
                inner_data = json.loads(inner_json_str)
                
                # Structure typique de réponse : [null, [ids], null, null, [[rc_id, [text_parts]]]]
                # On cherche la partie qui contient le texte de la réponse
                if len(inner_data) > 5 and inner_data[5]:
                    # Parfois le texte est ici
                    for candidate in inner_data[5]:
                        if isinstance(candidate, list) and len(candidate) > 1:
                            if isinstance(candidate[1], list) and candidate[1]:
                                return candidate[1][0]
                
                # Autre structure possible (plus fréquente)
                if len(inner_data) > 4 and inner_data[4]:
                    for item in inner_data[4]:
                        if isinstance(item, list) and len(item) > 1:
                            # Le texte est souvent dans le deuxième élément du sous-élément
                            if isinstance(item[1], list) and item[1]:
                                return item[1][0]
        return None
    except Exception as e:
        print(f"Erreur d'extraction: {e}")
        return None

def get_gemini_response_real(prompt: str):
    cookies = get_cookies_from_file(COOKIES_FILE)
    if not cookies:
        return {"error": "Fichier de cookies introuvable ou vide."}

    url = "https://gemini.google.com/app"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "Origin": "https://gemini.google.com",
        "Referer": "https://gemini.google.com/",
    }

    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".google.com")

    try:
        # 1. Obtenir SNlM0e
        resp = session.get(url, headers=headers, timeout=15)
        match = re.search(r'"SNlM0e":"(.*?)"', resp.text)
        if not match:
            return {"error": "Cookies invalides ou expirés (SNlM0e non trouvé)."}
        token = match.group(1)

        # 2. Envoyer la requête
        chat_url = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        req_inner = [[prompt], None, ["", "", ""]]
        
        payload = {
            "f.req": json.dumps([None, json.dumps(req_inner)]),
            "at": token
        }
        
        params = {"_reqid": "12345", "rt": "c"}
        chat_resp = session.post(chat_url, params=params, data=payload, headers=headers, timeout=30)
        
        if chat_resp.status_code != 200:
            return {"error": f"Erreur Google: {chat_resp.status_code}"}

        # 3. Extraire le texte
        answer = extract_gemini_text(chat_resp.text)
        if answer:
            return {"status": "success", "answer": answer}
        else:
            return {"status": "partial", "raw": chat_resp.text[:500]}

    except Exception as e:
        return {"error": str(e)}

@app.get("/gemini")
async def gemini_endpoint(prompt: str, uid: Optional[str] = None):
    result = get_gemini_response_real(prompt)
    
    if "error" in result:
        return {"status": "error", "uid": uid, "error": result["error"]}
    
    return {
        "status": "success",
        "uid": uid,
        "prompt": prompt,
        "answer": result.get("answer", "Réponse reçue mais format d'extraction inconnu."),
        "raw_preview": result.get("raw")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
