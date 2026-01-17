
import firebase_admin
from firebase_admin import credentials, firestore, auth
import datetime
import random

# Khởi tạo Firebase tái sử dụng logic từ các tệp hiện có hoặc khởi tạo trực tiếp
try:
    cred = credentials.Certificate("firebase_config.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Connected to Firebase.")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)

def seed_users():
    print("Creating sample user...")
    try:
        # Check if user exists
        try:
            auth.get_user_by_email("admin@example.com")
            print("   User 'admin@example.com' already exists.")
        except auth.UserNotFoundError:
            auth.create_user(
                email="admin@example.com",
                password="password123",
                display_name="Admin User"
            )
            print("   ✅ Created user: admin@example.com / password123")
    except Exception as e:
        print(f"   ❌ Error creating user: {e}")

def seed_seasons():
    print("Seeding sample seasons...")
    collection = db.collection("seasons")
    
    # Check if empty
    docs = list(collection.limit(1).stream())
    if len(docs) > 0:
        print("   Database already has data. Skipping seed.")
        return

    crops = ["lúa", "ngô", "cà phê", "tiêu", "điều"]
    provinces = ["Hà Nội", "Đắk Lắk", "Cần Thơ", "Sóc Trăng", "Đồng Nai"]
    
    samples = []
    for i in range(10):
        # Random dates in last 6 months
        sow_date = datetime.datetime.now() - datetime.timedelta(days=random.randint(100, 180))
        harvest_date = sow_date + datetime.timedelta(days=random.randint(90, 120))
        
        doc_data = {
            "farmer_name": f"Nông dân {i+1}",
            "province": random.choice(provinces),
            "crop": random.choice(crops),
            "area": round(random.uniform(0.5, 5.0), 1),
            "sow_date": sow_date.strftime("%Y-%m-%d"),
            "harvest_date": harvest_date.strftime("%Y-%m-%d"),
            "fertilizer": "NPK, hữu cơ",
            "created_at": datetime.datetime.now().isoformat(),
            "user": "admin@example.com",
            # Add some pre-calculated fields to look good
            "actual_yield": round(random.uniform(2.0, 8.0), 2)
        }
        samples.append(doc_data)

    count = 0
    for data in samples:
        collection.add(data)
        count += 1
    
    print(f"   ✅ Added {count} sample seasons.")

if __name__ == "__main__":
    seed_users()
    seed_seasons()
    print("🎉 Seeding complete!")
