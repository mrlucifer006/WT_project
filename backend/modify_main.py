import re

with open('backend/app/main.py', 'r') as f:
    content = f.read()

# 1. Imports
content = content.replace(
    'from app.services.google_sheets import GoogleSheetService',
    'from app.services.csv_service import csv_service\nfrom fastapi.middleware.cors import CORSMiddleware\nfrom fastapi.responses import FileResponse'
)

# 2. CORS and Setup
content = content.replace(
    'app = FastAPI()',
    'app = FastAPI()\n\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=["*"],\n    allow_credentials=True,\n    allow_methods=["*"],\n    allow_headers=["*"],\n)'
)

# 3. Remove templates
content = content.replace('templates = Jinja2Templates(directory="templates")', '')
content = content.replace('google_sheet_service = GoogleSheetService()', '')

# 4. Fix Google Sheets references
content = content.replace('google_sheet_service', 'csv_service')
content = content.replace('settings.SHEET_URL, ', '')
content = content.replace('settings.SHEET_URL', '""') # where used without comma

# 5. Add new endpoints for WA and CSV
new_endpoints = """
@app.get("/api/whatsapp/status")
async def get_wa_status():
    return {"connected": whatsapp_service.is_connected, "qr_ready": whatsapp_service.qr_code is not None}

@app.get("/api/whatsapp/qr")
async def get_wa_qr():
    if whatsapp_service.qr_code:
        return {"qr_code": whatsapp_service.qr_code}
    return JSONResponse(status_code=404, content={"message": "QR not ready"})

@app.get("/api/csv/download")
async def download_csv():
    file_path = "transactions.csv"
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename="transactions.csv", media_type="text/csv")
    return JSONResponse(status_code=404, content={"message": "CSV not found"})

@app.post("/api/whatsapp/logout")
async def wa_logout():
    whatsapp_service.logout()
    return {"status": "logged out"}
"""

content = content.replace('@app.get("/", response_class=HTMLResponse)', new_endpoints + '\n@app.get("/", response_class=HTMLResponse)')

# Change all TemplateResponse to JSONResponse where needed
# But since this is a big file, we can just let it be or replace it.
# The plan is to change the endpoints to return JSON.

with open('backend/app/main.py', 'w') as f:
    f.write(content)
