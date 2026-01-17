import requests
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# --- Kết nối Firebase ---
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Cấu hình API ---
API_KEY = "8e054550351ac98ddb1c99ddb6e5adcd"  
CITY = "Hanoi"
URL = f"https://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric&lang=vi"

def fetch_weather():
    response = requests.get(URL)
    data = response.json()

    # --- Tạo bản ghi ---
    record = {
        "Year": datetime.datetime.now().year,
        "TempAvg": data["main"]["temp"],
        "RainfallAnnual": data.get("rain", {}).get("1h", 0),
        "HumidityAvg": data["main"]["humidity"],
        "Time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # --- Lưu vào Firestore ---
    db.collection("Weather").add(record)
    print("✅ Dữ liệu thời tiết đã được lưu:", record)

if __name__ == "__main__":
    fetch_weather()
