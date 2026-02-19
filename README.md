# Press-1 IVR Bot 5 - VoipZone

VoipZone P1 Bot - Automated press-one IVR system with Telegram bot management.

## System Overview
- **Bot:** VoipZone P1 Bot (@voipzonep1_bot)
- **SIP:** 162.33.179.45
- **MagnusBilling:** login.voipzone.net/mbilling
- **Payment:** Oxapay (USDT)
- **Database:** PostgreSQL (ivr_bot5)
- **Webhook Port:** 8004
- **Support:** @voipzonee

## Deployment

```bash
mkdir -p /opt/tgbot5
cd /opt/tgbot5
git clone https://github.com/msezgi38/tgbot2.git .

sudo -u postgres createdb ivr_bot5
sudo -u postgres psql -d ivr_bot5 -f /opt/tgbot5/database/schema.sql

cat /opt/tgbot5/asterisk/configs/extensions_callix.conf >> /etc/asterisk/extensions.conf
echo '#include "pjsip_users5.conf"' >> /etc/asterisk/pjsip.conf
touch /etc/asterisk/pjsip_users5.conf
asterisk -rx "core reload"

iptables -A INPUT -p tcp --dport 8004 -j ACCEPT

# fail2ban whitelist
echo -e "[DEFAULT]\nignoreip = 127.0.0.1/8 ::1 162.33.179.45" >> /etc/fail2ban/jail.local
systemctl restart fail2ban

cd /opt/tgbot5
pm2 start ecosystem.config.js
pm2 save
```
