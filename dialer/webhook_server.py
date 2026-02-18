# =============================================================================
# Webhook Server - DTMF & Call Event Handler (User-Scoped)
# =============================================================================
# FastAPI application that receives call events from Asterisk
# - Processes DTMF keypad presses (Press-1 detection)
# - Updates call records, campaign stats
# - Handles per-user billing
# =============================================================================

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict
from decimal import Decimal

import asyncpg
import aiohttp
from fastapi import FastAPI, Request
import uvicorn

import path_setup  # Must be before config import

from config import (
    DATABASE_URL,
    TELEGRAM_BOT_TOKEN,
    WEBHOOK_HOST,
    WEBHOOK_PORT,
    MINIMUM_BILLABLE_SECONDS,
    BILLING_INCREMENT_SECONDS,
    COST_PER_MINUTE
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IVR Webhook Server")

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None


async def send_press1_notification(campaign_id: int, phone_number: str, duration: int, cost: float):
    """Send Telegram notification when someone presses 1"""
    try:
        async with db_pool.acquire() as conn:
            # Get campaign owner's telegram_id
            row = await conn.fetchrow("""
                SELECT u.telegram_id, c.name as campaign_name
                FROM campaigns c
                JOIN users u ON c.user_id = u.id
                WHERE c.id = $1
            """, campaign_id)
            
            if not row:
                return
            
            telegram_id = row['telegram_id']
            campaign_name = row['campaign_name']
            
            text = (
                f"🔔 <b>Press-1 Alert!</b>\n\n"
                f"📞 Number: <code>{phone_number}</code>\n"
                f"📋 Campaign: {campaign_name}\n"
                f"⏱ Duration: {duration}s\n"
                f"💰 Cost: ${cost:.4f}\n\n"
                f"✅ This person pressed 1!"
            )
            
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={
                    'chat_id': telegram_id,
                    'text': text,
                    'parse_mode': 'HTML'
                })
            
            logger.info(f"🔔 Press-1 notification sent to {telegram_id} for {phone_number}")
    except Exception as e:
        logger.error(f"Failed to send press-1 notification: {e}")


@app.on_event("startup")
async def startup():
    """Initialize database connection on startup"""
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=5, max_size=20
    )
    logger.info("✅ Webhook Server started - Database connected")


@app.on_event("shutdown")
async def shutdown():
    """Close database connection on shutdown"""
    global db_pool
    if db_pool:
        await db_pool.close()
    logger.info("Webhook Server stopped")


@app.post("/webhook/dtmf")
async def handle_dtmf(request: Request):
    """
    Handle DTMF events from Asterisk
    
    Expected payload:
    {
        "call_id": "uniqueid",
        "digit": "1",              (DTMF digit pressed)
        "duration": 45,            (call duration in seconds)
        "campaign_id": "123",
        "campaign_data_id": "456"
    }
    """
    try:
        # Accept both form-encoded (Asterisk CURL) and JSON (manual test)
        content_type = request.headers.get('content-type', '')
        if 'json' in content_type:
            data = await request.json()
        else:
            data = dict(await request.form())
        
        call_id = data.get('call_id')
        digit = data.get('digit', '')
        duration = int(data.get('duration', 0))
        campaign_id = int(data.get('campaign_id', 0))
        campaign_data_id = int(data.get('campaign_data_id', 0))
        
        logger.info(f"📥 DTMF Webhook: call={call_id}, digit={digit}, "
                    f"duration={duration}s, campaign={campaign_id}")
        
        pressed_one = (digit == '1')
        
        # Calculate billable cost
        cost = calculate_cost(duration)
        
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Update call record
                await conn.execute("""
                    UPDATE calls
                    SET status = CASE WHEN $1 THEN 'ANSWER' ELSE status END,
                        dtmf_pressed = $2,
                        duration = $3,
                        billsec = $3,
                        cost = $4,
                        answered_at = $5,
                        ended_at = $5
                    WHERE call_id = $6
                """, True, 1 if pressed_one else 0,
                    duration, cost, datetime.now(), call_id)
                
                # Update campaign_data status
                status = 'completed' if pressed_one else 'answered'
                await conn.execute("""
                    UPDATE campaign_data
                    SET status = $1
                    WHERE id = $2
                """, status, campaign_data_id)
                
                # Update campaign counters
                if pressed_one:
                    await conn.execute("""
                        UPDATE campaigns
                        SET completed = completed + 1,
                            answered = answered + 1,
                            pressed_one = pressed_one + 1,
                            actual_cost = actual_cost + $1
                        WHERE id = $2
                    """, cost, campaign_id)
                else:
                    await conn.execute("""
                        UPDATE campaigns
                        SET completed = completed + 1,
                            answered = answered + 1,
                            actual_cost = actual_cost + $1
                        WHERE id = $2
                    """, cost, campaign_id)
                
                # Deduct from user credits
                await conn.execute("""
                    UPDATE users
                    SET credits = credits - $1,
                        total_spent = total_spent + $1,
                        total_calls = total_calls + 1
                    WHERE id = (
                        SELECT user_id FROM campaigns WHERE id = $2
                    )
                """, cost, campaign_id)
        
        # Send Telegram notification for press-1
        if pressed_one:
            try:
                async with db_pool.acquire() as conn:
                    phone_row = await conn.fetchrow(
                        "SELECT phone_number FROM campaign_data WHERE id = $1",
                        campaign_data_id
                    )
                    phone = phone_row['phone_number'] if phone_row else 'Unknown'
                asyncio.create_task(
                    send_press1_notification(campaign_id, phone, duration, float(cost))
                )
            except Exception as e:
                logger.error(f"Error getting phone for notification: {e}")
        
        return {
            "status": "ok",
            "pressed_one": pressed_one,
            "cost": float(cost),
            "duration": duration
        }
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/webhook/hangup")
async def handle_hangup(request: Request):
    """
    Handle call hangup events
    
    Expected payload:
    {
        "call_id": "uniqueid",
        "duration": 0,
        "hangup_cause": "NORMAL_CLEARING",
        "campaign_id": "123",
        "campaign_data_id": "456"
    }
    """
    try:
        # Accept both form-encoded (Asterisk CURL) and JSON (manual test)
        content_type = request.headers.get('content-type', '')
        if 'json' in content_type:
            data = await request.json()
        else:
            data = dict(await request.form())
        
        call_id = data.get('call_id')
        duration = int(data.get('duration', 0))
        hangup_cause = data.get('hangup_cause', 'Unknown')
        campaign_id = int(data.get('campaign_id', 0))
        campaign_data_id = int(data.get('campaign_data_id', 0))
        
        logger.info(f"📴 Hangup Webhook: call={call_id}, "
                    f"duration={duration}s, cause={hangup_cause}")
        
        cost = calculate_cost(duration)
        
        # Determine status based on hangup cause
        if hangup_cause in ('BUSY', 'USER_BUSY'):
            status = 'BUSY'
        elif hangup_cause in ('NO_ANSWER', 'NO_USER_RESPONSE'):
            status = 'NO ANSWER'
        elif duration > 0:
            status = 'ANSWER'
        else:
            status = 'FAILED'
        
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Update call record
                await conn.execute("""
                    UPDATE calls
                    SET status = $1,
                        duration = $2,
                        billsec = $2,
                        cost = $3,
                        hangup_cause = $4,
                        ended_at = $5
                    WHERE call_id = $6
                """, status, duration, cost, hangup_cause,
                    datetime.now(), call_id)
                
                # Update campaign_data
                data_status = 'failed' if status in ('BUSY', 'NO ANSWER', 'FAILED') else 'completed'
                await conn.execute("""
                    UPDATE campaign_data
                    SET status = $1
                    WHERE id = $2
                """, data_status, campaign_data_id)
                
                # Update campaign counters
                if status in ('BUSY', 'NO ANSWER', 'FAILED'):
                    await conn.execute("""
                        UPDATE campaigns
                        SET completed = completed + 1,
                            failed = failed + 1,
                            actual_cost = actual_cost + $1
                        WHERE id = $2
                    """, cost, campaign_id)
                
                # Deduct cost even for failed calls (if billable)
                if cost > 0:
                    await conn.execute("""
                        UPDATE users
                        SET credits = credits - $1,
                            total_spent = total_spent + $1,
                            total_calls = total_calls + 1
                        WHERE id = (
                            SELECT user_id FROM campaigns WHERE id = $2
                        )
                    """, cost, campaign_id)
        
        return {
            "status": "ok",
            "call_status": status,
            "cost": float(cost)
        }
        
    except Exception as e:
        logger.error(f"❌ Hangup webhook error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/webhook/oxapay")
async def handle_oxapay_webhook(request: Request):
    """
    Handle Oxapay payment completion webhook
    
    Oxapay sends POST when payment status changes.
    On successful payment, credits are added to user's account.
    """
    try:
        data = await request.json()
        
        track_id = data.get('trackId', '')
        status = data.get('status', '')
        amount = float(data.get('amount', 0))
        order_id = data.get('orderId', '')
        
        logger.info(f"💰 Oxapay Webhook: track={track_id}, status={status}, amount={amount}")
        
        # Only process successful/completed payments
        if status not in ('Paid', 'Confirming', 'Complete'):
            logger.info(f"⏳ Payment {track_id} status: {status} (waiting)")
            return {"status": "ok", "action": "waiting"}
        
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Find payment record
                payment = await conn.fetchrow("""
                    SELECT id, user_id, credits, status as payment_status
                    FROM payments
                    WHERE track_id = $1
                """, track_id)
                
                if not payment:
                    logger.warning(f"⚠️ Payment not found: {track_id}")
                    return {"status": "error", "message": "Payment not found"}
                
                # Avoid double-crediting
                if payment['payment_status'] == 'completed':
                    logger.info(f"ℹ️ Payment {track_id} already processed")
                    return {"status": "ok", "action": "already_processed"}
                
                credits_to_add = payment['credits']
                user_id = payment['user_id']
                
                # Update payment status
                await conn.execute("""
                    UPDATE payments
                    SET status = 'completed', completed_at = $1
                    WHERE track_id = $2
                """, datetime.now(), track_id)
                
                # Add credits to user
                await conn.execute("""
                    UPDATE users
                    SET credits = credits + $1
                    WHERE id = $2
                """, credits_to_add, user_id)
                
                logger.info(f"✅ Payment completed! User {user_id} +{credits_to_add} credits")
        
        return {
            "status": "ok",
            "action": "credits_added",
            "credits": credits_to_add
        }
        
    except Exception as e:
        logger.error(f"❌ Oxapay webhook error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/stats/user/{user_id}")
async def get_user_stats(user_id: int):
    """Get per-user statistics"""
    try:
        async with db_pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    u.credits,
                    u.total_spent,
                    u.total_calls,
                    (SELECT COUNT(*) FROM campaigns WHERE user_id = u.id) as campaigns,
                    (SELECT COUNT(*) FROM user_trunks WHERE user_id = u.id AND status = 'active') as active_trunks,
                    (SELECT COUNT(*) FROM leads WHERE user_id = u.id) as lead_lists
                FROM users u
                WHERE u.id = $1
            """, user_id)
            
            if stats:
                return {"status": "ok", "stats": dict(stats)}
            return {"status": "error", "message": "User not found"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}


def calculate_cost(duration_seconds: int) -> Decimal:
    """
    Calculate call cost based on duration
    
    Rules:
    - Minimum billable: MINIMUM_BILLABLE_SECONDS (default 6s)
    - Billing increment: BILLING_INCREMENT_SECONDS (default 6s)
    - Cost per minute: COST_PER_MINUTE from config
    """
    if duration_seconds <= 0:
        return Decimal('0')
    
    # Apply minimum
    billable = max(duration_seconds, MINIMUM_BILLABLE_SECONDS)
    
    # Round up to next increment
    if billable % BILLING_INCREMENT_SECONDS != 0:
        billable = ((billable // BILLING_INCREMENT_SECONDS) + 1) * BILLING_INCREMENT_SECONDS
    
    # Calculate cost
    cost = Decimal(str(COST_PER_MINUTE)) * Decimal(str(billable)) / Decimal('60')
    
    return round(cost, 4)


# =============================================================================
# Main Entry Point
# =============================================================================
if __name__ == "__main__":
    uvicorn.run(
        "webhook_server:app",
        host=WEBHOOK_HOST,
        port=WEBHOOK_PORT,
        reload=False,
        workers=2
    )
