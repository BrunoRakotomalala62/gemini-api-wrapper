import os
import requests
import json
import re
import time
import mimetypes
import base64
import io
from PIL import Image
from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Gemini API Wrapper")

# Configuration CORS
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
        # On rafraîchit si pas de session ou si la session a plus de 20 minutes
        if self.session and self.token and (time.time() - self.last_update < 1200):
            return self.session, self.token
        
        cookies = {}
        target_file = COOKIES_FILE
        if not os.path.exists(target_file):
            cookie_files = [f for f in os.listdir('.') if 'cookies' in f and f.endswith('.txt')]
            if cookie_files:
                target_file = cookie_files[0]
            else:
                raise Exception("Fichier de cookies non trouvé.")

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
            if not match: 
                # Tentative de récupération alternative du token
                match = re.search(r'SNlM0e\\":\\"(.*?)\\"', resp.text)
            
            if not match:
                raise Exception("Token SNlM0e non trouvé. Vérifiez les cookies.")
            
            self.token = match.group(1)
            self.last_update = time.time()
            return self.session, self.token
        except Exception as e:
            print(f"Erreur Auth: {e}")
            raise

    def optimize_image(self, image_content):
        """Redimensionne l'image pour éviter les payloads trop lourds."""
        try:
            img = Image.open(io.BytesIO(image_content))
            # Convertir en RGB si nécessaire (pour PNG/RGBA)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Max 1024px sur le côté le plus long
            img.thumbnail((1024, 1024), Image.LANCZOS)
            
            output = io.BytesIO()
            img.save(output, format="JPEG", quality=80)
            return output.getvalue()
        except Exception as e:
            print(f"Erreur optimisation image: {e}")
            return image_content

    def upload_image(self, image_data):
        try:
            session, token = self.refresh()
            size = len(image_data)
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(size),
                "X-Goog-Upload-Header-Content-Type": "image/jpeg",
                "X-Goog-Upload-Protocol": "resumable"
            }
            
            resp = session.post("https://content-push.googleapis.com/upload/", headers=headers, timeout=30)
            upload_url = resp.headers.get("X-Goog-Upload-Url")
            if not upload_url: return None
            
            headers = {
                "X-Goog-Upload-Command": "upload, finalize",
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Header-Content-Length": str(size)
            }
            resp = session.post(upload_url, headers=headers, data=image_data, timeout=60)
            return resp.text if resp.status_code == 200 else None
        except: return None

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
    image_content = None
    
    try:
        session, token = gemini_auth.refresh()
        
        if image:
            if image.startswith("data:image"):
                header, encoded = image.split(",", 1)
                image_content = base64.b64decode(encoded)
            elif image.startswith("http"):
                img_resp = requests.get(image, timeout=15)
                if img_resp.status_code == 200:
                    image_content = img_resp.content

            if image_content:
                optimized_data = gemini_auth.optimize_image(image_content)
                file_id = gemini_auth.upload_image(optimized_data)

        # Construction requête
        if file_id:
            req = [[prompt, 0, None, [[[file_id, 1], None, None]]], None, ["", "", ""]]
        else:
            # Fallback text-only si upload échoue
            if image: prompt = f"[Image: {image}]\n{prompt}"
            req = [[prompt], None, ["", "", ""]]
            
        payload = {"f.req": json.dumps([None, json.dumps(req)]), "at": token}
        url = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        
        resp = session.post(url, data=payload, params={"rt": "c"}, timeout=(10, 60), stream=True)
        
        answer = None
        for line in resp.iter_lines():
            if line:
                decoded = line.decode('utf-8')
                res = extract_text(decoded)
                if res:
                    answer = res
                    break
        resp.close()
        
        return {
            "status": "success",
            "uid": uid,
            "answer": answer or "Désolé, je n'ai pas pu analyser cette demande.",
            "execution_time": f"{round(time.time() - start_time, 2)}s",
            "image_processed": True if file_id else False
        }
    except Exception as e:
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
