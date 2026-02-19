# =============================================================================
# Configuration for Press-1 IVR Bot 4 (Sonvia)
# =============================================================================

import os

# =============================================================================
# Telegram Bot Configuration
# =============================================================================
TELEGRAM_BOT_TOKEN = "8148291481:AAGC2wTBsRWVxG2Ayzbl90mere3iXxLobz4"

# =============================================================================
# Oxapay Payment Gateway Configuration
# =============================================================================
OXAPAY_API_KEY = "FS8WYO-SG7UFK-XGPTBJ-YGFIP0"
OXAPAY_API_URL = "https://api.oxapay.com/v1/payment/invoice"
OXAPAY_WEBHOOK_URL = "http://195.85.114.55:8003/webhook/oxapay"

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
    "database": "ivr_bot4",
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
    "secret": "IVRBotSecure2026",      # ⚠️ Must match manager.conf
}

# =============================================================================
# Asterisk Trunk Configuration (Dynamic Per-User)
# =============================================================================
IVR_CONTEXT = "press-one-ivr-4"
DEFAULT_CALLER_ID = "1234567890"         # Fallback CallerID if user has none

# PJSIP Dynamic Config Generation
PJSIP_CONFIG_DIR = "/etc/asterisk"                    # Asterisk config directory
PJSIP_USERS_CONF = "pjsip_users4.conf"               # Generated per-user trunk configs
ASTERISK_RELOAD_CMD = 'asterisk -rx "pjsip reload"'   # Command to reload PJSIP after changes

# =============================================================================
# MagnusBilling API Configuration
# =============================================================================
MAGNUSBILLING_URL = "http://195.85.114.82/mbilling"
MAGNUSBILLING_API_KEY = "rdprzmyqwlpmgaimdhpiytfdeudgkitl"
MAGNUSBILLING_API_SECRET = "xncyloxgewabwychyyqdfzeljtnjsfkq"

# =============================================================================
# Webhook Server Configuration
# =============================================================================
WEBHOOK_HOST = "0.0.0.0"
WEBHOOK_PORT = 8003
WEBHOOK_URL = "http://localhost:8003"    # Internal webhook for Asterisk

# =============================================================================
# Billing Configuration
# =============================================================================
COST_PER_MINUTE = 1.0                    # 1 credit = 1 minute
MINIMUM_BILLABLE_SECONDS = 6             # Minimum 6 seconds billing
BILLING_INCREMENT_SECONDS = 6            # Bill in 6-second increments

# =============================================================================
# Campaign Configuration
# =============================================================================
MAX_CONCURRENT_CALLS = 10                # Max simultaneous calls
CALL_TIMEOUT_SECONDS = 30                # Total call timeout
DTMF_TIMEOUT_SECONDS = 10               # Wait time for DTMF input
RETRY_FAILED_CALLS = False               # Retry failed calls
DELAY_BETWEEN_CALLS = 2                  # Seconds between each call

# =============================================================================
# Logging Configuration
# =============================================================================
LOG_LEVEL = "INFO"                       # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "bot.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# =============================================================================
# Admin Configuration
# =============================================================================
ADMIN_TELEGRAM_IDS = [8207528566, 326854865]

# Test Mode - Bypasses balance checks for admins
TEST_MODE = True                          # Set to False in production

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

# Create directories if they don't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
