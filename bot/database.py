# =============================================================================
# Database Helper - PostgreSQL ORM (Bot 2 - Callix)
# =============================================================================
# Identical to Bot 1 - connects to separate database (ivr_bot2)
# =============================================================================

import asyncpg
from typing import Optional, Dict, List
from datetime import datetime
import logging

from config import DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    """Database interface for IVR Bot 2"""
    
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
            logger.info("✅ Database connected (ivr_bot2)")
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
    # Campaign Operations
    # =========================================================================
    
    async def create_campaign(
        self,
        user_id: int,
        name: str,
        caller_id: Optional[str] = None
    ) -> int:
        """Create new campaign"""
        async with self.pool.acquire() as conn:
            campaign_id = await conn.fetchval("""
                INSERT INTO campaigns (user_id, name, caller_id, status)
                VALUES ($1, $2, $3, 'draft')
                RETURNING id
            """, user_id, name, caller_id)
            return campaign_id
    
    async def add_campaign_numbers(
        self,
        campaign_id: int,
        phone_numbers: List[str]
    ) -> int:
        """Add phone numbers to campaign"""
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
    
    async def get_campaign_stats(self, campaign_id: int) -> Dict:
        """Get campaign statistics"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    name, total_numbers, completed, answered,
                    pressed_one, failed, status, actual_cost,
                    created_at, started_at
                FROM campaigns
                WHERE id = $1
            """, campaign_id)
            return dict(stats) if stats else {}
    
    async def get_user_campaigns(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's campaigns"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    id, name, total_numbers, completed,
                    pressed_one, status, actual_cost, created_at
                FROM campaigns
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, user_id, limit)
            return [dict(row) for row in rows]
    
    # =========================================================================
    # SIP Account Operations (MagnusBilling API)
    # =========================================================================
    
    async def save_sip_account(
        self,
        user_id: int,
        sip_username: str,
        sip_password: str,
        sip_id: int = None
    ) -> int:
        """Save auto-created SIP account to database"""
        async with self.pool.acquire() as conn:
            account_id = await conn.fetchval("""
                INSERT INTO sip_accounts (user_id, sip_id, sip_username, sip_password)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, user_id, sip_id, sip_username, sip_password)
            logger.info(f"📞 SIP account saved: {sip_username} for user {user_id}")
            return account_id
    
    async def get_user_sip_accounts(self, user_id: int) -> List[Dict]:
        """Get user's SIP accounts"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, sip_username, sip_password, sip_host, is_active, created_at
                FROM sip_accounts
                WHERE user_id = $1
                ORDER BY created_at DESC
            """, user_id)
            return [dict(row) for row in rows]

    # =========================================================================
    # Statistics
    # =========================================================================
    
    async def get_user_stats(self, telegram_id: int) -> Dict:
        """Get user statistics"""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("""
                SELECT credits, total_spent, total_calls, created_at
                FROM users
                WHERE telegram_id = $1
            """, telegram_id)
            
            if not user:
                return {}
            
            campaign_count = await conn.fetchval("""
                SELECT COUNT(*) FROM campaigns
                WHERE user_id = (
                    SELECT id FROM users WHERE telegram_id = $1
                )
            """, telegram_id)
            
            return {
                **dict(user),
                'campaign_count': campaign_count
            }


# Global database instance
db = Database()
