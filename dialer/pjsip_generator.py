# =============================================================================
# PJSIP Dynamic Config Generator (Per-User Trunks)
# =============================================================================
# Reads active user_trunks from the database and generates pjsip_users.conf
# Then triggers Asterisk to reload the PJSIP module
# =============================================================================

import asyncio
import asyncpg
import logging
import os
import subprocess
from typing import List, Dict

from config import DATABASE_URL, PJSIP_CONFIG_DIR, PJSIP_USERS_CONF, ASTERISK_RELOAD_CMD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PJSIPGenerator:
    """Generates dynamic PJSIP config from user_trunks table"""
    
    def __init__(self):
        self.db_pool = None
    
    async def connect(self):
        """Connect to database"""
        self.db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        logger.info("✅ Database connected for PJSIP generation")
    
    async def close(self):
        """Close database connection"""
        if self.db_pool:
            await self.db_pool.close()
    
    async def get_active_trunks(self) -> List[Dict]:
        """Fetch all active trunks from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    ut.id, ut.user_id, ut.name,
                    ut.sip_host, ut.sip_port, ut.sip_username, ut.sip_password,
                    ut.transport, ut.codecs, ut.pjsip_endpoint_name,
                    u.username as owner_username
                FROM user_trunks ut
                JOIN users u ON ut.user_id = u.id
                WHERE ut.status = 'active'
                ORDER BY ut.id ASC
            """)
            return [dict(row) for row in rows]
    
    def generate_trunk_config(self, trunk: Dict) -> str:
        """Generate PJSIP config block for a single trunk"""
        ep = trunk['pjsip_endpoint_name']
        host = trunk['sip_host']
        port = trunk['sip_port'] or 5060
        user = trunk['sip_username']
        password = trunk['sip_password']
        transport = f"transport-{trunk['transport'] or 'udp'}"
        codecs = trunk['codecs'] or 'ulaw,alaw,gsm'
        owner = trunk['owner_username'] or f"user_{trunk['user_id']}"
        
        config = f"""; === {ep} ({trunk['name']} | Owner: {owner}) ===

[{ep}]
type=registration
transport={transport}
outbound_auth={ep}_auth
server_uri=sip:{host}:{port}
client_uri=sip:{user}@{host}

[{ep}_auth]
type=auth
auth_type=userpass
username={user}
password={password}

[{ep}]
type=aor
contact=sip:{host}:{port}

[{ep}]
type=endpoint
transport={transport}
context=press-one-ivr
outbound_auth={ep}_auth
aors={ep}
from_user={user}
allow=!all,{codecs}
direct_media=no

"""
        return config
    
    async def generate_config(self) -> str:
        """Generate full PJSIP users config from all active trunks"""
        trunks = await self.get_active_trunks()
        
        header = f"""; =============================================================================
; PJSIP User Trunks - AUTO-GENERATED ({len(trunks)} trunks)
; =============================================================================
; DO NOT EDIT MANUALLY - This file is regenerated from the database
; =============================================================================

"""
        config = header
        
        for trunk in trunks:
            config += self.generate_trunk_config(trunk)
        
        return config
    
    async def write_config(self) -> str:
        """Generate and write config to file"""
        config = await self.generate_config()
        
        config_path = os.path.join(PJSIP_CONFIG_DIR, PJSIP_USERS_CONF)
        
        with open(config_path, 'w') as f:
            f.write(config)
        
        logger.info(f"✅ PJSIP config written to {config_path}")
        return config_path
    
    def reload_asterisk(self) -> bool:
        """Trigger Asterisk to reload PJSIP"""
        try:
            result = subprocess.run(
                ASTERISK_RELOAD_CMD,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("🔄 Asterisk PJSIP reloaded successfully")
                return True
            else:
                logger.error(f"❌ PJSIP reload failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ PJSIP reload error: {e}")
            return False
    
    async def regenerate_and_reload(self) -> bool:
        """Full pipeline: generate config → write → reload"""
        try:
            config_path = await self.write_config()
            success = self.reload_asterisk()
            return success
        except Exception as e:
            logger.error(f"❌ Regeneration failed: {e}")
            return False


# =============================================================================
# CLI Entry Point
# =============================================================================
async def main():
    """Generate PJSIP config and reload Asterisk"""
    generator = PJSIPGenerator()
    
    try:
        await generator.connect()
        
        # Generate and display config
        config = await generator.generate_config()
        print(config)
        
        # Write to file and reload
        await generator.write_config()
        generator.reload_asterisk()
        
    finally:
        await generator.close()


if __name__ == "__main__":
    asyncio.run(main())
