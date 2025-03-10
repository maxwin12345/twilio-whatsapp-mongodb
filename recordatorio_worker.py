import time
from datetime import datetime
from pymongo import MongoClient
from twilio.rest import Client
import os

# Conectar a MongoDB
mongo_uri = os.environ.get("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["assistant"]
recordatorios_collection = db["recordatorios"]

# Configuración de Twilio
twilio_sid = os.environ.get("TWILIO_SID")
twilio_token = os.environ.get("TWILIO_TOKEN")
twilio_numero = 'whatsapp:+14155238886'
twilio_client = Client(twilio_sid, twilio_token)

def enviar_recordatorios():
    while True:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        pendientes = recordatorios_collection.find({
            "fecha_hora": ahora,
            "recordatorio_enviado": False
        })

        for recordatorio in pendientes:
            mensaje = f"🔔 Recordatorio: {recordatorio['tarea']}"
            twilio_client.messages.create(
                from_=twilio_numero,
                body=mensaje,
                to=recordatorio["numero_usuario"]
            )
            recordatorios_collection.update_one(
                {"_id": recordatorio["_id"]},
                {"$set": {"recordatorio_enviado": True}}
            )
        
        time.sleep(60)  # Revisar cada minuto

if __name__ == "__main__":
    enviar_recordatorios()
