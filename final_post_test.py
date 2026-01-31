import requests
import json
import base64
import time
import subprocess
import os

def run_test():
    # 1. Lire le base64 préparé
    with open('/home/ubuntu/gemini-api-wrapper/final_b64.txt', 'r') as f:
        image_b64 = f.read().strip()
    
    # 2. Lancer le serveur en arrière-plan
    print("Démarrage du serveur FastAPI...")
    server_process = subprocess.Popen(
        ["python3", "main.py"],
        cwd="/home/ubuntu/gemini-api-wrapper",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Attendre que le serveur démarre
    time.sleep(5)
    
    try:
        # 3. Préparer la requête POST
        url = "http://127.0.0.1:8000/gemini"
        payload = {
            "pro": "Décris précisément ce que tu vois sur cette image.",
            "image": image_b64,
            "uid": "user_test_final_62"
        }
        
        print(f"Envoi de la requête POST à {url}...")
        response = requests.post(url, json=payload, timeout=60)
        
        # 4. Afficher les résultats
        print("\n--- STATUS CODE ---")
        print(response.status_code)
        
        print("\n--- RÉPONSE JSON ---")
        result = response.json()
        print(json.dumps(result, indent=4, ensure_ascii=False))
        
        if response.status_code == 200 and result.get("status") == "success":
            print("\n✅ TEST RÉUSSI : La méthode POST a fonctionné avec les paramètres pro, image et uid.")
        else:
            print("\n❌ ÉCHEC DU TEST")
            
    except Exception as e:
        print(f"Erreur lors du test : {e}")
    finally:
        # Arrêter le serveur
        server_process.terminate()
        print("\nServeur arrêté.")

if __name__ == "__main__":
    run_test()
