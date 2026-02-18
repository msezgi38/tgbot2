# =============================================================================
# MagnusBilling API Client (Python)
# =============================================================================
# Reverse-engineered from magnussolution/magnusbilling-api PHP wrapper
# REST API: POST {base_url}/index.php/{module}/{action}
# Auth: API key + HMAC-SHA512 signature
# =============================================================================

import time
import hmac
import hashlib
import json
import logging
import aiohttp
from urllib.parse import urlencode

from config import MAGNUSBILLING_URL, MAGNUSBILLING_API_KEY, MAGNUSBILLING_API_SECRET

logger = logging.getLogger(__name__)


class MagnusBillingClient:
    """Python client for MagnusBilling REST API"""

    def __init__(self, url=None, api_key=None, api_secret=None):
        self.url = url or MAGNUSBILLING_URL
        self.api_key = api_key or MAGNUSBILLING_API_KEY
        self.api_secret = api_secret or MAGNUSBILLING_API_SECRET

    async def _query(self, params: dict) -> dict:
        """Execute API request with HMAC-SHA512 authentication"""
        module = params.get('module', '')
        action = params.get('action', '')

        # Generate nonce (matching PHP: microtime nonce)
        nonce = str(int(time.time() * 1000000))
        params['nonce'] = nonce

        # Build POST data and sign
        post_data = urlencode(params)
        sign = hmac.new(
            self.api_secret.encode('utf-8'),
            post_data.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        headers = {
            'Key': self.api_key,
            'Sign': sign,
        }

        endpoint = f"{self.url}/index.php/{module}/{action}"

        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, data=params, headers=headers, ssl=False) as resp:
                text = await resp.text()
                try:
                    result = json.loads(text)
                    return result
                except json.JSONDecodeError:
                    logger.error(f"MagnusBilling API invalid response: {text[:200]}")
                    return {"success": False, "error": text[:200]}

    # =========================================================================
    # User Management
    # =========================================================================

    async def create_user(self, username: str, password: str, credit: float = 0,
                          firstname: str = "", email: str = "") -> dict:
        """Create a new MagnusBilling user (automatically creates SIP account)"""
        data = {
            'module': 'user',
            'action': 'save',
            'createUser': 1,
            'id': 0,
            'username': username,
            'password': password,
            'active': 1,
            'credit': credit,
        }
        if firstname:
            data['firstname'] = firstname
        if email:
            data['email'] = email

        result = await self._query(data)
        logger.info(f"📞 MagnusBilling create_user({username}): {result}")
        return result

    async def get_user_by_username(self, username: str) -> dict:
        """Read user info by username"""
        filter_data = json.dumps([{
            "type": "string",
            "field": "username",
            "value": username,
            "comparison": "eq"
        }])

        result = await self._query({
            'module': 'user',
            'action': 'read',
            'page': 1,
            'start': 0,
            'limit': 1,
            'filter': filter_data,
        })
        return result

    async def get_user_id(self, username: str) -> int:
        """Get MagnusBilling user ID by username"""
        result = await self.get_user_by_username(username)
        if result.get('rows') and len(result['rows']) > 0:
            return result['rows'][0]['id']
        return None

    async def get_user_balance(self, username: str) -> float:
        """Get user credit balance"""
        result = await self.get_user_by_username(username)
        if result.get('rows') and len(result['rows']) > 0:
            return float(result['rows'][0].get('credit', 0))
        return 0.0

    async def add_credit(self, user_id: int, amount: float, description: str = "Credit from TG Bot") -> dict:
        """Add credit/refill to a user"""
        result = await self._query({
            'module': 'refill',
            'action': 'save',
            'id': 0,
            'id_user': user_id,
            'credit': amount,
            'payment': 1,
            'description': description,
        })
        logger.info(f"💰 MagnusBilling add_credit(user_id={user_id}, amount={amount}): {result}")
        return result

    async def delete_user(self, user_id: int) -> dict:
        """Delete a MagnusBilling user"""
        result = await self._query({
            'module': 'user',
            'action': 'destroy',
            'id': user_id,
        })
        logger.info(f"🗑 MagnusBilling delete_user({user_id}): {result}")
        return result

    async def update_user(self, user_id: int, data: dict) -> dict:
        """Update user fields"""
        data['module'] = 'user'
        data['action'] = 'save'
        data['id'] = user_id
        result = await self._query(data)
        return result

    # =========================================================================
    # SIP Account Info
    # =========================================================================

    async def get_sip_account(self, username: str) -> dict:
        """Get SIP account details for a user"""
        filter_data = json.dumps([{
            "type": "string",
            "field": "username",
            "value": username,
            "comparison": "eq"
        }])

        result = await self._query({
            'module': 'sip',
            'action': 'read',
            'page': 1,
            'start': 0,
            'limit': 1,
            'filter': filter_data,
        })
        return result

    async def get_plans(self) -> list:
        """Get all available billing plans"""
        result = await self._query({
            'module': 'plan',
            'action': 'read',
            'page': 1,
            'start': 0,
            'limit': 100,
        })
        return result.get('rows', [])

    async def change_plan(self, user_id: int, plan_id: int) -> dict:
        """Change user's billing plan"""
        result = await self._query({
            'module': 'user',
            'action': 'save',
            'id': user_id,
            'id_plan': plan_id,
        })
        logger.info(f"📋 MagnusBilling change_plan(user_id={user_id}, plan_id={plan_id}): {result}")
        return result

    async def update_callerid(self, user_id: int, callerid: str) -> dict:
        """Update SIP account caller ID (via sip module, like PHP update_sip_user.php)"""
        # First get the SIP account ID for this user
        sip_id = await self.get_sip_id(user_id)
        if not sip_id:
            return {"success": False, "error": "SIP account not found for this user"}
        
        result = await self._query({
            'module': 'sip',
            'action': 'save',
            'id': sip_id,
            'callerid': callerid,
        })
        logger.info(f"📞 MagnusBilling update_callerid(sip_id={sip_id}, cid={callerid}): {result}")
        return result

    async def get_sip_id(self, user_id: int) -> int:
        """Get SIP account ID for a MagnusBilling user"""
        filter_data = json.dumps([{
            "type": "numeric",
            "field": "id_user",
            "value": user_id,
            "comparison": "eq"
        }])
        
        result = await self._query({
            'module': 'sip',
            'action': 'read',
            'page': 1,
            'start': 0,
            'limit': 1,
            'filter': filter_data,
        })
        
        if result.get('rows') and len(result['rows']) > 0:
            return result['rows'][0]['id']
        return None
    
    async def get_sip_details(self, user_id: int) -> dict:
        """Get full SIP account details by MagnusBilling user ID"""
        filter_data = json.dumps([{
            "type": "numeric",
            "field": "id_user",
            "value": user_id,
            "comparison": "eq"
        }])
        
        result = await self._query({
            'module': 'sip',
            'action': 'read',
            'page': 1,
            'start': 0,
            'limit': 25,
            'filter': filter_data,
        })
        
        logger.info(f"SIP details for user_id={user_id}: {result}")
        return result

    async def update_sip(self, sip_id: int, data: dict) -> dict:
        """Update SIP account fields (name, defaultuser, callerid, host, secret)"""
        data['module'] = 'sip'
        data['action'] = 'save'
        data['id'] = sip_id
        result = await self._query(data)
        logger.info(f"📞 MagnusBilling update_sip(sip_id={sip_id}): {result}")
        return result

    # =========================================================================
    # Test Connection
    # =========================================================================

    async def test_connection(self) -> bool:
        """Test if API connection works"""
        try:
            result = await self._query({
                'module': 'user',
                'action': 'read',
                'page': 1,
                'start': 0,
                'limit': 1,
            })
            if 'rows' in result:
                logger.info("✅ MagnusBilling API connection successful")
                return True
            else:
                logger.error(f"❌ MagnusBilling API unexpected response: {result}")
                return False
        except Exception as e:
            logger.error(f"❌ MagnusBilling API connection failed: {e}")
            return False


# Singleton instance
magnus = MagnusBillingClient()
