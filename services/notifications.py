from fastapi import FastAPI
from common import db, INSTANCE
from fastapi.middleware.cors import CORSMiddleware
import json

app=FastAPI(title='Notification Service')
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cad.kpi.ua"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
@app.get('/health')
def health(): return {'status':'ok','service':'notifications','instance':INSTANCE}
@app.get('/notifications')
def notifications():
    raw=db().lrange('notifications',0,-1)
    return {'items':[json.loads(i) for i in raw], 'served_by':INSTANCE}
