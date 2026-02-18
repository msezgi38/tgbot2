# =============================================================================
# Database Helper - PostgreSQL ORM and Queries
# =============================================================================
# AsyncPG-based database interface for the Telegram bot
# Supports per-user trunk, lead, and campaign management
# =============================================================================

import asyncpg
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging

from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    """Database interface for IVR Bot (User-Scoped)"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=5,
                max_size=20
            )
            logger.info("✅ Database connected")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database disconnected")
    
    # =========================================================================
    # User Operations
    # =========================================================================
    
    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Dict:
        """Get existing user or create new one"""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("""
                SELECT * FROM users WHERE telegram_id = $1
            """, telegram_id)
            
            if user:
                await conn.execute("""
                    UPDATE users SET last_active = $1 WHERE telegram_id = $2
                """, datetime.now(), telegram_id)
                return dict(user)
            
            user = await conn.fetchrow("""
                INSERT INTO users (telegram_id, username, first_name, last_name)
                VALUES ($1, $2, $3, $4)
                RETURNING *
            """, telegram_id, username, first_name, last_name)
            
            logger.info(f"👤 New user created: {telegram_id} ({username})")
            return dict(user)
    
    async def set_magnus_info(self, telegram_id: int, magnus_username: str, magnus_user_id: int):
        """Save MagnusBilling user mapping"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET magnus_username = $1, magnus_user_id = $2
                WHERE telegram_id = $3
            """, magnus_username, magnus_user_id, telegram_id)
    
    async def get_magnus_info(self, telegram_id: int) -> dict:
        """Get MagnusBilling user info for a telegram user"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT magnus_username, magnus_user_id FROM users WHERE telegram_id = $1
            """, telegram_id)
            return dict(row) if row else None
    
    async def clear_magnus_info(self, telegram_id: int) -> bool:
        """Clear MagnusBilling SIP account info and trunks for a user (admin reset)"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Get user id
                user_row = await conn.fetchrow(
                    "SELECT id FROM users WHERE telegram_id = $1", telegram_id
                )
                if not user_row:
                    return False
                
                # Nullify trunk references in campaigns
                await conn.execute("""
                    UPDATE campaigns SET trunk_id = NULL 
                    WHERE trunk_id IN (SELECT id FROM user_trunks WHERE user_id = $1)
                """, user_row['id'])
                
                # Delete user trunks
                await conn.execute(
                    "DELETE FROM user_trunks WHERE user_id = $1", user_row['id']
                )
                
                # Clear magnus info
                await conn.execute("""
                    UPDATE users SET magnus_username = NULL, magnus_user_id = NULL
                    WHERE telegram_id = $1
                """, telegram_id)
                
                return True
    
    async def get_all_users(self) -> List[Dict]:
        """Get all registered users for admin view"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    id, telegram_id, username, first_name, last_name,
                    credits, total_spent, total_calls, caller_id,
                    is_active, created_at, last_active
                FROM users
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in rows]

    async def get_all_users_with_call_stats(self) -> List[Dict]:
        """Get all registered users with per-user call, P1, and SIP stats"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    u.id, u.telegram_id, u.username, u.first_name, u.last_name,
                    u.credits, u.total_spent, u.total_calls, u.caller_id,
                    COALESCE(u.magnus_username, t.sip_username) as sip_account,
                    u.is_active, u.created_at, u.last_active,
                    COALESCE(cs.real_calls, 0) as real_calls,
                    COALESCE(cs.p1_count, 0) as p1_count
                FROM users u
                LEFT JOIN (
                    SELECT DISTINCT ON (user_id) user_id, sip_username
                    FROM user_trunks
                    WHERE status = 'active'
                    ORDER BY user_id, created_at DESC
                ) t ON t.user_id = u.id
                LEFT JOIN (
                    SELECT 
                        c.user_id,
                        COUNT(cl.id) as real_calls,
                        COUNT(cl.id) FILTER (WHERE cl.dtmf_pressed > 0) as p1_count
                    FROM campaigns c
                    JOIN calls cl ON cl.campaign_id = c.id
                    GROUP BY c.user_id
                ) cs ON cs.user_id = u.id
                ORDER BY u.created_at DESC
            """)
            return [dict(row) for row in rows]
    
    async def get_user_credits(self, telegram_id: int) -> float:
        """Get user's available credits"""
        async with self.pool.acquire() as conn:
            credits = await conn.fetchval("""
                SELECT credits FROM users WHERE telegram_id = $1
            """, telegram_id)
            return float(credits or 0)
    
    async def add_credits(self, telegram_id: int, amount: float) -> float:
        """Add credits to user account"""
        async with self.pool.acquire() as conn:
            new_balance = await conn.fetchval("""
                UPDATE users
                SET credits = credits + $1
                WHERE telegram_id = $2
                RETURNING credits
            """, amount, telegram_id)
            return float(new_balance)
    
    async def set_caller_id(self, telegram_id: int, caller_id: str):
        """Set user's default caller ID"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET caller_id = $1 WHERE telegram_id = $2
            """, caller_id, telegram_id)
    
    async def validate_cid(self, cid: str):
        """Validate a caller ID"""
        clean_cid = ''.join(filter(str.isdigit, cid))
        if len(clean_cid) < 10 or len(clean_cid) > 15:
            return False, "CID must be 10-15 digits"
        return True, "Valid"
    
    # =========================================================================
    # SIP Trunk Operations (Per-User)
    # =========================================================================
    
    async def create_trunk(
        self,
        user_id: int,
        name: str,
        sip_host: str,
        sip_username: str,
        sip_password: str,
        sip_port: int = 5060,
        transport: str = 'udp',
        codecs: str = 'ulaw,alaw,gsm',
        caller_id: Optional[str] = None,
        max_channels: int = 10
    ) -> Dict:
        """Create a new SIP trunk for a user"""
        async with self.pool.acquire() as conn:
            # Generate unique PJSIP endpoint name
            trunk = await conn.fetchrow("""
                INSERT INTO user_trunks (
                    user_id, name, sip_host, sip_port, sip_username,
                    sip_password, transport, codecs, caller_id, max_channels
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
            """, user_id, name, sip_host, sip_port, sip_username,
                sip_password, transport, codecs, caller_id, max_channels)
            
            trunk_dict = dict(trunk)
            
            # Set auto-generated pjsip endpoint name
            endpoint_name = f"callix_{user_id}_trunk_{trunk_dict['id']}"
            await conn.execute("""
                UPDATE user_trunks SET pjsip_endpoint_name = $1 WHERE id = $2
            """, endpoint_name, trunk_dict['id'])
            
            trunk_dict['pjsip_endpoint_name'] = endpoint_name
            logger.info(f"🔌 Trunk created: {endpoint_name} for user {user_id}")
            return trunk_dict
    
    async def get_user_trunks(self, user_id: int) -> List[Dict]:
        """Get all trunks for a user"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM user_trunks
                WHERE user_id = $1
                ORDER BY created_at DESC
            """, user_id)
            return [dict(row) for row in rows]
    
    async def get_trunk(self, trunk_id: int) -> Optional[Dict]:
        """Get a single trunk by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM user_trunks WHERE id = $1
            """, trunk_id)
            return dict(row) if row else None
    
    async def update_trunk(self, trunk_id: int, **kwargs) -> bool:
        """Update trunk fields"""
        if not kwargs:
            return False
        
        allowed_fields = {
            'name', 'sip_host', 'sip_port', 'sip_username', 'sip_password',
            'transport', 'codecs', 'caller_id', 'max_channels', 'status'
        }
        
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False
        
        async with self.pool.acquire() as conn:
            sets = ', '.join([f"{k} = ${i+1}" for i, k in enumerate(updates.keys())])
            values = list(updates.values())
            values.append(trunk_id)
            
            await conn.execute(f"""
                UPDATE user_trunks
                SET {sets}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ${len(values)}
            """, *values)
            return True
    
    async def delete_trunk(self, trunk_id: int) -> bool:
        """Delete a trunk (nullifies campaign references first)"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Nullify trunk reference in campaigns to avoid FK violation
                await conn.execute("""
                    UPDATE campaigns SET trunk_id = NULL WHERE trunk_id = $1
                """, trunk_id)
                # Now safely delete the trunk
                result = await conn.execute("""
                    DELETE FROM user_trunks WHERE id = $1
                """, trunk_id)
                return 'DELETE 1' in result
    
    async def get_active_trunks(self) -> List[Dict]:
        """Get all active trunks (for PJSIP config generation)"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT ut.*, u.telegram_id, u.username
                FROM user_trunks ut
                JOIN users u ON ut.user_id = u.id
                WHERE ut.status = 'active'
                ORDER BY ut.id ASC
            """)
            return [dict(row) for row in rows]
    
    # =========================================================================
    # Lead Operations (Per-User)
    # =========================================================================
    
    async def create_lead_list(
        self,
        user_id: int,
        list_name: str,
        description: Optional[str] = None
    ) -> int:
        """Create a new lead list"""
        async with self.pool.acquire() as conn:
            lead_id = await conn.fetchval("""
                INSERT INTO leads (user_id, list_name, description)
                VALUES ($1, $2, $3)
                RETURNING id
            """, user_id, list_name, description)
            logger.info(f"📋 Lead list created: {list_name} for user {user_id}")
            return lead_id
    
    async def add_lead_numbers(
        self,
        lead_id: int,
        phone_numbers: List[str]
    ) -> int:
        """Add phone numbers to a lead list"""
        async with self.pool.acquire() as conn:
            await conn.executemany("""
                INSERT INTO lead_numbers (lead_id, phone_number)
                VALUES ($1, $2)
            """, [(lead_id, num) for num in phone_numbers])
            
            count = len(phone_numbers)
            await conn.execute("""
                UPDATE leads
                SET total_numbers = total_numbers + $1,
                    available_numbers = available_numbers + $1
                WHERE id = $2
            """, count, lead_id)
            
            return count
    
    async def get_user_leads(self, user_id: int) -> List[Dict]:
        """Get all lead lists for a user"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM leads
                WHERE user_id = $1
                ORDER BY created_at DESC
            """, user_id)
            return [dict(row) for row in rows]
    
    async def get_lead(self, lead_id: int) -> Optional[Dict]:
        """Get a single lead list"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM leads WHERE id = $1
            """, lead_id)
            return dict(row) if row else None
    
    async def get_lead_numbers(
        self,
        lead_id: int,
        status: str = 'available',
        limit: int = 100
    ) -> List[Dict]:
        """Get phone numbers from a lead list"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM lead_numbers
                WHERE lead_id = $1 AND status = $2
                ORDER BY id ASC
                LIMIT $3
            """, lead_id, status, limit)
            return [dict(row) for row in rows]
    
    async def reset_lead_list(self, lead_id: int) -> int:
        """Reset all lead numbers back to 'available' status so they can be called again"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Reset all numbers to available
                result = await conn.execute("""
                    UPDATE lead_numbers
                    SET status = 'available', times_used = 0, last_used_at = NULL
                    WHERE lead_id = $1 AND status != 'available'
                """, lead_id)
                
                # Count how many were reset
                reset_count = int(result.split(' ')[-1]) if result else 0
                
                # Update the available count to match total
                await conn.execute("""
                    UPDATE leads
                    SET available_numbers = total_numbers
                    WHERE id = $1
                """, lead_id)
                
                logger.info(f"🔄 Lead list {lead_id} reset: {reset_count} numbers back to available")
                return reset_count
    
    async def delete_lead_list(self, lead_id: int) -> bool:
        """Delete a lead list and all its numbers"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Nullify campaign_data references to lead_numbers (FK constraint)
                await conn.execute("""
                    UPDATE campaign_data SET lead_number_id = NULL
                    WHERE lead_number_id IN (
                        SELECT id FROM lead_numbers WHERE lead_id = $1
                    )
                """, lead_id)
                # Delete lead numbers
                await conn.execute("DELETE FROM lead_numbers WHERE lead_id = $1", lead_id)
                # Delete the lead list
                result = await conn.execute("DELETE FROM leads WHERE id = $1", lead_id)
            return 'DELETE 1' in result
    
    async def copy_leads_to_campaign(self, campaign_id: int, lead_id: int) -> int:
        """Copy lead numbers into campaign_data for a campaign"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Copy ALL numbers from lead list (allow reuse across campaigns)
                result = await conn.execute("""
                    INSERT INTO campaign_data (campaign_id, lead_number_id, phone_number)
                    SELECT $1, ln.id, ln.phone_number
                    FROM lead_numbers ln
                    WHERE ln.lead_id = $2
                """, campaign_id, lead_id)
                
                # Count inserted
                count = int(result.split(' ')[-1]) if result else 0
                
                # Update campaign total
                await conn.execute("""
                    UPDATE campaigns
                    SET total_numbers = $1
                    WHERE id = $2
                """, count, campaign_id)
                
                return count
    
    # =========================================================================
    # Payment Operations
    # =========================================================================
    
    async def create_payment(
        self,
        user_id: int,
        track_id: str,
        amount: float,
        credits: float,
        currency: str = "USDT",
        payment_url: str = None
    ) -> int:
        """Create payment record"""
        async with self.pool.acquire() as conn:
            payment_id = await conn.fetchval("""
                INSERT INTO payments (
                    user_id, track_id, amount, currency,
                    credits, status, payment_url
                )
                VALUES ($1, $2, $3, $4, $5, 'pending', $6)
                RETURNING id
            """, user_id, track_id, amount, currency, credits, payment_url)
            return payment_id
    
    async def confirm_payment(self, track_id: str, tx_hash: Optional[str] = None) -> bool:
        """Confirm payment and add credits to user"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                payment = await conn.fetchrow("""
                    SELECT user_id, credits, status FROM payments
                    WHERE track_id = $1
                """, track_id)
                
                if not payment or payment['status'] != 'pending':
                    return False
                
                await conn.execute("""
                    UPDATE payments
                    SET status = 'confirmed',
                        tx_hash = $1,
                        confirmed_at = $2
                    WHERE track_id = $3
                """, tx_hash, datetime.now(), track_id)
                
                telegram_id = await conn.fetchval("""
                    SELECT telegram_id FROM users WHERE id = $1
                """, payment['user_id'])
                
                await self.add_credits(telegram_id, payment['credits'])
                
                logger.info(f"💳 Payment confirmed: {track_id} → +{payment['credits']} credits")
                return True
    
    # =========================================================================
    # Subscription Operations
    # =========================================================================
    
    async def ensure_subscriptions_table(self):
        """Create subscriptions table if it doesn't exist"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    telegram_id BIGINT,
                    payment_track_id TEXT,
                    amount FLOAT,
                    status TEXT DEFAULT 'pending',
                    starts_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            logger.info("✅ Subscriptions table ready")
    
    async def create_subscription(self, user_id: int, telegram_id: int, track_id: str, amount: float) -> int:
        """Create a pending subscription"""
        async with self.pool.acquire() as conn:
            sub_id = await conn.fetchval("""
                INSERT INTO subscriptions (user_id, telegram_id, payment_track_id, amount, status)
                VALUES ($1, $2, $3, $4, 'pending')
                RETURNING id
            """, user_id, telegram_id, track_id, amount)
            logger.info(f"📦 Subscription created: #{sub_id} for user {telegram_id}, track={track_id}")
            return sub_id
    
    async def activate_subscription(self, track_id: str) -> Optional[Dict]:
        """Activate subscription after payment confirmed. Returns subscription info."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                sub = await conn.fetchrow("""
                    SELECT * FROM subscriptions WHERE payment_track_id = $1 AND status = 'pending'
                """, track_id)
                
                if not sub:
                    return None
                
                now = datetime.now()
                expires = now + timedelta(days=30)
                
                await conn.execute("""
                    UPDATE subscriptions
                    SET status = 'active', starts_at = $1, expires_at = $2
                    WHERE id = $3
                """, now, expires, sub['id'])
                
                logger.info(f"✅ Subscription activated: #{sub['id']} until {expires}")
                return {
                    'id': sub['id'],
                    'telegram_id': sub['telegram_id'],
                    'amount': sub['amount'],
                    'expires_at': expires
                }
    
    async def get_active_subscription(self, telegram_id: int) -> Optional[Dict]:
        """Get user's active subscription (not expired)"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM subscriptions
                WHERE telegram_id = $1 AND status = 'active' AND expires_at > NOW()
                ORDER BY expires_at DESC LIMIT 1
            """, telegram_id)
            return dict(row) if row else None
    
    async def get_subscription_by_track_id(self, track_id: str) -> Optional[Dict]:
        """Get subscription by payment track ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM subscriptions WHERE payment_track_id = $1
            """, track_id)
            return dict(row) if row else None
    
    async def freeze_subscription(self, telegram_id: int) -> bool:
        """Freeze a user's active subscription"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE subscriptions SET status = 'frozen'
                WHERE telegram_id = $1 AND status = 'active' AND expires_at > NOW()
            """, telegram_id)
            return 'UPDATE' in result and result != 'UPDATE 0'
    
    async def unfreeze_subscription(self, telegram_id: int) -> bool:
        """Unfreeze a user's frozen subscription"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE subscriptions SET status = 'active'
                WHERE telegram_id = $1 AND status = 'frozen'
            """, telegram_id)
            return 'UPDATE' in result and result != 'UPDATE 0'
    
    async def get_subscription_status(self, telegram_id: int) -> Optional[str]:
        """Get subscription status for a user (active, frozen, pending, etc)"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT status FROM subscriptions
                WHERE telegram_id = $1 AND expires_at > NOW()
                ORDER BY created_at DESC LIMIT 1
            """, telegram_id)
            return row['status'] if row else None
    
    async def grant_subscription(self, telegram_id: int, days: int = 30) -> Optional[Dict]:
        """Admin: manually grant a subscription to a user"""
        async with self.pool.acquire() as conn:
            # Get user_id from telegram_id
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_id = $1", telegram_id
            )
            if not user_row:
                return None
            
            now = datetime.now()
            expires = now + timedelta(days=days)
            
            sub_id = await conn.fetchval("""
                INSERT INTO subscriptions (user_id, telegram_id, payment_track_id, amount, status, starts_at, expires_at)
                VALUES ($1, $2, $3, 0, 'active', $4, $5)
                RETURNING id
            """, user_row['id'], telegram_id, f"manual_{telegram_id}_{int(now.timestamp())}", now, expires)
            
            logger.info(f"🎁 Manual subscription granted: user {telegram_id}, expires {expires}")
            return {
                'id': sub_id,
                'telegram_id': telegram_id,
                'expires_at': expires
            }
    
    async def get_all_subscriptions(self) -> list:
        """Get all subscriptions with user info"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT s.*, u.telegram_id as tg_id, u.username, u.first_name
                FROM subscriptions s
                JOIN users u ON u.id = s.user_id
                WHERE s.status IN ('active', 'frozen') AND s.expires_at > NOW()
                ORDER BY s.created_at DESC
                LIMIT 50
            """)
            return [dict(r) for r in rows]
    
    # =========================================================================
    # Campaign Operations
    # =========================================================================
    
    async def create_campaign(
        self,
        user_id: int,
        name: str,
        trunk_id: Optional[int] = None,
        lead_id: Optional[int] = None,
        caller_id: Optional[str] = None,
        country_code: str = '',
        cps: int = 5,
        voice_file: Optional[str] = None,
        outro_file: Optional[str] = None
    ) -> int:
        """Create new campaign linked to user's trunk and lead list"""
        async with self.pool.acquire() as conn:
            campaign_id = await conn.fetchval("""
                INSERT INTO campaigns (user_id, name, trunk_id, lead_id, caller_id, country_code, cps, voice_file, outro_file, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'draft')
                RETURNING id
            """, user_id, name, trunk_id, lead_id, caller_id, country_code, cps, voice_file, outro_file)
            return campaign_id
    
    async def add_campaign_numbers(
        self,
        campaign_id: int,
        phone_numbers: List[str]
    ) -> int:
        """Add phone numbers directly to campaign (legacy support)"""
        async with self.pool.acquire() as conn:
            await conn.executemany("""
                INSERT INTO campaign_data (campaign_id, phone_number)
                VALUES ($1, $2)
            """, [(campaign_id, num) for num in phone_numbers])
            
            count = len(phone_numbers)
            await conn.execute("""
                UPDATE campaigns
                SET total_numbers = total_numbers + $1
                WHERE id = $2
            """, count, campaign_id)
            
            return count
    
    async def start_campaign(self, campaign_id: int) -> bool:
        """Start campaign execution"""
        async with self.pool.acquire() as conn:
            # Get campaign to check for lead_id
            campaign = await conn.fetchrow("""
                SELECT lead_id, trunk_id FROM campaigns WHERE id = $1
            """, campaign_id)
            
            if not campaign:
                return False
            
            # If campaign has a lead_id but no numbers yet, copy leads
            if campaign['lead_id']:
                existing = await conn.fetchval("""
                    SELECT COUNT(*) FROM campaign_data WHERE campaign_id = $1
                """, campaign_id)
                
                if existing == 0:
                    await self.copy_leads_to_campaign(campaign_id, campaign['lead_id'])
            
            await conn.execute("""
                UPDATE campaigns
                SET status = 'running', started_at = $1
                WHERE id = $2
            """, datetime.now(), campaign_id)
            return True
    
    async def stop_campaign(self, campaign_id: int) -> bool:
        """Stop/pause campaign"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE campaigns
                SET status = 'paused'
                WHERE id = $1
            """, campaign_id)
            return True
    
    async def delete_campaign(self, campaign_id: int, user_id: int = None) -> bool:
        """Delete a campaign and its data"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Delete campaign data (numbers)
                await conn.execute("DELETE FROM campaign_data WHERE campaign_id = $1", campaign_id)
                # Delete call records
                await conn.execute("DELETE FROM calls WHERE campaign_id = $1", campaign_id)
                # Delete campaign
                if user_id:
                    await conn.execute("DELETE FROM campaigns WHERE id = $1 AND user_id = $2", campaign_id, user_id)
                else:
                    await conn.execute("DELETE FROM campaigns WHERE id = $1", campaign_id)
            return True
    
    async def get_campaign(self, campaign_id: int) -> Optional[Dict]:
        """Get single campaign with trunk info"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT c.*, 
                       ut.pjsip_endpoint_name as trunk_endpoint,
                       ut.name as trunk_name,
                       l.list_name as lead_name
                FROM campaigns c
                LEFT JOIN user_trunks ut ON c.trunk_id = ut.id
                LEFT JOIN leads l ON c.lead_id = l.id
                WHERE c.id = $1
            """, campaign_id)
            return dict(row) if row else None
    
    async def get_campaign_stats(self, campaign_id: int) -> Dict:
        """Get campaign statistics - computed live from campaign_data and calls"""
        async with self.pool.acquire() as conn:
            # Get campaign info
            campaign = await conn.fetchrow("""
                SELECT
                    c.name, c.status, c.created_at, c.started_at,
                    c.total_numbers, c.actual_cost,
                    ut.name as trunk_name,
                    l.list_name as lead_name
                FROM campaigns c
                LEFT JOIN user_trunks ut ON c.trunk_id = ut.id
                LEFT JOIN leads l ON c.lead_id = l.id
                WHERE c.id = $1
            """, campaign_id)
            
            if not campaign:
                return {}
            
            result = dict(campaign)
            
            # Count live stats from campaign_data table
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE status NOT IN ('pending')) as completed,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed
                FROM campaign_data
                WHERE campaign_id = $1
            """, campaign_id)
            
            # Count answered and pressed_one from calls table
            call_stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE status IN ('ANSWER', 'ANSWERED', 'COMPLETED')) as answered,
                    COUNT(*) FILTER (WHERE dtmf_pressed > 0) as pressed_one,
                    COALESCE(SUM(cost), 0) as total_cost
                FROM calls
                WHERE campaign_id = $1
            """, campaign_id)
            
            result['completed'] = stats['completed'] if stats else 0
            result['failed'] = stats['failed'] if stats else 0
            result['answered'] = call_stats['answered'] if call_stats else 0
            result['pressed_one'] = call_stats['pressed_one'] if call_stats else 0
            if call_stats and call_stats['total_cost']:
                result['actual_cost'] = float(call_stats['total_cost'])
            
            return result
    
    async def get_user_campaigns(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's campaigns"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    c.id,
                    c.name,
                    c.total_numbers,
                    c.status,
                    c.actual_cost,
                    c.created_at,
                    ut.name as trunk_name,
                    l.list_name as lead_name,
                    (SELECT COUNT(*) FROM campaign_data cd WHERE cd.campaign_id = c.id AND cd.status NOT IN ('pending')) as completed
                FROM campaigns c
                LEFT JOIN user_trunks ut ON c.trunk_id = ut.id
                LEFT JOIN leads l ON c.lead_id = l.id
                WHERE c.user_id = $1
                ORDER BY c.created_at DESC
                LIMIT $2
            """, user_id, limit)
            
            return [dict(row) for row in rows]
    
    async def reset_campaign(self, campaign_id: int):
        """Reset a campaign - set all numbers back to pending, delete call logs"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Reset all campaign_data to pending
                await conn.execute("""
                    UPDATE campaign_data SET status = 'pending', called_at = NULL, call_id = NULL
                    WHERE campaign_id = $1
                """, campaign_id)
                # Delete call logs
                await conn.execute("DELETE FROM calls WHERE campaign_id = $1", campaign_id)
                # Reset campaign counters and status
                await conn.execute("""
                    UPDATE campaigns
                    SET status = 'paused', completed = 0, answered = 0, 
                        pressed_one = 0, failed = 0, actual_cost = 0,
                        started_at = NULL, completed_at = NULL
                    WHERE id = $1
                """, campaign_id)
    
    # =========================================================================
    # Voice Files (Per-User)
    # =========================================================================
    
    async def save_voice_file(self, user_id: int, name: str, duration: int = 0, file_path: str = None) -> int:
        """Save a voice file record"""
        async with self.pool.acquire() as conn:
            voice_id = await conn.fetchval("""
                INSERT INTO voice_files (user_id, name, duration, file_path)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, user_id, name, duration, file_path)
            return voice_id
    
    async def get_user_voice_files(self, user_id: int) -> List[Dict]:
        """Get user's voice files"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM voice_files
                WHERE user_id = $1
                ORDER BY created_at DESC
            """, user_id)
            return [dict(row) for row in rows]
    
    async def get_voice_file(self, voice_id: int) -> Optional[Dict]:
        """Get a single voice file"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM voice_files WHERE id = $1
            """, voice_id)
            return dict(row) if row else None
    
    # =========================================================================
    # Call Logs
    # =========================================================================
    
    async def get_campaign_call_logs(self, campaign_id: int, limit: int = 20) -> List[Dict]:
        """Get call logs for a campaign"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM calls
                WHERE campaign_id = $1
                ORDER BY started_at DESC
                LIMIT $2
            """, campaign_id, limit)
            return [dict(row) for row in rows]
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    async def get_user_stats(self, telegram_id: int) -> Dict:
        """Get user statistics"""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("""
                SELECT
                    credits,
                    total_spent,
                    total_calls,
                    created_at
                FROM users
                WHERE telegram_id = $1
            """, telegram_id)
            
            if not user:
                return {}
            
            user_id = await conn.fetchval("""
                SELECT id FROM users WHERE telegram_id = $1
            """, telegram_id)
            
            campaign_count = await conn.fetchval("""
                SELECT COUNT(*) FROM campaigns WHERE user_id = $1
            """, user_id)
            
            trunk_count = await conn.fetchval("""
                SELECT COUNT(*) FROM user_trunks WHERE user_id = $1
            """, user_id)
            
            lead_count = await conn.fetchval("""
                SELECT COUNT(*) FROM leads WHERE user_id = $1
            """, user_id)
            
            return {
                **dict(user),
                'campaign_count': campaign_count,
                'trunk_count': trunk_count,
                'lead_count': lead_count
            }
    
    # =========================================================================
    # Preset CIDs (shared utility)
    # =========================================================================
    
    async def get_preset_cids(self) -> List[Dict]:
        """Return preset caller IDs"""
        return [
            {"name": "US Default", "number": "12025551234"},
            {"name": "US Toll Free", "number": "18005551234"},
            {"name": "UK Default", "number": "442071234567"},
        ]

    # =========================================================================
    # Saved Caller IDs (Quick Switch)
    # =========================================================================
    
    async def ensure_saved_callerids_table(self):
        """Create saved_callerids table if it doesn't exist"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_callerids (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    caller_id VARCHAR(50) NOT NULL,
                    label VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, caller_id)
                )
            """)
    
    async def get_saved_callerids(self, user_id: int) -> list:
        """Get all saved caller IDs for a user"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, caller_id, label, created_at
                FROM saved_callerids
                WHERE user_id = $1
                ORDER BY created_at DESC
            """, user_id)
            return [dict(r) for r in rows]
    
    async def save_callerid(self, user_id: int, caller_id: str, label: str = None) -> int:
        """Save a caller ID for quick switching"""
        async with self.pool.acquire() as conn:
            cid_id = await conn.fetchval("""
                INSERT INTO saved_callerids (user_id, caller_id, label)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, caller_id) DO UPDATE SET label = $3
                RETURNING id
            """, user_id, caller_id, label)
            return cid_id
    
    async def get_saved_callerid(self, cid_id: int) -> dict:
        """Get a specific saved caller ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, user_id, caller_id, label
                FROM saved_callerids WHERE id = $1
            """, cid_id)
            return dict(row) if row else None
    
    async def delete_saved_callerid(self, cid_id: int):
        """Delete a saved caller ID"""
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM saved_callerids WHERE id = $1", cid_id)


# Global database instance
db = Database()
