import requests
import json

url = "https://gemini-api-wrapper--dukgiqn.replit.app/gemini"
payload = {
    "pro": "Décris cette image précisément.",
    "image": "https://files.manuscdn.com/user_upload_by_module/session_file/310519663326674938/tHktmMBMIWyLAbWe.jpg",
    "uid": "test-manus-001"
}
headers = {
    "Content-Type": "application/json"
}

print(f"Envoi de la requête POST à {url}...")
try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Statut Code: {response.status_code}")
    print("Réponse brute:")
    print(response.text)
    
    # Essayer de parser le JSON si possible
    try:
        data = response.json()
        print("\nRéponse JSON parsée:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        pass
        
except Exception as e:
    print(f"Erreur lors de la requête : {e}")
