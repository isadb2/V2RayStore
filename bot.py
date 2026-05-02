"""
╔══════════════════════════════════════════════════╗
║         Excore VPN Bot - Single File Version     ║
║         Telegram VPN Sales Bot with Admin Panel  ║
╚══════════════════════════════════════════════════╝

متغیرهای محیطی مورد نیاز:
  BOT_TOKEN            - توکن ربات از BotFather
  DATABASE_URL         - آدرس PostgreSQL (مثلاً از Railway)
  ADMIN_USERS          - آیدی‌های ادمین با کاما (مثال: 123456,789012)
  USDT_WALLET_ADDRESS  - آدرس کیف پول USDT/TRC20
  CRYPTO_CURRENCY      - نوع ارز دیجیتال (پیش‌فرض: USDT_TRC20)
  WEBHOOK_URL          - آدرس عمومی Railway برای webhook (اختیاری، اگر خالی باشد polling فعال می‌شود)
  PORT                 - پورت وب‌سرور (پیش‌فرض: 8443)
"""

import asyncio
import logging
import os
import json
from datetime import datetime, timezone
from typing import Optional, List
from dotenv import load_dotenv

import asyncpg
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.error import TelegramError
from telegram.constants import ParseMode

load_dotenv()

# ═══════════════════════════════════════════════════
#  ایموجی‌ها — برای تغییر هر ایموجی مقدار آن را اینجا عوض کنید
# ═══════════════════════════════════════════════════
EMOJI_WELCOME       = "💎"   # ایموجی پیام خوش‌آمدگویی
EMOJI_BALANCE       = "🪙"   # ایموجی موجودی
EMOJI_SUBSCRIPTION  = "🌟"   # ایموجی اشتراک‌های فعال
EMOJI_QUICK_ACCESS  = "🌐"   # ایموجی دسترسی سریع
EMOJI_BUY           = "🏅"   # ایموجی خرید سرویس
EMOJI_MY_SERVICES   = "😁"   # ایموجی سرویس‌های من
EMOJI_REFERRAL      = "👩‍🎓"  # ایموجی معرفی دوستان
EMOJI_WALLET        = "💰"   # ایموجی کیف پول
EMOJI_APPS          = "🎯"   # ایموجی دریافت برنامه‌ها
EMOJI_SUPPORT       = "💬"   # ایموجی پشتیبانی
EMOJI_DURATION      = "⏱"   # ایموجی مدت سرویس
EMOJI_USERS         = "👤"   # ایموجی لیمیت اتصال
EMOJI_VOLUME        = "💾"   # ایموجی حجم
EMOJI_PRICE         = "💲"   # ایموجی قیمت
EMOJI_VPN_DESC      = "🛡"   # ایموجی توضیح VPN
EMOJI_NO_SERVICE    = "😊"   # ایموجی بدون سرویس
EMOJI_LINUX         = "🐧"   # ایموجی لینوکس
EMOJI_WINDOWS       = "🪟"   # ایموجی ویندوز
EMOJI_APPLE         = "🍎"   # ایموجی اپل
EMOJI_TICKET        = "🎫"   # ایموجی تیکت
EMOJI_SUCCESS       = "✅"   # ایموجی موفقیت
EMOJI_ERROR         = "❌"   # ایموجی خطا
EMOJI_WARNING       = "⚠️"   # ایموجی هشدار
EMOJI_ADMIN         = "👑"   # ایموجی ادمین
EMOJI_STATS         = "📊"   # ایموجی آمار
EMOJI_BROADCAST     = "📢"   # ایموجی ارسال همگانی
EMOJI_SETTINGS      = "⚙️"   # ایموجی تنظیمات
EMOJI_ORDER         = "📦"   # ایموجی سفارش
EMOJI_CONFIRM       = "✔️"   # ایموجی تایید
EMOJI_REJECT        = "🚫"   # ایموجی رد
EMOJI_CONFIG        = "🔑"   # ایموجی کانفیگ
EMOJI_BACK          = "🔙"   # ایموجی بازگشت
EMOJI_REFERRAL_LINK = "🔗"   # ایموجی لینک رفرال
EMOJI_REWARD        = "🎁"   # ایموجی جایزه رفرال

# ═══════════════════════════════════════════════════
#  تنظیمات اصلی
# ═══════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN           = os.getenv("BOT_TOKEN", "8734599238:AAHGC_Y_vVRVO66U59LSRSfinD9qRseVHCs")
DATABASE_URL        = os.getenv("DATABASE_URL", "postgresql://postgres:KlSJaIrPXGKCXRMgAIxwQQxqhjgPgCgT@postgres.railway.internal:5432/railway")
ADMIN_USERS_STR     = os.getenv("ADMIN_USERS", "8105229274")
USDT_WALLET         = os.getenv("USDT_WALLET_ADDRESS", "YOUR_USDT_WALLET_ADDRESS")
CRYPTO_CURRENCY     = os.getenv("CRYPTO_CURRENCY", "USDT_TRC20")
WEBHOOK_URL         = os.getenv("WEBHOOK_URL", "")
PORT                = int(os.getenv("PORT", "8443"))

REFERRAL_REWARD_TOMAN = 10000  # مبلغ پاداش رفرال به تومان

ADMIN_IDS: List[int] = []
if ADMIN_USERS_STR:
    for _a in ADMIN_USERS_STR.split(","):
        try:
            ADMIN_IDS.append(int(_a.strip()))
        except ValueError:
            pass

# لینک‌های دانلود برنامه‌ها — در اینجا تغییر دهید
APP_LINKS = {
    "linux":   {"link": "https://v2rayng.com/linux",   "desc": "V2RayN برای لینوکس — نصب با دستور: snap install v2rayan"},
    "windows": {"link": "https://github.com/2dust/v2rayN/releases", "desc": "V2RayN برای ویندوز — فایل Setup.exe را دانلود کنید"},
    "apple":   {"link": "https://apps.apple.com/app/streisand/id6450534064", "desc": "Streisand برای آیفون و مک‌بوک — از App Store دانلود کنید"},
}

# State های ConversationHandler
(
    SUPPORT_WAITING_MESSAGE,
    ADMIN_WAITING_WALLET,
    ADMIN_WAITING_CONFIG,
    ADMIN_WAITING_BROADCAST,
    ADMIN_WAITING_BALANCE,
    ADMIN_WAITING_SERVICE_NAME,
    ADMIN_WAITING_SERVICE_DAYS,
    ADMIN_WAITING_SERVICE_LIMIT,
    ADMIN_WAITING_SERVICE_VOLUME,
    ADMIN_WAITING_SERVICE_PRICE,
    ADMIN_WAITING_SERVICE_DESC,
) = range(11)

# ═══════════════════════════════════════════════════
#  دیتابیس
# ═══════════════════════════════════════════════════
_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id      BIGINT PRIMARY KEY,
                username     TEXT,
                first_name   TEXT,
                balance      INTEGER DEFAULT 0,
                referrer_id  BIGINT,
                join_date    TIMESTAMPTZ DEFAULT NOW(),
                is_banned    BOOLEAN DEFAULT FALSE,
                is_admin     BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS services (
                id          SERIAL PRIMARY KEY,
                name        TEXT NOT NULL,
                days        INTEGER NOT NULL,
                user_limit  INTEGER NOT NULL DEFAULT 1,
                volume_gb   FLOAT NOT NULL DEFAULT 1,
                price_toman INTEGER NOT NULL,
                description TEXT,
                is_active   BOOLEAN DEFAULT TRUE
            );

            CREATE TABLE IF NOT EXISTS orders (
                id           SERIAL PRIMARY KEY,
                user_id      BIGINT REFERENCES users(user_id),
                service_id   INTEGER REFERENCES services(id),
                status       TEXT DEFAULT 'pending',
                config_text  TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                confirmed_at TIMESTAMPTZ,
                admin_id     BIGINT
            );

            CREATE TABLE IF NOT EXISTS referrals (
                id              SERIAL PRIMARY KEY,
                referrer_id     BIGINT REFERENCES users(user_id),
                referred_user_id BIGINT REFERENCES users(user_id) UNIQUE,
                reward_claimed  BOOLEAN DEFAULT FALSE,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS wallet_transactions (
                id          SERIAL PRIMARY KEY,
                user_id     BIGINT REFERENCES users(user_id),
                amount      INTEGER NOT NULL,
                type        TEXT NOT NULL,
                description TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id         SERIAL PRIMARY KEY,
                user_id    BIGINT REFERENCES users(user_id),
                admin_id   BIGINT,
                status     TEXT DEFAULT 'open',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS ticket_messages (
                id        SERIAL PRIMARY KEY,
                ticket_id INTEGER REFERENCES tickets(id),
                sender_id BIGINT,
                text      TEXT,
                sent_at   TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)

        # سرویس پیش‌فرض اگر وجود ندارد
        existing = await conn.fetchval("SELECT COUNT(*) FROM services")
        if existing == 0:
            await conn.execute("""
                INSERT INTO services (name, days, user_limit, volume_gb, price_toman, description, is_active)
                VALUES ('7 روزه 1 گیگ', 7, 1, 1, 200000, 'فیلترشکن ایران مناسب کاربران ایران.', TRUE)
            """)

        # تنظیمات اولیه
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ('usdt_wallet', $1)
            ON CONFLICT (key) DO NOTHING
        """, USDT_WALLET)

        # ادمین‌های اولیه از env
        for admin_id in ADMIN_IDS:
            await conn.execute("""
                INSERT INTO users (user_id, first_name, is_admin)
                VALUES ($1, 'Admin', TRUE)
                ON CONFLICT (user_id) DO UPDATE SET is_admin = TRUE
            """, admin_id)

    logger.info("✅ دیتابیس آماده شد")

# ═══════════════════════════════════════════════════
#  توابع کمکی دیتابیس
# ═══════════════════════════════════════════════════
async def upsert_user(user_id: int, username: str, first_name: str, referrer_id: Optional[int] = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)
        if existing:
            await conn.execute(
                "UPDATE users SET username=$2, first_name=$3 WHERE user_id=$1",
                user_id, username, first_name
            )
            return existing
        else:
            is_admin = user_id in ADMIN_IDS
            row = await conn.fetchrow("""
                INSERT INTO users (user_id, username, first_name, referrer_id, is_admin)
                VALUES ($1, $2, $3, $4, $5) RETURNING *
            """, user_id, username, first_name, referrer_id, is_admin)
            # ثبت رفرال
            if referrer_id and referrer_id != user_id:
                await conn.execute("""
                    INSERT INTO referrals (referrer_id, referred_user_id)
                    VALUES ($1, $2) ON CONFLICT DO NOTHING
                """, referrer_id, user_id)
            return row

async def get_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

async def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    user = await get_user(user_id)
    return user and user["is_admin"]

async def get_active_services():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM services WHERE is_active=TRUE ORDER BY id")

async def get_service(service_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM services WHERE id=$1", service_id)

async def get_user_active_orders(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT o.*, s.name as service_name, s.days, s.volume_gb
            FROM orders o JOIN services s ON o.service_id=s.id
            WHERE o.user_id=$1 AND o.status='confirmed'
            ORDER BY o.confirmed_at DESC
        """, user_id)

async def get_setting(key: str, default: str = "") -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key=$1", key)
        return row["value"] if row else default

async def set_setting(key: str, value: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value=$2
        """, key, value)

async def add_wallet_transaction(user_id: int, amount: int, ttype: str, description: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO wallet_transactions (user_id, amount, type, description)
            VALUES ($1, $2, $3, $4)
        """, user_id, amount, ttype, description)
        if ttype == "credit":
            await conn.execute("UPDATE users SET balance=balance+$1 WHERE user_id=$2", amount, user_id)
        else:
            await conn.execute("UPDATE users SET balance=balance-$1 WHERE user_id=$2", amount, user_id)

async def get_wallet_history(user_id: int, limit: int = 10):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM wallet_transactions WHERE user_id=$1
            ORDER BY created_at DESC LIMIT $2
        """, user_id, limit)

async def create_order(user_id: int, service_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO orders (user_id, service_id, status)
            VALUES ($1, $2, 'pending') RETURNING id
        """, user_id, service_id)
        return row["id"]

async def get_orders_by_status(status: str, limit: int = 20):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT o.*, u.username, u.first_name, s.name as service_name, s.price_toman
            FROM orders o
            JOIN users u ON o.user_id=u.user_id
            JOIN services s ON o.service_id=s.id
            WHERE o.status=$1 ORDER BY o.created_at DESC LIMIT $2
        """, status, limit)

async def get_order(order_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT o.*, u.username, u.first_name, s.name as service_name, s.price_toman
            FROM orders o
            JOIN users u ON o.user_id=u.user_id
            JOIN services s ON o.service_id=s.id
            WHERE o.id=$1
        """, order_id)

async def update_order_status(order_id: int, status: str, admin_id: Optional[int] = None, config_text: Optional[str] = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        confirmed_at = datetime.now(timezone.utc) if status == "confirmed" else None
        await conn.execute("""
            UPDATE orders SET status=$2, admin_id=$3, config_text=$4, confirmed_at=$5
            WHERE id=$1
        """, order_id, status, admin_id, config_text, confirmed_at)

async def get_all_users(limit: int = 50, offset: int = 0):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM users ORDER BY join_date DESC LIMIT $1 OFFSET $2
        """, limit, offset)

async def ban_user(user_id: int, ban: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_banned=$2 WHERE user_id=$1", user_id, ban)

async def get_stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        users_count   = await conn.fetchval("SELECT COUNT(*) FROM users")
        orders_total  = await conn.fetchval("SELECT COUNT(*) FROM orders")
        orders_pending= await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status='pending'")
        orders_confirmed = await conn.fetchval("SELECT COUNT(*) FROM orders WHERE status='confirmed'")
        total_revenue = await conn.fetchval("""
            SELECT COALESCE(SUM(s.price_toman),0)
            FROM orders o JOIN services s ON o.service_id=s.id
            WHERE o.status='confirmed'
        """)
        return {
            "users": users_count,
            "orders_total": orders_total,
            "orders_pending": orders_pending,
            "orders_confirmed": orders_confirmed,
            "revenue": total_revenue,
        }

async def open_or_get_ticket(user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM tickets WHERE user_id=$1 AND status='open'", user_id
        )
        if row:
            return row["id"]
        row = await conn.fetchrow(
            "INSERT INTO tickets (user_id) VALUES ($1) RETURNING id", user_id
        )
        return row["id"]

async def add_ticket_message(ticket_id: int, sender_id: int, text: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO ticket_messages (ticket_id, sender_id, text) VALUES ($1, $2, $3)
        """, ticket_id, sender_id, text)

async def get_open_tickets():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT t.*, u.username, u.first_name,
                   (SELECT text FROM ticket_messages WHERE ticket_id=t.id ORDER BY sent_at DESC LIMIT 1) as last_msg
            FROM tickets t JOIN users u ON t.user_id=u.user_id
            WHERE t.status='open' ORDER BY t.created_at DESC LIMIT 30
        """)

async def get_ticket_messages(ticket_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM ticket_messages WHERE ticket_id=$1 ORDER BY sent_at
        """, ticket_id)

async def close_ticket(ticket_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tickets SET status='closed' WHERE id=$1", ticket_id)

async def get_referral_count(user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=$1", user_id
        ) or 0

async def process_referral_reward(referred_user_id: int):
    """پس از اولین خرید موفق، به معرف جایزه داده می‌شود."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        ref = await conn.fetchrow("""
            SELECT * FROM referrals WHERE referred_user_id=$1 AND reward_claimed=FALSE
        """, referred_user_id)
        if ref:
            await conn.execute(
                "UPDATE referrals SET reward_claimed=TRUE WHERE id=$1", ref["id"]
            )
            await add_wallet_transaction(
                ref["referrer_id"], REFERRAL_REWARD_TOMAN, "credit",
                f"جایزه معرفی کاربر {referred_user_id}"
            )
            return ref["referrer_id"]
    return None

# ═══════════════════════════════════════════════════
#  کیبوردها
# ═══════════════════════════════════════════════════
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("پنل", callback_data="panel"),
            InlineKeyboardButton("کانال", callback_data="channel"),
            InlineKeyboardButton("خرید", callback_data="buy_service"),
            InlineKeyboardButton("پشتیبان", callback_data="support"),
        ],
        [
            InlineKeyboardButton(f"خرید سرویس {EMOJI_BUY}", callback_data="buy_service"),
            InlineKeyboardButton(f"سرویس های من {EMOJI_MY_SERVICES}", callback_data="my_services"),
        ],
        [
            InlineKeyboardButton(f"معرفی دوستان {EMOJI_REFERRAL}", callback_data="referral"),
            InlineKeyboardButton(f"کیف پول {EMOJI_WALLET}", callback_data="wallet"),
        ],
        [
            InlineKeyboardButton(f"دریافت برنامه ها {EMOJI_APPS}", callback_data="apps"),
            InlineKeyboardButton(f"پشتیبانی {EMOJI_SUPPORT}", callback_data="support"),
        ],
    ])

def back_keyboard(back_cb="main_menu"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data=back_cb)]
    ])

def back_and_buy_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"خرید سرویس {EMOJI_BUY}", callback_data="buy_service")],
        [InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="main_menu")],
    ])

def apps_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{EMOJI_LINUX} لینوکس", callback_data="app_linux"),
            InlineKeyboardButton(f"{EMOJI_WINDOWS} ویندوز", callback_data="app_windows"),
        ],
        [InlineKeyboardButton(f"{EMOJI_APPLE} اپل (آیفون و مک‌بوک)", callback_data="app_apple")],
        [InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="main_menu")],
    ])

def service_keyboard(service):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➖", callback_data=f"srv_ign"),
            InlineKeyboardButton(str(service["user_limit"]), callback_data=f"srv_ign"),
            InlineKeyboardButton("➕", callback_data=f"srv_ign"),
        ],
        [
            InlineKeyboardButton("➖", callback_data=f"srv_ign"),
            InlineKeyboardButton(str(service["days"]), callback_data=f"srv_ign"),
            InlineKeyboardButton("➕", callback_data=f"srv_ign"),
        ],
        [
            InlineKeyboardButton("➖", callback_data=f"srv_ign"),
            InlineKeyboardButton(str(int(service["volume_gb"])), callback_data=f"srv_ign"),
            InlineKeyboardButton("➕", callback_data=f"srv_ign"),
        ],
        [InlineKeyboardButton("ثبت سفارش", callback_data=f"order_{service['id']}")],
    ])

def admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{EMOJI_USERS} کاربران", callback_data="admin_users"),
            InlineKeyboardButton(f"{EMOJI_ORDER} سفارشات", callback_data="admin_orders"),
        ],
        [
            InlineKeyboardButton(f"{EMOJI_STATS} آمار", callback_data="admin_stats"),
            InlineKeyboardButton(f"{EMOJI_BROADCAST} ارسال همگانی", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(f"🛍 مدیریت سرویس‌ها", callback_data="admin_services_list"),
            InlineKeyboardButton(f"{EMOJI_SETTINGS} تنظیمات کیف پول", callback_data="admin_wallet_settings"),
        ],
        [
            InlineKeyboardButton(f"{EMOJI_TICKET} تیکت‌ها", callback_data="admin_tickets"),
        ],
    ])

def order_admin_keyboard(order_id: int, status: str):
    buttons = []
    if status == "pending":
        buttons.append([
            InlineKeyboardButton(f"{EMOJI_CONFIRM} تایید پرداخت", callback_data=f"adm_confirm_{order_id}"),
            InlineKeyboardButton(f"{EMOJI_REJECT} رد سفارش", callback_data=f"adm_reject_{order_id}"),
        ])
    elif status == "confirmed":
        buttons.append([
            InlineKeyboardButton(f"{EMOJI_CONFIG} ارسال کانفیگ", callback_data=f"adm_send_config_{order_id}"),
        ])
    buttons.append([InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="admin_orders")])
    return InlineKeyboardMarkup(buttons)

# ═══════════════════════════════════════════════════
#  هندلرهای اصلی
# ═══════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر /start"""
    tg_user = update.effective_user
    ref_id = None

    # بررسی لینک رفرال
    if context.args:
        try:
            ref_id = int(context.args[0].replace("ref_", ""))
            if ref_id == tg_user.id:
                ref_id = None
        except (ValueError, AttributeError):
            pass

    user = await upsert_user(tg_user.id, tg_user.username or "", tg_user.first_name or "", ref_id)

    if user and user["is_banned"]:
        await update.message.reply_text("❌ حساب شما مسدود شده است.")
        return

    balance = user["balance"] if user else 0

    # تعداد سرویس‌های فعال
    pool = await get_pool()
    async with pool.acquire() as conn:
        active_count = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE user_id=$1 AND status='confirmed'", tg_user.id
        )

    text = (
        f"{EMOJI_WELCOME} خوش آمدید به Excore\n\n"
        f"{EMOJI_BALANCE} موجودی: {balance:,} تومان\n"
        f"{EMOJI_SUBSCRIPTION} اشتراک‌های فعال: {active_count}\n\n"
        f"{EMOJI_QUICK_ACCESS} دسترسی سریع\n"
        f"پنل | کانال | خرید | پشتیبان"
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=main_menu_keyboard())
    elif update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=main_menu_keyboard())
        except TelegramError:
            await update.callback_query.message.reply_text(text, reply_markup=main_menu_keyboard())

# ─────────────────────────────────────────────────
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به منوی اصلی از callback"""
    query = update.callback_query
    await query.answer()
    tg_user = update.effective_user
    user = await get_user(tg_user.id)
    balance = user["balance"] if user else 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        active_count = await conn.fetchval(
            "SELECT COUNT(*) FROM orders WHERE user_id=$1 AND status='confirmed'", tg_user.id
        )

    text = (
        f"{EMOJI_WELCOME} خوش آمدید به Excore\n\n"
        f"{EMOJI_BALANCE} موجودی: {balance:,} تومان\n"
        f"{EMOJI_SUBSCRIPTION} اشتراک‌های فعال: {active_count}\n\n"
        f"{EMOJI_QUICK_ACCESS} دسترسی سریع\n"
        f"پنل | کانال | خرید | پشتیبان"
    )
    try:
        await query.edit_message_text(text, reply_markup=main_menu_keyboard())
    except TelegramError:
        await query.message.reply_text(text, reply_markup=main_menu_keyboard())

# ─────────────────────────────────────────────────
async def buy_service_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    services = await get_active_services()
    if not services:
        await query.edit_message_text(
            "در حال حاضر سرویس فعالی موجود نیست.",
            reply_markup=back_keyboard()
        )
        return

    for service in services:
        text = (
            f"🛒 خرید سرویس\n\n"
            f"{EMOJI_DURATION} مدت: {service['days']} روز\n"
            f"{EMOJI_USERS} لیمیت اتصال: {service['user_limit']} نفر\n"
            f"{EMOJI_VOLUME} حجم: {service['volume_gb']} گیگ\n"
            f"{EMOJI_PRICE} قیمت نهایی: {service['price_toman']:,} تومان\n\n"
            f"{EMOJI_VPN_DESC} {service['description'] or ''}"
        )
        try:
            await query.edit_message_text(text, reply_markup=service_keyboard(service))
        except TelegramError:
            await query.message.reply_text(text, reply_markup=service_keyboard(service))
        break  # فعلاً فقط اولین سرویس

# ─────────────────────────────────────────────────
async def place_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    service_id = int(query.data.split("_")[1])
    user_id = update.effective_user.id

    user = await get_user(user_id)
    if user and user["is_banned"]:
        await query.answer("حساب شما مسدود است.", show_alert=True)
        return

    service = await get_service(service_id)
    if not service:
        await query.answer("سرویس یافت نشد.", show_alert=True)
        return

    order_id = await create_order(user_id, service_id)
    wallet_address = await get_setting("usdt_wallet", USDT_WALLET)

    text = (
        f"{EMOJI_ORDER} سفارش شما ثبت شد (شماره: #{order_id})\n\n"
        f"برای پرداخت لطفاً مبلغ\n"
        f"💰 {service['price_toman']:,} تومان\n"
        f"را به آدرس {CRYPTO_CURRENCY} زیر ارسال کنید:\n\n"
        f"<code>{wallet_address}</code>\n\n"
        f"بعد از پرداخت، ادمین سفارش شما را تایید و کانفیگ ارسال می‌کند.\n"
        f"شماره سفارش خود را نگه دارید: #{order_id}"
    )

    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())
    except TelegramError:
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())

    # اطلاع به ادمین‌ها
    tg_user = update.effective_user
    admin_text = (
        f"{EMOJI_ORDER} سفارش جدید #{order_id}\n\n"
        f"👤 کاربر: {tg_user.first_name} (@{tg_user.username or 'N/A'})\n"
        f"🆔 آیدی: {user_id}\n"
        f"🛍 سرویس: {service['name']}\n"
        f"💰 مبلغ: {service['price_toman']:,} تومان\n"
        f"📅 تاریخ: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC"
    )
    admin_kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{EMOJI_CONFIRM} تایید", callback_data=f"adm_confirm_{order_id}"),
            InlineKeyboardButton(f"{EMOJI_REJECT} رد", callback_data=f"adm_reject_{order_id}"),
        ]
    ])
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_text, reply_markup=admin_kb)
        except TelegramError:
            pass

# ─────────────────────────────────────────────────
async def my_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    orders = await get_user_active_orders(user_id)

    if not orders:
        text = (
            f"{EMOJI_NO_SERVICE} در حال حاضر سرویسی برای شما ثبت نشده است.\n\n"
            f"برای خرید سرویس جدید، از دکمه زیر استفاده کنید."
        )
        try:
            await query.edit_message_text(text, reply_markup=back_and_buy_keyboard())
        except TelegramError:
            await query.message.reply_text(text, reply_markup=back_and_buy_keyboard())
        return

    text = f"📋 سرویس‌های فعال شما:\n\n"
    buttons = []
    for order in orders:
        conf_date = order["confirmed_at"]
        conf_str = conf_date.strftime("%Y-%m-%d") if conf_date else "N/A"
        text += (
            f"🔹 {order['service_name']}\n"
            f"   تاریخ تایید: {conf_str}\n"
            f"   شماره سفارش: #{order['id']}\n\n"
        )
        if order["config_text"]:
            buttons.append([
                InlineKeyboardButton(
                    f"{EMOJI_CONFIG} دریافت کانفیگ #{order['id']}",
                    callback_data=f"get_config_{order['id']}"
                )
            ])

    buttons.append([InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="main_menu")])
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except TelegramError:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ─────────────────────────────────────────────────
async def get_config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])
    user_id = update.effective_user.id

    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT * FROM orders WHERE id=$1 AND user_id=$2", order_id, user_id
        )
    if not order or not order["config_text"]:
        await query.answer("کانفیگ یافت نشد.", show_alert=True)
        return

    await query.message.reply_text(
        f"{EMOJI_CONFIG} کانفیگ سرویس شما:\n\n<code>{order['config_text']}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard("my_services")
    )

# ─────────────────────────────────────────────────
async def apps_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        f"{EMOJI_APPS} انتخاب پلتفرم\n\n"
        f"یکی از پلتفرم‌ها را انتخاب کنید"
    )
    try:
        await query.edit_message_text(text, reply_markup=apps_keyboard())
    except TelegramError:
        await query.message.reply_text(text, reply_markup=apps_keyboard())

async def app_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    platform = query.data.split("_")[1]  # linux / windows / apple
    info = APP_LINKS.get(platform, {})

    platform_names = {"linux": "لینوکس", "windows": "ویندوز", "apple": "اپل (آیفون و مک‌بوک)"}
    name = platform_names.get(platform, platform)

    text = (
        f"📥 دانلود برنامه برای {name}\n\n"
        f"🔗 لینک دانلود:\n{info.get('link', 'N/A')}\n\n"
        f"📖 راهنما:\n{info.get('desc', '')}"
    )
    try:
        await query.edit_message_text(text, reply_markup=back_keyboard("apps"),
                                       disable_web_page_preview=True)
    except TelegramError:
        await query.message.reply_text(text, reply_markup=back_keyboard("apps"),
                                        disable_web_page_preview=True)

# ─────────────────────────────────────────────────
async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = await get_user(user_id)
    count = await get_referral_count(user_id)
    bot = await context.bot.get_me()
    ref_link = f"https://t.me/{bot.username}?start=ref_{user_id}"

    text = (
        f"{EMOJI_REFERRAL_LINK} معرفی دوستان — کسب درآمد با دعوت\n\n"
        f"لینک اختصاصی شما:\n<code>{ref_link}</code>\n\n"
        f"👥 تعداد دعوت‌شدگان: {count}\n"
        f"{EMOJI_REWARD} به ازای هر خرید دوست، {REFERRAL_REWARD_TOMAN:,} تومان اعتبار هدیه می‌گیرید.\n\n"
        f"لینک را با دوستانتان به اشتراک بگذارید {EMOJI_REFERRAL}"
    )
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())
    except TelegramError:
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())

# ─────────────────────────────────────────────────
async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user = await get_user(user_id)
    balance = user["balance"] if user else 0
    history = await get_wallet_history(user_id, 5)

    text = f"{EMOJI_WALLET} کیف پول\n\n💰 موجودی: {balance:,} تومان\n\n"
    if history:
        text += "📜 آخرین تراکنش‌ها:\n"
        for tx in history:
            sign = "+" if tx["type"] == "credit" else "-"
            text += f"  {sign}{tx['amount']:,} — {tx['description'] or ''}\n"
    else:
        text += "تاریخچه‌ای موجود نیست."

    try:
        await query.edit_message_text(text, reply_markup=back_keyboard())
    except TelegramError:
        await query.message.reply_text(text, reply_markup=back_keyboard())

# ─────────────────────────────────────────────────
async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال توسعه...", show_alert=False)

async def channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("لینک کانال در تنظیمات تعریف نشده.", show_alert=True)

async def ignore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

# ═══════════════════════════════════════════════════
#  سیستم پشتیبانی (Conversation)
# ═══════════════════════════════════════════════════
async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        send_func = query.message.reply_text
    else:
        send_func = update.message.reply_text

    text = (
        f"{EMOJI_SUPPORT} پشتیبانی\n\n"
        f"لطفاً پیام خود را بنویسید.\n"
        f"برای خروج از چت پشتیبانی /cancel را وارد کنید."
    )
    await send_func(text)
    return SUPPORT_WAITING_MESSAGE

async def support_receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or update.message.caption or ""

    user = await get_user(user_id)
    if user and user["is_banned"]:
        await update.message.reply_text("حساب شما مسدود است.")
        return ConversationHandler.END

    ticket_id = await open_or_get_ticket(user_id)
    await add_ticket_message(ticket_id, user_id, text)

    await update.message.reply_text(
        f"{EMOJI_SUCCESS} پیام شما ارسال شد. منتظر پاسخ پشتیبانی باشید.\n"
        f"شماره تیکت: #{ticket_id}\n"
        f"برای خروج /cancel را وارد کنید."
    )

    tg_user = update.effective_user
    admin_text = (
        f"{EMOJI_TICKET} تیکت جدید / پیام جدید #{ticket_id}\n\n"
        f"👤 کاربر: {tg_user.first_name} (@{tg_user.username or 'N/A'})\n"
        f"🆔 آیدی: {user_id}\n"
        f"💬 پیام:\n{text}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📨 پاسخ", callback_data=f"adm_reply_{ticket_id}_{user_id}")]
    ])
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_text, reply_markup=kb)
        except TelegramError:
            pass

    return SUPPORT_WAITING_MESSAGE

async def support_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # بستن تیکت باز
    pool = await get_pool()
    async with pool.acquire() as conn:
        ticket = await conn.fetchrow(
            "SELECT id FROM tickets WHERE user_id=$1 AND status='open'", user_id
        )
        if ticket:
            await close_ticket(ticket["id"])

    await update.message.reply_text(
        f"{EMOJI_SUCCESS} از پشتیبانی خارج شدید.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ═══════════════════════════════════════════════════
#  پنل ادمین
# ═══════════════════════════════════════════════════
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("❌ دسترسی ندارید.")
        return
    await update.message.reply_text(
        f"{EMOJI_ADMIN} پنل مدیریت Excore",
        reply_markup=admin_menu_keyboard()
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    await query.answer()
    data = query.data

    # ───── آمار ─────
    if data == "admin_stats":
        stats = await get_stats()
        text = (
            f"{EMOJI_STATS} آمار ربات\n\n"
            f"👥 کاربران: {stats['users']}\n"
            f"📦 کل سفارشات: {stats['orders_total']}\n"
            f"⏳ در انتظار تایید: {stats['orders_pending']}\n"
            f"{EMOJI_CONFIRM} تاییدشده: {stats['orders_confirmed']}\n"
            f"💰 درآمد کل: {stats['revenue']:,} تومان"
        )
        await query.edit_message_text(text, reply_markup=back_keyboard("admin_back"))

    # ───── سفارشات ─────
    elif data == "admin_orders":
        buttons = [
            [
                InlineKeyboardButton("⏳ در انتظار", callback_data="admin_orders_pending"),
                InlineKeyboardButton(f"{EMOJI_CONFIRM} تاییدشده", callback_data="admin_orders_confirmed"),
                InlineKeyboardButton(f"{EMOJI_REJECT} ردشده", callback_data="admin_orders_rejected"),
            ],
            [InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="admin_back")],
        ]
        await query.edit_message_text(
            f"{EMOJI_ORDER} مدیریت سفارشات",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("admin_orders_"):
        status_map = {"pending": "در انتظار", "confirmed": "تایید‌شده", "rejected": "ردشده"}
        status = data.replace("admin_orders_", "")
        orders = await get_orders_by_status(status)
        if not orders:
            await query.edit_message_text(
                f"سفارشی با وضعیت «{status_map.get(status, status)}» وجود ندارد.",
                reply_markup=back_keyboard("admin_orders")
            )
            return
        buttons = []
        for o in orders:
            label = f"#{o['id']} — {o['first_name']} — {o['service_name']} — {o['price_toman']:,}T"
            buttons.append([InlineKeyboardButton(label, callback_data=f"admin_order_detail_{o['id']}")])
        buttons.append([InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="admin_orders")])
        await query.edit_message_text(
            f"سفارشات {status_map.get(status, status)}:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("admin_order_detail_"):
        order_id = int(data.split("_")[-1])
        order = await get_order(order_id)
        if not order:
            await query.answer("سفارش یافت نشد.", show_alert=True)
            return
        text = (
            f"{EMOJI_ORDER} جزئیات سفارش #{order_id}\n\n"
            f"👤 کاربر: {order['first_name']} (@{order['username'] or 'N/A'})\n"
            f"🆔 آیدی: {order['user_id']}\n"
            f"🛍 سرویس: {order['service_name']}\n"
            f"💰 مبلغ: {order['price_toman']:,} تومان\n"
            f"📊 وضعیت: {order['status']}\n"
            f"📅 تاریخ: {order['created_at'].strftime('%Y-%m-%d %H:%M')}"
        )
        await query.edit_message_text(text, reply_markup=order_admin_keyboard(order_id, order["status"]))

    # ───── تایید سفارش ─────
    elif data.startswith("adm_confirm_"):
        order_id = int(data.split("_")[-1])
        await update_order_status(order_id, "confirmed", user_id)
        order = await get_order(order_id)
        await query.edit_message_text(
            f"{EMOJI_SUCCESS} سفارش #{order_id} تایید شد.\nبرای ارسال کانفیگ دکمه زیر را بزنید:",
            reply_markup=order_admin_keyboard(order_id, "confirmed")
        )
        # اطلاع به کاربر
        if order:
            try:
                await context.bot.send_message(
                    order["user_id"],
                    f"{EMOJI_SUCCESS} سفارش شما تایید شد.\nکانفیگ به زودی ارسال می‌شود."
                )
            except TelegramError:
                pass
            # پاداش رفرال
            await process_referral_reward(order["user_id"])

    # ───── رد سفارش ─────
    elif data.startswith("adm_reject_"):
        order_id = int(data.split("_")[-1])
        await update_order_status(order_id, "rejected", user_id)
        order = await get_order(order_id)
        await query.edit_message_text(
            f"{EMOJI_REJECT} سفارش #{order_id} رد شد.",
            reply_markup=back_keyboard("admin_orders")
        )
        if order:
            try:
                await context.bot.send_message(
                    order["user_id"],
                    f"{EMOJI_REJECT} متأسفانه سفارش #{order_id} رد شد.\nبرای اطلاعات بیشتر با پشتیبانی تماس بگیرید."
                )
            except TelegramError:
                pass

    # ───── ارسال کانفیگ ─────
    elif data.startswith("adm_send_config_"):
        order_id = int(data.split("_")[-1])
        context.user_data["config_order_id"] = order_id
        await query.edit_message_text(
            f"{EMOJI_CONFIG} کانفیگ سفارش #{order_id} را وارد کنید:\n(متن کانفیگ را ارسال کنید)"
        )
        return  # ادامه در هندلر متن

    # ───── کاربران ─────
    elif data == "admin_users":
        users = await get_all_users(20, 0)
        buttons = []
        for u in users:
            status = "🔴" if u["is_banned"] else "🟢"
            label = f"{status} {u['first_name']} (@{u['username'] or 'N/A'}) — {u['balance']:,}T"
            buttons.append([InlineKeyboardButton(label, callback_data=f"admin_user_{u['user_id']}")])
        buttons.append([InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="admin_back")])
        await query.edit_message_text(
            f"{EMOJI_USERS} لیست کاربران:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("admin_user_"):
        uid = int(data.split("_")[-1])
        u = await get_user(uid)
        if not u:
            await query.answer("کاربر یافت نشد.", show_alert=True)
            return
        ban_btn_text = "آنبن" if u["is_banned"] else "بن"
        text = (
            f"👤 کاربر: {u['first_name']} (@{u['username'] or 'N/A'})\n"
            f"🆔 آیدی: {uid}\n"
            f"💰 موجودی: {u['balance']:,} تومان\n"
            f"📅 عضویت: {u['join_date'].strftime('%Y-%m-%d')}\n"
            f"وضعیت: {'مسدود' if u['is_banned'] else 'فعال'}"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"{'🔓' if u['is_banned'] else '🔒'} {ban_btn_text}", callback_data=f"admin_ban_{uid}_{0 if u['is_banned'] else 1}"),
                InlineKeyboardButton("💰 تغییر موجودی", callback_data=f"admin_balance_{uid}"),
            ],
            [InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="admin_users")],
        ])
        await query.edit_message_text(text, reply_markup=kb)

    elif data.startswith("admin_ban_"):
        parts = data.split("_")
        uid = int(parts[2])
        ban = parts[3] == "1"
        await ban_user(uid, ban)
        status = "مسدود" if ban else "فعال"
        await query.edit_message_text(
            f"{EMOJI_SUCCESS} کاربر {uid} {status} شد.",
            reply_markup=back_keyboard("admin_users")
        )

    elif data.startswith("admin_balance_"):
        uid = int(data.split("_")[-1])
        context.user_data["balance_user_id"] = uid
        await query.edit_message_text(
            f"مبلغ برای کاربر {uid} را ارسال کنید:\n"
            f"(مثبت برای افزایش، منفی برای کاهش)"
        )

    # ───── مدیریت سرویس‌ها ─────
    elif data == "admin_services_list":
        services = await get_active_services()
        pool = await get_pool()
        async with pool.acquire() as conn:
            all_services = await conn.fetch("SELECT * FROM services ORDER BY id")
        buttons = []
        for s in all_services:
            status = "✅" if s["is_active"] else "❌"
            buttons.append([InlineKeyboardButton(
                f"{status} {s['name']} — {s['price_toman']:,}T",
                callback_data=f"admin_service_toggle_{s['id']}"
            )])
        buttons.append([InlineKeyboardButton("➕ افزودن سرویس", callback_data="admin_add_service")])
        buttons.append([InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="admin_back")])
        await query.edit_message_text(
            "🛍 مدیریت سرویس‌ها:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("admin_service_toggle_"):
        sid = int(data.split("_")[-1])
        pool = await get_pool()
        async with pool.acquire() as conn:
            srv = await conn.fetchrow("SELECT is_active FROM services WHERE id=$1", sid)
            if srv:
                new_status = not srv["is_active"]
                await conn.execute("UPDATE services SET is_active=$2 WHERE id=$1", sid, new_status)
        await query.answer("وضعیت سرویس تغییر کرد.", show_alert=True)
        # بازخوانی لیست
        query.data = "admin_services_list"
        await admin_callback(update, context)

    elif data == "admin_add_service":
        context.user_data["new_service"] = {}
        await query.edit_message_text("نام سرویس را وارد کنید (مثال: 30 روزه 5 گیگ):")
        return

    # ───── تنظیمات کیف پول ─────
    elif data == "admin_wallet_settings":
        current = await get_setting("usdt_wallet", USDT_WALLET)
        await query.edit_message_text(
            f"آدرس فعلی کیف پول:\n<code>{current}</code>\n\nآدرس جدید را ارسال کنید:",
            parse_mode=ParseMode.HTML
        )
        context.user_data["waiting_wallet"] = True

    # ───── تیکت‌ها ─────
    elif data == "admin_tickets":
        tickets = await get_open_tickets()
        if not tickets:
            await query.edit_message_text(
                "تیکت باز وجود ندارد.",
                reply_markup=back_keyboard("admin_back")
            )
            return
        buttons = []
        for t in tickets:
            last = (t["last_msg"] or "")[:30]
            buttons.append([InlineKeyboardButton(
                f"#{t['id']} — {t['first_name']} — {last}",
                callback_data=f"admin_ticket_{t['id']}_{t['user_id']}"
            )])
        buttons.append([InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="admin_back")])
        await query.edit_message_text(
            f"{EMOJI_TICKET} تیکت‌های باز:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("admin_ticket_"):
        parts = data.split("_")
        ticket_id = int(parts[2])
        ticket_user_id = int(parts[3])
        msgs = await get_ticket_messages(ticket_id)
        text = f"💬 تیکت #{ticket_id}\n\n"
        for m in msgs[-10:]:
            role = "👤 کاربر" if m["sender_id"] == ticket_user_id else f"{EMOJI_ADMIN} ادمین"
            text += f"{role}: {m['text']}\n"
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📨 پاسخ", callback_data=f"adm_reply_{ticket_id}_{ticket_user_id}"),
                InlineKeyboardButton("✔️ بستن تیکت", callback_data=f"adm_close_ticket_{ticket_id}"),
            ],
            [InlineKeyboardButton(f"{EMOJI_BACK} بازگشت", callback_data="admin_tickets")],
        ])
        await query.edit_message_text(text, reply_markup=kb)

    elif data.startswith("adm_reply_"):
        parts = data.split("_")
        ticket_id = int(parts[2])
        ticket_user_id = int(parts[3])
        context.user_data["reply_ticket_id"] = ticket_id
        context.user_data["reply_user_id"] = ticket_user_id
        await query.edit_message_text(
            f"پیام پاسخ برای تیکت #{ticket_id} را ارسال کنید:"
        )

    elif data.startswith("adm_close_ticket_"):
        ticket_id = int(data.split("_")[-1])
        await close_ticket(ticket_id)
        await query.edit_message_text(
            f"{EMOJI_SUCCESS} تیکت #{ticket_id} بسته شد.",
            reply_markup=back_keyboard("admin_tickets")
        )

    # ───── ارسال همگانی ─────
    elif data == "admin_broadcast":
        context.user_data["waiting_broadcast"] = True
        await query.edit_message_text(
            f"{EMOJI_BROADCAST} پیام همگانی خود را ارسال کنید:"
        )

    # ───── بازگشت ادمین ─────
    elif data == "admin_back":
        await query.edit_message_text(
            f"{EMOJI_ADMIN} پنل مدیریت Excore",
            reply_markup=admin_menu_keyboard()
        )

# ─────────────────────────────────────────────────
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هندلر پیام‌های متنی ادمین برای حالت‌های مختلف"""
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        return

    text = update.message.text or ""

    # ارسال کانفیگ
    if "config_order_id" in context.user_data:
        order_id = context.user_data.pop("config_order_id")
        await update_order_status(order_id, "confirmed", user_id, text)
        order = await get_order(order_id)
        await update.message.reply_text(
            f"{EMOJI_SUCCESS} کانفیگ ذخیره و ارسال شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"{EMOJI_BACK} پنل", callback_data="admin_back")
            ]])
        )
        if order:
            try:
                await context.bot.send_message(
                    order["user_id"],
                    f"{EMOJI_SUCCESS} سفارش شما تایید شد. کانفیگ شما:\n\n<code>{text}</code>",
                    parse_mode=ParseMode.HTML
                )
            except TelegramError:
                pass
        return

    # تغییر موجودی کاربر
    if "balance_user_id" in context.user_data:
        uid = context.user_data.pop("balance_user_id")
        try:
            amount = int(text.replace(",", "").strip())
            ttype = "credit" if amount > 0 else "debit"
            await add_wallet_transaction(uid, abs(amount), ttype, f"تغییر توسط ادمین {user_id}")
            await update.message.reply_text(f"{EMOJI_SUCCESS} موجودی کاربر {uid} با {amount:,} تومان تغییر کرد.")
        except ValueError:
            await update.message.reply_text(f"{EMOJI_ERROR} مقدار نامعتبر.")
        return

    # تنظیم کیف پول
    if context.user_data.pop("waiting_wallet", False):
        await set_setting("usdt_wallet", text.strip())
        await update.message.reply_text(
            f"{EMOJI_SUCCESS} آدرس کیف پول به‌روز شد.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"{EMOJI_BACK} پنل", callback_data="admin_back")
            ]])
        )
        return

    # ارسال همگانی
    if context.user_data.pop("waiting_broadcast", False):
        all_users = await get_all_users(1000, 0)
        sent = 0
        for u in all_users:
            if not u["is_banned"]:
                try:
                    await context.bot.send_message(u["user_id"], text)
                    sent += 1
                    await asyncio.sleep(0.05)
                except TelegramError:
                    pass
        await update.message.reply_text(f"{EMOJI_SUCCESS} پیام به {sent} کاربر ارسال شد.")
        return

    # پاسخ به تیکت
    if "reply_ticket_id" in context.user_data:
        ticket_id = context.user_data.pop("reply_ticket_id")
        ticket_user_id = context.user_data.pop("reply_user_id", None)
        await add_ticket_message(ticket_id, user_id, text)
        await update.message.reply_text(f"{EMOJI_SUCCESS} پاسخ ارسال شد.")
        if ticket_user_id:
            try:
                await context.bot.send_message(
                    ticket_user_id,
                    f"💬 پاسخ پشتیبانی (تیکت #{ticket_id}):\n\n{text}"
                )
            except TelegramError:
                pass
        return

    # افزودن سرویس جدید — مرحله‌به‌مرحله
    if "new_service" in context.user_data:
        ns = context.user_data["new_service"]
        if "name" not in ns:
            ns["name"] = text
            await update.message.reply_text("تعداد روز سرویس را وارد کنید (مثال: 30):")
        elif "days" not in ns:
            try:
                ns["days"] = int(text)
                await update.message.reply_text("لیمیت کاربر را وارد کنید (مثال: 1):")
            except ValueError:
                await update.message.reply_text(f"{EMOJI_ERROR} عدد صحیح وارد کنید.")
        elif "user_limit" not in ns:
            try:
                ns["user_limit"] = int(text)
                await update.message.reply_text("حجم (گیگابایت) را وارد کنید (مثال: 5):")
            except ValueError:
                await update.message.reply_text(f"{EMOJI_ERROR} عدد صحیح وارد کنید.")
        elif "volume_gb" not in ns:
            try:
                ns["volume_gb"] = float(text)
                await update.message.reply_text("قیمت (تومان) را وارد کنید (مثال: 200000):")
            except ValueError:
                await update.message.reply_text(f"{EMOJI_ERROR} عدد وارد کنید.")
        elif "price" not in ns:
            try:
                ns["price"] = int(text.replace(",", ""))
                await update.message.reply_text("توضیح سرویس را وارد کنید:")
            except ValueError:
                await update.message.reply_text(f"{EMOJI_ERROR} عدد صحیح وارد کنید.")
        elif "desc" not in ns:
            ns["desc"] = text
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO services (name, days, user_limit, volume_gb, price_toman, description, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                """, ns["name"], ns["days"], ns["user_limit"], ns["volume_gb"], ns["price"], ns["desc"])
            context.user_data.pop("new_service")
            await update.message.reply_text(
                f"{EMOJI_SUCCESS} سرویس «{ns['name']}» اضافه شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"{EMOJI_BACK} پنل", callback_data="admin_back")
                ]])
            )

# ═══════════════════════════════════════════════════
#  هندلر پیام‌های عمومی (کاربران)
# ═══════════════════════════════════════════════════
async def general_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اگر کاربر پیامی فرستاد که در هیچ conversation نبود"""
    if await is_admin(update.effective_user.id):
        await admin_text_handler(update, context)
        return
    # کاربران عادی → بازگشت به منو
    await start(update, context)

# ═══════════════════════════════════════════════════
#  راه‌اندازی ربات
# ═══════════════════════════════════════════════════
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler پشتیبانی
    support_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(support_start, pattern="^support$")],
        states={
            SUPPORT_WAITING_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, support_receive_message),
            ],
        },
        fallbacks=[CommandHandler("cancel", support_cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(support_conv)

    # Callback query ها
    app.add_handler(CallbackQueryHandler(show_main_menu,     pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(buy_service_menu,   pattern="^buy_service$"))
    app.add_handler(CallbackQueryHandler(place_order,        pattern=r"^order_\d+$"))
    app.add_handler(CallbackQueryHandler(my_services,        pattern="^my_services$"))
    app.add_handler(CallbackQueryHandler(get_config_callback,pattern=r"^get_config_\d+$"))
    app.add_handler(CallbackQueryHandler(apps_menu,          pattern="^apps$"))
    app.add_handler(CallbackQueryHandler(app_download,       pattern=r"^app_(linux|windows|apple)$"))
    app.add_handler(CallbackQueryHandler(referral_menu,      pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(wallet_menu,        pattern="^wallet$"))
    app.add_handler(CallbackQueryHandler(panel_callback,     pattern="^panel$"))
    app.add_handler(CallbackQueryHandler(channel_callback,   pattern="^channel$"))
    app.add_handler(CallbackQueryHandler(ignore_callback,    pattern="^srv_ign$"))

    # Callback های ادمین
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^adm_"))

    # پیام‌های متنی عمومی
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        general_message_handler
    ))

    return app


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده!")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL تنظیم نشده!")

    await init_db()
    app = build_app()

    if WEBHOOK_URL:
        # حالت Webhook (توصیه شده برای Railway)
        logger.info(f"🚀 حالت Webhook روی پورت {PORT}")
        await app.bot.set_my_commands([
            BotCommand("start", "شروع و منوی اصلی"),
            BotCommand("admin", "پنل مدیریت"),
            BotCommand("cancel", "خروج از چت پشتیبانی"),
        ])
        await app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"{WEBHOOK_URL.rstrip('/')}/webhook",
            url_path="/webhook",
        )
    else:
        # حالت Polling (برای تست محلی)
        logger.info("🚀 حالت Polling")
        await app.bot.set_my_commands([
            BotCommand("start", "شروع و منوی اصلی"),
            BotCommand("admin", "پنل مدیریت"),
            BotCommand("cancel", "خروج از چت پشتیبانی"),
        ])
        await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
