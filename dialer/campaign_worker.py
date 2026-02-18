# =============================================================================
# Campaign Worker - Async Call Processing Engine (Per-User Trunk)
# =============================================================================
# Manages campaign execution with per-user trunk routing:
# - Fetches running campaigns from database
# - Resolves user-specific PJSIP endpoints
# - Processes call queue with rate limiting
# - Monitors campaign progress
# =============================================================================

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime
import asyncpg

import path_setup  # Must be first - sets up path to tgbot2/bot/config.py

from ami_client import AsteriskAMIClient
from config import (
    DATABASE_URL, AMI_CONFIG, IVR_CONTEXT,
    MAX_CONCURRENT_CALLS, CALL_TIMEOUT_SECONDS,
    DELAY_BETWEEN_CALLS, TEST_MODE
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CampaignWorker:
    """Manages campaign execution with per-user trunk routing"""
    
    def __init__(self):
        self.ami_client = AsteriskAMIClient()
        self.db_pool: Optional[asyncpg.Pool] = None
        self.running = False
        self.active_calls = 0
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)
        
    async def start(self):
        """Initialize and start campaign worker"""
        logger.info("🚀 Starting Campaign Worker...")
        
        # Connect to database
        self.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20
        )
        logger.info("✅ Database connected")
        
        # Share db_pool with AMI client for event handlers
        self.ami_client.db_pool = self.db_pool
        
        # Connect to Asterisk AMI
        connected = await self.ami_client.connect()
        if not connected:
            logger.error("❌ Failed to connect to Asterisk AMI")
            return False
        
        self.running = True
        logger.info("✅ Campaign Worker started successfully")
        
        # Start main processing loop
        await self.processing_loop()
        
        return True
    
    async def stop(self):
        """Stop campaign worker"""
        logger.info("🛑 Stopping Campaign Worker...")
        self.running = False
        
        while self.active_calls > 0:
            logger.info(f"Waiting for {self.active_calls} active calls to complete...")
            await asyncio.sleep(5)
        
        await self.ami_client.disconnect()
        
        if self.db_pool:
            await self.db_pool.close()
        
        logger.info("✅ Campaign Worker stopped")
    
    async def processing_loop(self):
        """Main processing loop"""
        logger.info("🔄 Processing loop started")
        while self.running:
            try:
                logger.info("🔍 Checking for running campaigns...")
                campaigns = await self.get_running_campaigns()
                
                if campaigns:
                    logger.info(f"📊 Found {len(campaigns)} running campaign(s)")
                    
                    for campaign in campaigns:
                        await self.process_campaign(campaign)
                else:
                    logger.info("💤 No running campaigns found")
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"❌ Error in processing loop: {e}", exc_info=True)
                await asyncio.sleep(10)
    
    async def get_running_campaigns(self) -> List[Dict]:
        """Fetch running campaigns with their user trunk info"""
        async with self.db_pool.acquire() as conn:
            # Debug: verify which database we're connected to
            db_name = await conn.fetchval("SELECT current_database()")
            count = await conn.fetchval("SELECT COUNT(*) FROM campaigns WHERE status = 'running'")
            logger.info(f"🔍 DB={db_name}, running campaigns count={count}")
            
            rows = await conn.fetch("""
                SELECT 
                    c.id, c.user_id, c.name, c.caller_id, 
                    c.total_numbers, c.completed,
                    c.trunk_id, c.lead_id, c.country_code, c.cps,
                c.voice_file, c.outro_file,
                ut.pjsip_endpoint_name as trunk_endpoint,
                    ut.caller_id as trunk_caller_id,
                    ut.max_channels as trunk_max_channels,
                    ut.status as trunk_status
                FROM campaigns c
                LEFT JOIN user_trunks ut ON c.trunk_id = ut.id
                WHERE c.status = 'running'
                AND c.completed < c.total_numbers
                ORDER BY c.created_at ASC
            """)
            
            return [dict(row) for row in rows]
    
    async def process_campaign(self, campaign: Dict):
        """Process a single campaign using its user-specific trunk"""
        campaign_id = campaign['id']
        user_id = campaign['user_id']
        trunk_endpoint = campaign.get('trunk_endpoint')
        
        # Validate trunk is available
        if not trunk_endpoint:
            logger.warning(f"⚠️ Campaign {campaign_id}: No trunk assigned")
            await self.pause_campaign(campaign_id, "No SIP trunk assigned")
            return
        
        if campaign.get('trunk_status') != 'active':
            logger.warning(f"⚠️ Campaign {campaign_id}: Trunk is not active")
            await self.pause_campaign(campaign_id, "SIP trunk is not active")
            return
        
        # Check user has sufficient credits
        if not TEST_MODE:
            credits = await self.get_user_credits(user_id)
            if credits <= 0:
                logger.warning(f"⚠️ Campaign {campaign_id}: User {user_id} has insufficient credits")
                await self.pause_campaign(campaign_id, "Insufficient credits")
                return
        
        # Determine CallerID: campaign override > trunk default > global default
        caller_id = campaign.get('caller_id') or campaign.get('trunk_caller_id')
        country_code = campaign.get('country_code', '')
        campaign_cps = campaign.get('cps', MAX_CONCURRENT_CALLS)
        campaign_semaphore = asyncio.Semaphore(campaign_cps)
        
        # Count currently active (dialing) calls for this campaign
        active_dialing = await self.get_active_dialing_count(campaign_id)
        available_slots = campaign_cps - active_dialing
        
        if available_slots <= 0:
            logger.info(f"⏳ Campaign {campaign_id}: {active_dialing} calls active, waiting (CPS={campaign_cps})")
            return
        
        # Fetch pending numbers (only as many as available slots)
        numbers = await self.get_pending_numbers(campaign_id, limit=available_slots)
        
        if not numbers:
            # Check if there are still dialing calls in progress
            if active_dialing > 0:
                logger.info(f"⏳ Campaign {campaign_id}: no pending numbers, {active_dialing} calls still active")
                return
            logger.info(f"✅ Campaign {campaign_id} completed")
            await self.complete_campaign(campaign_id)
            return
        
        logger.info(f"📞 Campaign {campaign_id}: dialing {len(numbers)} numbers (CPS={campaign_cps})")
        
        # Process each number with campaign-specific concurrency
        tasks = []
        for number_data in numbers:
            # Prepend country code if set
            if country_code and not number_data['phone_number'].startswith(country_code):
                number_data['phone_number'] = country_code + number_data['phone_number']
            task = asyncio.create_task(
                self.dial_number(campaign, number_data, trunk_endpoint, caller_id)
            )
            tasks.append(task)
            await asyncio.sleep(DELAY_BETWEEN_CALLS)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def get_pending_numbers(self, campaign_id: int, limit: int = 10) -> List[Dict]:
        """Fetch pending phone numbers for a campaign (deduplicated)"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT ON (phone_number) id, phone_number
                FROM campaign_data
                WHERE campaign_id = $1
                AND status = 'pending'
                AND phone_number NOT IN (
                    SELECT phone_number FROM campaign_data
                    WHERE campaign_id = $1 AND status = 'dialing'
                )
                ORDER BY phone_number, id ASC
                LIMIT $2
            """, campaign_id, limit)
            
            return [dict(row) for row in rows]
    
    async def get_active_dialing_count(self, campaign_id: int) -> int:
        """Count how many numbers are currently being dialed for a campaign"""
        async with self.db_pool.acquire() as conn:
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM campaign_data
                WHERE campaign_id = $1 AND status = 'dialing'
            """, campaign_id)
            return count or 0
    
    async def dial_number(
        self,
        campaign: Dict,
        number_data: Dict,
        trunk_endpoint: str,
        caller_id: Optional[str]
    ):
        """Dial a single number using the user's specific trunk"""
        async with self.semaphore:
            campaign_id = campaign['id']
            campaign_data_id = number_data['id']
            phone_number = number_data['phone_number']
            
            try:
                self.active_calls += 1
                logger.info(f"📞 Dialing {phone_number} via {trunk_endpoint} for campaign {campaign_id}")
                
                await self.update_number_status(campaign_data_id, 'dialing')
                
                # Generate a unique call_id so we can track it in both DB and dialplan
                import uuid
                call_id = str(uuid.uuid4())
                
                # Asterisk Playback() expects path WITHOUT extension
                import os
                voice_file = campaign.get('voice_file', '') or ''
                if voice_file:
                    voice_file = os.path.splitext(voice_file)[0]
                
                outro_file = campaign.get('outro_file', '') or ''
                if outro_file:
                    outro_file = os.path.splitext(outro_file)[0]
                
                # Create call record BEFORE originating (so stats always have data)
                await self.create_call_record(
                    campaign_id=campaign_id,
                    campaign_data_id=campaign_data_id,
                    call_id=call_id,
                    phone_number=phone_number,
                    caller_id=caller_id,
                    trunk_endpoint=trunk_endpoint
                )
                await self.update_number_call_id(campaign_data_id, call_id)
                
                result = await self.ami_client.originate_call(
                    destination=phone_number,
                    trunk_endpoint=trunk_endpoint,
                    caller_id=caller_id,
                    variables={
                        'CAMPAIGN_ID': str(campaign_id),
                        'CAMPAIGN_DATA_ID': str(campaign_data_id),
                        'VOICE_FILE': voice_file,
                        'OUTRO_FILE': outro_file,
                        'CALL_ID': call_id
                    }
                )
                
                if result:
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
        caller_id: Optional[str],
        trunk_endpoint: Optional[str] = None
    ):
        """Create initial call record in database"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO calls (
                    campaign_id, campaign_data_id, call_id,
                    phone_number, caller_id, trunk_endpoint,
                    status, started_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, 'INITIATED', $7)
            """, campaign_id, campaign_data_id, call_id,
                phone_number, caller_id, trunk_endpoint, datetime.now())
    
    async def update_number_status(self, campaign_data_id: int, status: str):
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE campaign_data
                SET status = $1, called_at = $2
                WHERE id = $3
            """, status, datetime.now(), campaign_data_id)
    
    async def update_number_call_id(self, campaign_data_id: int, call_id: str):
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE campaign_data
                SET call_id = $1
                WHERE id = $2
            """, call_id, campaign_data_id)
    
    async def get_user_credits(self, user_id: int) -> float:
        async with self.db_pool.acquire() as conn:
            credits = await conn.fetchval("""
                SELECT credits FROM users WHERE id = $1
            """, user_id)
            return float(credits or 0)
    
    async def pause_campaign(self, campaign_id: int, reason: str):
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE campaigns
                SET status = 'paused'
                WHERE id = $1
            """, campaign_id)
        logger.info(f"⏸️ Campaign {campaign_id} paused: {reason}")
    
    async def complete_campaign(self, campaign_id: int):
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
    worker = CampaignWorker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
