import os
import json

import firebase_admin
from firebase_admin import credentials

_DB_URL = "https://delta-mick-api-default-rtdb.firebaseio.com/"

def init_firebase():
    if firebase_admin._apps:
        return  # not init again

    cred_json = os.environ["FIREBASE_CREDENTIALS"]
    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)

    firebase_admin.initialize_app(cred, {
        "databaseURL": _DB_URL
    })