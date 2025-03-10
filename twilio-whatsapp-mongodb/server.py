from fastapi import FastAPI, Request
import openai
import pymongo
import os

app = FastAPI()

# Conexión con MongoDB Atlas (REEMPLAZA CON TU CADENA)
MONGO_URI = "mongodb+srv://asistentemax:winickI1825@cluster0.zj8cb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = pymongo.MongoClient(MONGO_URI)
db = client["assistant"]
notas_collection = db["notas"]

@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    data = await request.form()
    message = data.get("Body")
    sender = data.get("From")

    if message.lower().startswith("apunta"):
        contenido = message[7:]  # Extraer el contenido después de "Apunta"
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
