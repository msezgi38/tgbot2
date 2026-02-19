# =============================================================================
# Configuration for Press-1 IVR Bot 5 (VoipZone)
# =============================================================================

import os

# =============================================================================
# Telegram Bot Configuration
# =============================================================================
TELEGRAM_BOT_TOKEN = "8598123893:AAFr6t93yJ9mMJdkFBgF8vfBb8lkF-u8rNU"

# =============================================================================
# Oxapay Payment Gateway Configuration
# =============================================================================
OXAPAY_API_KEY = "HDKDIN-KVJZXE-SHVATN-D3B9US"
OXAPAY_API_URL = "https://api.oxapay.com/v1/payment/invoice"
OXAPAY_WEBHOOK_URL = "http://195.85.114.55:8004/webhook/oxapay"

# Payment Configuration
MIN_TOPUP_AMOUNT = 50  # Minimum $50 USDT top-up
DEFAULT_CURRENCY = "USDT"
MONTHLY_SUB_PRICE = 250  # Default monthly subscription price in USD

# =============================================================================
# Database Configuration
# =============================================================================
DATABASE_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "ivr_bot5",
    "user": "postgres",
    "password": "ivr2026secure",
}

DATABASE_URL = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"

# =============================================================================
# Asterisk AMI Configuration
# =============================================================================
AMI_CONFIG = {
    "host": "127.0.0.1",
    "port": 5038,
    "username": "ivr_bot",
    "secret": "IVRBotSecure2026",
}

# =============================================================================
# Asterisk Trunk Configuration (Dynamic Per-User)
# =============================================================================
IVR_CONTEXT = "press-one-ivr-5"
DEFAULT_CALLER_ID = "1234567890"

PJSIP_CONFIG_DIR = "/etc/asterisk"
PJSIP_USERS_CONF = "pjsip_users5.conf"
ASTERISK_RELOAD_CMD = 'asterisk -rx "pjsip reload"'

# =============================================================================
# MagnusBilling API Configuration
# =============================================================================
MAGNUSBILLING_URL = "https://login.voipzone.net/mbilling"
MAGNUSBILLING_API_KEY = "rdprzmyqwlpmgaimdhpiytfdeudgkitl"
MAGNUSBILLING_API_SECRET = "xncyloxgewabwychyyqdfzeljtnjsfkq"

# =============================================================================
# Webhook Server Configuration
# =============================================================================
WEBHOOK_HOST = "0.0.0.0"
WEBHOOK_PORT = 8004
WEBHOOK_URL = "http://localhost:8004"

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
LOG_FILE = "bot.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# Admin Configuration
# =============================================================================
ADMIN_TELEGRAM_IDS = [6594169471, 326854865]

# Test Mode
TEST_MODE = True

# =============================================================================
# Country Codes
# =============================================================================
SUPPORTED_COUNTRY_CODES = {
    "1": "🇺🇸 US/Canada",
    "44": "🇬🇧 UK",
    "49": "🇩🇪 Germany",
    "61": "🇦🇺 Australia",
    "33": "🇫🇷 France",
    "39": "🇮🇹 Italy",
    "34": "🇪🇸 Spain",
    "31": "🇳🇱 Netherlands",
    "90": "🇹🇷 Turkey",
    "81": "🇯🇵 Japan",
    "86": "🇨🇳 China",
    "91": "🇮🇳 India",
    "55": "🇧🇷 Brazil",
    "7": "🇷🇺 Russia",
    "971": "🇦🇪 UAE",
    "966": "🇸🇦 Saudi Arabia",
    "none": "🌍 No Prefix (already includes code)",
}

# =============================================================================
# File Paths
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
