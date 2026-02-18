# =============================================================================
# Oxapay Payment Handler (Bot 2 - Callix)
# =============================================================================

import aiohttp
import logging
import uuid
from typing import Dict, Optional

from config import OXAPAY_API_KEY, OXAPAY_API_URL, OXAPAY_WEBHOOK_URL, CREDIT_PACKAGES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OxapayHandler:
    """Oxapay payment gateway integration"""
    
    def __init__(self):
        self.api_key = OXAPAY_API_KEY
        self.api_url = OXAPAY_API_URL
        self.webhook_url = OXAPAY_WEBHOOK_URL
    
    async def create_payment(
        self,
        amount: float,
        currency: str = "USDT",
        order_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict:
        if not order_id:
            order_id = str(uuid.uuid4())
        
        payload = {
            "merchant": self.api_key,
            "amount": amount,
            "currency": currency,
            "orderId": order_id,
            "callbackUrl": self.webhook_url,
            "description": description or "Callix IVR Bot Credits",
            "returnUrl": "https://t.me/your_bot_username",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('result') == 100:
                        result = {
                            'success': True,
                            'track_id': data.get('trackId'),
                            'payment_url': data.get('payLink'),
                            'amount': amount,
                            'currency': currency,
                            'order_id': order_id
                        }
                        logger.info(f"✅ Payment created: {result['track_id']}")
                        return result
                    else:
                        error_msg = data.get('message', 'Unknown error')
                        logger.error(f"❌ Oxapay error: {error_msg}")
                        return {'success': False, 'error': error_msg}
                        
        except Exception as e:
            logger.error(f"❌ Exception creating payment: {e}")
            return {'success': False, 'error': str(e)}
    
    def verify_webhook(self, data: Dict) -> bool:
        return True
    
    def get_credit_package(self, package_id: str) -> Optional[Dict]:
        return CREDIT_PACKAGES.get(package_id)
    
    def list_packages(self) -> Dict:
        return CREDIT_PACKAGES


oxapay = OxapayHandler()
