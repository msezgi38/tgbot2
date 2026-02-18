# =============================================================================
# Dialer config import - loads from bot directory
# =============================================================================
# This file makes config importable from the dialer directory
# by adding the bot directory to Python path
# =============================================================================

import sys
import os

# Add bot directory to path so we can import config
bot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bot')
sys.path.insert(0, bot_dir)

# Now config can be imported in ami_client.py, campaign_worker.py, webhook_server.py
