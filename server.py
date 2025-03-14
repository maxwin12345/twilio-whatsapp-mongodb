from fastapi import FastAPI, Request
from pymongo import MongoClient
from starlette.responses import Response
from datetime import datetime, timedelta
import os
import json
import openai
from openai import ChatCompletion  # Importa directamente ChatCompletion

app = FastAPI()

# -------------------------------------------------------------------
# 1. CONFIGURACIONES BÁSICAS
# -------------------------------------------------------------------
MONGO_URI = os.environ.get("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["assistant"]
notas_collection = db["notas"]
recordatorios_collection = db["recordatorios"]

openai.api_key = os.environ.get("OPENAI_API_KEY")

# -------------------------------------------------------------------
# 2. FUNCIÓN PARA RESPUESTAS GENERALES CON CHAT COMPLETION
# -------------------------------------------------------------------
def get_gpt_response(user_message: str) -> str:
    """
    Llama a la API de OpenAI (ChatCompletion) para obtener una respuesta genérica.
    """
    response = ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un asistente personal en WhatsApp. "
                    "Ayuda con notas, recordatorios y eventos. "
                    "Responde de forma clara y útil."
                )
            },
            {"role": "user", "content": user_message}
        ]
    )
    return response.choices[0].message.content.strip()

# -------------------------------------------------------------------
# 3. FUNCIÓN PARA EXTRAER RECORDATORIOS (CHAT COMPLETION)
# -------------------------------------------------------------------
def extraer_recordatorio(mensaje_usuario: str):
    """
    Intenta extraer un recordatorio en formato JSON.
    Maneja fechas relativas como "mañana" y "pasado mañana".
    Si no se detecta recordatorio, devuelve None.
    """
    hoy = datetime.now()
    manana = hoy + timedelta(days=1)
    pasado_manana = hoy + timedelta(days=2)

    system_instructions = f"""
Hoy es {hoy.strftime('%Y-%m-%d')}.
Si el usuario dice "mañana", asume que es {manana.strftime('%Y-%m-%d')}.
Si el usuario dice "pasado mañana", asume que es {pasado_manana.strftime('%Y-%m-%d')}.
Extrae la tarea y la fecha exacta (en formato YYYY-MM-DD HH:MM) del siguiente mensaje si es un recordatorio.
Si no es un recordatorio, devuelve 'null' (sin comillas).
La respuesta debe ser un JSON válido, por ejemplo:
{{
  "tarea": "Comprar leche",
  "fecha_hora": "2025-03-10 15:00"
}}
No incluyas texto adicional.
"""

    user_prompt = f'Mensaje: "{mensaje_usuario}"'

    try:
        respuesta = ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0
        )
    except Exception as e:
        print(f"⚠️ Error al llamar a OpenAI: {e}")
        return None

    contenido = respuesta.choices[0].message.content.strip()

    # Quita delimitadores de bloques de código si existen
    if contenido.startswith("```") and contenido.endswith("```"):
        contenido = contenido.strip("```").strip()

    if contenido.lower() == "null":
        return None

    try:
        datos_recordatorio = json.loads(contenido)
        fecha_str = datos_recordatorio["fecha_hora"]
        fecha_hora_obj = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M")
        datos_recordatorio["fecha_hora"] = fecha_hora_obj

        print(f"✅ Recordatorio extraído: {datos_recordatorio}")
        return datos_recordatorio
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"⚠️ Error al extraer recordatorio: {e}")
        return None

# -------------------------------------------------------------------
# 4. ENDPOINT PRINCIPAL /whatsapp_webhook
# -------------------------------------------------------------------
@app.post("/whatsapp_webhook")
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        message = form_data.get("Body", "").strip()
        sender = form_data.get("From", "").strip()

        print(f"📩 Mensaje recibido: '{message}' de {sender}")

        datos_recordatorio = extraer_recordatorio(message)

        if datos_recordatorio:
            recordatorio = {
                "tarea": datos_recordatorio["tarea"],
                "fecha_hora": datos_recordatorio["fecha_hora"],
                "numero_usuario": sender,
                "recordatorio_enviado": False
            }
            recordatorios_collection.insert_one(recordatorio)
            response_message = (
                f"⏰ Recordatorio guardado: '{datos_recordatorio['tarea']}' "
                f"para el {datos_recordatorio['fecha_hora'].strftime('%Y-%m-%d %H:%M')}"
            )
        else:
            decision_prompt = f"""
El usuario escribió: "{message}".

Decide la acción a tomar y responde ÚNICAMENTE con el JSON correspondiente:

Si es una nota:
{{"accion": "guardar_nota", "contenido": "Texto de la nota"}}

Si el usuario quiere ver sus notas:
{{"accion": "listar_notas"}}

Si el usuario quiere ver sus recordatorios:
{{"accion": "listar_recordatorios"}}

Si el usuario quiere actualizar un recordatorio:
{{"accion": "actualizar_recordatorio", "id": "ID del recordatorio", "nueva_fecha": "YYYY-MM-DD HH:MM"}}

Si el usuario quiere eliminar un recordatorio:
{{"accion": "eliminar_recordatorio", "id": "ID del recordatorio"}}

Si no se entiende el mensaje:
{{"accion": "ninguna"}}

Responde solo en formato JSON sin texto adicional.
"""
            respuesta = ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": decision_prompt}],
                temperature=0
            )
            contenido_decision = respuesta.choices[0].message.content.strip()

            if contenido_decision.startswith("```") and contenido_decision.endswith("```"):
                contenido_decision = contenido_decision.strip("```").strip()

            try:
                decision = json.loads(contenido_decision)
            except json.JSONDecodeError as e:
                print(f"⚠️ Error al decodificar JSON de OpenAI: {e}")
                decision = {"accion": "ninguna"}

            if decision.get("accion") == "guardar_nota":
                notas_collection.insert_one({"contenido": decision["contenido"]})
                response_message = f"✅ Nota guardada: {decision['contenido']}"
            elif decision.get("accion") == "listar_notas":
                notas = list(notas_collection.find({}, {"_id": 0, "contenido": 1}))
                if notas:
                    response_message = "📝 Notas guardadas:\n" + "\n".join([f"- {n['contenido']}" for n in notas])
                else:
                    response_message = "📂 No tienes notas guardadas."
            elif decision.get("accion") == "listar_recordatorios":
                recordatorios = list(
                    recordatorios_collection.find(
                        {"numero_usuario": sender},
                        {"_id": 1, "tarea": 1, "fecha_hora": 1}
                    )
                )
                if recordatorios:
                    lines = []
                    for rec in recordatorios:
                        fecha_str = rec["fecha_hora"].strftime("%Y-%m-%d %H:%M") if isinstance(rec["fecha_hora"], datetime) else rec["fecha_hora"]
                        lines.append(f"- {rec['_id']}: {rec['tarea']} para el {fecha_str}")
                    response_message = "⏰ Recordatorios guardados:\n" + "\n".join(lines)
                else:
                    response_message = "📂 No tienes recordatorios guardados."
            elif decision.get("accion") == "actualizar_recordatorio":
                response_message = "⚠️ Aún no se implementa la actualización de recordatorios."
            elif decision.get("accion") == "eliminar_recordatorio":
                response_message = "⚠️ Aún no se implementa la eliminación de recordatorios."
            else:
                response_message = get_gpt_response(message)

        twilio_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{response_message}</Message>
</Response>
"""
        print("➡️ TwiML final a Twilio:\n", twilio_response)

        return Response(content=twilio_response, media_type="application/xml")

    except Exception as e:
        print(f"❌ Error en webhook: {e}")
        error_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>❌ Error en el servidor.</Message>
</Response>
"""
        return Response(content=error_response, media_type="application/xml")

