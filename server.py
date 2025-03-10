from fastapi import FastAPI, Request
from pymongo import MongoClient
import os

app = FastAPI()

# Conexión con MongoDB Atlas
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["assistant"]
notas_collection = db["notas"]

@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    data = await request.form()
    message = data.get("Body")
    sender = data.get("From")

    if message.lower().startswith("apunta"):
        contenido = message[7:].strip()  # Extraer el contenido después de "Apunta"
        nueva_nota = {"contenido": contenido}
        notas_collection.insert_one(nueva_nota)
        response_message = f"✅ Nota guardada: {contenido}"
    elif message.lower() == "listar notas":
        notas = list(notas_collection.find({}, {"_id": 0, "contenido": 1}))
        response_message = "📝 Notas guardadas:\n" + "\n".join([f"- {nota['contenido']}" for nota in notas])
    else:
        response_message = "🤖 Comandos disponibles:\n- 'Apunta [nota]'\n- 'Listar notas'"

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/xml"},
        "body": f"""<Response><Message>{response_message}</Message></Response>"""
    }

