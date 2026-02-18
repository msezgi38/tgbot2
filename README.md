# Press-1 IVR Bot 2 - Callix
# Setup & Deployment Guide

## 📋 Bu Nedir?
Bu, birinci IVR Bot'un (tgbot) ikinci kopyasıdır.
- **Sağlayıcı:** Callix (sip.callix.pro)
- **Telegram Bot:** Farklı token ile ayrı bot
- **Oxapay:** Farklı API key ile ayrı hesap
- **Veritabanı:** Ayrı (ivr_bot2)
- **Webhook Port:** 8001 (Bot 1: 8000)
- **Asterisk:** Aynı sunucu, farklı trunk (callix_trunk)

## 🔧 Farklar (Bot 1 vs Bot 2)

| Ayar | Bot 1 (tgbot) | Bot 2 (tgbot2) |
|------|--------------|-----------------|
| SIP Trunk | magnus_trunk | callix_trunk |
| SIP Host | sip.1337global.sbs | sip.callix.pro |
| Dialplan Context | press-one-ivr | press-one-ivr-2 |
| Webhook Port | 8000 | 8001 |
| Database | ivr_bot | ivr_bot2 |
| Telegram Token | 8585205125:... | 8309805045:... |
| Oxapay Key | QSTFGZ-... | SPIWDL-... |
| Support | - | @callixcalvin |
| Admin ID | - | 8500048750 |

## 🚀 Kurulum Adımları

### 1. Veritabanı Oluştur
```bash
psql -U postgres -c "CREATE DATABASE ivr_bot2;"
psql -U postgres -d ivr_bot2 -f database/schema.sql
```

### 2. Asterisk'e Trunk Ekle
**⚠️ Mevcut pjsip.conf dosyasının SONUNA ekle (silme!)**
```bash
# Callix trunk ekle
sudo cat asterisk/configs/pjsip_callix_trunk.conf >> /etc/asterisk/pjsip.conf

# Callix dialplan ekle
sudo cat asterisk/configs/extensions_callix.conf >> /etc/asterisk/extensions.conf

# Asterisk'i yeniden yükle
sudo asterisk -rx "core reload"

# Her iki trunk'ı kontrol et
sudo asterisk -rx "pjsip show registrations"
# magnus_trunk ... Registered
# callix_trunk ... Registered
```

### 3. Callix SIP Bilgilerini Gir
`asterisk/configs/pjsip_callix_trunk.conf` dosyasında:
- `YOUR_CALLIX_USERNAME` → Callix kullanıcı adınız
- `YOUR_CALLIX_PASSWORD` → Callix şifreniz

### 4. DB Şifresini Gir
`bot/config.py` dosyasında:
- `your_db_password` → PostgreSQL şifreniz

### 5. Python Bağımlılıklarını Kur
```bash
cd /path/to/tgbot2
pip install -r bot/requirements.txt
pip install -r dialer/requirements.txt
```

### 6. Servisleri Başlat (3 Terminal)

**Terminal 1: Webhook (Port 8001)**
```bash
cd /path/to/tgbot2/dialer
python webhook_server.py
```

**Terminal 2: Campaign Worker**
```bash
cd /path/to/tgbot2/dialer
python campaign_worker.py
```

**Terminal 3: Telegram Bot**
```bash
cd /path/to/tgbot2/bot
python main.py
```

## ⚡ Hızlı Test

### Trunk kayıtlı mı?
```bash
sudo asterisk -rx "pjsip show registrations"
# İKİ trunk da "Registered" görmeli
```

### Webhook 2 çalışıyor mu?
```bash
curl http://localhost:8001/
# {"service":"Callix IVR Bot Webhook Server","status":"running","port":8001}
```

### Bot çalışıyor mu?
Telegram'da yeni bota /start gönderin

## 📂 Dosya Yapısı
```
tgbot2/
├── asterisk/configs/
│   ├── pjsip_callix_trunk.conf     # ← Mevcut pjsip.conf'a EKLE
│   └── extensions_callix.conf       # ← Mevcut extensions.conf'a EKLE
├── bot/
│   ├── main.py                      # Telegram bot
│   ├── database.py                  # DB işlemleri
│   ├── oxapay_handler.py            # Ödeme sistemi
│   ├── config.py                    # ⚠️ DB şifresi güncelle
│   └── requirements.txt
├── dialer/
│   ├── ami_client.py                # AMI bağlantısı
│   ├── campaign_worker.py           # Kampanya işleyici
│   ├── webhook_server.py            # Port 8001
│   └── requirements.txt
├── database/
│   └── schema.sql                   # ivr_bot2 şeması
└── README.md                        # Bu dosya
```

## ⚠️ Önemli Notlar

1. **Asterisk configs EKLEME şeklinde** - Mevcut dosyaları silmeyin!
2. **Port 8001** kullanıyor - Bot 1 ile çakışmaz
3. **Ayrı veritabanı** (ivr_bot2) - Bot 1'in verilerine karışmaz
4. **Aynı AMI bağlantısı** - Asterisk ortak kullanılır
5. **IVR ses dosyası** ortak - her iki bot da aynı dosyayı çalar
