# =============================================================================
# Python Dialer - Asterisk AMI Client (Bot 2 - Callix)
# =============================================================================
# Uses callix_trunk for outbound calls via sip.callix.pro
# =============================================================================

import asyncio
import logging
from typing import Dict, Optional
from panoramisk import Manager
from config import AMI_CONFIG, TRUNK_NAME, IVR_CONTEXT, DEFAULT_CALLER_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AsteriskAMIClient:
    """Asterisk Manager Interface client for call origination"""
    
    def __init__(self):
        self.manager: Optional[Manager] = None
        self.connected = False
        
    async def connect(self):
        """Establish connection to Asterisk AMI"""
        try:
            self.manager = Manager(
                host=AMI_CONFIG['host'],
                port=AMI_CONFIG['port'],
                username=AMI_CONFIG['username'],
                secret=AMI_CONFIG['secret'],
                ping_delay=10,
                ping_tries=3
            )
            
            await self.manager.connect()
            self.connected = True
            logger.info("✅ Connected to Asterisk AMI (Callix Bot)")
            
            self.manager.register_event('Hangup', self.on_hangup)
            self.manager.register_event('DialEnd', self.on_dial_end)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to AMI: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Close AMI connection"""
        if self.manager:
            await self.manager.close()
            self.connected = False
            logger.info("Disconnected from Asterisk AMI")
    
    async def originate_call(
        self,
        destination: str,
        caller_id: Optional[str] = None,
        variables: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Originate a call through Callix trunk
        
        Args:
            destination: Phone number to call
            caller_id: CallerID to display (optional)
            variables: Channel variables to set (optional)
            
        Returns:
            Unique call ID if successful, None if failed
        """
        if not self.connected:
            logger.error("Not connected to AMI")
            return None
        
        try:
            # Build channel string for Callix trunk
            channel = f"PJSIP/{destination}@{TRUNK_NAME}"
            
            cid = caller_id or DEFAULT_CALLER_ID
            
            action_params = {
                'Action': 'Originate',
                'Channel': channel,
                'Context': IVR_CONTEXT,
                'Exten': destination,
                'Priority': '1',
                'CallerID': cid,
                'Timeout': '30000',
                'Async': 'true',
            }
            
            if variables:
                var_list = [f"{k}={v}" for k, v in variables.items()]
                action_params['Variable'] = ','.join(var_list)
            
            logger.info(f"📞 Originating call to {destination} via {TRUNK_NAME}")
            logger.debug(f"Channel: {channel}, CallerID: {cid}")
            
            response = await self.manager.send_action(action_params)
            
            if response.success:
                call_id = response.headers.get('UniqueID', '')
                logger.info(f"✅ Call originated successfully - ID: {call_id}")
                return call_id
            else:
                logger.error(f"❌ Failed to originate call: {response.headers.get('Message', 'Unknown error')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception during call origination: {e}")
            return None
    
    async def on_hangup(self, manager, event):
        """Handle Hangup events"""
        call_id = event.get('Uniqueid', '')
        cause = event.get('Cause-txt', 'Unknown')
        logger.info(f"📴 Call {call_id} hung up - Cause: {cause}")
    
    async def on_dial_end(self, manager, event):
        """Handle DialEnd events"""
        call_id = event.get('Uniqueid', '')
        status = event.get('DialStatus', 'Unknown')
        logger.info(f"📊 Dial ended for {call_id} - Status: {status}")
    
    async def get_active_channels(self) -> int:
        """Get count of active channels"""
        if not self.connected:
            return 0
        
        try:
            response = await self.manager.send_action({
                'Action': 'CoreShowChannels'
            })
            return int(response.headers.get('ListItems', '0'))
            
        except Exception as e:
            logger.error(f"Error getting active channels: {e}")
            return 0
    
    async def check_trunk_status(self) -> bool:
        """Check if Callix trunk is registered"""
        if not self.connected:
            return False
        
        try:
            response = await self.manager.send_action({
                'Action': 'PJSIPShowRegistrations'
            })
            return TRUNK_NAME in str(response)
            
        except Exception as e:
            logger.error(f"Error checking trunk status: {e}")
            return False


# =============================================================================
# Usage Example
# =============================================================================
async def main():
    """Example usage of AMI client"""
    client = AsteriskAMIClient()
    
    connected = await client.connect()
    if not connected:
        print("Failed to connect to Asterisk")
        return
    
    trunk_ok = await client.check_trunk_status()
    print(f"Callix trunk status: {'✅ Registered' if trunk_ok else '❌ Not registered'}")
    
    call_id = await client.originate_call(
        destination="1234567890",
        caller_id="9876543210",
        variables={
            "CAMPAIGN_ID": "123",
            "USER_ID": "456"
        }
    )
    
    if call_id:
        print(f"Call originated with ID: {call_id}")
    
    await asyncio.sleep(60)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
