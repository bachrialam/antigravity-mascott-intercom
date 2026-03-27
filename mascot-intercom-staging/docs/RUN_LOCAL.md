# Menjalankan aplikasi (Intercom) di lokal

Tidak ada frontend terpisah di project ini. Yang bisa dijalankan di lokal adalah **API server** + **dokumentasi interaktif (Swagger UI)** di browser.

---

## 1. Persiapan

- Python 3.11+
- File `.env` di **root project** (samping `deploy.sh`) dengan variabel:
  - `OPENAI_API_KEY_DATA_BOT`
  - `WEAVIATE_URL`
  - `WEAVIATE_API_KEY`
  - `INTERCOM_TOKEN`
  - `INTERCOM_ADMIN_ID`

---

## 2. Jalankan server

Dari **root project** (`mascot-intercom-staging`):

```bash
cd /Users/fauzulbachrienuralief/mascot-intercom-staging
pip install -r requirements.txt
python -m src.integrations.intercom.app
```

Server akan listen di **http://localhost:8080** (atau nilai `PORT` di `.env`).

---

## 3. Buka UI di browser

| URL | Isi |
|-----|-----|
| **http://localhost:8080/docs** | Swagger UI – tes endpoint (GET /health, POST /intercom/webhook, dll.) |
| **http://localhost:8080/redoc** | ReDoc – dokumentasi API |
| **http://localhost:8080/** | Info service + daftar endpoint |
| **http://localhost:8080/health** | Health check |

Gunakan **Swagger UI** (`/docs`) untuk mencoba **POST /intercom/webhook** dengan payload JSON dari halaman tersebut.

---

## 4. (Opsional) Port atau host lain

```bash
PORT=3000 python -m src.integrations.intercom.app
```

Lalu buka: **http://localhost:3000/docs**
