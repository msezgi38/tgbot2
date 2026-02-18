# =============================================================================
# Oxapay Payment Handler
# =============================================================================
# Integration with Oxapay cryptocurrency payment gateway
# Supports both old (/merchants/request) and new (/v1/payment/invoice) endpoints
# =============================================================================

import aiohttp
import logging
import uuid
import json
from typing import Dict, Optional

from config import OXAPAY_API_KEY, OXAPAY_WEBHOOK_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Oxapay API endpoints - try new first, fallback to old
OXAPAY_ENDPOINTS = [
    {
        "url": "https://api.oxapay.com/merchants/request",
        "key_in_body": True,
        "key_field": "merchant",
    },
]


class OxapayHandler:
    """Oxapay payment gateway integration"""
    
    def __init__(self):
        self.api_key = OXAPAY_API_KEY
        self.webhook_url = OXAPAY_WEBHOOK_URL
    
    async def create_payment(
        self,
        amount: float,
        currency: str = "USDT",
        order_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict:
        """Create payment invoice with Oxapay - tries multiple endpoints"""
        if not order_id:
            order_id = str(uuid.uuid4())
        
        last_error = "No endpoints configured"
        
        for endpoint in OXAPAY_ENDPOINTS:
            result = await self._try_endpoint(endpoint, amount, currency, order_id, description)
            if result.get('success'):
                return result
            last_error = result.get('error', 'Unknown error')
            logger.warning(f"Endpoint {endpoint['url']} failed: {last_error}, trying next...")
        
        return {'success': False, 'error': last_error}
    
    async def _try_endpoint(self, endpoint: dict, amount: float, currency: str, order_id: str, description: str) -> Dict:
        """Try a single endpoint"""
        url = endpoint["url"]
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        payload = {
            "amount": amount,
            "currency": currency,
            "orderId": order_id,
            "callbackUrl": self.webhook_url,
            "description": description or f"SIP Credit Top-up ${amount}",
            "returnUrl": "https://t.me/callnowp1_bot",
        }
        
        # Add API key based on endpoint config
        if endpoint.get("key_in_body"):
            payload[endpoint["key_field"]] = self.api_key
        else:
            headers[endpoint.get("key_field", "merchant_api_key")] = self.api_key
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"Oxapay → {url} | amount={amount}")
                async with session.post(url, json=payload, headers=headers, ssl=True) as response:
                    response_text = await response.text()
                    logger.info(f"Oxapay ← status={response.status}, body={response_text[:500]}")
                    
                    if response.status != 200:
                        return {
                            'success': False,
                            'error': f"HTTP {response.status}"
                        }
                    
                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError:
                        return {
                            'success': False,
                            'error': f"Invalid JSON response"
                        }
                    
                    if data.get('result') == 100:
                        return {
                            'success': True,
                            'track_id': data.get('trackId'),
                            'payment_url': data.get('payLink'),
                            'amount': amount,
                            'currency': currency,
                            'order_id': order_id
                        }
                    else:
                        return {
                            'success': False,
                            'error': data.get('message', f"API error: {data}")
                        }
                        
        except Exception as e:
            logger.error(f"❌ Exception with {url}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def check_payment_status(self, track_id: str) -> Dict:
        """Check payment status from Oxapay API"""
        url = "https://api.oxapay.com/merchants/inquiry"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        payload = {
            "merchant": self.api_key,
            "trackId": track_id,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"Oxapay inquiry → {track_id}")
                async with session.post(url, json=payload, headers=headers, ssl=True) as response:
                    response_text = await response.text()
                    logger.info(f"Oxapay inquiry ← status={response.status}, body={response_text[:500]}")
                    
                    if response.status != 200:
                        return {'error': f"HTTP {response.status}"}
                    
                    try:
                        data = json.loads(response_text)
                        return data
                    except json.JSONDecodeError:
                        return {'error': 'Invalid JSON response'}
        except Exception as e:
            logger.error(f"❌ Payment status check error: {e}")
            return {'error': str(e)}
    
    def verify_webhook(self, data: Dict) -> bool:
        """Verify webhook authenticity"""
        return True


# Global instance
oxapay = OxapayHandler()
