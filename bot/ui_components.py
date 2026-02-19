# =============================================================================
# UI Components Library - Telegram Bot
# =============================================================================
# Reusable UI components for consistent, modern interface design
# =============================================================================

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math


class UIComponents:
    """Modern UI component library for Telegram bot"""
    
    # =========================================================================
    # Visual Elements - Unicode Characters
    # =========================================================================
    
    # Progress bar blocks
    BLOCK_FULL = "█"
    BLOCK_LIGHT = "▓"
    BLOCK_MEDIUM = "▒"
    BLOCK_SPARSE = "░"
    
    # Separators
    SEPARATOR_LIGHT = "─" * 30
    SEPARATOR_MEDIUM = "━" * 30
    SEPARATOR_HEAVY = "═" * 30
    SEPARATOR_DOTTED = "·" * 30
    
    # Status indicators
    STATUS_EMOJIS = {
        'draft': '📝',
        'pending': '⏳',
        'running': '🟢',
        'active': '🟢',
        'paused': '🟡',
        'stopped': '🔴',
        'completed': '✅',
        'success': '✅',
        'failed': '❌',
        'error': '⚠️'
    }
    
    # Action emojis
    ACTION_EMOJIS = {
        'start': '▶️',
        'pause': '⏸️',
        'resume': '🔄',
        'stop': '⏹️',
        'delete': '🗑️',
        'refresh': '🔄',
        'details': '📊',
        'edit': '✏️',
        'download': '📥',
        'upload': '📤'
    }
    
    # =========================================================================
    # Progress Bar
    # =========================================================================
    
    @staticmethod
    def progress_bar(
        current: int,
        total: int,
        width: int = 10,
        show_percentage: bool = True,
        style: str = "blocks"
    ) -> str:
        """
        Create a visual progress bar
        
        Args:
            current: Current progress value
            total: Total/maximum value
            width: Bar width in characters
            show_percentage: Whether to show percentage
            style: "blocks", "dots", or "simple"
            
        Returns:
            Formatted progress bar string
        """
        if total == 0:
            percentage = 0
        else:
            percentage = min(100, (current / total) * 100)
        
        filled = int((percentage / 100) * width)
        
        if style == "blocks":
            bar = UIComponents.BLOCK_FULL * filled
            bar += UIComponents.BLOCK_SPARSE * (width - filled)
        elif style == "dots":
            bar = "●" * filled + "○" * (width - filled)
        else:  # simple
            bar = "=" * filled + "-" * (width - filled)
        
        if show_percentage:
            return f"[{bar}] {percentage:.1f}%"
        else:
            return f"[{bar}]"
    
    # =========================================================================
    # Status Badge
    # =========================================================================
    
    @staticmethod
    def status_badge(status: str) -> str:
        """Get emoji badge for status"""
        status_lower = status.lower()
        emoji = UIComponents.STATUS_EMOJIS.get(status_lower, '❓')
        return f"{emoji} {status.title()}"
    
    # =========================================================================
    # Campaign Card
    # =========================================================================
    
    @staticmethod
    def campaign_card(campaign: Dict) -> str:
        """
        Format campaign data as a rich card
        
        Args:
            campaign: Dictionary with campaign data
            
        Returns:
            Formatted campaign card string
        """
        status_emoji = UIComponents.STATUS_EMOJIS.get(
            campaign.get('status', 'draft').lower(),
            '❓'
        )
        
        name = campaign.get('name', 'Unnamed Campaign')
        total = campaign.get('total_numbers', 0)
        completed = campaign.get('completed', 0)
        pressed_one = campaign.get('pressed_one', 0)
        cost = campaign.get('actual_cost', 0.0)
        campaign_id = campaign.get('id', 0)
        
        # Progress bar
        progress = UIComponents.progress_bar(completed, total, width=12)
        
        # Success rate
        if completed > 0:
            success_rate = (pressed_one / completed) * 100
            success_indicator = "🟢" if success_rate > 30 else "🟡" if success_rate > 10 else "🔴"
        else:
            success_rate = 0
            success_indicator = "⚪"
        
        card = f"""
{status_emoji} **{name}**
{UIComponents.SEPARATOR_LIGHT}
📊 Progress: {progress}
   • Total: {total} numbers
   • Completed: {completed}
   • Success: {pressed_one} {success_indicator} ({success_rate:.1f}%)
💰 Cost: ${cost:.2f}
📅 ID: `{campaign_id}`
        """.strip()
        
        return card
    
    # =========================================================================
    # Call Log Entry
    # =========================================================================
    
    @staticmethod
    def call_log_entry(call: Dict, index: int = 1) -> str:
        """
        Format individual call log entry
        
        Args:
            call: Dictionary with call data
            index: Entry number
            
        Returns:
            Formatted call log string
        """
        phone = call.get('phone_number', 'Unknown')
        status = call.get('status', 'Unknown')
        dtmf = call.get('dtmf_pressed', 0)
        duration = call.get('billsec', 0)
        cost = call.get('cost', 0.0)
        
        # Status emoji
        if dtmf == 1:
            result_emoji = "✅"
            result_text = "Pressed 1"
        elif status == "ANSWER":
            result_emoji = "📞"
            result_text = "Answered"
        elif status == "BUSY":
            result_emoji = "📵"
            result_text = "Busy"
        elif status == "NO ANSWER":
            result_emoji = "🔇"
            result_text = "No Answer"
        else:
            result_emoji = "❌"
            result_text = status
        
        entry = f"""
{index}. {result_emoji} `{phone}`
   {result_text} • {duration}s • ${cost:.4f}
        """.strip()
        
        return entry
    
    # =========================================================================
    # Statistics Dashboard
    # =========================================================================
    
    @staticmethod
    def stats_dashboard(stats: Dict) -> str:
        """
        Format statistics as a visual dashboard
        
        Args:
            stats: Dictionary with statistics data
            
        Returns:
            Formatted dashboard string
        """
        total = stats.get('total_numbers', 0)
        completed = stats.get('completed', 0)
        answered = stats.get('answered', 0)
        pressed_one = stats.get('pressed_one', 0)
        failed = stats.get('failed', 0)
        cost = stats.get('actual_cost', 0.0)
        
        # Calculate rates
        completion_rate = (completed / total * 100) if total > 0 else 0
        answer_rate = (answered / completed * 100) if completed > 0 else 0
        success_rate = (pressed_one / answered * 100) if answered > 0 else 0
        
        # Progress bars
        completion_bar = UIComponents.progress_bar(completed, total, width=10)
        answer_bar = UIComponents.progress_bar(answered, completed, width=10)
        success_bar = UIComponents.progress_bar(pressed_one, answered, width=10)
        
        dashboard = f"""
📊 **Campaign Statistics**
{UIComponents.SEPARATOR_MEDIUM}

📈 **Overall Progress**
{completion_bar}
└ {completed} / {total} calls completed

📞 **Answer Rate**
{answer_bar}
└ {answered} calls answered

✅ **Success Rate (Pressed 1)**
{success_bar}
└ {pressed_one} successful conversions

❌ **Failed Calls:** {failed}
💰 **Total Cost:** ${cost:.2f}

{UIComponents.SEPARATOR_LIGHT}
**Efficiency Metrics:**
• Completion: {completion_rate:.1f}%
• Answer: {answer_rate:.1f}%
• Conversion: {success_rate:.1f}%
        """.strip()
        
        return dashboard
    
    # =========================================================================
    # Cost Display
    # =========================================================================
    
    @staticmethod
    def cost_display(amount: float, currency: str = "USD", label: str = "Cost") -> str:
        """Format cost with proper currency symbol"""
        symbols = {
            "USD": "$",
            "USDT": "₮",
            "EUR": "€",
            "BTC": "₿",
            "ETH": "Ξ"
        }
        symbol = symbols.get(currency.upper(), "$")
        return f"💰 {label}: {symbol}{amount:.2f}"
    
    # =========================================================================
    # Time Formatting
    # =========================================================================
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """Format seconds into human-readable duration"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    @staticmethod
    def format_timestamp(dt: datetime, include_time: bool = True) -> str:
        """Format datetime for display"""
        if not dt:
            return "N/A"
        
        if include_time:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return dt.strftime("%Y-%m-%d")
    
    # =========================================================================
    # Package Card (for credit purchasing)
    # =========================================================================
    
    @staticmethod
    def package_card(
        credits: int,
        price: float,
        currency: str = "USDT",
        savings: Optional[float] = None
    ) -> str:
        """
        Format credit package as a card
        
        Args:
            credits: Number of credits
            price: Package price
            currency: Currency code
            savings: Optional savings percentage
            
        Returns:
            Formatted package card
        """
        card = f"💎 **{credits} Credits** - ${price} {currency}"
        
        if savings:
            card += f"\n   💚 Save {savings:.0f}%!"
        
        # Add value indicator
        per_credit = price / credits
        card += f"\n   📊 ${per_credit:.3f} per credit"
        
        return card
    
    # =========================================================================
    # Main Menu
    # =========================================================================
    
    @staticmethod
    def main_menu_text(user_data: Dict) -> str:
        """
        Create main menu welcome text
        
        Args:
            user_data: User data dictionary
            
        Returns:
            Formatted main menu text
        """
        first_name = user_data.get('first_name', 'User')
        credits = user_data.get('credits', 0.0)
        total_calls = user_data.get('total_calls', 0)
        
        # Credit status indicator
        if credits > 100:
            credit_status = "🟢"
        elif credits > 20:
            credit_status = "🟡"
        else:
            credit_status = "🔴"
        
        text = f"""
🤖 **Proline P1 Bot**
{UIComponents.SEPARATOR_HEAVY}

👋 Welcome back, **{first_name}**!

**Your Account:**
{credit_status} Credits: **{credits:.2f}**
📞 Total Calls: **{total_calls}**

{UIComponents.SEPARATOR_LIGHT}

**Quick Actions:**
💳 Buy Credits
📝 New Campaign
📊 My Campaigns
⚙️ Settings

Ready to launch your next campaign? 🚀
        """.strip()
        
        return text


# Global UI instance for easy imports
ui = UIComponents()
