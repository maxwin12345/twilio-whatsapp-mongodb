from fastapi import FastAPI, Request
from pymongo import MongoClient
from starlette.responses import Response
from datetime import datetime
import os
import openai
import json

app = FastAPI()

# Conexión MongoDB Atlas
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["assistant"]
notas_collection = db["notas"]
recordatorios_collection = db["recordatorios"]

# Configuración OpenAI
openai.api_key = os.environ.get("OPENAI_API_KEY")

def get_gpt_response(user_message):
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Eres un asistente personal en WhatsApp, ayuda a Max con notas, recordatorios y eventos."},
            {"role": "user", "content": user_message}
        ]
    )
    return response.choices[0].message.content.strip()


def extraer_recordatorio(mensaje_usuario):
    prompt = f"""
    Extrae la tarea, fecha y hora del siguiente mensaje si es un recordatorio.
    Si no es un recordatorio devuelve null.

    Mensaje: \"{mensaje_usuario}\"

    Devuelve en formato JSON:
    {{
      "tarea": "string",
      "fecha_hora": "YYYY-MM-DD HH:MM"
    }}
    """

    respuesta = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}],
        temperature=0
    )

    contenido = respuesta.choices[0].message.content
    try:
        datos_recordatorio = json.loads(contenido)
        return datos_recordatorio
    except json.JSONDecodeError:
        return None

@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        message = form_data.get("Body", "").strip()
        sender = form_data.get("From", "").strip()

        datos_recordatorio = extraer_recordatorio(message)

        if datos_recordatorio and datos_recordatorio.get("tarea"):
            try:
                fecha_hora_obj = datetime.strptime(datos_recordatorio["fecha_hora"], "%Y-%m-%d %H:%M")
                recordatorio = {
                    "tarea": datos_recordatorio["tarea"],
                    "fecha_hora": fecha_hora_obj,
                    "numero_usuario": sender,
                    "recordatorio_enviado": False
                }
                recordatorios_collection.insert_one(recordatorio)

                response_message = f"⏰ Recordatorio guardado: {datos_recordatorio['tarea']} para el {datos_recordatorio['fecha_hora']}."

            except ValueError as ve:
                response_message = f"⚠️ Error con el formato de fecha/hora: {ve}. Asegúrate de escribir claramente el día y la hora."
        else:
            response_message = get_gpt_response(message)

        twilio_response = f"""
        <Response>
            <Message>{response_message}</Message>
        </Response>
        """
        return Response(content=twilio_response, media_type="application/xml")

    except Exception as e:
        print(f"Error en webhook: {e}")
        return Response(content="<Response><Message>❌ Error en el servidor.</Message></Response>", media_type="application/xml")
