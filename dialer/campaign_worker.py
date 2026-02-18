# =============================================================================
# Campaign Worker - Async Call Processing Engine (Bot 2 - Callix)
# =============================================================================
# Processes campaigns using callix_trunk through Asterisk
# Connects to ivr_bot2 database
# =============================================================================

import path_setup  # noqa: F401 - adds bot/ to sys.path

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
import asyncpg

from ami_client import AsteriskAMIClient
from config import (
    DATABASE_URL,
    MAX_CONCURRENT_CALLS,
    DELAY_BETWEEN_CALLS,
    CALL_TIMEOUT_SECONDS,
    TRUNK_NAME
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CampaignWorker:
    """Manages campaign execution and call processing"""
    
    def __init__(self):
        self.ami_client = AsteriskAMIClient()
        self.db_pool: Optional[asyncpg.Pool] = None
        self.running = False
        self.active_calls = 0
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
        
    async def start(self):
        """Initialize and start campaign worker"""
        logger.info(f"🚀 Starting Campaign Worker (Callix - {TRUNK_NAME})...")
        
        # Connect to database
        self.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20
        )
        logger.info("✅ Database connected (ivr_bot2)")
        
        # Connect to Asterisk AMI
        connected = await self.ami_client.connect()
        if not connected:
            logger.error("❌ Failed to connect to Asterisk AMI")
            return False
        
        # Check trunk status
        trunk_ok = await self.ami_client.check_trunk_status()
        if trunk_ok:
            logger.info(f"✅ {TRUNK_NAME} trunk is registered")
        else:
            logger.warning(f"⚠️ {TRUNK_NAME} trunk may not be registered")
        
        self.running = True
        logger.info("✅ Campaign Worker (Callix) started successfully")
        
        # Start main processing loop
        await self.processing_loop()
        
        return True
    
    async def stop(self):
        """Stop campaign worker"""
        logger.info("🛑 Stopping Campaign Worker (Callix)...")
        self.running = False
        
        while self.active_calls > 0:
            logger.info(f"Waiting for {self.active_calls} active calls to complete...")
            await asyncio.sleep(5)
        
        await self.ami_client.disconnect()
        
        if self.db_pool:
            await self.db_pool.close()
        
        logger.info("✅ Campaign Worker (Callix) stopped")
    
    async def processing_loop(self):
        """Main processing loop"""
        while self.running:
            try:
                campaigns = await self.get_running_campaigns()
                
                if campaigns:
                    logger.info(f"📊 Found {len(campaigns)} running campaign(s)")
                    
                    for campaign in campaigns:
                        await self.process_campaign(campaign)
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"❌ Error in processing loop: {e}")
                await asyncio.sleep(10)
    
    async def get_running_campaigns(self) -> List[Dict]:
        """Fetch campaigns with status 'running' from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, user_id, name, caller_id, total_numbers, completed
                FROM campaigns
                WHERE status = 'running'
                AND completed < total_numbers
                ORDER BY created_at ASC
            """)
            
            return [dict(row) for row in rows]
    
    async def process_campaign(self, campaign: Dict):
        """Process a single campaign"""
        campaign_id = campaign['id']
        user_id = campaign['user_id']
        
        credits = await self.get_user_credits(user_id)
        if credits <= 0:
            logger.warning(f"⚠️ Campaign {campaign_id}: User {user_id} has insufficient credits")
            await self.pause_campaign(campaign_id, "Insufficient credits")
            return
        
        numbers = await self.get_pending_numbers(campaign_id, limit=10)
        
        if not numbers:
            logger.info(f"✅ Campaign {campaign_id} completed")
            await self.complete_campaign(campaign_id)
            return
        
        tasks = []
        for number_data in numbers:
            task = asyncio.create_task(
                self.dial_number(campaign, number_data)
            )
            tasks.append(task)
            await asyncio.sleep(DELAY_BETWEEN_CALLS)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def get_pending_numbers(self, campaign_id: int, limit: int = 10) -> List[Dict]:
        """Fetch pending phone numbers for a campaign"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, phone_number
                FROM campaign_data
                WHERE campaign_id = $1
                AND status = 'pending'
                ORDER BY id ASC
                LIMIT $2
            """, campaign_id, limit)
            
            return [dict(row) for row in rows]
    
    async def dial_number(self, campaign: Dict, number_data: Dict):
        """Dial a single number"""
        async with self.semaphore:
            campaign_id = campaign['id']
            campaign_data_id = number_data['id']
            phone_number = number_data['phone_number']
            caller_id = campaign.get('caller_id') or None
            
            try:
                self.active_calls += 1
                logger.info(f"📞 Dialing {phone_number} for campaign {campaign_id}")
                
                await self.update_number_status(campaign_data_id, 'dialing')
                
                call_id = await self.ami_client.originate_call(
                    destination=phone_number,
                    caller_id=caller_id,
                    variables={
                        'CAMPAIGN_ID': str(campaign_id),
                        'CAMPAIGN_DATA_ID': str(campaign_data_id)
                    }
                )
                
                if call_id:
                    await self.create_call_record(
                        campaign_id=campaign_id,
                        campaign_data_id=campaign_data_id,
                        call_id=call_id,
                        phone_number=phone_number,
                        caller_id=caller_id
                    )
                    
                    await self.update_number_call_id(campaign_data_id, call_id)
                    
                    logger.info(f"✅ Call initiated: {phone_number} → {call_id}")
                else:
                    logger.error(f"❌ Failed to dial {phone_number}")
                    await self.update_number_status(campaign_data_id, 'failed')
                    
            except Exception as e:
                logger.error(f"❌ Error dialing {phone_number}: {e}")
                await self.update_number_status(campaign_data_id, 'failed')
                
            finally:
                self.active_calls -= 1
    
    async def create_call_record(
        self,
        campaign_id: int,
        campaign_data_id: int,
        call_id: str,
        phone_number: str,
        caller_id: Optional[str]
    ):
        """Create initial call record in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO calls (
                    campaign_id, campaign_data_id, call_id,
                    phone_number, caller_id, status, started_at
                )
                VALUES ($1, $2, $3, $4, $5, 'INITIATED', $6)
            """, campaign_id, campaign_data_id, call_id,
                phone_number, caller_id, datetime.now())
    
    async def update_number_status(self, campaign_data_id: int, status: str):
        """Update campaign_data status"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE campaign_data
                SET status = $1, called_at = $2
                WHERE id = $3
            """, status, datetime.now(), campaign_data_id)
    
    async def update_number_call_id(self, campaign_data_id: int, call_id: str):
        """Update campaign_data with call_id"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE campaign_data
                SET call_id = $1
                WHERE id = $2
            """, call_id, campaign_data_id)
    
    async def get_user_credits(self, user_id: int) -> float:
        """Get user's available credits"""
        async with self.db_pool.acquire() as conn:
            credits = await conn.fetchval("""
                SELECT credits FROM users WHERE id = $1
            """, user_id)
            return float(credits or 0)
    
    async def pause_campaign(self, campaign_id: int, reason: str):
        """Pause a campaign"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE campaigns
                SET status = 'paused'
                WHERE id = $1
            """, campaign_id)
        
        logger.info(f"⏸️ Campaign {campaign_id} paused: {reason}")
    
    async def complete_campaign(self, campaign_id: int):
        """Mark campaign as completed"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE campaigns
                SET status = 'completed', completed_at = $1
                WHERE id = $2
            """, datetime.now(), campaign_id)
        
        logger.info(f"✅ Campaign {campaign_id} marked as completed")


# =============================================================================
# Main Entry Point
# =============================================================================
async def main():
    """Main function to run campaign worker"""
    worker = CampaignWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
