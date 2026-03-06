# MultiTrans — Deploy lên Render.com (FREE)

## Cấu trúc thư mục (QUAN TRỌNG — giữ nguyên)
```
multitrans-render/
├── server.py           ← Backend Flask
├── requirements.txt    ← Thư viện Python
├── render.yaml         ← Config Render tự động
└── static/
    └── index.html      ← Giao diện web
```

---

## BƯỚC 1 — Tạo tài khoản GitHub (nếu chưa có)
→ https://github.com/signup
→ Đăng ký bằng email, miễn phí

---

## BƯỚC 2 — Tạo repo GitHub mới
1. Đăng nhập GitHub → click dấu "+" góc trên phải → "New repository"
2. Đặt tên: `multitrans` (hoặc tên bất kỳ)
3. Chọn **Public**
4. Click **"Create repository"**

---

## BƯỚC 3 — Upload file lên GitHub
Trên trang repo vừa tạo:
1. Click **"uploading an existing file"**
2. Kéo thả TẤT CẢ file trong thư mục `multitrans-render/` vào
   ⚠️ Kéo cả thư mục `static/` luôn
3. Kéo thả: `server.py`, `requirements.txt`, `render.yaml`, và thư mục `static/`
4. Click **"Commit changes"**

---

## BƯỚC 4 — Tạo tài khoản Render (không cần thẻ)
→ https://render.com
→ Click **"Get Started for Free"**
→ Đăng ký bằng GitHub (nhanh nhất) hoặc email

---

## BƯỚC 5 — Deploy lên Render
1. Đăng nhập Render → Dashboard
2. Click **"New +"** → chọn **"Web Service"**
3. Click **"Connect a repository"** → chọn repo `multitrans` vừa tạo
4. Điền thông tin:
   - **Name**: multitrans (tùy ý)
   - **Region**: Singapore (gần VN nhất)
   - **Branch**: main
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn server:app`
   - **Instance Type**: chọn **Free**
5. Click **"Create Web Service"**

---

## BƯỚC 6 — Chờ deploy (3-5 phút)
Render sẽ tự build. Khi xong hiện:
```
✅ Your service is live 🎉
```
URL của bạn sẽ là dạng:
```
https://multitrans-xxxx.onrender.com
```

---

## LƯU Ý free tier Render
- Server sẽ "ngủ" sau 15 phút không dùng
- Lần đầu truy cập sau khi ngủ sẽ chậm ~30 giây (đang wake up)
- Để tránh ngủ: dùng https://uptimerobot.com ping mỗi 10 phút (miễn phí)

---

## Cách dùng UptimeRobot (giữ server luôn online)
1. Vào https://uptimerobot.com → đăng ký miễn phí
2. Click "Add New Monitor"
3. Monitor Type: **HTTP(s)**
4. URL: `https://multitrans-xxxx.onrender.com/api/ping`
5. Monitoring Interval: **10 minutes**
6. Click "Create Monitor"
