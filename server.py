from fastapi import FastAPI, Request, Form
from pymongo import MongoClient
import os
import openai  # Asegúrate de importar OpenAI correctamente
from starlette.responses import Response

app = FastAPI()

# Conexión con MongoDB Atlas
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["assistant"]
notas_collection = db["notas"]

# Configurar OpenAI GPT
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")



client_openai = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def get_gpt_response(user_message):
    completion = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Eres un asistente personal en WhatsApp, ayuda a Max con notas, recordatorios y eventos."},
            {"role": "user", "content": user_message}
        ]
    )
    return completion.choices[0].message.content.strip()


@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        message = form_data.get("Body", "").strip()
        sender = form_data.get("From", "").strip()

        if message.lower().startswith("apunta"):
            contenido = message[7:].strip()
            if contenido:
                notas_collection.insert_one({"contenido": contenido})
                response_message = f"✅ Nota guardada: {contenido}"
            else:
                response_message = "⚠️ No escribiste una nota válida."
        elif message.lower() == "listar notas":
            notas = list(notas_collection.find({}, {"_id": 0, "contenido": 1}))
            response_message = "📝 Notas guardadas:\n" + "\n".join([f"- {nota['contenido']}" for nota in notas]) if notas else "📂 No tienes notas guardadas."
        else:
            response_message = get_gpt_response(message)  # Respuesta de OpenAI

        twilio_response = f"""
        <Response>
            <Message>{response_message}</Message>
        </Response>
        """
        return Response(content=twilio_response, media_type="application/xml")

    except Exception as e:
        print(f"Error en webhook: {e}")
        return Response(content="<Response><Message>❌ Error en el servidor.</Message></Response>", media_type="application/xml")

