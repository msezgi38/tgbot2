# =============================================================================
# Mock Database for UI Testing (User-Scoped PJSIP)
# =============================================================================
# Dummy data version - No PostgreSQL required
# Supports per-user trunks, leads, campaigns
# =============================================================================

from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockDatabase:
    """Mock database with sample data for UI testing"""
    
    def __init__(self):
        self.connected = False
        self.users = {}
        self.campaigns = {}
        self.next_campaign_id = 100
        
        # Per-user trunks
        self.trunks = {}
        self.next_trunk_id = 1
        
        # Per-user leads
        self.leads_store = {}
        self.next_lead_id = 1
        self.lead_numbers_store = {}
        self.next_lead_number_id = 1
        
        # Voice files
        self.voice_files = {}
        self.next_voice_id = 1
        
        # Preset CIDs
        self.preset_cids = []
        
    async def connect(self):
        self.connected = True
        logger.info("✅ Mock Database connected (UI Test Mode)")
        return True
    
    async def close(self):
        self.connected = False
    
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
        if telegram_id not in self.users:
            self.users[telegram_id] = {
                'id': len(self.users) + 1,
                'telegram_id': telegram_id,
                'username': username,
                'first_name': first_name or 'Test User',
                'last_name': last_name,
                'balance': 22.60,
                'credits': 22.60,
                'total_spent': 234.50,
                'total_calls': 567,
                'caller_id': '18889092337',
                'country_code': '+1',
                'available_lines': 112,
                'lines_used': 437,
                'system_status': 'Ready',
                'is_active': True,
                'created_at': datetime.now() - timedelta(days=30),
                'last_active': datetime.now()
            }
            
            # Create sample trunks for new user
            user_id = self.users[telegram_id]['id']
            await self._create_sample_trunks(user_id)
            await self._create_sample_leads(user_id)
            
            logger.info(f"👤 Mock user created: {telegram_id} ({username})")
        
        return self.users[telegram_id]
    
    async def get_all_users(self):
        """Get all registered users"""
        return list(self.users.values())
    
    async def _create_sample_trunks(self, user_id: int):
        """No sample trunks - users add their own"""
        pass
    
    async def _create_sample_leads(self, user_id: int):
        """No sample leads - users add their own"""
        pass
    
    async def get_user_credits(self, telegram_id: int) -> float:
        user = await self.get_or_create_user(telegram_id)
        return user['credits']
    
    async def add_credits(self, telegram_id: int, amount: float) -> float:
        user = await self.get_or_create_user(telegram_id)
        user['credits'] += amount
        user['balance'] += amount
        return user['credits']
    
    async def set_caller_id(self, telegram_id: int, caller_id: str) -> bool:
        user = await self.get_or_create_user(telegram_id)
        user['caller_id'] = caller_id
        return True
    
    async def validate_cid(self, cid: str) -> tuple:
        clean_cid = ''.join(filter(str.isdigit, cid))
        if len(clean_cid) < 10 or len(clean_cid) > 15:
            return False, "CID must be 10-15 digits"
        return True, "CID validated successfully"
    
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
        trunk_id = self.next_trunk_id
        self.next_trunk_id += 1
        
        endpoint_name = f"user_{user_id}_trunk_{trunk_id}"
        trunk = {
            'id': trunk_id,
            'user_id': user_id,
            'name': name,
            'sip_host': sip_host,
            'sip_port': sip_port,
            'sip_username': sip_username,
            'sip_password': sip_password,
            'transport': transport,
            'codecs': codecs,
            'caller_id': caller_id,
            'max_channels': max_channels,
            'status': 'active',
            'pjsip_endpoint_name': endpoint_name,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
        }
        self.trunks[trunk_id] = trunk
        logger.info(f"🔌 Trunk created: {endpoint_name}")
        return trunk
    
    async def get_user_trunks(self, user_id: int) -> List[Dict]:
        return [t for t in self.trunks.values() if t['user_id'] == user_id]
    
    async def get_trunk(self, trunk_id: int) -> Optional[Dict]:
        return self.trunks.get(trunk_id)
    
    async def update_trunk(self, trunk_id: int, **kwargs) -> bool:
        if trunk_id in self.trunks:
            for k, v in kwargs.items():
                if k in self.trunks[trunk_id]:
                    self.trunks[trunk_id][k] = v
            self.trunks[trunk_id]['updated_at'] = datetime.now()
            return True
        return False
    
    async def delete_trunk(self, trunk_id: int) -> bool:
        if trunk_id in self.trunks:
            del self.trunks[trunk_id]
            return True
        return False
    
    async def get_active_trunks(self) -> List[Dict]:
        return [t for t in self.trunks.values() if t['status'] == 'active']
    
    # =========================================================================
    # Lead Operations (Per-User)
    # =========================================================================
    
    async def create_lead_list(
        self,
        user_id: int,
        list_name: str,
        description: Optional[str] = None
    ) -> int:
        lead_id = self.next_lead_id
        self.next_lead_id += 1
        
        self.leads_store[lead_id] = {
            'id': lead_id,
            'user_id': user_id,
            'list_name': list_name,
            'description': description,
            'total_numbers': 0,
            'available_numbers': 0,
            'created_at': datetime.now(),
        }
        logger.info(f"📋 Lead list created: {list_name}")
        return lead_id
    
    async def add_lead_numbers(self, lead_id: int, phone_numbers: List[str]) -> int:
        count = len(phone_numbers)
        if lead_id in self.leads_store:
            self.leads_store[lead_id]['total_numbers'] += count
            self.leads_store[lead_id]['available_numbers'] += count
        
        for num in phone_numbers:
            num_id = self.next_lead_number_id
            self.next_lead_number_id += 1
            self.lead_numbers_store[num_id] = {
                'id': num_id,
                'lead_id': lead_id,
                'phone_number': num,
                'status': 'available',
                'times_used': 0,
            }
        
        return count
    
    async def get_user_leads(self, user_id: int) -> List[Dict]:
        return [l for l in self.leads_store.values() if l['user_id'] == user_id]
    
    async def get_lead(self, lead_id: int) -> Optional[Dict]:
        return self.leads_store.get(lead_id)
    
    async def get_lead_numbers(self, lead_id: int, status: str = 'available', limit: int = 100) -> List[Dict]:
        numbers = [n for n in self.lead_numbers_store.values() 
                   if n['lead_id'] == lead_id and n['status'] == status]
        return numbers[:limit]
    
    async def delete_lead_list(self, lead_id: int) -> bool:
        if lead_id in self.leads_store:
            # Remove numbers too
            to_remove = [nid for nid, n in self.lead_numbers_store.items() if n['lead_id'] == lead_id]
            for nid in to_remove:
                del self.lead_numbers_store[nid]
            del self.leads_store[lead_id]
            return True
        return False
    
    async def copy_leads_to_campaign(self, campaign_id: int, lead_id: int) -> int:
        """Mock: copy leads to campaign data"""
        if lead_id not in self.leads_store:
            return 0
        lead = self.leads_store[lead_id]
        count = lead.get('available_numbers', 0)
        if campaign_id in self.campaigns:
            self.campaigns[campaign_id]['total_numbers'] = count
        return count
    
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
        cps: int = 5
    ) -> int:
        campaign_id = self.next_campaign_id
        self.next_campaign_id += 1
        
        trunk_name = None
        if trunk_id and trunk_id in self.trunks:
            trunk_name = self.trunks[trunk_id]['name']
        
        lead_name = None
        if lead_id and lead_id in self.leads_store:
            lead_name = self.leads_store[lead_id]['list_name']
        
        self.campaigns[campaign_id] = {
            'id': campaign_id,
            'user_id': user_id,
            'name': name,
            'trunk_id': trunk_id,
            'lead_id': lead_id,
            'caller_id': caller_id,
            'country_code': country_code,
            'cps': cps,
            'trunk_name': trunk_name,
            'lead_name': lead_name,
            'total_numbers': 0,
            'completed': 0,
            'answered': 0,
            'pressed_one': 0,
            'failed': 0,
            'status': 'draft',
            'estimated_cost': 0.00,
            'actual_cost': 0.00,
            'created_at': datetime.now(),
            'started_at': None,
            'completed_at': None
        }
        return campaign_id
    
    async def add_campaign_numbers(self, campaign_id: int, phone_numbers: List[str]) -> int:
        if campaign_id in self.campaigns:
            count = len(phone_numbers)
            self.campaigns[campaign_id]['total_numbers'] = count
            self.campaigns[campaign_id]['estimated_cost'] = count * 1.0
        return len(phone_numbers)
    
    async def start_campaign(self, campaign_id: int) -> bool:
        if campaign_id in self.campaigns:
            camp = self.campaigns[campaign_id]
            camp['status'] = 'running'
            camp['started_at'] = datetime.now()
            # Copy leads if linked
            if camp.get('lead_id') and camp['total_numbers'] == 0:
                await self.copy_leads_to_campaign(campaign_id, camp['lead_id'])
        return True
    
    async def stop_campaign(self, campaign_id: int) -> bool:
        if campaign_id in self.campaigns:
            self.campaigns[campaign_id]['status'] = 'paused'
        return True
    
    async def get_campaign(self, campaign_id: int) -> Optional[Dict]:
        return self.campaigns.get(campaign_id)
    
    async def get_campaign_stats(self, campaign_id: int) -> Dict:
        return self.campaigns.get(campaign_id, {})
    
    async def get_user_campaigns(self, user_id: int, limit: int = 10) -> List[Dict]:
        sample_campaigns = [
            {
                'id': 1, 'name': 'Product Launch 2026', 'total_numbers': 100,
                'completed': 85, 'pressed_one': 28, 'status': 'running',
                'actual_cost': 14.50, 'trunk_name': 'MagnusBilling #1',
                'lead_name': 'US Contacts Jan 2026',
                'created_at': datetime.now() - timedelta(hours=2)
            },
            {
                'id': 2, 'name': 'Lead Generation Q1', 'total_numbers': 250,
                'completed': 250, 'pressed_one': 67, 'status': 'completed',
                'actual_cost': 42.30, 'trunk_name': 'VoIP.ms Trunk',
                'lead_name': 'UK Prospects',
                'created_at': datetime.now() - timedelta(days=3)
            },
            {
                'id': 3, 'name': 'Customer Survey', 'total_numbers': 50,
                'completed': 12, 'pressed_one': 4, 'status': 'paused',
                'actual_cost': 2.80, 'trunk_name': 'MagnusBilling #1',
                'lead_name': 'VIP Customers',
                'created_at': datetime.now() - timedelta(days=1)
            },
        ]
        
        for campaign in self.campaigns.values():
            if campaign['user_id'] == user_id:
                sample_campaigns.append(campaign)
        
        return sample_campaigns[:limit]
    
    # =========================================================================
    # Voice Files
    # =========================================================================
    
    async def get_user_voice_files(self, user_id: int) -> List[Dict]:
        return list(self.voice_files.values())
    
    async def save_voice_file(self, user_id: int, name: str, duration: int = 30) -> int:
        voice_id = self.next_voice_id
        self.next_voice_id += 1
        self.voice_files[voice_id] = {
            'id': voice_id, 'name': name, 'duration': duration,
            'uploaded_at': datetime.now()
        }
        return voice_id
    
    async def get_voice_file(self, voice_id: int) -> Dict:
        return self.voice_files.get(voice_id, {})
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    async def get_user_stats(self, telegram_id: int) -> Dict:
        user = await self.get_or_create_user(telegram_id)
        user_id = user['id']
        trunk_count = len([t for t in self.trunks.values() if t['user_id'] == user_id])
        lead_count = len([l for l in self.leads_store.values() if l['user_id'] == user_id])
        
        return {
            'credits': user['credits'],
            'total_spent': user['total_spent'],
            'total_calls': user['total_calls'],
            'created_at': user['created_at'],
            'campaign_count': 4,
            'trunk_count': trunk_count,
            'lead_count': lead_count,
        }
    
    # =========================================================================
    # Payment Operations (Mock)
    # =========================================================================
    
    async def create_payment(self, user_id, track_id, amount, credits, currency="USDT", payment_url=None) -> int:
        logger.info(f"💳 Mock payment created: {credits} credits for ${amount}")
        return 1
    
    async def confirm_payment(self, track_id, tx_hash=None) -> bool:
        return True
    
    # =========================================================================
    # Caller ID & Misc
    # =========================================================================
    
    async def get_preset_cids(self) -> List[Dict]:
        return self.preset_cids
    
    async def get_caller_id(self, telegram_id: int) -> str:
        user = await self.get_or_create_user(telegram_id)
        return user.get('caller_id', '18889092337')
    
    async def get_balance(self, telegram_id: int) -> float:
        user = await self.get_or_create_user(telegram_id)
        return user.get('balance', 0.0)
    
    async def get_campaign_call_logs(self, campaign_id: int, limit: int = 50) -> List[Dict]:
        return [
            {'phone_number': '+1234567890', 'status': 'pressed_one', 'answered': True, 'pressed_one': True, 'duration': 45, 'cost': 0.75, 'timestamp': datetime.now() - timedelta(minutes=5)},
            {'phone_number': '+1234567891', 'status': 'answered', 'answered': True, 'pressed_one': False, 'duration': 30, 'cost': 0.50, 'timestamp': datetime.now() - timedelta(minutes=10)},
            {'phone_number': '+1234567892', 'status': 'no_answer', 'answered': False, 'pressed_one': False, 'duration': 0, 'cost': 0.10, 'timestamp': datetime.now() - timedelta(minutes=15)},
            {'phone_number': '+1234567893', 'status': 'failed', 'answered': False, 'pressed_one': False, 'duration': 0, 'cost': 0.05, 'timestamp': datetime.now() - timedelta(minutes=20)},
        ][:limit]


# Global mock database instance
db = MockDatabase()
