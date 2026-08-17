from fastapi import FastAPI, BackgroundTasks, Request, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import os
import shutil
import socket
import json
import asyncio
from datetime import datetime, timedelta

from app.services.csv_service import csv_service
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.services.qr_generator import QRGenerator
from app.services.whatsapp import whatsapp_service
from app.services.crypto import crypto_service
from app.config import settings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files safely
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

os.makedirs("generated_qrs", exist_ok=True)
app.mount("/generated_qrs", StaticFiles(directory="generated_qrs"), name="generated_qrs")



# Initialize services
qr_generator = QRGenerator()


def get_local_ip():
    try:
        # Connect to a public DNS to determine local IP used for routing
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

# Global state for active sessions
active_sessions = {}
SESSION_FILE = "sessions.json"
STATE_FILE = "server_state.json"

def save_sessions():
    """Saves active sessions to JSON file."""
    try:
        data = {}
        for tid, session in active_sessions.items():
            data[tid] = {
                "name": session["name"],
                "phone": session["phone"],
                "transaction_id": session["transaction_id"],
                "duration": session["duration"],
                "start_time": session["start_time"].isoformat(),
                "end_time": session["end_time"].isoformat(),
                "restore_key": session.get("restore_key") # Save restore key
            }
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print("Sessions saved to disk.")
    except Exception as e:
        print(f"Failed to save sessions: {e}")

def load_sessions():
    """Loads sessions from JSON file."""
    global active_sessions
    try:
        import os
        if not os.path.exists(SESSION_FILE):
            return

        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
            
        for tid, session in data.items():
            active_sessions[tid] = {
                "name": session["name"],
                "phone": session["phone"],
                "transaction_id": session["transaction_id"],
                "duration": session["duration"],
                "start_time": datetime.fromisoformat(session["start_time"]),
                "end_time": datetime.fromisoformat(session["end_time"]),
                "restore_key": session.get("restore_key") # Load restore key
            }
        print(f"Loaded {len(active_sessions)} sessions from disk.")
    except Exception as e:
        print(f"Failed to load sessions: {e}")

def load_server_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading server state: {e}")
    return {}

def save_server_state(data):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving server state: {e}")

@app.on_event("startup")
async def startup_event():
    global active_sessions
    # Start WhatsApp service
    whatsapp_service.start()
    
    # Initialize CSV Service
    print("CSV Attendance Service active.")

    load_sessions()
    
    # Cleanup expired sessions
    now = datetime.now()
    initial_count = len(active_sessions)
    active_sessions = {
        tid: session 
        for tid, session in active_sessions.items() 
        if session["end_time"] > now
    }
    
    if len(active_sessions) < initial_count:
        print(f"Cleaned up {initial_count - len(active_sessions)} expired sessions on startup.")
        save_sessions()

    # Start Hourly Stats Task
    asyncio.create_task(hourly_stats_task())
    
    # Restore timers for active sessions
    now = datetime.now()
    for tid, session in active_sessions.items():
        # Check buffer time again just in case, but main check is done above
        if session["end_time"] > now:
            remaining_seconds = (session["end_time"] - now).total_seconds()
            remaining_minutes = remaining_seconds / 60
            print(f"Restoring timer for {session['name']} ({remaining_minutes:.2f} mins left)")
            asyncio.create_task(session_timer_task(session["phone"], session["duration"], tid, is_resume=True, resume_seconds=remaining_seconds))


@app.get("/api/whatsapp/status")
async def get_wa_status():
    return {"connected": whatsapp_service.is_connected, "qr_ready": whatsapp_service.qr_code is not None}

@app.get("/api/whatsapp/qr")
async def get_wa_qr():
    if whatsapp_service.qr_code:
        return {"qr_code": whatsapp_service.qr_code}
    return JSONResponse(status_code=404, content={"message": "QR not ready"})

@app.get("/api/whatsapp/qr_image")
async def get_wa_qr_image():
    if whatsapp_service.qr_code:
        import io
        import qrcode
        from fastapi.responses import Response
        
        img = qrcode.make(whatsapp_service.qr_code)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")
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

def render_scan_html(status: str, name: str = "", phone: str = "", transaction_id: str = "", duration: int = 15, plan: str = "General Entry", message: str = "") -> str:
    if status == "success":
        content = f"""
        <div class="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <span class="material-icons text-3xl">check_circle</span>
        </div>
        <h1 class="text-2xl font-bold text-slate-900 mb-1">Verified Successfully</h1>
        <p class="text-slate-500 text-xs mb-6">Entry pass is valid and registered.</p>
        <div class="bg-slate-50 rounded-xl p-4 text-left border border-slate-200 space-y-2.5 text-xs">
            <div class="flex justify-between"><span class="font-medium text-slate-500">Attendee</span><span class="font-bold text-slate-900">{name}</span></div>
            <div class="flex justify-between"><span class="font-medium text-slate-500">Phone</span><span class="font-mono text-slate-700">{phone}</span></div>
            <div class="flex justify-between"><span class="font-medium text-slate-500">Pass Type</span><span class="font-bold text-slate-900">{plan}</span></div>
            <div class="flex justify-between"><span class="font-medium text-slate-500">Duration</span><span class="font-bold text-indigo-600">{duration} Mins</span></div>
            <div class="pt-2 border-t border-slate-200 flex justify-between"><span class="font-medium text-slate-500">Entry ID</span><span class="font-mono text-slate-600">{transaction_id}</span></div>
        </div>
        <form id="startTimerForm" class="mt-6">
            <input type="hidden" name="name" value="{name}">
            <input type="hidden" name="phone" value="{phone}">
            <input type="hidden" name="transaction_id" value="{transaction_id}">
            <input type="hidden" name="duration" value="{duration}">
            <button type="submit" id="startTimerBtn" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl shadow-md transition-all flex items-center justify-center text-sm">
                <span class="material-icons text-sm mr-2">timer</span> Start {duration} Min Session
            </button>
        </form>
        <div id="timerMessage" class="hidden mt-3 text-xs font-medium"></div>
        <script>
            document.getElementById('startTimerForm').addEventListener('submit', async (e) => {{
                e.preventDefault();
                const btn = document.getElementById('startTimerBtn');
                const msg = document.getElementById('timerMessage');
                const formData = new FormData(e.target);
                btn.disabled = true;
                btn.innerHTML = '<span class="material-icons text-sm mr-2 animate-spin">refresh</span> Starting...';
                try {{
                    const res = await fetch('/start_timer', {{ method: 'POST', body: formData }});
                    const data = await res.json();
                    if (res.ok) {{
                        msg.className = 'mt-3 p-3 bg-emerald-50 text-emerald-700 rounded-xl text-xs font-medium border border-emerald-100 flex items-center justify-center';
                        msg.innerHTML = '<span class="material-icons text-sm mr-1.5">alarm_on</span> Session started! Notifications active.';
                        msg.classList.remove('hidden');
                        btn.classList.add('hidden');
                    }} else {{
                        msg.className = 'mt-3 p-3 bg-red-50 text-red-700 rounded-xl text-xs font-medium border border-red-100';
                        msg.textContent = data.message || 'Failed to start session';
                        msg.classList.remove('hidden');
                        btn.disabled = false;
                    }}
                }} catch(err) {{
                    msg.className = 'mt-3 p-3 bg-red-50 text-red-700 rounded-xl text-xs font-medium border border-red-100';
                    msg.textContent = 'Network error: ' + err.message;
                    msg.classList.remove('hidden');
                    btn.disabled = false;
                }}
            }});
        </script>
        """
    elif status == "check_restore":
        content = f"""
        <div class="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <span class="material-icons text-3xl">restore</span>
        </div>
        <h1 class="text-2xl font-bold text-slate-900 mb-1">Session In Progress</h1>
        <p class="text-slate-500 text-xs mb-6">Attendee: <strong>{name}</strong> ({plan} - {duration}m)</p>
        <p class="text-xs text-slate-600 mb-6">This entry is currently active in the venue.</p>
        <a href="/" class="inline-block bg-slate-900 hover:bg-slate-800 text-white font-semibold py-2.5 px-6 rounded-xl text-xs transition-colors">
            Back to Dashboard
        </a>
        """
    else:
        content = f"""
        <div class="w-16 h-16 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4">
            <span class="material-icons text-3xl">cancel</span>
        </div>
        <h1 class="text-2xl font-bold text-slate-900 mb-1">Verification Failed</h1>
        <p class="text-slate-500 text-xs mb-6">{message or "Invalid or expired QR code"}</p>
        <a href="/" class="inline-block bg-slate-900 hover:bg-slate-800 text-white font-semibold py-2.5 px-6 rounded-xl text-xs transition-colors">
            Back to Dashboard
        </a>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pass Verification</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>body {{ font-family: 'Inter', sans-serif; }}</style>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen flex items-center justify-center p-4">
    <div class="max-w-md w-full bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-200 p-8 text-center">
        {content}
    </div>
</body>
</html>"""

@app.get("/")
async def read_root():
    return {
        "status": "online",
        "service": "Event Pass Verification API",
        "version": "1.0.0"
    }

@app.post("/submit_entry")
async def submit_entry(
    background_tasks: BackgroundTasks, 
    name: str = Form(...),
    phone: str = Form(...),
    entry_type: str = Form("General Entry"),
    duration: int = Form(15)
):
    """
    Endpoint to trigger individual entry pass processing.
    """
    import random
    timestamp_part = datetime.now().strftime("%Y%m%d-%H%M%S")
    random_part = str(random.randint(100, 999))
    transaction_id = f"ENTRY-{timestamp_part}-{random_part}"

    background_tasks.add_task(process_entry_task, name, phone, transaction_id, entry_type, duration)
    return {"status": "Processing started", "message": "Entry pass generation initiated", "entry_id": transaction_id}

@app.get("/verify", response_class=HTMLResponse)
async def verify_entry(request: Request, token: str):
    """
    Verifies entry based on encrypted token and secure key.
    """
    try:
        # Decrypt Token
        try:
            data = crypto_service.decrypt(token)
            transaction_id = data.get("transaction_id")
            name = data.get("name")
            phone = data.get("phone")
            duration = data.get("duration", 15)
            plan = data.get("plan", "General Entry")
            secure_key = data.get("secure_key")
        except Exception:
            return HTMLResponse(content=render_scan_html("error", message="Invalid or Tampered QR Code"), status_code=400)

        # Validate Security Key
        # 1. Check if ACTIVE SESSION exists
        if transaction_id in active_sessions:
            return HTMLResponse(content=render_scan_html("check_restore", name=name, phone=phone, transaction_id=transaction_id, duration=duration, plan=plan))

        # 2. Validate Security Key (Pending Session)
        if transaction_id not in pending_keys:
            current_status = csv_service.get_entry_status(transaction_id)
            if current_status and current_status.strip().lower() == "in":
                return HTMLResponse(content=render_scan_html("error", message="Entry ALREADY processed/used."), status_code=400)
            else:
                return HTMLResponse(content=render_scan_html("error", message="Invalid QR Code: Entry not found or expired."), status_code=404)
        
        if pending_keys[transaction_id] != secure_key:
            return HTMLResponse(content=render_scan_html("error", message="Security Check Failed: Invalid Key."), status_code=403)

        # Update CSV status
        csv_service.update_entry_status(transaction_id, "In")
        
        # Send WhatsApp Message
        msg = f"Welcome {name}! Your entry is confirmed. Please proceed to the check-in desk for your {duration} mins session."
        whatsapp_service.send_message(phone, msg)
        
        return HTMLResponse(content=render_scan_html("success", name=name, phone=phone, transaction_id=transaction_id, duration=duration, plan=plan))
        
    except Exception as e:
        print(f"Verification Failed: {e}")
        return HTMLResponse(content=render_scan_html("error", message="Verification Processing Failed"), status_code=500)

# Global state for pending keys (Security)
PENDING_KEYS_FILE = "pending_keys.json"
pending_keys = {}

def load_pending_keys():
    """Loads pending keys from JSON file."""
    global pending_keys
    try:
        if os.path.exists(PENDING_KEYS_FILE):
            with open(PENDING_KEYS_FILE, "r") as f:
                pending_keys = json.load(f)
        print(f"Loaded {len(pending_keys)} pending keys.")
    except Exception as e:
        print(f"Failed to load pending keys: {e}")

def save_pending_keys():
    """Saves pending keys to JSON file."""
    try:
        with open(PENDING_KEYS_FILE, "w") as f:
            json.dump(pending_keys, f, indent=4)
    except Exception as e:
        print(f"Failed to save pending keys: {e}")

# Load keys on startup
load_pending_keys()

def process_entry_task(name: str, phone: str, transaction_id: str, entry_type: str = "General Entry", duration: int = 15):
    from app.config import log_debug
    import secrets
    log_debug(f"Starting entry task for: {name}, {phone}, {transaction_id}, {entry_type}, {duration}m")
    
    # 1. Clean Phone
    phone = phone.replace(" ", "").replace("-", "").replace("+", "")
    
    # 2. Generate 14-digit Secure Key
    secure_key = str(secrets.randbelow(10**14)).zfill(14)
    
    # Store key
    pending_keys[transaction_id] = secure_key
    save_pending_keys()
    
    # 3. Generate QR Data (Encrypted Token with Key)
    data = {
        "transaction_id": transaction_id,
        "name": name,
        "phone": phone,
        "duration": duration,
        "plan": entry_type,
        "secure_key": secure_key
    }
    
    try:
        token = crypto_service.encrypt(data)
        
        # Build URL
        base_url = os.environ.get("RENDER_EXTERNAL_URL", f"http://{get_local_ip()}:5000")
        qr_data = f"{base_url}/verify?token={token}"
        log_debug(f"QR Content: {qr_data}")
        
    except Exception as e:
        log_debug(f"Encryption failed: {e}")
        return
    
    # 4. Generate QR Image
    try:
        qr_path = qr_generator.generate_qr(qr_data)
        log_debug(f"Generated QR at {qr_path}")
    except Exception as e:
        log_debug(f"QR Generation failed: {e}")
        return

    # 5. Save to CSV
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Order: Timestamp, Name, Phone, Entry ID, Duration, Status, Entry Type
        row_data = [timestamp, name, phone, transaction_id, duration, "Pending", entry_type]
        csv_service.append_data(row_data)
    except Exception as e:
        log_debug(f"Failed to save to CSV: {e}")

    # 6. Send Message via WhatsApp
    caption = f"Hello {name}, your entry pass ({transaction_id}) for {entry_type} ({duration} mins) is confirmed. Here is your unique QR pass."
    
    try:
        log_debug(f"Attempting to send QR to {phone}")
        success = whatsapp_service.send_image(phone, qr_path, caption)
        if success:
            log_debug(f"Sent QR to {name} ({phone})")
        else:
            log_debug(f"Failed to send QR to {name} ({phone})")
    except Exception as e:
        log_debug(f"Error sending WhatsApp message: {e}")

async def hourly_stats_task():
    """Background task to send hourly statistics (Persistent)."""
    print("Starting Hourly Stats Task...")
    
    while True:
        try:
            state = load_server_state()
            last_report_str = state.get("last_hourly_report")
            
            now = datetime.now()
            
            if last_report_str:
                last_report_time = datetime.fromisoformat(last_report_str)
                next_report_time = last_report_time + timedelta(hours=1)
                wait_seconds = (next_report_time - now).total_seconds()
            else:
                last_report_time = now
                save_server_state({"last_hourly_report": now.isoformat()})
                wait_seconds = 3600
            
            print(f"Hourly Stats: Last run {last_report_time}, Next run in {wait_seconds:.2f}s")
            
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            
            # --- Perform Task ---
            stats = csv_service.get_stats_for_today()
            
            msg = (
                f"Hourly Report\n"
                f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
                f"Total Entries: {stats['count']}"
            )
            
            print(f"Sending Hourly Report: {msg}")
            whatsapp_service.send_message(settings.ADMIN_PHONE, msg)
            
            # --- Update State ---
            new_now = datetime.now()
            save_server_state({"last_hourly_report": new_now.isoformat()})
            
            await asyncio.sleep(1) 
            
        except Exception as e:
            print(f"Error in hourly stats task: {e}")
            await asyncio.sleep(60)
            
            print(f"Sending Hourly Report: {msg}")
            whatsapp_service.send_message(settings.ADMIN_PHONE, msg)
            
            # --- Update State ---
            new_now = datetime.now()
            save_server_state({"last_hourly_report": new_now.isoformat()})
            
            await asyncio.sleep(1) 
            
        except Exception as e:
            print(f"Error in hourly stats task: {e}")
            await asyncio.sleep(60)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = f"Server Error\nPath: {request.url.path}\nError: {str(exc)}"
    print(error_msg)
    
    try:
        whatsapp_service.send_message(settings.ADMIN_PHONE, error_msg)
    except Exception as e:
        print(f"Failed to send error alert: {e}")
        
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "details": str(exc)},
    )

@app.post("/start_timer")
async def start_timer(
    background_tasks: BackgroundTasks,
    phone: str = Form(...),
    duration: str = Form(...),
    name: str = Form(None),
    transaction_id: str = Form(None)
):
    print(f"DEBUG START TIMER: phone={phone}, duration={duration}, name={name}, tid={transaction_id}")
    
    if not name or not transaction_id:
        return JSONResponse(status_code=400, content={"status": "Error", "message": "Missing name or transaction_id"})

    try:
        duration_int = int(duration)
    except ValueError:
        duration_int = 15 

    # Store session info
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=duration_int)
    
    active_sessions[transaction_id] = {
        "name": name,
        "phone": phone,
        "transaction_id": transaction_id,
        "duration": duration_int,
        "start_time": start_time,
        "end_time": end_time
    }
    
    save_sessions()

    # Remove Secure Key (Now it is truly used)
    if transaction_id in pending_keys:
        del pending_keys[transaction_id]
        save_pending_keys()

    # Generate Restore Key
    import secrets
    restore_key = secrets.token_urlsafe(12) # approx 16 chars
    active_sessions[transaction_id]["restore_key"] = restore_key
    save_sessions()

    background_tasks.add_task(session_timer_task, phone, duration_int, transaction_id)
    return {
        "status": "Timer started",
        "end_time": end_time.isoformat(),
        "duration": duration_int,
        "restore_key": restore_key
    }

@app.post("/api/verify_restore")
async def verify_restore(request: Request):
    """
    Verifies a restore key for an active session.
    """
    try:
        data = await request.json()
        transaction_id = data.get("transaction_id")
        restore_key = data.get("restore_key")
        
        if transaction_id in active_sessions:
            session = active_sessions[transaction_id]
            if session.get("restore_key") == restore_key:
                return {
                    "status": "restored",
                    "end_time": session["end_time"].isoformat(),
                    "duration": session["duration"],
                    "start_time": session["start_time"].isoformat()
                }
        
        return JSONResponse(status_code=403, content={"status": "error", "message": "Invalid Restore Key or Session Ended"})
        
    except Exception as e:
        print(f"Restore verification failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": "Server Error"})

@app.get("/participants")
async def view_participants():
    return {"message": "Use frontend/participants.html or /api/sessions"}

@app.get("/health")
async def view_health():
    return {
        "status": "healthy",
        "active_sessions": len(active_sessions),
        "whatsapp_connected": whatsapp_service.is_connected
    }

@app.post("/health/login")
async def health_login(username: str = Form(...), password: str = Form(...)):
    if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
        return {"status": "authenticated"}
    else:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Invalid Credentials"})

@app.get("/data")
async def view_data():
    return {"message": "Use frontend/data.html or /api/csv/download"}

@app.get("/api/health_stats")
async def get_health_stats():
    return {
        "active_sessions": len(active_sessions),
        "server_time": datetime.now().isoformat()
    }

@app.get("/api/stats")
async def get_stats():
    daily = csv_service.get_stats_for_today()
    total = csv_service.get_total_stats()
    return {
        "total_entries": total.get("count", 0),
        "today_entries": daily.get("count", 0),
        "active_sessions": len(active_sessions)
    }

@app.get("/api/sessions")
async def get_sessions():
    now = datetime.now()
    sessions_list = []
    
    for tid, session in active_sessions.items():
        remaining = (session["end_time"] - now).total_seconds()
        status = "Active"
        if remaining <= 0:
            remaining = 0
            status = "Ended"
        elif remaining <= (settings.WARNING_BUFFER_MINUTES * 60):
            status = "Warning"
            
        sessions_list.append({
            "name": session["name"],
            "phone": session["phone"],
            "transaction_id": session["transaction_id"],
            "duration": session["duration"],
            "start_time": session["start_time"].strftime("%H:%M:%S"),
            "end_time": session["end_time"].strftime("%H:%M:%S"),
            "remaining_seconds": int(remaining),
            "status": status
        })
        
    return sessions_list

async def session_timer_task(phone: str, duration: int, transaction_id: str, is_resume: bool = False, resume_seconds: float = None):
    from app.config import log_debug
    # Global variables for session management
    global active_sessions
    
    loop = asyncio.get_event_loop()
    
    try:
        log_debug(f"Timer task START: {phone}, {duration}m, resume={is_resume}, remaining={resume_seconds}")
        
        if not is_resume:
            try:
                msg = f"Your {duration} minutes session has STARTED now. Have fun!"
                log_debug(f"Sending start msg to {phone}")
                # Use executor to avoid blocking async loop since send_message might sleep/wait
                await loop.run_in_executor(None, whatsapp_service.send_message, phone, msg)
                log_debug(f"Start msg sent to {phone}")
            except Exception as e:
                log_debug(f"Failed to send start message: {e}")
        
        warning_buffer_mins = settings.WARNING_BUFFER_MINUTES
        total_seconds = duration * 60
        warning_time_seconds = (duration - warning_buffer_mins) * 60
        
        # Calculate how much time to sleep until warning
        if is_resume and resume_seconds is not None:
             # We are resuming.
             # Time already elapsed = Total - Remaining
             elapsed = total_seconds - resume_seconds
             
             # Time until warning triggers
             sleep_until_warning = warning_time_seconds - elapsed
        else:
             sleep_until_warning = warning_time_seconds

        # 1. Sleep until Warning Time
        if sleep_until_warning > 0:
            log_debug(f"Sleeping {sleep_until_warning}s until warning for {phone}")
            await asyncio.sleep(sleep_until_warning)
            
            # Send Warning
            try:
                msg = f"Warning: You have {warning_buffer_mins} minutes remaining in your session."
                log_debug(f"Sending warning to {phone}")
                await loop.run_in_executor(None, whatsapp_service.send_message, phone, msg)
                log_debug(f"Sent warning to {phone}")
            except Exception as e:
                log_debug(f"Failed to send warning: {e}")
                
            # Sleep remaining buffer time
            remaining_after_warning = total_seconds - warning_time_seconds # Should be buffer * 60
            log_debug(f"Sleeping remaining {remaining_after_warning}s after warning for {phone}")
            await asyncio.sleep(remaining_after_warning)
            
        else:
            # We are PAST the warning time (or warning time is 0/negative)
            # Just sleep the remaining duration
            remaining = resume_seconds if (is_resume and resume_seconds is not None) else total_seconds
            
            if remaining > 0:
                log_debug(f"Past warning time. Sleeping remaining {remaining}s for {phone}")
                await asyncio.sleep(remaining)

    except asyncio.CancelledError:
        log_debug(f"Timer task cancelled for {transaction_id}")
        raise
    except Exception as e:
        log_debug(f"CRITICAL ERROR in session_timer_task: {e}")
        
    # Time Ended - Cleanup
    try:
        msg = f"Your session time of {duration} minutes has ended. Please proceed to exit."
        await loop.run_in_executor(None, whatsapp_service.send_message, phone, msg)
        log_debug(f"Sent ended message to {phone}")
        
        # Remove from active sessions
        if transaction_id in active_sessions:
            del active_sessions[transaction_id]
            save_sessions()
            log_debug(f"Session {transaction_id} expired and removed.")
            
    except Exception as e:
        log_debug(f"Failed to send ended message: {e}")
