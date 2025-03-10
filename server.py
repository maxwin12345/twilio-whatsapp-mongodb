from fastapi import FastAPI, Request, Form
from pymongo import MongoClient
import os
from starlette.responses import Response

app = FastAPI()

# Conexión con MongoDB Atlas
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["assistant"]
notas_collection = db["notas"]

@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        message = form_data.get("Body", "").strip()
        sender = form_data.get("From", "").strip()

        response_message = "🤖 Comandos disponibles:\n- 'Apunta [nota]'\n- 'Listar notas'"

        if message.lower().startswith("apunta"):
            contenido = message[7:].strip()  # Extraer el contenido después de "Apunta"
            if contenido:
                nueva_nota = {"contenido": contenido}
                notas_collection.insert_one(nueva_nota)
                response_message = f"✅ Nota guardada: {contenido}"
            else:
                response_message = "⚠️ No escribiste una nota válida después de 'Apunta'."

        elif message.lower() == "listar notas":
            notas = list(notas_collection.find({}, {"_id": 0, "contenido": 1}))
            if notas:
                response_message = "📝 Notas guardadas:\n" + "\n".join([f"- {nota['contenido']}" for nota in notas])
            else:
                response_message = "📂 No tienes notas guardadas."

        # Responder en formato XML para Twilio
        twilio_response = f"""
        <Response>
            <Message>{response_message}</Message>
        </Response>
        """
        return Response(content=twilio_response, media_type="application/xml")

    except Exception as e:
        print(f"Error en webhook: {e}")  # Agregar logs en consola
        return Response(content="<Response><Message>❌ Error en el servidor. Inténtalo más tarde.</Message></Response>",
                        media_type="application/xml")
