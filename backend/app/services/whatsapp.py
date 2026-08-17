import os
import threading
import time
import logging
from datetime import datetime
from neonize.client import NewClient
from neonize.events import ConnectedEv, PairStatusEv, QREv, Event, LoggedOutEv, MessageEv
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
        self.is_connected = False
        self.qr_code = None
        self.last_active = datetime.now()
        
        self._init_client()

    def _init_client(self):
        self.client = NewClient(self.db_path)
        
        # Setup event listeners
        @self.client.event(ConnectedEv)
        def on_connected(client, event: ConnectedEv):
            from app.config import log_debug
            log_debug("WhatsApp Connected")
            self.is_connected = True
            self.qr_code = None
            self.last_active = datetime.now()

        @self.client.event(PairStatusEv)
        def on_pair_status(client, event: PairStatusEv):
            from app.config import log_debug
            log_debug(f"Pair Status: {event}")
            
        @self.client.event.qr
        def on_qr(client, data_qr: bytes):
            from app.config import log_debug
            import segno
            log_debug(f"QR Code received via event.qr: {len(data_qr)} bytes")
            try:
                segno.make_qr(data_qr).terminal(compact=True)
            except Exception:
                pass
            if isinstance(data_qr, bytes):
                self.qr_code = data_qr.decode("utf-8", errors="ignore")
            else:
                self.qr_code = str(data_qr)
            
        @self.client.event(LoggedOutEv)
        def on_logged_out(client, event: LoggedOutEv):
            from app.config import log_debug
            log_debug("Logged out from WhatsApp")
            self.is_connected = False
            self.logout()
            
        @self.client.event(MessageEv)
        def on_message(client, event: MessageEv):
            self.last_active = datetime.now()

    def check_inactivity(self):
        """Check if inactive for 2 days. If so, logout."""
        delta = datetime.now() - self.last_active
        if delta.total_seconds() > 2 * 24 * 3600:
            logging.info("Inactive for > 2 days. Deleting session.")
            self.logout()

    def logout(self):
        """Force logout and delete session DB."""
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.is_connected = False
        self.qr_code = None
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                logging.info(f"Deleted {self.db_path}")
            except Exception as e:
                logging.error(f"Failed to delete DB: {e}")
        # Re-initialize client to get new QR
        self._init_client()
        self.start()

    def start(self):
        """Starts the neonize client in a separate thread."""
        def run_client():
            from app.config import log_debug
            log_debug("Starting WhatsApp Client Thread...")
            
            while True:
                try:
                    self.check_inactivity()
                    self.client.connect()
                except Exception as e:
                    log_debug(f"WhatsApp client disconnected/error: {e}. Reconnecting in 5s...")
                    self.is_connected = False
                    time.sleep(5)

        if hasattr(self, 'thread') and self.thread.is_alive():
            return
            
        self.thread = threading.Thread(target=run_client, daemon=True)
        self.thread.start()
        
    def ensure_connection(self):
        """Waits for connection with timeout."""
        if self.is_connected:
            self.last_active = datetime.now()
            return True
            
        from app.config import log_debug
        log_debug("Waiting for WhatsApp connection...")
        
        for _ in range(30):
            if self.is_connected:
                log_debug("WhatsApp connected successfully.")
                self.last_active = datetime.now()
                return True
            time.sleep(0.5)
            
        if not self.thread.is_alive():
            log_debug("Thread died, restarting...")
            self.start()
            
        return False

    def send_image(self, phone_number: str, image_path: str, caption: str = ""):
        from app.config import log_debug
        
        if not self.ensure_connection():
            log_debug("WhatsApp client not connected. Attempting to send anyway, might fail or queue.")

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
            return True
        except Exception as e:
            log_debug(f"Failed to send image: {e}")
            return False

    def send_message(self, phone_number: str, message: str):
        from app.config import log_debug
        
        if not self.ensure_connection():
            log_debug("WhatsApp client not connected. Attempting to send anyway.")

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
