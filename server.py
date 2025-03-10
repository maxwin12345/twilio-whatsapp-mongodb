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
    Extrae la tarea, fecha y hora exactas del siguiente mensaje si es un recordatorio.
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
        fecha_hora_obj = datetime.strptime(datos_recordatorio["fecha_hora"], "%Y-%m-%d %H:%M")
        datos_recordatorio["fecha_hora"] = fecha_hora_obj
        return datos_recordatorio
    except (json.JSONDecodeError, ValueError, KeyError):
        return None

@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        message = form_data.get("Body", "").strip()
        sender = form_data.get("From", "").strip()

        datos_recordatorio = extraer_recordatorio(message)

        if datos_recordatorio and datos_recordatorio.get("tarea"):
            recordatorio = {
                "tarea": datos_recordatorio["tarea"],
                "fecha_hora": datetime.strptime(datos_recordatorio["fecha_hora"], "%Y-%m-%d %H:%M"),
                "numero_usuario": sender,
                "recordatorio_enviado": False
            }
            
            recordatorios_collection.insert_one(recordatorio)

            response_message = f"⏰ Recordatorio guardado: {datos_recordatorio['tarea']} para el {datos_recordatorio['fecha_hora']}."
        else:
            # Si no es un recordatorio, usa GPT para determinar si guardar nota o listar
            prompt = f"""
            El usuario escribió el siguiente mensaje: "{message}".

            Si el usuario quiere guardar una nota, responde solo con:
            {{"accion": "guardar_nota", "contenido": "contenido de la nota"}}

            Si el usuario quiere listar sus notas guardadas, responde solo con:
            {{"accion": "listar_notas"}}

            Si ninguna aplica responde solo con:
            {{"accion": "ninguna"}}
            """

            respuesta = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": prompt}],
                temperature=0
            )

            decision = json.loads(respuesta.choices[0].message.content)

            if decision["accion"] == "guardar_nota":
                notas_collection.insert_one({"contenido": decision["contenido"]})
                response_message = f"✅ Nota guardada: {decision['contenido']}"

            elif decision["accion"] == "listar_notas":
                notas = list(notas_collection.find({}, {"_id": 0, "contenido": 1}))
                response_message = "📝 Notas guardadas:\n" + "\n".join([f"- {nota['contenido']}" for nota in notas]) if notas else "📂 No tienes notas guardadas."

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
