from fastapi import FastAPI, Request
from pymongo import MongoClient
import os
import openai
from starlette.responses import Response
import json
from datetime import datetime

app = FastAPI()

# Conexión con MongoDB Atlas
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["assistant"]
notas_collection = db["notas"]
recordatorios_collection = db["recordatorios"]

# Configuración correcta para OpenAI >=1.0.0
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

# ✅ Función para extraer recordatorios automáticamente
def extraer_recordatorio(mensaje_usuario):
    prompt = f"""
    Del siguiente mensaje identifica claramente si se trata de un recordatorio o no.

    Si es un recordatorio, extrae:
    - tarea (la acción del recordatorio)
    - fecha_hora (formato exacto YYYY-MM-DD HH:MM en 24 horas)

    Si no detectas claramente una fecha y hora, devuelve null.

    Ejemplos:
    - "Recuérdame llamar mañana a las 10am" -> {{"tarea":"llamar","fecha_hora":"2025-03-10 10:00"}}
    - "Hola, ¿cómo estás?" -> null

    Mensaje: "{mensaje_usuario}"

    Responde ÚNICAMENTE en formato JSON válido sin explicaciones adicionales.
    """

    respuesta = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
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
            fecha_hora_str = datos_recordatorio["fecha_hora"]

            try:
                fecha_hora_obj = datetime.strptime(fecha_hora_str, "%Y-%m-%d %H:%M")
            except ValueError:
                response_message = "⚠️ La fecha y hora del recordatorio no es válida, intenta de nuevo."
            else:
                recordatorio = {
                    "tarea": datos_recordatorio["tarea"],
                    "fecha_hora": fecha_hora_obj,
                    "numero_usuario": sender,
                    "recordatorio_enviado": False
                }
                recordatorios_collection.insert_one(recordatorio)

                response_message = f"⏰ Recordatorio guardado: {datos_recordatorio['tarea']} para el {fecha_hora_str}."
            except ValueError:
                response_message = "⚠️ Formato de fecha inválido, intenta de nuevo."

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
