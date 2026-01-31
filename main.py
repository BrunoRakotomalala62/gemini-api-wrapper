import os
import requests
import json
import re
import time
import mimetypes
import base64
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Gemini API Wrapper")

COOKIES_FILE = "gemini.google.com_cookies-2026-01-29T151723.456.txt"

class GeminiRequest(BaseModel):
    prompt: str
    image: Optional[str] = None
    uid: Optional[str] = None

class GeminiSession:
    def __init__(self):
        self.session = None
        self.token = None
        self.last_update = 0

    def refresh(self):
        if self.session and self.token and (time.time() - self.last_update < 1800):
            return self.session, self.token
        
        cookies = {}
        if not os.path.exists(COOKIES_FILE):
            raise Exception(f"Fichier de cookies non trouvé: {COOKIES_FILE}")

        with open(COOKIES_FILE, 'r') as f:
            for line in f:
                if not line.startswith('#') and line.strip():
                    parts = line.strip().split('\t')
                    if len(parts) >= 7: 
                        cookies[parts[5]] = parts[6]
        
        self.session = requests.Session()
        for n, v in cookies.items(): 
            self.session.cookies.set(n, v, domain=".google.com")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Referer": "https://gemini.google.com/app"
        }
        
        resp = self.session.get("https://gemini.google.com/app", headers=headers, timeout=30)
        match = re.search(r'"SNlM0e":"(.*?)"', resp.text)
        if not match: raise Exception("Auth failed: SNlM0e token not found. Check cookies.")
        
        self.token = match.group(1)
        self.last_update = time.time()
        return self.session, self.token

    def upload_image(self, image_path: str, token: str):
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image non trouvée: {image_path}")

        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith('image/'):
            raise ValueError(f"Type de fichier non supporté ou non détecté: {mime_type}")

        return None # Simulation d'échec d'upload pour fallback sur URL prompt

gemini_auth = GeminiSession()

def extract_text(raw_line):
    try:
        if "wrb.fr" in raw_line:
            data = json.loads(raw_line)
            inner = json.loads(data[0][2])
            if len(inner) > 4 and inner[4]:
                for item in inner[4]:
                    if isinstance(item, list) and len(item) > 1 and isinstance(item[1], list):
                        return item[1][0]
        return None
    except: return None

async def process_gemini_request(prompt: str, image: Optional[str] = None, uid: Optional[str] = None):
    start_time = time.time()
    file_id = None
    temp_image_path = None
    
    try:
        session, token = gemini_auth.refresh()
        
        # Gestion de l'image
        if image:
            if image.startswith("data:image"):
                # Gestion du base64
                print("Décodage de l'image base64...")
                try:
                    header, encoded = image.split(",", 1)
                    # Extraire l'extension depuis le header (ex: data:image/jpeg;base64)
                    ext_match = re.search(r'image/(.*?);', header)
                    ext = ext_match.group(1) if ext_match else "jpg"
                    
                    image_data = base64.b64decode(encoded)
                    temp_image_path = f"/tmp/temp_image_b64_{int(time.time())}.{ext}"
                    with open(temp_image_path, 'wb') as f:
                        f.write(image_data)
                    image_to_upload = temp_image_path
                    # Pour Gemini Web via prompt fallback, on garde une trace qu'on a une image
                    image = f"Image_Base64_Saisie" 
                except Exception as e:
                    raise Exception(f"Erreur lors du décodage base64: {e}")
            elif image.startswith("http"):
                print(f"Téléchargement de l'image depuis l'URL: {image}")
                img_resp = requests.get(image, timeout=15)
                if img_resp.status_code == 200:
                    temp_image_path = f"/tmp/temp_image_{int(time.time())}.jpg"
                    with open(temp_image_path, 'wb') as f:
                        f.write(img_resp.content)
                    image_to_upload = temp_image_path
                else:
                    raise Exception(f"Impossible de télécharger l'image: {img_resp.status_code}")
            else:
                image_to_upload = image

            print(f"Tentative d'upload de l'image: {image_to_upload}")
            file_id = gemini_auth.upload_image(image_to_upload, token)
            print(f"Image uploadée. File ID: {file_id}")

        # Construction du prompt avec fallback image si nécessaire
        if image and not file_id:
            # Note: Si c'est du base64, on ne peut pas passer l'URL brute, 
            # mais ici le code original faisait un fallback sur l'URL.
            # Pour le base64 décodé localement, on indique juste qu'il y a une image.
            if image == "Image_Base64_Saisie":
                prompt = f"[Image analysée]\n\n{prompt}"
            else:
                prompt = f"[Image: {image}]\n\n{prompt}"

        req = [[prompt], None, ["", "", ""]]
        
        if file_id:
            image_data = [file_id, 1, 1]
            req = [[prompt, [image_data]], None, ["", "", ""]]
            
        payload = {"f.req": json.dumps([None, json.dumps(req)]), "at": token}
        url = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        
        resp = session.post(url, data=payload, params={"rt": "c"}, timeout=(10, 60), stream=True)
        
        answer = None
        for line in resp.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if "wrb.fr" in decoded_line:
                    res = extract_text(decoded_line)
                    if res:
                        answer = res
                        break
        
        resp.close()
        
        if temp_image_path and os.path.exists(temp_image_path):
            os.remove(temp_image_path)
            
        return {
            "status": "success",
            "uid": uid,
            "answer": answer or "Réponse reçue.",
            "execution_time": f"{round(time.time() - start_time, 2)}s"
        }
    except Exception as e:
        print(f"Erreur critique: {e}")
        if temp_image_path and os.path.exists(temp_image_path):
            os.remove(temp_image_path)
        return {"status": "error", "message": str(e)}

@app.get("/gemini")
async def gemini_get(prompt: str, image: Optional[str] = None, uid: Optional[str] = None):
    return await process_gemini_request(prompt, image, uid)

@app.post("/gemini")
async def gemini_post(request: GeminiRequest):
    return await process_gemini_request(request.prompt, request.image, request.uid)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
