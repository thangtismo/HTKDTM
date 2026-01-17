import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase():
    """
    Khởi tạo Firebase app và trả về Firestore client.
    """
    cred = credentials.Certificate("firebase_config.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    return db
