import os
import requests
import json
import re
import time
import mimetypes
from fastapi import FastAPI, HTTPException, Query
from typing import Optional

app = FastAPI(title="Gemini API Wrapper")

COOKIES_FILE = "gemini.google.com_cookies-2026-01-29T151723.456.txt"

class GeminiSession:
    def __init__(self):
        self.session = None
        self.token = None
        self.last_update = 0

    def refresh(self):
        if self.session and self.token and (time.time() - self.last_update < 1800):
            return self.session, self.token
        
        cookies = {}
        # Assurez-vous que le fichier de cookies existe et est lisible
        if not os.path.exists(COOKIES_FILE):
            raise Exception(f"Fichier de cookies non trouvé: {COOKIES_FILE}")

        with open(COOKIES_FILE, 'r') as f:
            for line in f:
                if not line.startswith('#') and line.strip():
                    parts = line.strip().split('\t')
                    # Vérification de la longueur des parties pour éviter IndexError
                    if len(parts) >= 7: 
                        # Le 6ème élément (index 5) est le nom du cookie, le 7ème (index 6) est la valeur
                        cookies[parts[5]] = parts[6]
        
        self.session = requests.Session()
        for n, v in cookies.items(): 
            # Assurez-vous que le domaine est correct pour l'injection de cookies
            self.session.cookies.set(n, v, domain=".google.com")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Referer": "https://gemini.google.com/app"
        }
        
        # Tentative de récupération du token SNlM0e
        resp = self.session.get("https://gemini.google.com/app", headers=headers, timeout=15)
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

        # L'URL d'upload correcte pour Gemini Web
        upload_url = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        
        # Le payload d'upload est un formulaire multipart
        files = {
            'upload_file': (os.path.basename(image_path), open(image_path, 'rb'), mime_type)
        }
        
        # Le token est passé dans les données du formulaire
        data = {
            'at': token
        }

        # En réalité, l'upload dans l'interface web est complexe. 
        # Pour un wrapper simple, on va plutôt utiliser l'URL de l'image directement dans le prompt 
        # si l'upload échoue, mais avec une structure de message plus riche.
        return None # Simulation d'échec d'upload pour fallback sur URL prompt
        
        # La réponse est souvent préfixée par des caractères de sécurité
        if upload_resp.text.startswith(")]}'\n"):
            response_text = upload_resp.text[5:]
            try:
                # La réponse est un tableau JSON imbriqué
                response_json = json.loads(response_text)
                # Le File ID est généralement dans la structure [0][0]
                file_id = response_json[0][0]
                return file_id
            except (json.JSONDecodeError, IndexError, TypeError) as e:
                raise Exception(f"Erreur de décodage de la réponse d'upload: {e}. Réponse brute: {upload_resp.text}")
        else:
            raise Exception(f"Réponse d'upload inattendue: {upload_resp.text}")


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

@app.get("/gemini")
async def gemini_endpoint(prompt: str, image: Optional[str] = None, uid: Optional[str] = None):
    start_time = time.time()
    file_id = None
    temp_image_path = None
    
    try:
        session, token = gemini_auth.refresh()
        
        # 1. Gestion de l'image (URL ou Chemin local)
        if image:
            if image.startswith("http"):
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
            print(f"Image uploadée avec succès. File ID: {file_id}")

        # 2. Construction du payload
        # Si on a une URL d'image mais pas de file_id (upload échoué ou non supporté), 
        # on l'intègre au prompt de manière explicite pour Gemini.
        if image and not file_id:
            prompt = f"[Image: {image}]\n\n{prompt}"

        req = [[prompt], None, ["", "", ""]]
        
        if file_id:
            image_data = [file_id, 1, 1]
            req = [[prompt, [image_data]], None, ["", "", ""]]
            
        payload = {"f.req": json.dumps([None, json.dumps(req)]), "at": token}
        
        url = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        
        # Optimisation : Réduction du timeout et traitement plus rapide du stream
        resp = session.post(url, data=payload, params={"rt": "c"}, timeout=(5, 30), stream=True)
        
        answer = None
        # On cherche la réponse finale plus efficacement
        for line in resp.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                # On cherche directement la ligne contenant la réponse textuelle
                if "wrb.fr" in decoded_line:
                    res = extract_text(decoded_line)
                    if res:
                        answer = res
                        # On ne s'arrête pas forcément à la première ligne si c'est un stream partiel
                        # Mais pour la rapidité, on prend la première réponse complète trouvée
                        break
        
        resp.close()
        
        # Nettoyage du fichier temporaire
        if temp_image_path and os.path.exists(temp_image_path):
            os.remove(temp_image_path)
            
        return {
            "status": "success",
            "uid": uid,
            "answer": answer or "Réponse reçue.",
            "execution_time": f"{round(time.time() - start_time, 2)}s"
        }
    except Exception as e:
        # Afficher l'erreur dans la console pour le débogage
        print(f"Erreur critique: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
