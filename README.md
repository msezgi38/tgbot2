# Press-1 IVR Bot 4 - Sonvia

Sonvia P1 Bot - Automated press-one IVR system with Telegram bot management.

## System Overview
- **Bot:** Sonvia P1 Bot (Telegram)
- **SIP:** 195.85.114.82
- **MagnusBilling:** 195.85.114.82/mbilling
- **Payment:** Oxapay (USDT)
- **Database:** PostgreSQL (ivr_bot4)
- **Webhook Port:** 8003

## Deployment

```bash
# 1. Clone
mkdir -p /opt/tgbot4
cd /opt/tgbot4
git clone <REPO_URL> .

# 2. Database
sudo -u postgres createdb ivr_bot4
sudo -u postgres psql -d ivr_bot4 -f database/schema.sql

# 3. Asterisk
cat asterisk/configs/extensions_callix.conf >> /etc/asterisk/extensions.conf
echo '#include "pjsip_users4.conf"' >> /etc/asterisk/pjsip.conf
touch /etc/asterisk/pjsip_users4.conf
asterisk -rx "core reload"

# 4. Firewall
iptables -A INPUT -p tcp --dport 8003 -j ACCEPT

# 5. PM2
cd /opt/tgbot4
pm2 start ecosystem.config.js
pm2 save
```

## Support
Telegram: @sonvia98
