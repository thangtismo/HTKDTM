import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
import numpy as np

# === 1. Đọc dữ liệu ===
# === 1. Đọc dữ liệu ===
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
# Xây dựng đường dẫn tuyệt đối đến file data tương đối với file script này
data_path = os.path.join(script_dir, '../data/rice_yield_vn.csv')
data = pd.read_csv(data_path)
print("Dữ liệu ban đầu:")
print(data.head())

# === 2. Chuẩn bị dữ liệu cho mô hình ===
X = data[['Year']]         # biến độc lập
y = data['Yield (ton/ha)'] # biến phụ thuộc

# === 3. Huấn luyện mô hình hồi quy tuyến tính ===
model = LinearRegression()
model.fit(X, y)

# === 4. Dự đoán ===
future_years = np.array([[2024], [2025], [2026]])  # năm muốn dự đoán
future_preds = model.predict(future_years)

# Hiển thị kết quả dự đoán
for year, pred in zip(future_years.flatten(), future_preds):
    print(f"🌾 Dự đoán năng suất lúa {year}: {pred:.3f} tấn/ha")

# === 5. Vẽ biểu đồ ===
plt.figure(figsize=(10,6))
plt.scatter(X, y, color='blue', label='Dữ liệu thật')
plt.plot(X, model.predict(X), color='red', label='Mô hình Linear Regression')
plt.scatter(future_years, future_preds, color='green', label='Dự đoán (2024-2026)', s=80)

plt.xlabel('Năm')
plt.ylabel('Năng suất (tấn/ha)')
plt.title('Dự báo năng suất lúa Việt Nam bằng Linear Regression')
plt.legend()
plt.grid(True)
plt.show()
