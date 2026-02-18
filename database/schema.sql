-- =============================================================================
-- Database Schema for IVR Bot 2 (Callix)
-- =============================================================================
-- This is IDENTICAL to Bot 1's schema, but runs in a SEPARATE database: ivr_bot2
--
-- Create database:   psql -U postgres -c "CREATE DATABASE ivr_bot2;"
-- Import schema:     psql -U postgres -d ivr_bot2 -f schema.sql
-- =============================================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    credits DECIMAL(12,4) DEFAULT 0.0,
    total_spent DECIMAL(12,4) DEFAULT 0.0,
    total_calls INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Payments table
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    track_id VARCHAR(255) UNIQUE,
    amount DECIMAL(12,4) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USDT',
    credits DECIMAL(12,4) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    tx_hash VARCHAR(255),
    payment_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP
);

-- Campaigns table
CREATE TABLE IF NOT EXISTS campaigns (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    caller_id VARCHAR(50),
    status VARCHAR(50) DEFAULT 'draft',
    total_numbers INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    answered INTEGER DEFAULT 0,
    pressed_one INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    actual_cost DECIMAL(12,4) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Campaign data (phone numbers)
CREATE TABLE IF NOT EXISTS campaign_data (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    phone_number VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    call_id VARCHAR(255),
    called_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Calls (CDR - Call Detail Records)
CREATE TABLE IF NOT EXISTS calls (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    campaign_data_id INTEGER REFERENCES campaign_data(id),
    call_id VARCHAR(255) UNIQUE,
    phone_number VARCHAR(50) NOT NULL,
    caller_id VARCHAR(50),
    status VARCHAR(50) DEFAULT 'INITIATED',
    dtmf_pressed INTEGER DEFAULT 0,
    hangup_cause VARCHAR(100),
    billsec INTEGER DEFAULT 0,
    cost DECIMAL(12,4) DEFAULT 0.0,
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);

-- SIP Accounts (auto-created via MagnusBilling API)
CREATE TABLE IF NOT EXISTS sip_accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    sip_id INTEGER,                          -- MagnusBilling SIP ID
    sip_username VARCHAR(100) NOT NULL,
    sip_password VARCHAR(255) NOT NULL,
    sip_host VARCHAR(255) DEFAULT 'sip.callix.pro',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_payments_track_id ON payments(track_id);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_user_id ON campaigns(user_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
CREATE INDEX IF NOT EXISTS idx_campaign_data_campaign_id ON campaign_data(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_data_status ON campaign_data(status);
CREATE INDEX IF NOT EXISTS idx_calls_campaign_id ON calls(campaign_id);
CREATE INDEX IF NOT EXISTS idx_calls_call_id ON calls(call_id);
CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status);
CREATE INDEX IF NOT EXISTS idx_sip_accounts_user_id ON sip_accounts(user_id);
