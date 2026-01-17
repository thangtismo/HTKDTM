# fix_and_merge.py
import pandas as pd
from pathlib import Path

# === ĐƯỜNG DẪN ===
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

weather_file = DATA_DIR / "weather_all_vn_annual_2000-2023.csv"
fao_file = DATA_DIR / "rice_yield_vn.csv"
output_file = DATA_DIR / "merged_yield_weather_vn.csv"

# === KIỂM TRA FILE ===
if not weather_file.exists():
    print(f"KHÔNG TÌM THẤY: {weather_file}")
    exit()
if not fao_file.exists():
    print(f"KHÔNG TÌM THẤY: {fao_file}")
    exit()

# === ĐỌC FILE WEATHER KHÔNG CÓ HEADER ===
print("Đang đọc file thời tiết (KHÔNG CÓ HEADER)...")
weather = pd.read_csv(weather_file, header=None)  # QUAN TRỌNG: header=None
print(f"   Dữ liệu thô: {len(weather)} dòng")

# GÁN TÊN CỘT ĐÚNG
weather.columns = ["Year", "TempAvg", "RainfallAnnual", "HumidityAvg"]
weather["Year"] = weather["Year"].astype(int)
print(f"   Đã gán cột: {list(weather.columns)}")

# === ĐỌC FILE FAO ===
print("Đang đọc file năng suất lúa...")
fao = pd.read_csv(fao_file)
print(f"   Cột: {list(fao.columns)}")

# Đổi tên cột Yield
if "Yield (ton/ha)" in fao.columns:
    fao = fao.rename(columns={"Yield (ton/ha)": "Yield_FAO"})
elif "Value" in fao.columns:
    fao = fao.rename(columns={"Value": "Yield_FAO"})

fao = fao[["Year", "Yield_FAO"]].drop_duplicates()
print(f"   FAO sau xử lý: {len(fao)} dòng")

# === GỘP DỮ LIỆU ===
print("Đang gộp theo Year...")
merged = weather.merge(fao, on="Year", how="left")

# Sắp xếp cột
merged = merged[["Year", "TempAvg", "RainfallAnnual", "HumidityAvg", "Yield_FAO"]]

# === LƯU FILE ===
merged.to_csv(output_file, index=False)

# === IN KẾT QUẢ ===
print("\n" + "="*60)
print("HOÀN TẤT – FILE GỘP ĐÃ SẴN SÀNG!")
print(f"   File: {output_file.name}")
print(f"   Số dòng: {len(merged)}")
print(f"   Năm: {merged['Year'].min()} → {merged['Year'].max()}")
print("\n5 DÒNG ĐẦU:")
print(merged.head())
print("="*60)