async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice/audio file upload for IVR"""
    
    if not context.user_data.get('creating_campaign'):
        await update.message.reply_text("Please use /new_campaign first")
        return
    
    if context.user_data.get('campaign_step') != 'voice':
        return
    
    # Get voice file info
    if update.message.voice:
        file = update.message.voice
        file_type = "voice message"
    elif update.message.audio:
        file = update.message.audio
        file_type = "audio file"
    else:
        return
    
    # In real implementation, we would save the file
    # For mock version, just acknowledge receipt
    await update.message.reply_text(f"✅ {file_type.capitalize()} received!")
    
    # Move to next step - CSV upload
    context.user_data['campaign_step'] = 'upload'
    
    await update.message.reply_text(
        """
📂 <b>Step 3: Upload Phone Numbers</b>

Upload your phone numbers as a CSV file.

<b>CSV Format:</b>
One phone number per line

Example:
1234567890
9876543210
5555555555

Send the CSV file now →
""",
        parse_mode='HTML'
    )
