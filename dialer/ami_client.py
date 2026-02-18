# =============================================================================
# Python Dialer - Asterisk AMI Client (Per-User Trunk Support)
# =============================================================================
# Handles call origination through Asterisk Manager Interface (AMI)
# Uses panoramisk for async AMI communication
# Supports dynamic per-user PJSIP endpoints
# =============================================================================

import asyncio
import logging
from typing import Dict, Optional
from panoramisk import Manager
import path_setup  # Must be before config import
from config import AMI_CONFIG, IVR_CONTEXT, DEFAULT_CALLER_ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AsteriskAMIClient:
    """Asterisk Manager Interface client for call origination (per-user trunk)"""
    
    def __init__(self):
        self.manager: Optional[Manager] = None
        self.connected = False
        self.db_pool = None  # Set by campaign_worker for event handlers
        
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
            logger.info("✅ Connected to Asterisk AMI")
            
            # Register event handlers
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
        trunk_endpoint: str,
        caller_id: Optional[str] = None,
        variables: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Originate a call through a user's specific PJSIP trunk
        
        Args:
            destination: Phone number to call
            trunk_endpoint: Per-user PJSIP endpoint name (e.g. user_5_trunk_1)
            caller_id: CallerID to display (optional)
            variables: Channel variables to set (optional)
            
        Returns:
            Unique call ID if successful, None if failed
        """
        if not self.connected:
            logger.error("Not connected to AMI")
            return None
        
        try:
            # Build channel string using user's specific trunk endpoint
            channel = f"PJSIP/{destination}@{trunk_endpoint}"
            
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
            
            # Add custom variables
            if variables:
                var_list = [f"{k}={v}" for k, v in variables.items()]
                action_params['Variable'] = ','.join(var_list)
            
            logger.info(f"📞 Originating call to {destination} via {trunk_endpoint}")
            logger.debug(f"Channel: {channel}, CallerID: {cid}")
            
            response = await self.manager.send_action(action_params)
            
            # panoramisk returns a list of Message objects
            if isinstance(response, list):
                resp = response[0] if response else None
            else:
                resp = response
            
            if resp and resp.response == 'Success':
                call_id = resp.headers.get('Uniqueid', resp.headers.get('UniqueID', ''))
                logger.info(f"✅ Call originated successfully - ID: {call_id}")
                return call_id
            else:
                msg = resp.headers.get('Message', 'Unknown error') if resp else 'No response'
                logger.error(f"❌ Failed to originate call: {msg}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Exception during call origination: {e}")
            return None
    
    async def on_hangup(self, manager, event):
        """Handle Hangup events - update campaign_data and calls"""
        call_id = event.get('Uniqueid', '')
        cause = event.get('Cause-txt', 'Unknown')
        cause_code = event.get('Cause', '')
        duration = int(event.get('Duration', 0) or 0)
        
        logger.info(f"📴 Call {call_id} hung up - Cause: {cause}")
        
        if self.db_pool and call_id:
            try:
                async with self.db_pool.acquire() as conn:
                    # Get the campaign_data_id from calls table
                    call_row = await conn.fetchrow("""
                        SELECT campaign_data_id, campaign_id FROM calls
                        WHERE call_id = $1
                    """, call_id)
                    
                    if call_row:
                        # Update calls table
                        await conn.execute("""
                            UPDATE calls
                            SET status = $1, hangup_cause = $2,
                                duration = $3, ended_at = NOW()
                            WHERE call_id = $4
                        """, cause or 'HANGUP', cause, duration, call_id)
                        
                        # Update campaign_data status based on hangup cause
                        # Normal hangup (cause 16) = completed, everything else = failed
                        data_status = 'completed' if cause_code in ('16', '') else 'failed'
                        await conn.execute("""
                            UPDATE campaign_data
                            SET status = $1
                            WHERE id = $2 AND status = 'dialing'
                        """, data_status, call_row['campaign_data_id'])
                        
                        logger.info(f"✅ Call {call_id} → campaign_data status: {data_status}")
            except Exception as e:
                logger.error(f"❌ Error updating hangup for {call_id}: {e}")
    
    async def on_dial_end(self, manager, event):
        """Handle DialEnd events - update call answer status"""
        call_id = event.get('Uniqueid', '')
        dial_status = event.get('DialStatus', 'Unknown')
        
        logger.info(f"📊 Dial ended for {call_id} - Status: {dial_status}")
        
        if self.db_pool and call_id:
            try:
                async with self.db_pool.acquire() as conn:
                    # Map Asterisk DialStatus to our call status
                    status_map = {
                        'ANSWER': 'ANSWER',
                        'BUSY': 'BUSY',
                        'NOANSWER': 'NO ANSWER',
                        'CANCEL': 'CANCEL',
                        'CONGESTION': 'CONGESTION',
                        'CHANUNAVAIL': 'FAILED',
                    }
                    call_status = status_map.get(dial_status, dial_status)
                    
                    await conn.execute("""
                        UPDATE calls
                        SET status = $1, answered_at = CASE WHEN $1 = 'ANSWER' THEN NOW() ELSE NULL END
                        WHERE call_id = $2
                    """, call_status, call_id)
                    
                    # If not answered, mark campaign_data as completed immediately
                    if dial_status != 'ANSWER':
                        await conn.execute("""
                            UPDATE campaign_data
                            SET status = 'completed'
                            WHERE id = (
                                SELECT campaign_data_id FROM calls WHERE call_id = $1
                            ) AND status = 'dialing'
                        """, call_id)
                        logger.info(f"📞 {call_id} not answered ({dial_status}) → slot freed")
            except Exception as e:
                logger.error(f"❌ Error updating dial_end for {call_id}: {e}")
    
    async def get_active_channels(self) -> int:
        """Get count of active channels"""
        if not self.connected:
            return 0
        
        try:
            response = await self.manager.send_action({
                'Action': 'CoreShowChannels'
            })
            if isinstance(response, list):
                resp = response[0] if response else None
            else:
                resp = response
            return int(resp.headers.get('ListItems', '0')) if resp else 0
        except Exception as e:
            logger.error(f"Error getting active channels: {e}")
            return 0
    
    async def check_trunk_status(self, endpoint_name: Optional[str] = None) -> bool:
        """Check if a specific PJSIP trunk is registered"""
        if not self.connected:
            return False
        
        try:
            response = await self.manager.send_action({
                'Action': 'PJSIPShowRegistrations'
            })
            
            if endpoint_name:
                return endpoint_name in str(response)
            return True
            
        except Exception as e:
            logger.error(f"Error checking trunk status: {e}")
            return False
    
    async def reload_pjsip(self) -> bool:
        """Reload PJSIP module after config changes"""
        if not self.connected:
            return False
        
        try:
            response = await self.manager.send_action({
                'Action': 'Command',
                'Command': 'pjsip reload'
            })
            logger.info("🔄 PJSIP reloaded")
            return True
        except Exception as e:
            logger.error(f"Error reloading PJSIP: {e}")
            return False


# =============================================================================
# Usage Example
# =============================================================================
async def main():
    """Example usage of AMI client with per-user trunk"""
    client = AsteriskAMIClient()
    
    connected = await client.connect()
    if not connected:
        print("Failed to connect to Asterisk")
        return
    
    # Originate a test call through a user-specific trunk
    call_id = await client.originate_call(
        destination="1234567890",
        trunk_endpoint="user_5_trunk_1",  # Per-user trunk endpoint
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
