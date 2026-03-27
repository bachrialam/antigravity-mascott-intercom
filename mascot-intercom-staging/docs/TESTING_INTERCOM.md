# Cara mengetes integrasi Intercom

**Service URL (staging):** `https://onboarding-assistant-rgpdxuavmq-uc.a.run.app`  
**Webhook URL untuk Intercom:** `https://onboarding-assistant-rgpdxuavmq-uc.a.run.app/intercom/webhook`

Untuk environment lain, ganti dengan URL Cloud Run Anda.

---

## 1. Cek service hidup (health check)

```bash
curl -s "https://onboarding-assistant-rgpdxuavmq-uc.a.run.app/health"
```

Harus mengembalikan JSON dengan `"status": "healthy"`.

---

## 2. Tes endpoint webhook dengan payload contoh

Ini mensimulasikan webhook Intercom tanpa perlu kirim pesan asli dari Intercom.

```bash
curl -X POST "https://onboarding-assistant-rgpdxuavmq-uc.a.run.app/intercom/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "conversation.user.created",
    "data": {
      "item": {
        "conversation_message": {
          "body": "How do I create a new design?"
        }
      }
    }
  }'
```

- Respon yang benar: `{"ok": true}` dengan status HTTP 200.
- Untuk memastikan bot benar-benar jalan: lihat **Cloud Run logs** (langkah 4); harus ada log seperti "Intercom webhook: queued mascot core processing" atau "Intercom reply sent successfully".

---

## 3. Tes dari Intercom (real flow)

**Prasyarat:** Pastikan `INTERCOM_ADMIN_ID` sudah diset di environment variables (Secrets) agar bot bisa mengirim balasan.

1. Buka file `docs/test_intercom_widget.html` di browser Anda.
2. Kirim pesan di widget (mis. "What is Kittl?").
3. Tunggu beberapa detik, bot akan membalas langsung di widget.
4. Cek log jika tidak ada balasan.

---

## 4. Cek log di Cloud Run

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=onboarding-assistant" \
  --project=mascot-intercom-staging \
  --limit=30 \
  --format="table(timestamp,textPayload)"
```

Atau lewat Console:  
**Cloud Run → pilih service `onboarding-assistant` → tab Logs**.

Yang menandakan webhook diproses dan dibalas:

- `Intercom webhook: queued mascot core processing for conv ...`
- `Sending reply to Intercom conversation ...`
- `Intercom reply sent successfully to conversation ...`

Jika ada error (Weaviate, OpenAI, Intercom API) akan muncul di log yang sama.

---

## Ringkasan

| Tes              | Perintah / aksi                    | Harapan                          |
|------------------|------------------------------------|----------------------------------|
| Service hidup    | `curl .../health`                  | `"status": "healthy"`            |
| Webhook respond  | `curl -X POST .../intercom/webhook` dengan JSON di atas | `{"ok": true}`, 200 |
| Bot Membalas     | Kirim pesan di widget Intercom     | **Bot membalas di chat window**  |
