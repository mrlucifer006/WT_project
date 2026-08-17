import os
import threading
import time
import logging
from datetime import datetime, timedelta
from neonize.client import NewClient
from neonize.events import ConnectedEv, PairStatusEv, LoggedOutEv, MessageEv
from neonize.utils import log
from neonize.utils.jid import build_jid

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.config import settings

class WhatsAppService:
    def __init__(self, session_name: str = None):
        if session_name is None:
            session_name = settings.WHATSAPP_SESSION_NAME
        self.session_name = session_name
        self.db_path = session_name + ".sqlite3"
        self.qr_code = None
        self.last_active = datetime.now()
        self._lock = threading.Lock()
        self.thread = None
        self._running = False
        
        self._init_client()

    def _init_client(self):
        with self._lock:
            self.client = NewClient(self.db_path)
            
            # Setup event listeners
            @self.client.event(ConnectedEv)
            def on_connected(client, event: ConnectedEv):
                from app.config import log_debug
                log_debug("WhatsApp Connected")
                self.qr_code = None
                self.last_active = datetime.now()

            @self.client.event(PairStatusEv)
            def on_pair_status(client, event: PairStatusEv):
                from app.config import log_debug
                log_debug(f"Pair Status: {event}")
                self.last_active = datetime.now()
                
            @self.client.event.qr
            def on_qr(client, data_qr: bytes):
                from app.config import log_debug
                import segno
                # Only capture and display QR if not logged in
                if not self.is_logged_in:
                    log_debug(f"QR Code received via event.qr: {len(data_qr)} bytes")
                    try:
                        segno.make_qr(data_qr).terminal(compact=True)
                    except Exception:
                        pass
                    if isinstance(data_qr, bytes):
                        self.qr_code = data_qr.decode("utf-8", errors="ignore")
                    else:
                        self.qr_code = str(data_qr)
                else:
                    self.qr_code = None
                
            @self.client.event(LoggedOutEv)
            def on_logged_out(client, event: LoggedOutEv):
                from app.config import log_debug
                log_debug("Logged out event received from WhatsApp")
                self.qr_code = None
                
            @self.client.event(MessageEv)
            def on_message(client, event: MessageEv):
                self.last_active = datetime.now()

    @property
    def is_connected(self) -> bool:
        """True if the socket is actively connected."""
        try:
            if self.client:
                return bool(self.client.is_connected)
        except Exception:
            pass
        return False

    @property
    def is_logged_in(self) -> bool:
        """True if session database has authenticated credentials."""
        try:
            if self.client:
                return bool(self.client.is_logged_in)
        except Exception:
            pass
        return False

    def check_inactivity(self):
        """Check if inactive for > 2 days. If so, delete session."""
        delta = datetime.now() - self.last_active
        if delta.total_seconds() > 2 * 24 * 3600:
            logger.info("Inactive for > 2 days. Cleaning up session.")
            self.logout()

    def logout(self):
        """Explicitly disconnect and delete session DB."""
        try:
            if self.client:
                self.client.disconnect()
        except Exception:
            pass
        self.qr_code = None
        
        # Remove sqlite db and WAL/SHM files
        for ext in ["", "-wal", "-shm"]:
            fpath = self.db_path + ext
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    logger.info(f"Deleted {fpath}")
                except Exception as e:
                    logger.error(f"Failed to delete {fpath}: {e}")
        
        self._init_client()

    def start(self):
        """Starts the neonize connection loop in a single background thread."""
        if self.thread is not None and self.thread.is_alive():
            return
            
        self._running = True

        def run_client():
            from app.config import log_debug
            log_debug("Starting WhatsApp Client Thread...")
            
            while self._running:
                try:
                    self.check_inactivity()
                    log_debug("Connecting to WhatsApp...")
                    self.client.connect()
                except Exception as e:
                    log_debug(f"WhatsApp connect ended/error: {e}. Reconnecting in 3s...")
                
                # Check if session is authenticated
                if self.is_logged_in:
                    self.qr_code = None
                    
                time.sleep(3)

        self.thread = threading.Thread(target=run_client, name="WhatsAppWorker", daemon=True)
        self.thread.start()
        
    def ensure_connection(self):
        """Waits briefly for connection if logged in."""
        if self.is_connected or self.is_logged_in:
            self.last_active = datetime.now()
            return True
            
        from app.config import log_debug
        log_debug("Waiting for WhatsApp connection...")
        
        for _ in range(20):
            if self.is_connected or self.is_logged_in:
                log_debug("WhatsApp connected.")
                self.last_active = datetime.now()
                return True
            time.sleep(0.5)
            
        return False

    def send_image(self, phone_number: str, image_path: str, caption: str = ""):
        from app.config import log_debug
        
        phone_number = phone_number.strip().replace("+", "").replace(" ", "").replace("-", "")
        if len(phone_number) == 10:
            phone_number = "91" + phone_number
            
        try:
            jid = build_jid(phone_number, "s.whatsapp.net")
        except Exception as e:
            log_debug(f"ERROR: Failed to build JID: {e}")
            return False

        try:
            if not os.path.exists(image_path):
                log_debug(f"ERROR: Image file not found at {image_path}")
                return False

            self.client.send_image(
                to=jid,
                file=image_path,
                caption=caption
            )
            self.last_active = datetime.now()
            log_debug(f"Successfully sent image pass to {phone_number}")
            return True
        except Exception as e:
            log_debug(f"Failed to send image to {phone_number}: {e}")
            return False

    def send_message(self, phone_number: str, message: str):
        from app.config import log_debug
        
        phone_number = phone_number.strip().replace("+", "").replace(" ", "").replace("-", "")
        if len(phone_number) == 10:
            phone_number = "91" + phone_number

        try:
            from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message
            jid = build_jid(phone_number, "s.whatsapp.net")
            msg = Message(conversation=message)
            self.client.send_message(
                to=jid,
                message=msg
            )
            self.last_active = datetime.now()
            logger.info(f"Sent message to {phone_number}: {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

# Global instance
whatsapp_service = WhatsAppService()
