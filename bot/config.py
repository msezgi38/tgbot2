# =============================================================================
# Configuration for Press-1 IVR Bot 2 (Callix)
# =============================================================================

import os

# =============================================================================
# Telegram Bot Configuration
# =============================================================================
TELEGRAM_BOT_TOKEN = "8309805045:AAFhVcnCMGSEkdThOWu1tS09mVFKWivWz2c"

# =============================================================================
# Oxapay Payment Gateway Configuration
# =============================================================================
OXAPAY_API_KEY = "SPIWDL-YMIWY2-RSRZRO-QB9H59"
OXAPAY_API_URL = "https://api.oxapay.com/merchants/request"
OXAPAY_WEBHOOK_URL = "https://your-domain.com/webhook/oxapay2"  # ⚠️ UPDATE THIS

# Payment Configuration
CREDIT_PACKAGES = {
    "10": {"credits": 10, "price": 5.00, "currency": "USDT"},
    "50": {"credits": 50, "price": 20.00, "currency": "USDT"},
    "100": {"credits": 100, "price": 35.00, "currency": "USDT"},
    "500": {"credits": 500, "price": 150.00, "currency": "USDT"},
}

# =============================================================================
# MagnusBilling API Configuration
# =============================================================================
MAGNUS_API_KEY = "falnbfnzxrwvwgrnutcbprhjrwjehwme"
MAGNUS_API_SECRET = "chfxdcubbngpsrhnpmmebuuntpcxhwvc"
MAGNUS_SIP_HOST = "sip.callix.pro"
MAGNUS_API_URL = "https://callix.pro/mbilling/index.php/rest/"
MAGNUS_DB_PASSWORD = "zmHsVfTT3yiy8YQX"

# =============================================================================
# Database Configuration (SEPARATE from Bot 1)
# =============================================================================
DATABASE_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "ivr_bot2",                 # ← Different database name!
    "user": "postgres",
    "password": "ivr2026secure",
}

DATABASE_URL = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"

# =============================================================================
# Asterisk AMI Configuration (SHARED - same Asterisk)
# =============================================================================
AMI_CONFIG = {
    "host": "127.0.0.1",
    "port": 5038,
    "username": "ivr_bot",                  # Same AMI user (shared Asterisk)
    "secret": "IVRBotSecure2026",
}

# =============================================================================
# Asterisk Trunk Configuration - CALLIX
# =============================================================================
TRUNK_NAME = "callix_trunk"                  # ← Different trunk!
DEFAULT_CALLER_ID = "1234567890"
IVR_CONTEXT = "press-one-ivr-2"             # ← Different context!

# =============================================================================
# Webhook Server Configuration (DIFFERENT PORT from Bot 1)
# =============================================================================
WEBHOOK_HOST = "0.0.0.0"
WEBHOOK_PORT = 8001                          # ← Port 8001 (Bot 1 uses 8000)
WEBHOOK_URL = "http://localhost:8001"

# =============================================================================
# Billing Configuration
# =============================================================================
COST_PER_MINUTE = 1.0
MINIMUM_BILLABLE_SECONDS = 6
BILLING_INCREMENT_SECONDS = 6

# =============================================================================
# Campaign Configuration
# =============================================================================
MAX_CONCURRENT_CALLS = 10
CALL_TIMEOUT_SECONDS = 30
DTMF_TIMEOUT_SECONDS = 10
RETRY_FAILED_CALLS = False
DELAY_BETWEEN_CALLS = 2

# =============================================================================
# Logging Configuration
# =============================================================================
LOG_LEVEL = "INFO"
LOG_FILE = "bot2.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# Admin Configuration
# =============================================================================
ADMIN_TELEGRAM_IDS = [8500048750]            # Callix admin account

# =============================================================================
# Support Configuration
# =============================================================================
SUPPORT_TELEGRAM = "@callixcalvin"

# =============================================================================
# File Paths
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
