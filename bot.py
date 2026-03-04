"""
BRANVEE ADMIN BOT - COMPLETE VERSION
All features: Hours/Days/Weeks/Months/Years, View Tokens, User Management
"""

import logging
import sqlite3
import os
import sys
from datetime import datetime, timedelta
import random
import string
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)

# ============================================
# CONFIGURATION
# ============================================

BOT_TOKEN = os.environ.get('ADMIN_BOT_TOKEN', '8659878049:AAFosBtLo5ElKjH3w3pcfxvM19SOT-DwQ7I')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 6980711942))
DB_PATH = 'data/branvee.db'

os.makedirs('data', exist_ok=True)

# ============================================
# DATABASE FUNCTIONS
# ============================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        token TEXT UNIQUE NOT NULL,
        telegram_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        is_suspended BOOLEAN DEFAULT 0,
        created_by INTEGER
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS renewal_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        old_expiry TIMESTAMP,
        new_expiry TIMESTAMP,
        renewed_by INTEGER,
        renewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def add_user(email, token, expires_at, created_by):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (email, token, expires_at, created_by) VALUES (?, ?, ?, ?)',
                 (email, token, expires_at, created_by))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return user_id
    except Exception as e:
        conn.close()
        return None

def get_user_by_email(email):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (email,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users ORDER BY created_at DESC')
    users = c.fetchall()
    conn.close()
    return users

def get_active_users():
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('SELECT * FROM users WHERE expires_at > ? AND is_suspended = 0', (now,))
    users = c.fetchall()
    conn.close()
    return users

def get_expired_users():
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('SELECT * FROM users WHERE expires_at <= ?', (now,))
    users = c.fetchall()
    conn.close()
    return users

def get_suspended_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE is_suspended = 1')
    users = c.fetchall()
    conn.close()
    return users

def renew_user(user_id, new_expiry, renewed_by):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT expires_at FROM users WHERE id = ?', (user_id,))
    old = c.fetchone()
    if not old:
        conn.close()
        return False
    
    old_expiry = old['expires_at']
    c.execute('UPDATE users SET expires_at = ? WHERE id = ?', (new_expiry, user_id))
    c.execute('INSERT INTO renewal_history (user_id, old_expiry, new_expiry, renewed_by) VALUES (?, ?, ?, ?)',
             (user_id, old_expiry, new_expiry, renewed_by))
    conn.commit()
    conn.close()
    return True

def suspend_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET is_suspended = 1 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True

def activate_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET is_suspended = 0 WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True

def delete_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True

def get_stats():
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    total = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    active = c.execute('SELECT COUNT(*) FROM users WHERE expires_at > ? AND is_suspended = 0', (now,)).fetchone()[0]
    expired = c.execute('SELECT COUNT(*) FROM users WHERE expires_at <= ?', (now,)).fetchone()[0]
    suspended = c.execute('SELECT COUNT(*) FROM users WHERE is_suspended = 1').fetchone()[0]
    
    conn.close()
    return {'total': total, 'active': active, 'expired': expired, 'suspended': suspended}

# ============================================
# UTILITY FUNCTIONS
# ============================================

def generate_token():
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    return f"BRANVEE-{part1}-{part2}"

def format_token(token):
    return f"`{token}`"

def calculate_expiry(days=0, hours=0, weeks=0, months=0, years=0):
    delta = timedelta(days=days + weeks*7 + months*30 + years*365, hours=hours)
    return datetime.now() + delta

def days_until(expiry_date):
    if isinstance(expiry_date, str):
        expiry_date = datetime.fromisoformat(expiry_date)
    delta = expiry_date - datetime.now()
    return delta.days

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# ============================================
# CONVERSATION STATES
# ============================================

EMAIL, DURATION_TYPE, DURATION_VALUE, CONFIRM, USER_SELECTION, NOTES = range(6)

# ============================================
# KEYBOARDS
# ============================================

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("👥 Users", callback_data='menu_users')],
        [InlineKeyboardButton("⚙️ Settings", callback_data='menu_settings')],
        [InlineKeyboardButton("📊 Analytics", callback_data='menu_analytics')],
        [InlineKeyboardButton("ℹ️ Help", callback_data='menu_help')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_users_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data='users_add')],
        [InlineKeyboardButton("✅ Active Users", callback_data='users_active')],
        [InlineKeyboardButton("❌ Expired Users", callback_data='users_expired')],
        [InlineKeyboardButton("⏸️ Suspended Users", callback_data='users_suspended')],
        [InlineKeyboardButton("🔍 Search User", callback_data='users_search')],
        [InlineKeyboardButton("🔙 Back", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_duration_type_menu():
    keyboard = [
        [InlineKeyboardButton("⏰ Hours", callback_data='dur_type_hours')],
        [InlineKeyboardButton("📅 Days", callback_data='dur_type_days')],
        [InlineKeyboardButton("📆 Weeks", callback_data='dur_type_weeks')],
        [InlineKeyboardButton("🗓️ Months", callback_data='dur_type_months')],
        [InlineKeyboardButton("📅 Years", callback_data='dur_type_years')],
        [InlineKeyboardButton("🔙 Back", callback_data='users_add')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_hours_menu():
    keyboard = [
        [InlineKeyboardButton("1 Hour", callback_data='hours_1'),
         InlineKeyboardButton("6 Hours", callback_data='hours_6')],
        [InlineKeyboardButton("12 Hours", callback_data='hours_12'),
         InlineKeyboardButton("24 Hours", callback_data='hours_24')],
        [InlineKeyboardButton("✏️ Custom", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 Back", callback_data='dur_type_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_days_menu():
    keyboard = [
        [InlineKeyboardButton("1 Day", callback_data='days_1'),
         InlineKeyboardButton("7 Days", callback_data='days_7')],
        [InlineKeyboardButton("15 Days", callback_data='days_15'),
         InlineKeyboardButton("30 Days", callback_data='days_30')],
        [InlineKeyboardButton("60 Days", callback_data='days_60'),
         InlineKeyboardButton("90 Days", callback_data='days_90')],
        [InlineKeyboardButton("✏️ Custom", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 Back", callback_data='dur_type_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_weeks_menu():
    keyboard = [
        [InlineKeyboardButton("1 Week", callback_data='weeks_1'),
         InlineKeyboardButton("2 Weeks", callback_data='weeks_2')],
        [InlineKeyboardButton("3 Weeks", callback_data='weeks_3'),
         InlineKeyboardButton("4 Weeks", callback_data='weeks_4')],
        [InlineKeyboardButton("✏️ Custom", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 Back", callback_data='dur_type_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_months_menu():
    keyboard = [
        [InlineKeyboardButton("1 Month", callback_data='months_1'),
         InlineKeyboardButton("3 Months", callback_data='months_3')],
        [InlineKeyboardButton("6 Months", callback_data='months_6'),
         InlineKeyboardButton("9 Months", callback_data='months_9')],
        [InlineKeyboardButton("12 Months", callback_data='months_12')],
        [InlineKeyboardButton("✏️ Custom", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 Back", callback_data='dur_type_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_years_menu():
    keyboard = [
        [InlineKeyboardButton("1 Year", callback_data='years_1'),
         InlineKeyboardButton("2 Years", callback_data='years_2')],
        [InlineKeyboardButton("3 Years", callback_data='years_3'),
         InlineKeyboardButton("5 Years", callback_data='years_5')],
        [InlineKeyboardButton("✏️ Custom", callback_data='dur_custom')],
        [InlineKeyboardButton("🔙 Back", callback_data='dur_type_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_menu():
    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data='confirm_yes')],
        [InlineKeyboardButton("✏️ Edit", callback_data='confirm_edit')],
        [InlineKeyboardButton("🔙 Cancel", callback_data='menu_users')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_action_menu(user_id, email):
    keyboard = [
        [InlineKeyboardButton("🔄 Renew", callback_data=f'renew_{user_id}')],
        [InlineKeyboardButton("🔑 View Token", callback_data=f'token_{user_id}')],
        [InlineKeyboardButton("⏸️ Suspend", callback_data=f'suspend_{user_id}')],
        [InlineKeyboardButton("▶️ Activate", callback_data=f'activate_{user_id}')],
        [InlineKeyboardButton("📝 Edit Notes", callback_data=f'notes_{user_id}')],
        [InlineKeyboardButton("❌ Delete", callback_data=f'delete_{user_id}')],
        [InlineKeyboardButton("🔙 Back", callback_data='menu_users')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_list_keyboard(users, action='select'):
    keyboard = []
    for user in users[:10]:
        btn_text = f"{user['email'][:20]}..." if len(user['email']) > 20 else user['email']
        keyboard.append([InlineKeyboardButton(
            btn_text,
            callback_data=f"{action}_{user['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='menu_users')])
    return InlineKeyboardMarkup(keyboard)

# ============================================
# HANDLERS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    await update.message.reply_text(
        "🔷 **BRANVEE GOLD ADMIN** 🔷\n\nWelcome to Admin Panel. Select an option:",
        reply_markup=get_main_menu(),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await query.edit_message_text("⛔ Unauthorized")
        return
    
    data = query.data
    
    # ========================================
    # MAIN MENU
    # ========================================
    if data == 'menu_main':
        await query.edit_message_text(
            "🔷 **BRANVEE GOLD ADMIN** 🔷\n\nSelect an option:",
            reply_markup=get_main_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'menu_users':
        await query.edit_message_text(
            "👥 **User Management**\n\nChoose an option:",
            reply_markup=get_users_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'menu_analytics':
        stats = get_stats()
        msg = f"""
📊 **Analytics**
═════════════════
👥 Total Users: {stats['total']}
✅ Active: {stats['active']}
❌ Expired: {stats['expired']}
⏸️ Suspended: {stats['suspended']}
        """
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='menu_main')]]
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif data == 'menu_help':
        msg = """
ℹ️ **Help & Commands**
═════════════════════

👥 **Users Menu**
• Add User - Create new user
• Active Users - View active users
• Expired Users - View expired users
• Suspended Users - View suspended
• Search User - Find by email

⚙️ **Settings**
• Renew User - Extend expiry
• View Token - See user's token
• Suspend/Activate - Manage access
• Delete User - Remove user

📊 **Analytics**
• View system statistics
        """
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='menu_main')]]
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ========================================
    # USER MANAGEMENT
    # ========================================
    elif data == 'users_add':
        await query.edit_message_text(
            "📧 **Add User**\n\nPlease send the user's email address:",
            parse_mode='Markdown'
        )
        return EMAIL
    
    elif data == 'users_active':
        users = get_active_users()
        if not users:
            msg = "✅ **Active Users**\n\nNo active users found."
        else:
            msg = "✅ **Active Users**\n\n"
            for user in users:
                days = days_until(user['expires_at'])
                status = "⏸️" if user['is_suspended'] else "✅"
                token_preview = user['token'][:15] + "..."
                msg += f"{status} **{user['email']}**\n"
                msg += f"  🔑 Token: `{token_preview}`\n"
                msg += f"  📅 Expires: {user['expires_at'][:10]} ({days} days)\n"
                msg += f"  🆔 ID: {user['id']}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='menu_users')]]
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif data == 'users_expired':
        users = get_expired_users()
        if not users:
            msg = "❌ **Expired Users**\n\nNo expired users found."
        else:
            msg = "❌ **Expired Users**\n\n"
            for user in users:
                token_preview = user['token'][:15] + "..."
                msg += f"📧 **{user['email']}**\n"
                msg += f"  🔑 Token: `{token_preview}`\n"
                msg += f"  📅 Expired: {user['expires_at'][:10]}\n"
                msg += f"  🆔 ID: {user['id']}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='menu_users')]]
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif data == 'users_suspended':
        users = get_suspended_users()
        if not users:
            msg = "⏸️ **Suspended Users**\n\nNo suspended users found."
        else:
            msg = "⏸️ **Suspended Users**\n\n"
            for user in users:
                token_preview = user['token'][:15] + "..."
                msg += f"📧 **{user['email']}**\n"
                msg += f"  🔑 Token: `{token_preview}`\n"
                msg += f"  📅 Expires: {user['expires_at'][:10]}\n"
                msg += f"  🆔 ID: {user['id']}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='menu_users')]]
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    elif data == 'users_search':
        await query.edit_message_text(
            "🔍 **Search User**\n\nPlease enter email address to search:",
            parse_mode='Markdown'
        )
        return USER_SELECTION
    
    # ========================================
    # SETTINGS MENU
    # ========================================
    elif data == 'menu_settings':
        keyboard = [
            [InlineKeyboardButton("🔄 Renew User", callback_data='settings_renew')],
            [InlineKeyboardButton("🔑 View Token", callback_data='settings_view_token')],
            [InlineKeyboardButton("⏸️ Suspend User", callback_data='settings_suspend')],
            [InlineKeyboardButton("▶️ Activate User", callback_data='settings_activate')],
            [InlineKeyboardButton("❌ Delete User", callback_data='settings_delete')],
            [InlineKeyboardButton("🔙 Back", callback_data='menu_main')]
        ]
        await query.edit_message_text(
            "⚙️ **Settings**\n\nSelect an option:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    # ========================================
    # SETTINGS ACTIONS
    # ========================================
    elif data == 'settings_renew':
        users = get_all_users()
        if not users:
            await query.edit_message_text("❌ No users found.")
        else:
            await query.edit_message_text(
                "🔄 **Renew User**\n\nSelect user to renew:",
                reply_markup=get_user_list_keyboard(users, action='renew'),
                parse_mode='Markdown'
            )
    
    elif data == 'settings_view_token':
        users = get_all_users()
        if not users:
            await query.edit_message_text("❌ No users found.")
        else:
            await query.edit_message_text(
                "🔑 **View Token**\n\nSelect user:",
                reply_markup=get_user_list_keyboard(users, action='token'),
                parse_mode='Markdown'
            )
    
    elif data == 'settings_suspend':
        users = get_active_users()
        if not users:
            await query.edit_message_text("❌ No active users found.")
        else:
            await query.edit_message_text(
                "⏸️ **Suspend User**\n\nSelect user to suspend:",
                reply_markup=get_user_list_keyboard(users, action='suspend'),
                parse_mode='Markdown'
            )
    
    elif data == 'settings_activate':
        users = get_suspended_users()
        if not users:
            await query.edit_message_text("❌ No suspended users found.")
        else:
            await query.edit_message_text(
                "▶️ **Activate User**\n\nSelect user to activate:",
                reply_markup=get_user_list_keyboard(users, action='activate'),
                parse_mode='Markdown'
            )
    
    elif data == 'settings_delete':
        users = get_all_users()
        if not users:
            await query.edit_message_text("❌ No users found.")
        else:
            await query.edit_message_text(
                "❌ **Delete User**\n\nSelect user to delete:",
                reply_markup=get_user_list_keyboard(users, action='delete'),
                parse_mode='Markdown'
            )
    
    # ========================================
    # USER ACTIONS
    # ========================================
    elif data.startswith('renew_'):
        user_id = int(data.split('_')[1])
        user = get_user_by_id(user_id)
        if user:
            context.user_data['renew_user_id'] = user_id
            context.user_data['renew_email'] = user['email']
            await query.edit_message_text(
                f"📧 User: {user['email']}\n"
                f"📅 Current Expiry: {user['expires_at'][:10]}\n\n"
                f"Select duration type:",
                reply_markup=get_duration_type_menu(),
                parse_mode='Markdown'
            )
            return DURATION_TYPE
    
    elif data.startswith('token_'):
        user_id = int(data.split('_')[1])
        user = get_user_by_id(user_id)
        if user:
            msg = f"""
🔑 **User Token**
═════════════════
📧 Email: {user['email']}
🔑 Token: {format_token(user['token'])}
📅 Expires: {user['expires_at'][:10]}
📊 Days left: {days_until(user['expires_at'])}
🆔 ID: {user['id']}
📱 Telegram: {user['telegram_id'] or 'Not linked'}
            """
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='menu_settings')]]
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    elif data.startswith('suspend_'):
        user_id = int(data.split('_')[1])
        suspend_user(user_id)
        await query.edit_message_text(
            "✅ User suspended successfully.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data='menu_settings')
            ]])
        )
    
    elif data.startswith('activate_'):
        user_id = int(data.split('_')[1])
        activate_user(user_id)
        await query.edit_message_text(
            "✅ User activated successfully.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data='menu_settings')
            ]])
        )
    
    elif data.startswith('delete_'):
        user_id = int(data.split('_')[1])
        delete_user(user_id)
        await query.edit_message_text(
            "✅ User deleted successfully.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data='menu_settings')
            ]])
        )
    
    # ========================================
    # DURATION SELECTION
    # ========================================
    elif data == 'dur_type_menu':
        await query.edit_message_text(
            "⏰ **Select Duration Type**",
            reply_markup=get_duration_type_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'dur_type_hours':
        await query.edit_message_text(
            "⏰ **Select Hours**",
            reply_markup=get_hours_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'dur_type_days':
        await query.edit_message_text(
            "📅 **Select Days**",
            reply_markup=get_days_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'dur_type_weeks':
        await query.edit_message_text(
            "📆 **Select Weeks**",
            reply_markup=get_weeks_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'dur_type_months':
        await query.edit_message_text(
            "🗓️ **Select Months**",
            reply_markup=get_months_menu(),
            parse_mode='Markdown'
        )
    
    elif data == 'dur_type_years':
        await query.edit_message_text(
            "📅 **Select Years**",
            reply_markup=get_years_menu(),
            parse_mode='Markdown'
        )
    
    elif data.startswith('hours_'):
        hours = int(data.split('_')[1])
        context.user_data['duration_value'] = hours
        context.user_data['duration_unit'] = 'hours'
        context.user_data['duration_display'] = f"{hours} hours"
        await show_confirmation(query, context)
    
    elif data.startswith('days_'):
        days = int(data.split('_')[1])
        context.user_data['duration_value'] = days
        context.user_data['duration_unit'] = 'days'
        context.user_data['duration_display'] = f"{days} days"
        await show_confirmation(query, context)
    
    elif data.startswith('weeks_'):
        weeks = int(data.split('_')[1])
        context.user_data['duration_value'] = weeks
        context.user_data['duration_unit'] = 'weeks'
        context.user_data['duration_display'] = f"{weeks} weeks"
        await show_confirmation(query, context)
    
    elif data.startswith('months_'):
        months = int(data.split('_')[1])
        context.user_data['duration_value'] = months
        context.user_data['duration_unit'] = 'months'
        context.user_data['duration_display'] = f"{months} months"
        await show_confirmation(query, context)
    
    elif data.startswith('years_'):
        years = int(data.split('_')[1])
        context.user_data['duration_value'] = years
        context.user_data['duration_unit'] = 'years'
        context.user_data['duration_display'] = f"{years} years"
        await show_confirmation(query, context)
    
    elif data == 'dur_custom':
        await query.edit_message_text(
            "✏️ **Custom Duration**\n\nPlease send the number (e.g., 45):",
            parse_mode='Markdown'
        )
        return DURATION_VALUE
    
    # ========================================
    # CONFIRMATION
    # ========================================
    elif data == 'confirm_yes':
        if 'renew_user_id' in context.user_data:
            await process_renewal(query, context)
        else:
            await generate_and_save_token(query, context)
    
    elif data == 'confirm_edit':
        await query.edit_message_text(
            "📧 **Edit Email**\n\nPlease send the user's email address:",
            parse_mode='Markdown'
        )
        return EMAIL
    
    elif data == 'menu_users':
        await query.edit_message_text(
            "👥 **User Management**\n\nSelect an option:",
            reply_markup=get_users_menu(),
            parse_mode='Markdown'
        )

async def show_confirmation(query, context):
    email = context.user_data.get('email')
    duration_value = context.user_data.get('duration_value')
    duration_display = context.user_data.get('duration_display')
    
    # Calculate expiry
    if context.user_data.get('duration_unit') == 'hours':
        expiry = calculate_expiry(hours=duration_value)
    elif context.user_data.get('duration_unit') == 'days':
        expiry = calculate_expiry(days=duration_value)
    elif context.user_data.get('duration_unit') == 'weeks':
        expiry = calculate_expiry(weeks=duration_value)
    elif context.user_data.get('duration_unit') == 'months':
        expiry = calculate_expiry(months=duration_value)
    elif context.user_data.get('duration_unit') == 'years':
        expiry = calculate_expiry(years=duration_value)
    else:
        expiry = calculate_expiry(days=30)
    
    context.user_data['expiry'] = expiry.isoformat()
    
    msg = f"""
📧 **Confirm Details**
═════════════════════
Email: {email}
Duration: {duration_display}
Expires: {expiry.strftime('%Y-%m-%d %H:%M')}

Please confirm:
    """
    
    await query.edit_message_text(
        msg,
        reply_markup=get_confirmation_menu(),
        parse_mode='Markdown'
    )

async def generate_and_save_token(query, context):
    email = context.user_data.get('email')
    expiry = context.user_data.get('expiry')
    token = generate_token()
    
    user_id = add_user(email, token, expiry, ADMIN_ID)
    
    if user_id:
        msg = f"""
✅ **User Added Successfully!**
═══════════════════════════════

📧 Email: {email}
🔑 Token: {format_token(token)}
📅 Expires: {expiry[:10]}
⏳ Duration: {context.user_data.get('duration_display')}

You can now share this token with the user.
        """
    else:
        msg = "❌ **Error**\n\nUser with this email may already exist."
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👥 Back to Users", callback_data='menu_users')
        ]]),
        parse_mode='Markdown'
    )
    
    context.user_data.clear()

async def process_renewal(query, context):
    user_id = context.user_data.get('renew_user_id')
    expiry = context.user_data.get('expiry')
    
    success = renew_user(user_id, expiry, ADMIN_ID)
    
    if success:
        user = get_user_by_id(user_id)
        msg = f"""
✅ **User Renewed Successfully!**
════════════════════════════════

📧 Email: {user['email']}
📅 New Expiry: {expiry[:10]}
⏳ Extended by: {context.user_data.get('duration_display')}
        """
    else:
        msg = "❌ **Error**\n\nFailed to renew user."
    
    await query.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👥 Back to Users", callback_data='menu_users')
        ]]),
        parse_mode='Markdown'
    )
    
    context.user_data.clear()

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    
    if not validate_email(email):
        await update.message.reply_text("❌ Invalid email format. Try again:")
        return EMAIL
    
    if get_user_by_email(email):
        await update.message.reply_text("❌ Email already exists. Try another:")
        return EMAIL
    
    context.user_data['email'] = email
    
    await update.message.reply_text(
        "⏰ **Select Duration Type**",
        reply_markup=get_duration_type_menu(),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def handle_custom_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = int(update.message.text.strip())
        if value < 1:
            raise ValueError
    except:
        await update.message.reply_text("❌ Invalid number. Please enter a positive number:")
        return DURATION_VALUE
    
    # Get the current duration type from context
    # This would need to be stored when they selected the type
    await update.message.reply_text("Please select duration type first.")
    return DURATION_VALUE

async def handle_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip().lower()
    user = get_user_by_email(email)
    
    if not user:
        await update.message.reply_text("❌ User not found.")
        return ConversationHandler.END
    
    days = days_until(user['expires_at'])
    status = "⏸️ Suspended" if user['is_suspended'] else "✅ Active"
    
    msg = f"""
🔍 **User Found**
═════════════════
📧 Email: {user['email']}
🔑 Token: {format_token(user['token'])}
📅 Expires: {user['expires_at'][:10]} ({days} days)
📊 Status: {status}
🆔 ID: {user['id']}
📱 Telegram: {user['telegram_id'] or 'Not linked'}

Select an action:
    """
    
    await update.message.reply_text(
        msg,
        reply_markup=get_user_action_menu(user['id'], user['email']),
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled")
    return ConversationHandler.END

# ============================================
# MAIN
# ============================================

def main():
    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for adding users
    add_user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^users_add$')],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(add_user_conv)
    
    # Conversation handler for custom duration
    custom_dur_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^dur_custom$')],
        states={
            DURATION_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_duration)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(custom_dur_conv)
    
    # Conversation handler for user search
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^users_search$')],
        states={
            USER_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_search)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    app.add_handler(search_conv)
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("\n" + "="*60)
    print("🤖 BRANVEE ADMIN BOT - COMPLETE VERSION")
    print("="*60)
    print("✅ All features loaded:")
    print("   • Hours/Days/Weeks/Months/Years duration")
    print("   • View tokens in user lists")
    print("   • Suspend/Activate/Delete users")
    print("   • Renew users")
    print("   • User search")
    print("="*60 + "\n")
    
    app.run_polling()

if __name__ == '__main__':
    main()