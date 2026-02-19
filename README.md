# Press-1 IVR Bot 3 - Proline

Proline P1 Bot - Automated press-one IVR system with Telegram bot management.

## System Overview
- **Bot:** Proline P1 Bot (Telegram)
- **SIP Provider:** Proline (sip.prolinecall.site)
- **MagnusBilling:** prolinecall.site/mbilling
- **Payment:** Oxapay (USDT)
- **Database:** PostgreSQL (ivr_bot3)
- **Asterisk:** Per-user trunk routing

## Quick Start

### 1. Database Setup
```bash
sudo -u postgres createdb ivr_bot3
sudo -u postgres psql -d ivr_bot3 -f database/schema.sql
```

### 2. Asterisk Configuration
```bash
# Proline trunk ekle
sudo cat asterisk/configs/pjsip_callix_trunk.conf >> /etc/asterisk/pjsip.conf

# Proline dialplan ekle
sudo cat asterisk/configs/extensions_callix.conf >> /etc/asterisk/extensions.conf

# Reload
asterisk -rx "core reload"
asterisk -rx "pjsip show registrations"
```

### 3. Start with PM2
```bash
cd /opt/tgbot3
pm2 start ecosystem.config.js
pm2 save
```

### 4. Firewall
```bash
ufw allow 8002/tcp  # Oxapay webhook port
```

## Key Ports
| Service | Port |
|---------|------|
| Webhook Server | 8002 |
| Oxapay Webhook | 8002 |

## Directory Structure
```
tgbot3/
├── bot/                    # Telegram bot
│   ├── main.py            # Bot entry point
│   ├── config.py          # Configuration
│   ├── database.py        # Database operations
│   ├── oxapay_handler.py  # Payment handler
│   └── magnus_client.py   # MagnusBilling API
├── dialer/                # Call engine
│   ├── campaign_worker.py # Campaign processor
│   ├── ami_client.py      # Asterisk AMI
│   └── pjsip_generator.py # Dynamic trunk config
├── asterisk/configs/      # Asterisk configs
├── database/schema.sql    # DB schema
├── ecosystem.config.js    # PM2 config
└── systemd/               # Systemd services
```

## Support
Telegram: @prolinecall
