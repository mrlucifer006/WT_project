# Developer Guide: Event Ticketing & Verification Architecture

## 1. Architecture Overview

```
Billing/
├── backend/                  # Python FastAPI application (Deploy to Render)
│   ├── app/
│   │   ├── config.py         # App configuration & environment variables
│   │   ├── main.py           # FastAPI endpoints, CORS, background tasks
│   │   └── services/
│   │       ├── crypto.py     # AES Token encryption & decryption
│   │       ├── csv_service.py# CSV transaction storage & stats calculation
│   │       ├── qr_generator.py # QR code image generation
│   │       └── whatsapp.py   # Neonize client, QR event capture, session cleanup
│   ├── requirements.txt      # Python dependencies
│   ├── run.py                # Local development entrypoint
│   └── transactions.csv      # Auto-generated CSV storage
├── frontend/                 # Static web application (Deploy to GitHub Pages)
│   ├── config.js             # Defines BACKEND_URL for API communication
│   ├── index.html            # Ticket booking form & WhatsApp login modal
│   ├── participants.html     # Live session monitoring dashboard
│   ├── health.html           # Server health & admin authentication
│   ├── data.html             # Revenue stats & CSV download dashboard
│   ├── scan_result.html      # QR scan verification & session launcher
│   └── static/               # Assets & styles
├── log/                      # Historical execution logs per workflow mandate
├── user_guide.md             # End-user and hosting setup guide
└── developer_guide.md        # Technical architectural documentation
```

---

## 2. Key Components & Services

### `backend/app/services/whatsapp.py`
- **Neonize Client**: Manages connection to WhatsApp Web protocols.
- **Event Listeners**:
  - `ConnectedEv`: Sets connection state and records `last_active` timestamp.
  - `QrEv`: Captures QR pairing string for the frontend.
  - `LoggedOutEv`: Deletes `my_session.sqlite3` and resets client.
  - `MessageEv`: Updates `last_active` timestamp.
- **Inactivity Deletion**: Evaluates delta between `datetime.now()` and `last_active`. If inactive for >48 hours, automatically triggers `logout()`, removing the sqlite3 session file.

### `backend/app/services/csv_service.py`
- Replaces Google Sheets API with local file-based append and query operations.
- Schema:
  `Timestamp`, `Name`, `Phone`, `Entry ID`, `Duration`, `Status`, `Entry Type`
- Thread-safe append and status updates.

### `backend/app/services/crypto.py`
- Generates 14-digit secure key and encrypts transaction payload into tamper-proof tokens embedded in participant QR codes.

---

## 3. API Surface

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/whatsapp/status` | `GET` | Returns `{ "connected": bool, "qr_ready": bool }` |
| `/api/whatsapp/qr` | `GET` | Returns `{ "qr_code": str }` for pairing |
| `/api/whatsapp/qr_image` | `GET` | Direct PNG image stream of WhatsApp pairing QR |
| `/api/whatsapp/logout` | `POST` | Disconnects and deletes session DB |
| `/api/csv/download` | `GET` | Streams `transactions.csv` to admin |
| `/submit_entry` | `POST` | Generates QR pass, logs to CSV, and sends WhatsApp message |
| `/verify` | `GET` | Decrypts and validates QR token against pending keys |
| `/start_timer` | `POST` | Starts active session countdown and WhatsApp notifications |
| `/api/sessions` | `GET` | Returns live active sessions for participants dashboard |
| `/api/stats` | `GET` | Returns attendance statistics (total, today, active) |
| `/api/health_stats` | `GET` | Returns server health and active session count |

---

## 4. Environment Variables Reference (Render / `.env`)

| Variable | Required? | Default | Description | Example |
| :--- | :---: | :--- | :--- | :--- |
| `ADMIN_PHONE` | **Recommended** | `""` | Phone number for receiving admin alerts, error notices, and hourly reports | `919342672711` |
| `ADMIN_USERNAME` | **Optional** | `"admin"` | Username to log into admin dashboard (`/health.html`, `/data.html`) | `admin` |
| `ADMIN_PASSWORD` | **Optional** | `"adminpassword"` | Password to log into admin dashboard | `SecretPass123` |
| `WHATSAPP_SESSION_NAME` | **Optional** | `"my_session"` | File prefix for SQLite session storage | `my_session` |
| `WARNING_BUFFER_MINUTES` | **Optional** | `5` | Minutes remaining in user session when warning message is sent | `5` |
| `MAX_RETRIES` | **Optional** | `3` | Maximum retry attempts for failed operations | `3` |
| `RETRY_DELAY_SECONDS` | **Optional** | `5` | Delay in seconds between retries | `5` |
| `SHEET_URL` | *Deprecated* | `""` | Left for legacy compatibility (system now uses local CSV) | - |

---

## 5. Local Development Setup

```bash
# 1. Start the Backend
cd backend
pip install -r requirements.txt
python run.py

# 2. Open the Frontend
# Open frontend/index.html in your browser or serve via live-server
```
