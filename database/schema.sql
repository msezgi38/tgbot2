-- =============================================================================
-- PostgreSQL Database Schema for Press-1 IVR Bot (User-Scoped PJSIP)
-- =============================================================================
-- This schema supports:
-- 1. User management and credit tracking
-- 2. Per-user SIP trunk management
-- 3. Per-user lead list management
-- 4. Campaign management (linked to user trunks & leads)
-- 5. Call detail records (CDR)
-- 6. Payment processing via Oxapay
-- =============================================================================

-- Drop existing tables if re-creating
DROP TABLE IF EXISTS calls CASCADE;
DROP TABLE IF EXISTS campaign_data CASCADE;
DROP TABLE IF EXISTS campaigns CASCADE;
DROP TABLE IF EXISTS lead_numbers CASCADE;
DROP TABLE IF EXISTS leads CASCADE;
DROP TABLE IF EXISTS user_trunks CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- =============================================================================
-- Users Table
-- =============================================================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,              -- Telegram user ID
    username VARCHAR(255),                            -- Telegram username
    first_name VARCHAR(255),                          -- Telegram first name
    last_name VARCHAR(255),                           -- Telegram last name
    credits DECIMAL(10, 2) DEFAULT 0.00,              -- Available credits/minutes
    total_spent DECIMAL(10, 2) DEFAULT 0.00,          -- Lifetime spending
    total_calls INTEGER DEFAULT 0,                    -- Total calls made
    caller_id VARCHAR(50),                            -- Default Caller ID
    country_code VARCHAR(10) DEFAULT '+1',            -- Default country code
    magnus_username VARCHAR(255),                     -- MagnusBilling SIP username
    magnus_user_id INTEGER,                           -- MagnusBilling user ID
    is_active BOOLEAN DEFAULT TRUE,                   -- Account status
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);

-- =============================================================================
-- Per-User SIP Trunk Configuration
-- =============================================================================
CREATE TABLE user_trunks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,                       -- Display name (e.g. "My MagnusBilling")
    sip_host VARCHAR(255) NOT NULL,                   -- SIP server host/IP
    sip_port INTEGER DEFAULT 5060,                    -- SIP port
    sip_username VARCHAR(255) NOT NULL,               -- SIP auth username
    sip_password VARCHAR(255) NOT NULL,               -- SIP auth password
    transport VARCHAR(10) DEFAULT 'udp',              -- udp, tcp, tls
    codecs VARCHAR(255) DEFAULT 'ulaw,alaw,gsm',     -- Allowed codecs
    caller_id VARCHAR(50),                            -- Trunk-specific CallerID
    max_channels INTEGER DEFAULT 10,                  -- Max concurrent calls on this trunk
    status VARCHAR(50) DEFAULT 'active',              -- active, disabled, error
    pjsip_endpoint_name VARCHAR(100),                 -- Auto-generated: user_{id}_trunk_{trunk_id}
    last_registered_at TIMESTAMP,                     -- Last successful registration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name)
);

CREATE INDEX idx_user_trunks_user_id ON user_trunks(user_id);
CREATE INDEX idx_user_trunks_status ON user_trunks(status);
CREATE INDEX idx_user_trunks_endpoint ON user_trunks(pjsip_endpoint_name);

-- =============================================================================
-- Per-User Lead Lists
-- =============================================================================
CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    list_name VARCHAR(255) NOT NULL,                  -- e.g. "US Contacts Jan 2026"
    description TEXT,                                 -- Optional description
    total_numbers INTEGER DEFAULT 0,                  -- Total phone numbers in list
    available_numbers INTEGER DEFAULT 0,              -- Numbers not yet used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, list_name)
);

CREATE INDEX idx_leads_user_id ON leads(user_id);

-- =============================================================================
-- Lead Phone Numbers
-- =============================================================================
CREATE TABLE lead_numbers (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    phone_number VARCHAR(50) NOT NULL,                -- Phone number
    status VARCHAR(50) DEFAULT 'available',           -- available, used, blacklisted, dnc
    times_used INTEGER DEFAULT 0,                     -- How many campaigns used this number
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_lead_numbers_lead_id ON lead_numbers(lead_id);
CREATE INDEX idx_lead_numbers_status ON lead_numbers(status);
CREATE INDEX idx_lead_numbers_phone ON lead_numbers(phone_number);

-- =============================================================================
-- Payments Table (Oxapay)
-- =============================================================================
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    track_id VARCHAR(255) UNIQUE,                     -- Oxapay track ID
    order_id VARCHAR(255),                            -- Our internal order ID
    amount DECIMAL(10, 2) NOT NULL,                   -- Payment amount
    currency VARCHAR(10) DEFAULT 'USDT',              -- Cryptocurrency
    credits DECIMAL(10, 2),                           -- Credits to add
    status VARCHAR(50) DEFAULT 'pending',             -- pending, paid, confirmed, failed
    payment_url TEXT,                                 -- Oxapay payment link
    tx_hash VARCHAR(255),                             -- Blockchain transaction hash
    callback_data JSONB,                              -- Raw webhook data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP,
    confirmed_at TIMESTAMP
);

CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_track_id ON payments(track_id);
CREATE INDEX idx_payments_status ON payments(status);

-- =============================================================================
-- Campaigns Table (linked to user trunk + lead list)
-- =============================================================================
CREATE TABLE campaigns (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    trunk_id INTEGER REFERENCES user_trunks(id),      -- Which SIP trunk to use
    lead_id INTEGER REFERENCES leads(id),             -- Which lead list to call
    name VARCHAR(255) NOT NULL,                       -- Campaign name
    caller_id VARCHAR(50),                            -- CallerID override for this campaign
    country_code VARCHAR(10) DEFAULT '',               -- Country code prefix (e.g. 49, 44, 1)
    cps INTEGER DEFAULT 5,                             -- Concurrent calls (1-50)
    total_numbers INTEGER DEFAULT 0,                  -- Total phone numbers
    completed INTEGER DEFAULT 0,                      -- Calls completed
    answered INTEGER DEFAULT 0,                       -- Calls answered
    pressed_one INTEGER DEFAULT 0,                    -- Successful press-1
    failed INTEGER DEFAULT 0,                         -- Failed calls
    status VARCHAR(50) DEFAULT 'draft',               -- draft, running, paused, completed
    voice_file VARCHAR(500),                            -- Path to voice/audio file for IVR
    outro_file VARCHAR(500),                             -- Path to outro audio file (plays after press-1)
    estimated_cost DECIMAL(10, 2),                    -- Estimated credit cost
    actual_cost DECIMAL(10, 2) DEFAULT 0.00,          -- Actual cost so far
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX idx_campaigns_user_id ON campaigns(user_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_trunk_id ON campaigns(trunk_id);
CREATE INDEX idx_campaigns_lead_id ON campaigns(lead_id);

-- =============================================================================
-- Campaign Data Table (Phone Numbers copied from leads at campaign start)
-- =============================================================================
CREATE TABLE campaign_data (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
    lead_number_id INTEGER REFERENCES lead_numbers(id), -- Reference to original lead
    phone_number VARCHAR(50) NOT NULL,                -- Destination number
    status VARCHAR(50) DEFAULT 'pending',             -- pending, dialing, answered, failed, completed
    call_id VARCHAR(255),                             -- Asterisk unique call ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    called_at TIMESTAMP
);

CREATE INDEX idx_campaign_data_campaign_id ON campaign_data(campaign_id);
CREATE INDEX idx_campaign_data_status ON campaign_data(status);
CREATE INDEX idx_campaign_data_call_id ON campaign_data(call_id);

-- =============================================================================
-- Calls Table (Call Detail Records)
-- =============================================================================
CREATE TABLE calls (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
    campaign_data_id INTEGER REFERENCES campaign_data(id) ON DELETE CASCADE,
    call_id VARCHAR(255) UNIQUE,                      -- Asterisk unique call ID
    phone_number VARCHAR(50) NOT NULL,                -- Destination
    caller_id VARCHAR(50),                            -- CallerID used
    trunk_endpoint VARCHAR(100),                      -- Which PJSIP endpoint was used
    status VARCHAR(50),                               -- ANSWER, BUSY, NO ANSWER, FAILED
    dtmf_pressed INTEGER DEFAULT 0,                   -- 1 if pressed, 0 if not
    duration INTEGER DEFAULT 0,                       -- Total call duration (seconds)
    billsec INTEGER DEFAULT 0,                        -- Billable duration (seconds)
    cost DECIMAL(10, 4) DEFAULT 0.0000,               -- Cost in credits
    hangup_cause VARCHAR(100),                        -- Asterisk hangup cause
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    answered_at TIMESTAMP,
    ended_at TIMESTAMP
);

CREATE INDEX idx_calls_campaign_id ON calls(campaign_id);
CREATE INDEX idx_calls_call_id ON calls(call_id);
CREATE INDEX idx_calls_status ON calls(status);

-- =============================================================================
-- Voice Files Table (Per-User)
-- =============================================================================
CREATE TABLE voice_files (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    file_path TEXT,                                    -- Path on server
    duration INTEGER DEFAULT 0,                       -- Duration in seconds
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_voice_files_user_id ON voice_files(user_id);

-- =============================================================================
