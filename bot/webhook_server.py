# =============================================================================
# Webhook Server - Oxapay Payment Callbacks
# =============================================================================
# HTTP server that receives payment status updates from Oxapay
# Activates subscriptions and credits when payments are confirmed
# =============================================================================

import logging
import json
from aiohttp import web
from datetime import datetime

logger = logging.getLogger(__name__)


class WebhookServer:
    """HTTP server for receiving Oxapay payment webhooks"""
    
    def __init__(self, db, bot_app=None, host="0.0.0.0", port=8000):
        self.db = db
        self.bot_app = bot_app  # telegram bot application for sending messages
        self.host = host
        self.port = port
        self.runner = None
    
    async def start(self):
        """Start the webhook HTTP server"""
        app = web.Application()
        app.router.add_post('/webhook/oxapay', self.handle_oxapay_webhook)
        app.router.add_post('/webhook/dtmf', self.handle_dtmf_webhook)
        app.router.add_post('/webhook/hangup', self.handle_hangup_webhook)
        app.router.add_get('/health', self.handle_health)
        
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"🌐 Webhook server started on {self.host}:{self.port}")
    
    async def stop(self):
        """Stop the webhook server"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("🔴 Webhook server stopped")
    
    async def handle_health(self, request):
        """Health check endpoint"""
        return web.json_response({"status": "ok", "time": datetime.now().isoformat()})
    
    async def handle_oxapay_webhook(self, request):
        """
        Handle Oxapay payment webhook callback.
        
        Oxapay sends POST with JSON body containing payment status updates.
        Key fields:
        - trackId: our payment tracking ID
        - status: "Waiting", "Confirming", "Paid", "Failed", "Expired"
        - amount: payment amount
        - txID: blockchain transaction hash
        """
        try:
            # Parse webhook data
            try:
                data = await request.json()
            except Exception:
                body = await request.text()
                logger.warning(f"⚠️ Webhook: Non-JSON body received: {body[:500]}")
                return web.json_response({"error": "Invalid JSON"}, status=400)
            
            logger.info(f"📨 Oxapay webhook received: {json.dumps(data, default=str)}")
            
            track_id = data.get('trackId') or data.get('track_id') or data.get('orderId')
            status = data.get('status', '').lower()
            tx_hash = data.get('txID') or data.get('tx_hash', '')
            
            if not track_id:
                logger.warning("⚠️ Webhook: No trackId in data")
                return web.json_response({"error": "No trackId"}, status=400)
            
            logger.info(f"📋 Webhook: trackId={track_id}, status={status}, txHash={tx_hash}")
            
            # Only process completed payments
            if status in ('paid', 'complete', 'completed', 'confirmed'):
                await self._handle_paid(track_id, tx_hash)
            elif status in ('failed', 'expired', 'canceled'):
                logger.info(f"❌ Payment {track_id} {status}")
            else:
                logger.info(f"⏳ Payment {track_id} status: {status} (waiting)")
            
            return web.json_response({"status": "ok"})
            
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def handle_dtmf_webhook(self, request):
        """Handle DTMF webhook from Asterisk dialplan"""
        try:
            # Accept both form-encoded (Asterisk CURL) and JSON
            content_type = request.content_type or ''
            if 'json' in content_type:
                data = await request.json()
            else:
                data = dict(await request.post())
            logger.info(f"\U0001f4de DTMF webhook: {data}")
            
            call_id = data.get('call_id', '')
            digit = data.get('digit', '')
            duration = int(data.get('duration', 0))
            campaign_id = data.get('campaign_id', '')
            campaign_data_id = data.get('campaign_data_id', '')
            amd_status = data.get('amd_status', '')
            
            if not call_id:
                return web.json_response({"error": "No call_id"}, status=400)
            
            dtmf_pressed = 1 if digit == '1' else 0
            
            # Calculate cost: 6-second billing increments
            import math
            if duration > 0:
                billable_seconds = max(duration, 6)  # minimum 6 seconds
                billable_minutes = math.ceil(billable_seconds / 6) * 6 / 60
                cost = round(billable_minutes * 1.0, 4)  # $1/minute
            else:
                cost = 0
            
            # Set proper status for stats counting
            if amd_status == 'MACHINE':
                call_status = 'MACHINE'
                cost = 0  # No charge for machine-detected calls
            elif dtmf_pressed:
                call_status = 'COMPLETED'
            elif duration > 0:
                call_status = 'ANSWER'
            else:
                call_status = 'NO ANSWER'
            
            async with self.db.pool.acquire() as conn:
                # Update calls table with DTMF result, status, and cost
                # Try call_id first, fallback to campaign_data_id
                result = await conn.execute("""
                    UPDATE calls 
                    SET dtmf_pressed = $1, duration = $2, 
                        status = $3, cost = $4,
                        ended_at = CURRENT_TIMESTAMP
                    WHERE call_id = $5
                """, dtmf_pressed, duration, call_status, cost, call_id)
                
                # If no rows matched by call_id, try campaign_data_id
                rows_updated = int(result.split()[-1])
                if rows_updated == 0 and campaign_data_id:
                    try:
                        cd_id = int(campaign_data_id)
                        await conn.execute("""
                            UPDATE calls 
                            SET dtmf_pressed = $1, duration = $2,
                                status = $3, cost = $4,
                                ended_at = CURRENT_TIMESTAMP
                            WHERE campaign_data_id = $5
                        """, dtmf_pressed, duration, call_status, cost, cd_id)
                    except (ValueError, TypeError):
                        pass
                
                # Update campaign_data status
                if campaign_data_id:
                    try:
                        cd_id = int(campaign_data_id)
                        if amd_status == 'MACHINE':
                            new_status = 'machine'
                        elif dtmf_pressed == 1:
                            new_status = 'completed'
                        else:
                            new_status = 'answered'
                        await conn.execute("""
                            UPDATE campaign_data SET status = $1 WHERE id = $2
                        """, new_status, cd_id)
                    except (ValueError, TypeError):
                        pass
            
            if amd_status == 'MACHINE':
                logger.info(f"🤖 AMD: Machine detected for call {call_id} — hung up")
            elif dtmf_pressed:
                logger.info(f"\u2705 DTMF Press-1 detected for call {call_id}!")
                # Send Telegram notification to campaign owner
                try:
                    async with self.db.pool.acquire() as conn2:
                        # Get campaign owner and phone number
                        info = await conn2.fetchrow("""
                            SELECT cd.phone_number, c.name as campaign_name, 
                                   u.telegram_id
                            FROM campaign_data cd
                            JOIN campaigns c ON cd.campaign_id = c.id
                            JOIN users u ON c.user_id = u.id
                            WHERE cd.id = $1
                        """, int(campaign_data_id) if campaign_data_id else 0)
                        
                        if info:
                            await self._notify_user(
                                info['telegram_id'],
                                f"🔔 <b>Press-1 Detected!</b>\n\n"
                                f"📞 Number: <code>{info['phone_number']}</code>\n"
                                f"📋 Campaign: {info['campaign_name']}\n"
                                f"⏱ Duration: {duration}s\n\n"
                                f"Someone pressed 1! ✅"
                            )
                except Exception as notify_err:
                    logger.error(f"Failed to send press-1 notification: {notify_err}")
            else:
                logger.info(f"\u274c No valid DTMF for call {call_id} (digit={digit})")
            
            return web.json_response({"status": "ok"})
        except Exception as e:
            logger.error(f"\u274c DTMF webhook error: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def handle_hangup_webhook(self, request):
        """Handle hangup webhook from Asterisk dialplan"""
        try:
            # Accept both form-encoded (Asterisk CURL) and JSON
            content_type = request.content_type or ''
            if 'json' in content_type:
                data = await request.json()
            else:
                data = dict(await request.post())
            logger.info(f"\U0001f534 Hangup webhook: {data}")
            
            call_id = data.get('call_id', '')
            duration = int(data.get('duration', 0))
            hangup_cause = data.get('hangup_cause', '')
            campaign_data_id = data.get('campaign_data_id', '')
            
            if not call_id:
                return web.json_response({"error": "No call_id"}, status=400)
            
            # Calculate cost
            import math
            if duration > 0:
                billable_seconds = max(duration, 6)
                billable_minutes = math.ceil(billable_seconds / 6) * 6 / 60
                cost = round(billable_minutes * 1.0, 4)
            else:
                cost = 0
            
            # Determine status
            if hangup_cause in ('BUSY', 'USER_BUSY'):
                status = 'BUSY'
            elif hangup_cause in ('NO_ANSWER', 'NO_USER_RESPONSE'):
                status = 'NO ANSWER'
            elif duration > 0:
                status = 'ANSWER'
            else:
                status = 'FAILED'
            
            async with self.db.pool.acquire() as conn:
                # Update calls table - try call_id first, fallback to campaign_data_id
                result = await conn.execute("""
                    UPDATE calls 
                    SET duration = COALESCE(NULLIF($1, 0), duration),
                        hangup_cause = $2, cost = $3,
                        ended_at = CURRENT_TIMESTAMP,
                        status = CASE WHEN status IN ('COMPLETED') THEN status ELSE $4 END
                    WHERE call_id = $5
                """, duration, hangup_cause, cost, status, call_id)
                
                rows_updated = int(result.split()[-1])
                if rows_updated == 0 and campaign_data_id:
                    try:
                        cd_id = int(campaign_data_id)
                        await conn.execute("""
                            UPDATE calls 
                            SET duration = COALESCE(NULLIF($1, 0), duration),
                                hangup_cause = $2, cost = $3,
                                ended_at = CURRENT_TIMESTAMP,
                                status = CASE WHEN status IN ('COMPLETED') THEN status ELSE $4 END
                            WHERE campaign_data_id = $5
                        """, duration, hangup_cause, cost, status, cd_id)
                    except (ValueError, TypeError):
                        pass
                
                # Update campaign_data if not already completed
                if campaign_data_id:
                    try:
                        cd_id = int(campaign_data_id)
                        await conn.execute("""
                            UPDATE campaign_data 
                            SET status = CASE 
                                WHEN status = 'dialing' THEN 'failed'
                                WHEN status = 'completed' THEN 'completed'
                                ELSE 'failed'
                            END
                            WHERE id = $1 AND status NOT IN ('completed')
                        """, cd_id)
                    except (ValueError, TypeError):
                        pass
            
            logger.info(f"\U0001f4f4 Call {call_id} hung up (cause={hangup_cause}, duration={duration}s)")
            return web.json_response({"status": "ok"})
        except Exception as e:
            logger.error(f"\u274c Hangup webhook error: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_paid(self, track_id: str, tx_hash: str = ""):
        """Process a confirmed payment — activate subscription or add credits"""
        
        # 1. Check if this is a subscription payment
        sub = await self.db.get_subscription_by_track_id(track_id)
        if sub and sub.get('status') == 'pending':
            result = await self.db.activate_subscription(track_id)
            if result:
                logger.info(f"✅ Subscription #{result['id']} activated for user {result['telegram_id']}")
                # Send Telegram notification
                await self._notify_user(
                    result['telegram_id'],
                    f"✅ <b>Subscription Activated!</b>\n\n"
                    f"💰 Amount: <b>${result['amount']:.2f}</b>\n"
                    f"📅 Valid until: <b>{result['expires_at'].strftime('%Y-%m-%d %H:%M')}</b>\n\n"
                    f"You now have full access to all features. 🚀"
                )
                return
        
        # 2. Otherwise check if it's a top-up payment
        confirmed = await self.db.confirm_payment(track_id, tx_hash)
        if confirmed:
            logger.info(f"✅ Top-up payment confirmed: {track_id}")
            # Get payment info to notify user
            try:
                async with self.db.pool.acquire() as conn:
                    payment = await conn.fetchrow("""
                        SELECT p.credits, u.telegram_id 
                        FROM payments p 
                        JOIN users u ON u.id = p.user_id 
                        WHERE p.track_id = $1
                    """, track_id)
                    if payment:
                        await self._notify_user(
                            payment['telegram_id'],
                            f"✅ <b>Payment Confirmed!</b>\n\n"
                            f"💰 <b>${payment['credits']:.2f}</b> credits added to your account.\n\n"
                            f"Thank you for your payment! 🎉"
                        )
            except Exception as e:
                logger.warning(f"Could not send payment notification: {e}")
        else:
            logger.warning(f"⚠️ Payment {track_id} not found or already confirmed")
    
    async def _notify_user(self, telegram_id: int, message: str):
        """Send a notification message to a user via Telegram"""
        if not self.bot_app:
            logger.warning("No bot_app set, cannot send notification")
            return
        try:
            await self.bot_app.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info(f"📤 Notification sent to {telegram_id}")
        except Exception as e:
            logger.error(f"❌ Failed to notify user {telegram_id}: {e}")
