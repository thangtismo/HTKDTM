import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase():
    """Initialize Firebase Admin SDK (once) and return Firestore client."""
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase_config.json")
        firebase_admin.initialize_app(cred)
    return firestore.client()
