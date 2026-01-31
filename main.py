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

    def upload_image(self, image_path: str):
        """
        Upload une image vers les serveurs Google pour obtenir un file_id utilisable par Gemini.
        """
        try:
            session, token = self.refresh()
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type:
                mime_type = 'image/jpeg'
            
            size = len(image_data)
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(size),
                "X-Goog-Upload-Header-Content-Type": mime_type,
                "X-Goog-Upload-Protocol": "resumable"
            }
            
            # Étape 1: Initialiser l'upload
            upload_url = "https://content-push.googleapis.com/upload/"
            resp = session.post(upload_url, headers=headers, timeout=30)
            
            if resp.status_code != 200:
                print(f"Échec initialisation upload: {resp.status_code}")
                return None
            
            upload_session_url = resp.headers.get("X-Goog-Upload-Url")
            if not upload_session_url:
                return None
            
            # Étape 2: Envoyer les données binaires
            headers = {
                "X-Goog-Upload-Command": "upload, finalize",
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Header-Content-Length": str(size)
            }
            resp = session.post(upload_session_url, headers=headers, data=image_data, timeout=60)
            
            if resp.status_code == 200:
                file_id = resp.text
                print(f"Image uploadée avec succès, file_id: {file_id}")
                return file_id
            
            return None
        except Exception as e:
            print(f"Erreur lors de l'upload vers Google: {e}")
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
    b64_image = None
    
    try:
        session, token = gemini_auth.refresh()
        
        # Gestion de l'image
        if image:
            if image.startswith("data:image"):
                try:
                    b64_image = image
                    header, encoded = image.split(",", 1)
                    ext_match = re.search(r'image/(.*?);', header)
                    ext = ext_match.group(1) if ext_match else "jpg"
                    
                    image_data = base64.b64decode(encoded)
                    temp_image_path = f"/tmp/temp_image_b64_{int(time.time())}.{ext}"
                    with open(temp_image_path, 'wb') as f:
                        f.write(image_data)
                except Exception as e:
                    print(f"Erreur décodage base64: {e}")
            elif image.startswith("http"):
                try:
                    img_resp = requests.get(image, timeout=15)
                    if img_resp.status_code == 200:
                        # Convertir en base64 pour le fallback
                        mime_type = img_resp.headers.get('Content-Type', 'image/jpeg')
                        encoded_string = base64.b64encode(img_resp.content).decode('utf-8')
                        b64_image = f"data:{mime_type};base64,{encoded_string}"
                        
                        temp_image_path = f"/tmp/temp_image_{int(time.time())}.jpg"
                        with open(temp_image_path, 'wb') as f:
                            f.write(img_resp.content)
                    else:
                        print(f"Échec téléchargement image: {img_resp.status_code}")
                except Exception as e:
                    print(f"Erreur téléchargement image: {e}")

            # Tentative d'upload réel vers Google (méthode recommandée)
            if temp_image_path and os.path.exists(temp_image_path):
                file_id = gemini_auth.upload_image(temp_image_path)

            # Fallback prompt si l'upload a échoué (injection Base64)
            if image and not file_id and b64_image:
                # On injecte l'image directement en Base64 dans le prompt si l'upload Google échoue
                prompt = f"Analyse cette image fournie en Base64 :\n{b64_image}\n\nQuestion : {prompt}"
            elif image and not file_id:
                # Dernier recours si même le base64 a échoué
                prompt = f"Analyse cette image : {image}\n\nQuestion : {prompt}"

        # Construction de la requête Gemini
        if file_id:
            # Structure pour inclure une image dans la requête Bard/Gemini
            image_data = [[file_id, 1], None, None]
            req = [[prompt, 0, None, [image_data]], None, ["", "", ""]]
        else:
            req = [[prompt], None, ["", "", ""]]
            
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
            "answer": answer or "Je n'ai pas pu générer de réponse.",
            "execution_time": f"{round(time.time() - start_time, 2)}s",
            "image_processed": True if file_id else False
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
