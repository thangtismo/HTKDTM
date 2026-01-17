# merge_final.py
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
    print("→ Kiểm tra file có tên đúng: weather_all_vn_annual_2000-2023.csv")
    exit()

if not fao_file.exists():
    print(f"KHÔNG TÌM THẤY: {fao_file}")
    exit()

# === ĐỌC DỮ LIỆU ===
print("Đang đọc file thời tiết...")
try:
    weather = pd.read_csv(weather_file)
    print(f"   Đọc thành công: {len(weather)} dòng, {len(weather.columns)} cột")
    print(f"   Cột: {list(weather.columns)}")
except Exception as e:
    print(f"LỖI ĐỌC FILE THỜI TIẾT: {e}")
    exit()

print("Đang đọc file năng suất lúa...")
try:
    fao = pd.read_csv(fao_file)
    print(f"   Đọc thành công: {len(fao)} dòng, {len(fao.columns)} cột")
    print(f"   Cột: {list(fao.columns)}")
except Exception as e:
    print(f"LỖI ĐỌC FILE FAO: {e}")
    exit()

# === SỬA CỘT FAO ===
if "Yield (ton/ha)" in fao.columns:
    fao = fao.rename(columns={"Yield (ton/ha)": "Yield_FAO"})
    print("   Đổi tên: Yield (ton/ha) → Yield_FAO")
elif "Value" in fao.columns:
    fao = fao.rename(columns={"Value": "Yield_FAO"})
    print("   Đổi tên: Value → Yield_FAO")
else:
    print("LỖI: Không tìm thấy cột năng suất (Value hoặc Yield (ton/ha))")
    print("Cột hiện có:", list(fao.columns))
    exit()

# Kiểm tra cột Year
if "Year" not in fao.columns:
    print("LỖI: File FAO không có cột 'Year'")
    print("Cột hiện có:", list(fao.columns))
    exit()

# Giữ lại chỉ 2 cột
fao = fao[["Year", "Yield_FAO"]].drop_duplicates()
print(f"   FAO sau xử lý: {len(fao)} dòng")

# === SỬA CỘT WEATHER ===
if "Year" not in weather.columns:
    print("LỖI: File weather không có cột 'Year'")
    print("Cột hiện có:", list(weather.columns))
    exit()

# === GỘP DỮ LIỆU ===
merged = weather.merge(fao, on="Year", how="left")

# Sắp xếp cột đẹp
merged = merged[["Year", "TempAvg", "RainfallAnnual", "HumidityAvg", "Yield_FAO"]]

# === LƯU FILE ===
merged.to_csv(output_file, index=False)

# === IN KẾT QUẢ ===
print("\n" + "="*50)
print("HOÀN TẤT GỘP DỮ LIỆU!")
print(f"   File đã lưu: {output_file}")
print(f"   Số dòng: {len(merged)}")
print(f"   Cột: {list(merged.columns)}")
print("\n5 DÒNG ĐẦU:")
print(merged.head())
print("="*50)