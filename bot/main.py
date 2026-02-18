# =============================================================================
# Telegram Bot - Main Application (Bot 2 - Callix)
# =============================================================================
# Press-1 IVR Bot - Campaign management via Telegram
# Uses callix_trunk via Asterisk for SIP connectivity
# =============================================================================

import logging
import csv
import io
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import TELEGRAM_BOT_TOKEN, CREDIT_PACKAGES, ADMIN_TELEGRAM_IDS, SUPPORT_TELEGRAM
from database import db
from oxapay_handler import oxapay
from magnus_api import magnus_api

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# =============================================================================
# Command Handlers
# =============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    user_data = await db.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    welcome_text = f"""
🤖 **Welcome to Callix IVR Bot!**

Hello {user.first_name}! 👋

This bot helps you run automated Press-1 IVR campaigns to reach thousands of people.

**How it works:**
1️⃣ Buy credits using cryptocurrency
2️⃣ Create your SIP account
3️⃣ Upload your contact list (CSV)
4️⃣ Start your campaign & get real-time results

**Available Commands:**
/balance - Check your credits
/buy - Purchase credits
/create\_sip - Create SIP account
/sip\_status - View your SIP accounts
/new\_campaign - Create new campaign
/campaigns - View your campaigns
/help - Get help

**Your Account:**
💰 Credits: {user_data['credits']:.2f}
📞 Total Calls: {user_data['total_calls']}

Support: {SUPPORT_TELEGRAM}

Ready to get started? Use /buy to purchase credits!
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown'
    )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command"""
    user = update.effective_user
    
    stats = await db.get_user_stats(user.id)
    
    if not stats:
        await update.message.reply_text("❌ User not found. Use /start first.")
        return
    
    balance_text = f"""
💰 **Your Account Balance**

**Available Credits:** {stats['credits']:.2f}
**Total Spent:** ${stats['total_spent']:.2f}
**Total Calls:** {stats['total_calls']}
**Total Campaigns:** {stats['campaign_count']}

**Pricing:** 1 credit = ~1 minute of calling

Need more credits? Use /buy
"""
    
    await update.message.reply_text(
        balance_text,
        parse_mode='Markdown'
    )


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /buy command - show credit packages"""
    
    keyboard = []
    for package_id, package_data in CREDIT_PACKAGES.items():
        credits = package_data['credits']
        price = package_data['price']
        currency = package_data['currency']
        
        button_text = f"💎 {credits} Credits - ${price} {currency}"
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"buy_{package_id}"
            )
        ])
    
    buy_text = """
💳 **Purchase Credits**

Select a package to continue:

**What you get:**
✅ Instant credit delivery
✅ Pay with cryptocurrency (USDT, BTC, ETH)
✅ Secure payment via Oxapay
✅ No hidden fees

Choose your package below:
"""
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        buy_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def handle_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buy package callback"""
    query = update.callback_query
    await query.answer()
    
    package_id = query.data.split('_')[1]
    package = oxapay.get_credit_package(package_id)
    
    if not package:
        await query.edit_message_text("❌ Invalid package")
        return
    
    user = update.effective_user
    
    user_data = await db.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    payment_result = await oxapay.create_payment(
        amount=package['price'],
        currency=package['currency'],
        description=f"{package['credits']} credits for Callix IVR Bot"
    )
    
    if not payment_result['success']:
        await query.edit_message_text(
            f"❌ Payment creation failed: {payment_result['error']}"
        )
        return
    
    await db.create_payment(
        user_id=user_data['id'],
        track_id=payment_result['track_id'],
        amount=package['price'],
        credits=package['credits'],
        currency=package['currency'],
        payment_url=payment_result['payment_url']
    )
    
    payment_text = f"""
✅ **Payment Created!**

**Package:** {package['credits']} credits
**Amount:** ${package['price']} {package['currency']}
**Track ID:** `{payment_result['track_id']}`

**Payment Link:**
{payment_result['payment_url']}

Click the link above to complete payment.
Credits will be added automatically after confirmation.

⏱️ Payment expires in 30 minutes.
"""
    
    keyboard = [[
        InlineKeyboardButton("💳 Pay Now", url=payment_result['payment_url'])
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        payment_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def new_campaign_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /new_campaign command"""
    user = update.effective_user
    
    user_data = await db.get_or_create_user(user.id)
    
    if user_data['credits'] <= 0:
        await update.message.reply_text(
            "❌ You don't have enough credits.\nUse /buy to purchase credits first."
        )
        return
    
    context.user_data['creating_campaign'] = True
    context.user_data['campaign_step'] = 'name'
    
    await update.message.reply_text(
        """
📝 **Create New Campaign**

Step 1: What would you like to name this campaign?

Example: "Product Launch 2026"
"""
    )


async def campaigns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /campaigns command - list user's campaigns"""
    user = update.effective_user
    
    user_data = await db.get_or_create_user(user.id)
    
    campaigns = await db.get_user_campaigns(user_data['id'], limit=10)
    
    if not campaigns:
        await update.message.reply_text(
            "📂 You don't have any campaigns yet.\n\nUse /new_campaign to create one!"
        )
        return
    
    campaigns_text = "📊 **Your Campaigns**\n\n"
    
    for camp in campaigns:
        status_emoji = {
            'draft': '📝',
            'running': '🚀',
            'paused': '⏸️',
            'completed': '✅'
        }.get(camp['status'], '❓')
        
        campaigns_text += f"{status_emoji} **{camp['name']}**\n"
        campaigns_text += f"   • Numbers: {camp['total_numbers']}\n"
        campaigns_text += f"   • Completed: {camp['completed']}\n"
        campaigns_text += f"   • Success: {camp['pressed_one']}\n"
        campaigns_text += f"   • Cost: ${camp['actual_cost']:.2f}\n"
        campaigns_text += f"   • Status: {camp['status']}\n"
        campaigns_text += f"   • /campaign\\_{camp['id']}\n\n"
    
    await update.message.reply_text(
        campaigns_text,
        parse_mode='Markdown'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = f"""
❓ **Help & Support**

**Commands:**
/start - Start the bot
/balance - Check your credits
/buy - Purchase credits
/new\\_campaign - Create new campaign
/campaigns - View all campaigns
/help - Show this help

**Campaign Creation:**
1. Use /new\\_campaign
2. Give it a name
3. Upload CSV file with phone numbers
4. Start the campaign

**CSV Format:**
Your CSV should have phone numbers in the first column:
```
1234567890
9876543210
5555555555
```

**Pricing:**
- 1 credit ≈ 1 minute of calling
- Minimum 6 seconds billing
- 6-second increments

**Support:**
If you need help, contact: {SUPPORT_TELEGRAM}
"""
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown'
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages during campaign creation"""
    
    if not context.user_data.get('creating_campaign'):
        await update.message.reply_text(
            "I didn't understand that. Use /help to see available commands."
        )
        return
    
    user = update.effective_user
    step = context.user_data.get('campaign_step')
    
    if step == 'name':
        campaign_name = update.message.text
        
        user_data = await db.get_or_create_user(user.id)
        
        campaign_id = await db.create_campaign(
            user_id=user_data['id'],
            name=campaign_name
        )
        
        context.user_data['campaign_id'] = campaign_id
        context.user_data['campaign_step'] = 'upload'
        
        await update.message.reply_text(
            f"""
✅ Campaign "{campaign_name}" created!

Step 2: Upload your phone numbers as a CSV file.

**CSV Format:**
```
1234567890
9876543210
5555555555
```

Send the CSV file now →
"""
        )


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle CSV file upload"""
    
    if not context.user_data.get('creating_campaign'):
        await update.message.reply_text("Please use /new_campaign first")
        return
    
    if context.user_data.get('campaign_step') != 'upload':
        return
    
    user = update.effective_user
    file = await update.message.document.get_file()
    
    file_content = await file.download_as_bytearray()
    
    try:
        csv_text = file_content.decode('utf-8')
        reader = csv.reader(io.StringIO(csv_text))
        
        phone_numbers = []
        for row in reader:
            if row and row[0].strip():
                phone = ''.join(filter(str.isdigit, row[0]))
                if phone:
                    phone_numbers.append(phone)
        
        if not phone_numbers:
            await update.message.reply_text("❌ No valid phone numbers found in CSV")
            return
        
        campaign_id = context.user_data['campaign_id']
        count = await db.add_campaign_numbers(campaign_id, phone_numbers)
        
        context.user_data['creating_campaign'] = False
        
        keyboard = [[
            InlineKeyboardButton(
                "🚀 Start Campaign",
                callback_data=f"start_campaign_{campaign_id}"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"""
✅ **Campaign Ready!**

📊 **Numbers uploaded:** {count}
💰 **Estimated cost:** ~{count} credits

Your campaign is ready to launch!
Click the button below to start calling.
""",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        await update.message.reply_text(
            f"❌ Error processing CSV file: {str(e)}\nPlease make sure it's a valid CSV."
        )


async def handle_start_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle start campaign callback"""
    query = update.callback_query
    await query.answer()
    
    campaign_id = int(query.data.split('_')[2])
    
    await db.start_campaign(campaign_id)
    
    await query.edit_message_text(
        f"""
🚀 **Campaign Started!**

Campaign ID: {campaign_id}

Your campaign is now running. You'll receive updates as calls are made.

Use /campaigns to check progress.
""",
        parse_mode='Markdown'
    )


# =============================================================================
# MagnusBilling SIP Commands
# =============================================================================

async def create_sip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /create_sip command - auto-create SIP account via MagnusBilling API"""
    user = update.effective_user
    
    user_data = await db.get_or_create_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    await update.message.reply_text("⏳ Creating SIP account...")
    
    result = await magnus_api.create_sip_user(
        callerid=str(user.id)
    )
    
    if result['success']:
        # Save SIP info to database
        await db.save_sip_account(
            user_id=user_data['id'],
            sip_username=result['username'],
            sip_password=result['password'],
            sip_id=result.get('sip_id')
        )
        
        sip_text = f"""
✅ **SIP Account Created!**

📞 **SIP Username:** `{result['username']}`
🔑 **SIP Password:** `{result['password']}`
🌐 **SIP Server:** `sip.callix.pro`
🔌 **Port:** 5060

**Connection Settings:**
```
Host: sip.callix.pro
Username: {result['username']}
Password: {result['password']}
Protocol: SIP/UDP
Port: 5060
Codecs: ulaw, alaw, g729
```

⚠️ Save these credentials! You'll need them to configure your softphone or PBX.

Support: {SUPPORT_TELEGRAM}
"""
        await update.message.reply_text(sip_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(
            f"❌ Failed to create SIP account: {result['error']}\n\nContact {SUPPORT_TELEGRAM} for help."
        )


async def sip_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sip_status command - list user's SIP accounts"""
    user = update.effective_user
    
    user_data = await db.get_or_create_user(user.id)
    
    sip_accounts = await db.get_user_sip_accounts(user_data['id'])
    
    if not sip_accounts:
        await update.message.reply_text(
            "📞 No SIP accounts found.\n\nUse /create_sip to create one!"
        )
        return
    
    sip_text = "📞 **Your SIP Accounts**\n\n"
    
    for acc in sip_accounts:
        sip_text += f"🔹 **{acc['sip_username']}**\n"
        sip_text += f"   Server: `sip.callix.pro`\n"
        sip_text += f"   Password: `{acc['sip_password']}`\n"
        sip_text += f"   Created: {acc['created_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
    
    await update.message.reply_text(sip_text, parse_mode='Markdown')


# =============================================================================
# Admin Commands (MagnusBilling Management)
# =============================================================================

async def admin_sip_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_sip_list - list all SIP users (admin only)"""
    user = update.effective_user
    
    if user.id not in ADMIN_TELEGRAM_IDS:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    await update.message.reply_text("⏳ Fetching SIP users from MagnusBilling...")
    
    result = await magnus_api.list_sip_users(limit=25)
    
    if result['success']:
        users = result['users']
        text = f"📋 **MagnusBilling SIP Users** ({result['count']} total)\n\n"
        
        for u in users[:20]:
            name = u.get('name', 'N/A')
            status = '🟢' if u.get('status', 0) == 1 else '🔴'
            text += f"{status} `{name}`\n"
        
        if result['count'] > 20:
            text += f"\n... and {result['count'] - 20} more"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Error: {result['error']}")


async def admin_api_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin_api_test - test MagnusBilling API (admin only)"""
    user = update.effective_user
    
    if user.id not in ADMIN_TELEGRAM_IDS:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    await update.message.reply_text("⏳ Testing MagnusBilling API connection...")
    
    api_ok = await magnus_api.test_connection()
    
    if api_ok:
        await update.message.reply_text("✅ MagnusBilling API connection successful!")
    else:
        await update.message.reply_text("❌ MagnusBilling API connection failed!")


# =============================================================================
# Main Application
# =============================================================================

async def post_init(application: Application):
    """Initialize database and test MagnusBilling API after app is created"""
    await db.connect()
    
    # Test MagnusBilling API
    api_ok = await magnus_api.test_connection()
    if api_ok:
        logger.info("✅ MagnusBilling API connected")
    else:
        logger.warning("⚠️ MagnusBilling API connection failed - SIP creation won't work")
    
    logger.info("✅ Callix IVR Bot initialized")


async def post_shutdown(application: Application):
    """Cleanup on shutdown"""
    await db.close()
    logger.info("🛑 Callix IVR Bot stopped")


def main():
    """Main function to run the bot"""
    
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CommandHandler("create_sip", create_sip_command))
    application.add_handler(CommandHandler("sip_status", sip_status_command))
    application.add_handler(CommandHandler("new_campaign", new_campaign_command))
    application.add_handler(CommandHandler("campaigns", campaigns_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Admin commands
    application.add_handler(CommandHandler("admin_sip_list", admin_sip_list_command))
    application.add_handler(CommandHandler("admin_api_test", admin_api_test_command))
    
    application.add_handler(
        CallbackQueryHandler(handle_buy_callback, pattern="^buy_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_start_campaign, pattern="^start_campaign_")
    )
    
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_handler(
        MessageHandler(filters.Document.ALL, handle_file)
    )
    
    logger.info("🚀 Starting Callix IVR Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
