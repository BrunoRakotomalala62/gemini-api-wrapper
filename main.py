import os
import requests
import json
import re
import time
import mimetypes
import base64
from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Gemini API Wrapper")

# Configuration CORS pour permettre les requêtes depuis Replit/Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COOKIES_FILE = "gemini.google.com_cookies-2026-01-29T151723.456.txt"

class GeminiRequest(BaseModel):
    pro: str = Field(..., description="Le prompt pour Gemini")
    image: Optional[str] = Field(None, description="URL ou base64 de l'image")
    uid: Optional[str] = Field(None, description="ID de l'utilisateur")

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
            # Fallback si le fichier spécifique n'existe pas, on cherche n'importe quel fichier de cookies
            cookie_files = [f for f in os.listdir('.') if 'cookies' in f and f.endswith('.txt')]
            if cookie_files:
                target_file = cookie_files[0]
                print(f"Utilisation du fichier de cookies trouvé: {target_file}")
            else:
                raise Exception(f"Fichier de cookies non trouvé.")
        else:
            target_file = COOKIES_FILE

        with open(target_file, 'r') as f:
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
        
        try:
            resp = self.session.get("https://gemini.google.com/app", headers=headers, timeout=30)
            match = re.search(r'"SNlM0e":"(.*?)"', resp.text)
            if not match: raise Exception("Auth failed: SNlM0e token not found. Check cookies.")
            
            self.token = match.group(1)
            self.last_update = time.time()
            return self.session, self.token
        except Exception as e:
            print(f"Erreur de rafraîchissement de session: {e}")
            raise

    def upload_image(self, image_path: str, token: str):
        # Pour l'instant, on garde la logique de fallback car l'upload Gemini est complexe
        return None 

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
                try:
                    header, encoded = image.split(",", 1)
                    ext_match = re.search(r'image/(.*?);', header)
                    ext = ext_match.group(1) if ext_match else "jpg"
                    
                    image_data = base64.b64decode(encoded)
                    temp_image_path = f"/tmp/temp_image_b64_{int(time.time())}.{ext}"
                    with open(temp_image_path, 'wb') as f:
                        f.write(image_data)
                    image_to_upload = temp_image_path
                    # On garde une trace qu'il s'agit d'une image base64
                    image_info = "Image transmise en Base64"
                except Exception as e:
                    print(f"Erreur décodage base64: {e}")
            elif image.startswith("http"):
                try:
                    img_resp = requests.get(image, timeout=15)
                    if img_resp.status_code == 200:
                        temp_image_path = f"/tmp/temp_image_{int(time.time())}.jpg"
                        with open(temp_image_path, 'wb') as f:
                            f.write(img_resp.content)
                        image_to_upload = temp_image_path
                    else:
                        print(f"Échec téléchargement image: {img_resp.status_code}")
                except Exception as e:
                    print(f"Erreur téléchargement image: {e}")

            # Fallback prompt si l'upload n'est pas implémenté
            if image and not file_id:
                if image.startswith("data:image") or "image_info" in locals():
                    prompt = f"[Analyse l'image jointe en Base64]\n\n{prompt}"
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
                # print(f"DEBUG: Ligne reçue: {decoded_line[:100]}") # Trop verbeux
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
            "answer": answer or "Je n'ai pas pu générer de réponse.",
            "execution_time": f"{round(time.time() - start_time, 2)}s"
        }
    except Exception as e:
        if temp_image_path and os.path.exists(temp_image_path):
            os.remove(temp_image_path)
        return {"status": "error", "message": str(e)}

@app.get("/gemini")
async def gemini_get(pro: str = Query(...), image: Optional[str] = None, uid: Optional[str] = None):
    return await process_gemini_request(pro, image, uid)

@app.post("/gemini")
async def gemini_post(request: GeminiRequest):
    return await process_gemini_request(request.pro, request.image, request.uid)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
