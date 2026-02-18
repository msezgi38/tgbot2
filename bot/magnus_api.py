# =============================================================================
# MagnusBilling API Client (Bot 2 - Callix)
# =============================================================================
# Handles SIP account creation and management via MagnusBilling REST API
# API Docs: https://callix.pro/mbilling/index.php/rest/
# =============================================================================

import aiohttp
import logging
import hashlib
import random
import string
from typing import Dict, Optional, List

from config import MAGNUS_API_KEY, MAGNUS_API_SECRET, MAGNUS_API_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MagnusBillingAPI:
    """MagnusBilling REST API client"""
    
    def __init__(self):
        self.api_key = MAGNUS_API_KEY
        self.api_secret = MAGNUS_API_SECRET
        self.base_url = MAGNUS_API_URL
    
    def _get_auth_params(self) -> Dict:
        """Get authentication parameters for API requests"""
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret
        }
    
    def _generate_password(self, length: int = 16) -> str:
        """Generate a random SIP password"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(length))
    
    def _generate_username(self, prefix: str = "ivr") -> str:
        """Generate a unique SIP username"""
        suffix = ''.join(random.choices(string.digits, k=6))
        return f"{prefix}{suffix}"
    
    # =========================================================================
    # SIP User Operations
    # =========================================================================
    
    async def create_sip_user(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        callerid: Optional[str] = None,
        id_user: Optional[int] = None
    ) -> Dict:
        """
        Create a new SIP user account in MagnusBilling
        
        Args:
            username: SIP username (auto-generated if not provided)
            password: SIP password (auto-generated if not provided)
            callerid: Caller ID number
            id_user: MagnusBilling user ID to associate with
            
        Returns:
            Dict with success status and SIP credentials
        """
        if not username:
            username = self._generate_username()
        if not password:
            password = self._generate_password()
        
        params = {
            **self._get_auth_params(),
            "name": username,
            "accountcode": username,
            "secret": password,
            "host": "dynamic",
            "type": "friend",
            "context": "billing",
            "dtmfmode": "rfc2833",
            "insecure": "no",
            "nat": "force_rport,comedia",
            "qualify": "yes",
            "directmedia": "no",
            "transport": "udp",
            "allow": "ulaw,alaw,gsm,g729",
            "disallow": "all",
        }
        
        if callerid:
            params["callerid"] = callerid
        if id_user:
            params["id_user"] = str(id_user)
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}Sip/save"
                
                async with session.post(url, data=params, ssl=False) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('success', False):
                        sip_id = data.get('rows', {}).get('id') or data.get('id')
                        
                        result = {
                            'success': True,
                            'sip_id': sip_id,
                            'username': username,
                            'password': password,
                            'host': 'dynamic',
                            'message': 'SIP user created successfully'
                        }
                        logger.info(f"✅ SIP user created: {username}")
                        return result
                    else:
                        error_msg = data.get('msg') or data.get('message') or str(data)
                        logger.error(f"❌ Failed to create SIP user: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg
                        }
                        
        except Exception as e:
            logger.error(f"❌ Exception creating SIP user: {e}")
            return {'success': False, 'error': str(e)}
    
    async def list_sip_users(self, limit: int = 25) -> Dict:
        """List existing SIP users"""
        params = {
            **self._get_auth_params(),
            "page": "1",
            "limit": str(limit)
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}Sip/read"
                
                async with session.get(url, params=params, ssl=False) as response:
                    data = await response.json()
                    
                    if response.status == 200:
                        return {
                            'success': True,
                            'users': data.get('rows', []),
                            'count': data.get('count', 0)
                        }
                    else:
                        return {'success': False, 'error': str(data)}
                        
        except Exception as e:
            logger.error(f"❌ Exception listing SIP users: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_sip_user(self, sip_id: int) -> Dict:
        """Get a specific SIP user by ID"""
        params = {
            **self._get_auth_params(),
            "id": str(sip_id)
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}Sip/read"
                
                async with session.get(url, params=params, ssl=False) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('rows'):
                        return {
                            'success': True,
                            'user': data['rows'][0] if isinstance(data['rows'], list) else data['rows']
                        }
                    else:
                        return {'success': False, 'error': 'SIP user not found'}
                        
        except Exception as e:
            logger.error(f"❌ Exception getting SIP user: {e}")
            return {'success': False, 'error': str(e)}
    
    async def delete_sip_user(self, sip_id: int) -> Dict:
        """Delete a SIP user"""
        params = {
            **self._get_auth_params(),
            "id": str(sip_id)
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}Sip/destroy"
                
                async with session.post(url, data=params, ssl=False) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('success', False):
                        logger.info(f"✅ SIP user {sip_id} deleted")
                        return {'success': True}
                    else:
                        return {'success': False, 'error': str(data)}
                        
        except Exception as e:
            logger.error(f"❌ Exception deleting SIP user: {e}")
            return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # User (Customer) Operations
    # =========================================================================
    
    async def create_user(
        self,
        username: str,
        password: str,
        credit: float = 0.0,
        id_group: int = 3,                   # Default customer group
        callingcard_pin: Optional[str] = None
    ) -> Dict:
        """Create a new MagnusBilling user/customer"""
        params = {
            **self._get_auth_params(),
            "username": username,
            "password": password,
            "credit": str(credit),
            "id_group": str(id_group),
            "active": "1",
        }
        
        if callingcard_pin:
            params["callingcard_pin"] = callingcard_pin
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}User/save"
                
                async with session.post(url, data=params, ssl=False) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('success', False):
                        user_id = data.get('rows', {}).get('id') or data.get('id')
                        logger.info(f"✅ MB user created: {username} (ID: {user_id})")
                        return {
                            'success': True,
                            'user_id': user_id,
                            'username': username
                        }
                    else:
                        error_msg = data.get('msg') or data.get('message') or str(data)
                        return {'success': False, 'error': error_msg}
                        
        except Exception as e:
            logger.error(f"❌ Exception creating MB user: {e}")
            return {'success': False, 'error': str(e)}
    
    async def add_credit(self, user_id: int, credit: float) -> Dict:
        """Add credit to a MagnusBilling user"""
        params = {
            **self._get_auth_params(),
            "id": str(user_id),
            "credit": str(credit)
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}User/save"
                
                async with session.post(url, data=params, ssl=False) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('success', False):
                        logger.info(f"✅ Added {credit} credit to user {user_id}")
                        return {'success': True}
                    else:
                        return {'success': False, 'error': str(data)}
                        
        except Exception as e:
            logger.error(f"❌ Exception adding credit: {e}")
            return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # Trunk / Provider Operations
    # =========================================================================
    
    async def get_trunks(self) -> Dict:
        """List available trunks/providers"""
        params = {
            **self._get_auth_params(),
            "page": "1",
            "limit": "50"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}Trunk/read"
                
                async with session.get(url, params=params, ssl=False) as response:
                    data = await response.json()
                    
                    if response.status == 200:
                        return {
                            'success': True,
                            'trunks': data.get('rows', []),
                            'count': data.get('count', 0)
                        }
                    else:
                        return {'success': False, 'error': str(data)}
                        
        except Exception as e:
            logger.error(f"❌ Exception getting trunks: {e}")
            return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # Call Summary / CDR
    # =========================================================================
    
    async def get_call_summary(self, id_user: Optional[int] = None) -> Dict:
        """Get call summary/CDR"""
        params = {
            **self._get_auth_params(),
            "page": "1",
            "limit": "50"
        }
        
        if id_user:
            params["id_user"] = str(id_user)
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}CallSummaryPerDay/read"
                
                async with session.get(url, params=params, ssl=False) as response:
                    data = await response.json()
                    
                    if response.status == 200:
                        return {
                            'success': True,
                            'summary': data.get('rows', [])
                        }
                    else:
                        return {'success': False, 'error': str(data)}
                        
        except Exception as e:
            logger.error(f"❌ Exception getting call summary: {e}")
            return {'success': False, 'error': str(e)}
    
    # =========================================================================
    # Health Check
    # =========================================================================
    
    async def test_connection(self) -> bool:
        """Test API connection"""
        try:
            result = await self.list_sip_users(limit=1)
            if result['success']:
                logger.info("✅ MagnusBilling API connection successful")
                return True
            else:
                logger.error(f"❌ MagnusBilling API test failed: {result['error']}")
                return False
        except Exception as e:
            logger.error(f"❌ MagnusBilling API connection error: {e}")
            return False


# Global instance
magnus_api = MagnusBillingAPI()
