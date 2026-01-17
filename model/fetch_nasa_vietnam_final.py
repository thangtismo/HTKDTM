import requests
import pandas as pd
import time
import random
from pathlib import Path
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import numpy as np

# ================== CẤU HÌNH ==================
BASE_DIR = Path(__file__).resolve().parents[1]  # LÊN 1 CẤP → E:\project_cuoiky\
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

PROVINCES_FILE = DATA_DIR / "vietnam_provinces_latlon.csv"
FAO_FILE = DATA_DIR / "rice_yield_vn.csv"
OUT_DIR = DATA_DIR / "nasa_data"
OUT_DIR.mkdir(exist_ok=True)

START_YEAR = 2000
END_YEAR = 2023
PARAMETERS = "T2M,PRECTOTCORR,RH2M"  # PRECTOTCORR là bản sửa lỗi
COMMUNITY = "AG"

# URL MỚI: DAILY → TỰ TÍNH ANNUAL
BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

PAUSE_MIN = 3.0
PAUSE_MAX = 5.0
USER_AGENT = "Vietnam-Climate-Research/1.0 (+contact@example.com)"
# ===========================================


def get_session():
    session = requests.Session()
    retry = Retry(total=6, backoff_factor=2.5, status_forcelist=[429, 500, 502, 503, 504], raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


session = get_session()


def fetch_nasa_daily(lat, lon, province):
    """Lấy dữ liệu DAILY từ NASA → trả về dict theo năm"""
    params = {
        "parameters": PARAMETERS,
        "community": COMMUNITY,
        "longitude": f"{lon:.6f}",
        "latitude": f"{lat:.6f}",
        "start": f"{START_YEAR}0101",
        "end": f"{END_YEAR}1231",
        "format": "JSON"
    }

    for attempt in range(6):
        try:
            resp = session.get(BASE_URL, params=params, timeout=90)

            if resp.status_code == 429:
                wait = 15 * (2 ** attempt)
                print(f"   [RATE LIMIT] {province} - Chờ {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                error_msg = resp.text[:200].replace("\n", " ")
                raise RuntimeError(f"HTTP {resp.status_code}: {error_msg}")

            data = resp.json()
            if "properties" not in data or "parameter" not in data["properties"]:
                raise ValueError("API trả về cấu trúc rỗng")

            # Xử lý dữ liệu daily
            params_data = data["properties"]["parameter"]
            daily_data = []

            for date_str, temp in params_data["T2M"].items():
                if temp is None or temp == -999:
                    continue
                year = int(date_str[:4])
                if START_YEAR <= year <= END_YEAR:
                    daily_data.append({
                        "Year": year,
                        "T2M": temp,
                        "PRECTOTCORR": params_data["PRECTOTCORR"].get(date_str, None),
                        "RH2M": params_data["RH2M"].get(date_str, None),
                    })

            # Nhóm theo năm → tính trung bình
            df = pd.DataFrame(daily_data)
            if df.empty:
                raise ValueError("Không có dữ liệu hợp lệ")

            annual = df.groupby("Year").agg({
                "T2M": "mean",
                "PRECTOTCORR": "sum",  # Tổng mưa
                "RH2M": "mean"
            }).round(4).reset_index()

            annual = annual.rename(columns={
                "T2M": "TempAvg",
                "PRECTOTCORR": "RainfallAnnual",
                "RH2M": "HumidityAvg"
            })

            return annual.to_dict("records")

        except Exception as e:
            if attempt == 5:
                raise RuntimeError(f"Thất bại sau 6 lần: {e}")
            wait = (3 ** attempt) + random.uniform(1, 3)
            print(f"   [LỖI] {province} (lần {attempt+1}): {e} → Chờ {wait:.1f}s")
            time.sleep(wait)


def process_one_province(row, all_data):
    province = row["Province"]
    lat, lon = row["Latitude"], row["Longitude"]
    cache_file = OUT_DIR / f"{province}_{START_YEAR}-{END_YEAR}.csv"

    if cache_file.exists():
        try:
            df = pd.read_csv(cache_file)
            if len(df) >= 20 and "Year" in df.columns:
                print(f"   [CACHE] {province}")
                all_data.extend(df.to_dict("records"))
                return True
        except:
            pass

    print(f"Đang lấy: {province} ({lat:.4f}, {lon:.4f}) [dùng DAILY → ANNUAL]")
    try:
        records = fetch_nasa_daily(lat, lon, province)
        df = pd.DataFrame(records)
        df["Province"] = province
        df = df[["Province", "Year", "TempAvg", "RainfallAnnual", "HumidityAvg"]]
        df.to_csv(cache_file, index=False)
        print(f"   [LƯU] {cache_file.name} ({len(df)} năm)")
        all_data.extend(records)
        return True

    except Exception as e:
        print(f"   [THẤT BẠI] {province}: {e}")
        return False

    finally:
        pause = random.uniform(PAUSE_MIN, PAUSE_MAX)
        print(f"   Chờ {pause:.1f}s...\n")
        time.sleep(pause)


def main():
    if not PROVINCES_FILE.exists():
        print(f"KHÔNG TÌM THẤY: {PROVINCES_FILE}")
        return

    print("Đang đọc danh sách 63 tỉnh thành...")
    provinces = pd.read_csv(PROVINCES_FILE)

    all_data = []
    success = 0

    for idx, row in provinces.iterrows():
        print(f"[{idx+1:2d}/63]", end=" ")
        if process_one_province(row, all_data):
            success += 1

    if not all_data:
        print("KHÔNG CÓ DỮ LIỆU!")
        return

    weather_all = pd.DataFrame(all_data)
    output_file = DATA_DIR / "weather_all_vn_annual_2000-2023.csv"
    weather_all.to_csv(output_file, index=False)
    print(f"\nHOÀN TẤT! Đã lưu {success}/63 tỉnh → {output_file.name}")

    if FAO_FILE.exists():
        try:
            fao = pd.read_csv(FAO_FILE)
            if "Value" in fao.columns:
                fao = fao.rename(columns={"Value": "Yield_FAO"})
            if {"Year", "Yield_FAO"}.issubset(fao.columns):
                merged = weather_all.merge(fao[["Year", "Yield_FAO"]], on="Year", how="left")
                merged_file = DATA_DIR / "merged_yield_weather_by_province.csv"
                merged.to_csv(merged_file, index=False)
                print(f"ĐÃ GỘP FAO → {merged_file.name}")
        except Exception as e:
            print(f"Lỗi gộp: {e}")


if __name__ == "__main__":
    print("=" * 70)
    print("NASA POWER API (DAILY → ANNUAL) - 63 TỈNH VIỆT NAM")
    print("Thời gian: ~20–25 phút (do xử lý daily data)")
    print("=" * 70)
    main()
    print("\nHOÀN TẤT!")