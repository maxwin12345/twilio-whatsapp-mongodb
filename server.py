from fastapi import FastAPI
from pymongo import MongoClient
import os

app = FastAPI()

# Obtiene la URI desde una variable de entorno
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["assistant"]
notas_collection = db["notas"]
