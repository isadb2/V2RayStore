"""
TrustVPN store bot — single-file starter

Stack:
- aiogram 3 (Telegram bot)
- asyncpg (PostgreSQL)
- asyncio polling

Install:
    pip install aiogram asyncpg python-dotenv

Environment variables:
    BOT_TOKEN=123456:ABC...
    DATABASE_URL=postgresql://user:pass@host:port/dbname
    ADMIN_IDS=123456789,987654321
    PAYMENT_ADDRESS=YOUR_CRYPTO_WALLET_ADDRESS
    PAYMENT_NETWORK=USDT-TRC20
    PAYMENT_NOTES=After payment, send tx hash here
    SUPPORT_CHANNEL_ID=-1001234567890   # optional, for support mirror

Notes:
- This bot intentionally does NOT use Telegram's built-in payments for digital goods, because Telegram's digital-goods flow uses Telegram Stars only.
- Crypto checkout is implemented as a manual/external confirmation flow: user submits tx hash, admin approves, then admin sends the config.
- Button labels / emojis are centralized in UI_TEXT below.
- Telegram button colors/styles are only partly supported by newer Bot API/client combinations. The code keeps the UI centralized so you can swap in raw Bot API styling later if needed.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import asyncpg
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from flask import Flask
from threading import Thread

app = Flask(__name__)


@app.get("/")
def home():
    return "ok", 200


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


Thread(target=run_web, daemon=True).start()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trustvpn-bot")


# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8734599238:AAHGC_Y_vVRVO66U59LSRSfinD9qRseVHCs")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:KlSJaIrPXGKCXRMgAIxwQQxqhjgPgCgT@postgres.railway.internal:5432/railway")
PAYMENT_ADDRESS = os.getenv("PAYMENT_ADDRESS", "")
PAYMENT_NETWORK = os.getenv("PAYMENT_NETWORK", "USDT-TRC20")
PAYMENT_NOTES = os.getenv("PAYMENT_NOTES", "پس از پرداخت، هش تراکنش را ارسال کن.")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "8105229274").split(",") if x.strip().isdigit()]
SUPPORT_CHANNEL_ID = int(os.getenv("SUPPORT_CHANNEL_ID", "0")) if os.getenv("SUPPORT_CHANNEL_ID", "0").strip() else 0

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required")
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS is required")


# =========================
# UI TEXT — edit emojis/labels here
# =========================

class UIText:
    # Main menu (reply keyboard)
    BUY_SERVICE = "🛒 خرید سرویس"
    MY_SERVICES = "🧾 سرویس های من"
    REFER_FRIENDS = "👥 معرفی دوستان"
    WALLET = "💳 کیف پول"
    APPS = "📲 دریافت برنامه ها"
    SUPPORT = "💬 پشتیبانی"

    # Common buttons
    BACK = "↩️ بازگشت"
    HOME = "🏠 منو"
    ORDER = "ثبت سفارش"
    PAY_DONE = "✅ پرداخت کردم"
    SEND_CONFIG = "📤 ارسال کانفیگ"
    APPROVE = "✅ تایید پرداخت"
    REJECT = "❌ رد پرداخت"
    CLOSE_TICKET = "🔒 بستن تیکت"

    # Admin panel
    ADMIN_PANEL = "پنل ادمین"
    ADMIN_USERS = "👤 کاربران"
    ADMIN_ORDERS = "📦 سفارش‌ها"
    ADMIN_PRODUCTS = "🧩 محصولات"
    ADMIN_SUPPORT = "🛟 پشتیبانی"
    ADMIN_BROADCAST = "📣 ارسال همگانی"
    ADMIN_STATS = "📈 آمار"


# =========================
# FSM
# =========================

class UserFlow(StatesGroup):
    waiting_tx_hash = State()
    waiting_support_message = State()


class AdminFlow(StatesGroup):
    waiting_config_text = State()
    waiting_broadcast = State()


# =========================
# DB helpers
# =========================

@dataclass
class Product:
    id: int
    title: str
    description: str
    price_toman: int
    duration_days: int
    slots: int
    traffic_gb: Decimal
    active: bool


async def init_db(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                tg_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                is_blocked BOOLEAN NOT NULL DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                price_toman INTEGER NOT NULL,
                duration_days INTEGER NOT NULL DEFAULT 7,
                slots INTEGER NOT NULL DEFAULT 1,
                traffic_gb NUMERIC(10,2) NOT NULL DEFAULT 1,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS orders (
                id BIGSERIAL PRIMARY KEY,
                user_tg_id BIGINT NOT NULL,
                product_id INTEGER NOT NULL REFERENCES products(id),
                qty_days INTEGER NOT NULL,
                qty_slots INTEGER NOT NULL,
                qty_gb NUMERIC(10,2) NOT NULL,
                total_price_toman INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_payment',
                payment_network TEXT,
                payment_address TEXT,
                tx_hash TEXT,
                admin_note TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                approved_at TIMESTAMPTZ,
                delivered_at TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS support_tickets (
                id BIGSERIAL PRIMARY KEY,
                user_tg_id BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                closed_at TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS support_links (
                id BIGSERIAL PRIMARY KEY,
                ticket_id BIGINT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
                admin_tg_id BIGINT NOT NULL,
                admin_message_id BIGINT NOT NULL,
                user_tg_id BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        count = await conn.fetchval("SELECT COUNT(*) FROM products")
        if count == 0:
            await conn.executemany(
                """
                INSERT INTO products (title, description, price_toman, duration_days, slots, traffic_gb, sort_order)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                [
                    ("پلن اقتصادی", "مناسب مصرف سبک و تست", 200000, 7, 1, Decimal("1.00"), 1),
                    ("پلن حرفه‌ای", "برای استفاده روزانه و پایدار", 350000, 30, 3, Decimal("5.00"), 2),
                    ("پلن ویژه", "حجم و مدت بیشتر برای مصرف سنگین", 590000, 30, 5, Decimal("10.00"), 3),
                ],
            )


async def upsert_user(msg: Message, pool: asyncpg.Pool) -> None:
    user = msg.from_user
    if not user:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (tg_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (tg_id)
            DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name, is_blocked = FALSE
            """,
            user.id,
            user.username,
            user.first_name,
        )


async def get_active_products(pool: asyncpg.Pool) -> list[Product]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM products WHERE active = TRUE ORDER BY sort_order, id"
        )
    return [Product(**dict(r)) for r in rows]


async def get_product(pool: asyncpg.Pool, product_id: int) -> Optional[Product]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
    return Product(**dict(row)) if row else None


async def create_order(pool: asyncpg.Pool, user_tg_id: int, product: Product) -> int:
    async with pool.acquire() as conn:
        order_id = await conn.fetchval(
            """
            INSERT INTO orders (user_tg_id, product_id, qty_days, qty_slots, qty_gb, total_price_toman, status, payment_network, payment_address)
            VALUES ($1, $2, $3, $4, $5, $6, 'awaiting_tx_hash', $7, $8)
            RETURNING id
            """,
            user_tg_id,
            product.id,
            product.duration_days,
            product.slots,
            product.traffic_gb,
            product.price_toman,
            PAYMENT_NETWORK,
            PAYMENT_ADDRESS,
        )
    return int(order_id)


async def get_order(pool: asyncpg.Pool, order_id: int) -> Optional[asyncpg.Record]:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT o.*, p.title AS product_title, p.description AS product_description
            FROM orders o
            JOIN products p ON p.id = o.product_id
            WHERE o.id = $1
            """,
            order_id,
        )


async def get_open_ticket(pool: asyncpg.Pool, user_tg_id: int) -> Optional[asyncpg.Record]:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM support_tickets WHERE user_tg_id = $1 AND status = 'open' ORDER BY id DESC LIMIT 1",
            user_tg_id,
        )


async def create_ticket(pool: asyncpg.Pool, user_tg_id: int) -> int:
    async with pool.acquire() as conn:
        ticket_id = await conn.fetchval(
            "INSERT INTO support_tickets (user_tg_id) VALUES ($1) RETURNING id", user_tg_id
        )
    return int(ticket_id)


# =========================
# Keyboards
# =========================


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    # If you want to change labels or emojis, edit UIText above.
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=UIText.BUY_SERVICE), KeyboardButton(text=UIText.MY_SERVICES)],
            [KeyboardButton(text=UIText.REFER_FRIENDS), KeyboardButton(text=UIText.WALLET)],
            [KeyboardButton(text=UIText.APPS), KeyboardButton(text=UIText.SUPPORT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="یکی از گزینه‌ها را انتخاب کن",
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=UIText.ADMIN_USERS), KeyboardButton(text=UIText.ADMIN_ORDERS)],
            [KeyboardButton(text=UIText.ADMIN_PRODUCTS), KeyboardButton(text=UIText.ADMIN_SUPPORT)],
            [KeyboardButton(text=UIText.ADMIN_BROADCAST), KeyboardButton(text=UIText.ADMIN_STATS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="پنل ادمین",
    )


def products_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=f"{p.title} — {p.price_toman:,} تومان", callback_data=f"product:{p.id}")] for p in products]
    buttons.append([InlineKeyboardButton(text=f"{UIText.BACK}", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_detail_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{UIText.ORDER}", callback_data=f"buy:{product_id}")],
            [InlineKeyboardButton(text=f"{UIText.BACK}", callback_data="nav:products")],
        ]
    )


def order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=UIText.PAY_DONE, callback_data=f"paydone:{order_id}")],
            [InlineKeyboardButton(text=UIText.BACK, callback_data="nav:products")],
        ]
    )


def admin_order_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status in ("awaiting_review", "awaiting_tx_hash", "paid_pending_delivery"):
        rows.append(
            [
                InlineKeyboardButton(text=UIText.APPROVE, callback_data=f"admin_approve:{order_id}"),
                InlineKeyboardButton(text=UIText.REJECT, callback_data=f"admin_reject:{order_id}"),
            ]
        )
    if status == "paid_confirmed":
        rows.append([InlineKeyboardButton(text=UIText.SEND_CONFIG, callback_data=f"admin_sendcfg:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text=UIText.BACK, callback_data="nav:admin_orders")]])


def support_hint_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=UIText.CLOSE_TICKET, callback_data="support:close")],
            [InlineKeyboardButton(text=UIText.HOME, callback_data="nav:home")],
        ]
    )


# =========================
# Utilities
# =========================


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def money_fmt(value: int) -> str:
    return f"{value:,} تومان"


def safe_text(s: Optional[str]) -> str:
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")


def order_details_text(order: asyncpg.Record) -> str:
    return (
        f"<b>سفارش #{order['id']}</b>\n"
        f"محصول: {safe_text(order['product_title'])}\n"
        f"مدت: {order['qty_days']} روز\n"
        f"تعداد: {order['qty_slots']} نفر\n"
        f"حجم: {order['qty_gb']} گیگ\n"
        f"مبلغ: {money_fmt(order['total_price_toman'])}\n"
        f"وضعیت: <code>{safe_text(order['status'])}</code>"
    )


def product_details_text(product: Product) -> str:
    return (
        f"<b>{safe_text(product.title)}</b>\n\n"
        f"{safe_text(product.description)}\n\n"
        f"⏳ مدت: {product.duration_days} روز\n"
        f"👥 تعداد: {product.slots} نفر\n"
        f"📦 حجم: {product.traffic_gb} گیگ\n"
        f"💰 قیمت: {money_fmt(product.price_toman)}"
    )


async def send_to_admins(bot: Bot, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except TelegramForbiddenError:
            logger.warning("Admin %s blocked the bot", admin_id)
        except Exception as exc:
            logger.exception("Failed to notify admin %s: %s", admin_id, exc)


async def get_user_count(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        return int(await conn.fetchval("SELECT COUNT(*) FROM users"))


async def get_order_count(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        return int(await conn.fetchval("SELECT COUNT(*) FROM orders"))


# =========================
# Routers
# =========================

user_router = Router()
admin_router = Router()


@user_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot, pool: asyncpg.Pool):
    await state.clear()
    await upsert_user(message, pool)
    text = (
        "<b>خوش آمدی به پنل فروش</b>\n\n"
        "از منو یکی از بخش‌ها را انتخاب کن.\n"
        "پرداخت‌ها فقط با ارز دیجیتال انجام می‌شود."
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@user_router.message(F.text == UIText.BUY_SERVICE)
async def user_buy_service(message: Message, pool: asyncpg.Pool):
    products = await get_active_products(pool)
    await message.answer(
        "یکی از سرویس‌ها را انتخاب کن:",
        reply_markup=products_keyboard(products),
    )


@user_router.message(F.text == UIText.MY_SERVICES)
async def user_my_services(message: Message, pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT o.id, o.status, p.title, o.created_at
            FROM orders o
            JOIN products p ON p.id = o.product_id
            WHERE o.user_tg_id = $1
            ORDER BY o.id DESC
            LIMIT 10
            """,
            message.from_user.id,
        )
    if not rows:
        await message.answer("هنوز سفارشی ثبت نشده است.")
        return
    lines = ["<b>سرویس‌های شما</b>"]
    for r in rows:
        lines.append(f"• #{r['id']} — {safe_text(r['title'])} — <code>{safe_text(r['status'])}</code>")
    await message.answer("\n".join(lines))


@user_router.message(F.text == UIText.REFER_FRIENDS)
async def user_refer(message: Message):
    await message.answer(
        "بخش معرفی دوستان آماده است.\n"
        "اینجا می‌توانیم کد دعوت، درصد زیرمجموعه و کیف پاداش را اضافه کنیم."
    )


@user_router.message(F.text == UIText.WALLET)
async def user_wallet(message: Message, pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COALESCE(SUM(total_price_toman),0) FROM orders WHERE user_tg_id = $1 AND status IN ('paid_confirmed','delivered')", message.from_user.id)
    await message.answer(f"موجودی/گردش حساب شما از سفارش‌ها: {money_fmt(int(total or 0))}")


@user_router.message(F.text == UIText.APPS)
async def user_apps(message: Message):
    await message.answer("لینک دانلود برنامه‌ها را اینجا قرار می‌دهیم.")


@user_router.message(F.text == UIText.SUPPORT)
async def user_support(message: Message, pool: asyncpg.Pool, state: FSMContext):
    ticket = await get_open_ticket(pool, message.from_user.id)
    if ticket is None:
        ticket_id = await create_ticket(pool, message.from_user.id)
        await message.answer(
            f"تیکت پشتیبانی #{ticket_id} ساخته شد.\n"
            "پیامت را ارسال کن تا به ادمین‌ها منتقل شود.",
            reply_markup=support_hint_keyboard(),
        )
    else:
        await message.answer(
            f"تیکت باز شما: #{ticket['id']}\n"
            "پیام بعدی‌ات به پشتیبانی ارسال می‌شود.",
            reply_markup=support_hint_keyboard(),
        )
    await state.set_state(UserFlow.waiting_support_message)


@user_router.message(UserFlow.waiting_support_message)
async def user_support_message(message: Message, pool: asyncpg.Pool, bot: Bot):
    if not message.text and not message.photo and not message.document and not message.video:
        await message.answer("لطفاً فقط متن یا فایل ارسال کن.")
        return

    ticket = await get_open_ticket(pool, message.from_user.id)
    if ticket is None:
        ticket_id = await create_ticket(pool, message.from_user.id)
    else:
        ticket_id = int(ticket["id"])

    user_line = (
        f"<b>پشتیبانی #{ticket_id}</b>\n"
        f"از: <code>{message.from_user.id}</code>"
    )
    if message.text:
        user_line += f"\n\n{safe_text(message.text)}"

    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_message(admin_id, user_line)
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO support_links (ticket_id, admin_tg_id, admin_message_id, user_tg_id)
                    VALUES ($1, $2, $3, $4)
                    """,
                    ticket_id,
                    admin_id,
                    sent.message_id,
                    message.from_user.id,
                )
        except Exception as exc:
            logger.exception("Support relay failed for admin %s: %s", admin_id, exc)

    await message.answer("پیام شما به پشتیبانی ارسال شد.")


@user_router.callback_query(F.data.startswith("nav:"))
async def nav_callbacks(callback: CallbackQuery, pool: asyncpg.Pool, state: FSMContext):
    await callback.answer()
    route = callback.data.split(":", 1)[1]
    if route == "home":
        await state.clear()
        await callback.message.answer("منو:", reply_markup=main_menu_keyboard())
    elif route == "products":
        products = await get_active_products(pool)
        await callback.message.edit_text("یکی از سرویس‌ها را انتخاب کن:", reply_markup=products_keyboard(products))
    elif route == "admin_orders":
        await callback.message.answer("از پنل ادمین، سفارش‌ها را بررسی کن.", reply_markup=admin_menu_keyboard())
    elif route == "admin":
        await callback.message.answer("پنل ادمین", reply_markup=admin_menu_keyboard())


@user_router.callback_query(F.data.startswith("product:"))
async def show_product(callback: CallbackQuery, pool: asyncpg.Pool):
    await callback.answer()
    product_id = int(callback.data.split(":", 1)[1])
    product = await get_product(pool, product_id)
    if not product:
        await callback.message.answer("محصول پیدا نشد.")
        return
    await callback.message.edit_text(product_details_text(product), reply_markup=product_detail_keyboard(product.id))


@user_router.callback_query(F.data.startswith("buy:"))
async def buy_product(callback: CallbackQuery, pool: asyncpg.Pool):
    await callback.answer()
    product_id = int(callback.data.split(":", 1)[1])
    product = await get_product(pool, product_id)
    if not product:
        await callback.message.answer("محصول پیدا نشد.")
        return

    order_id = await create_order(pool, callback.from_user.id, product)
    text = (
        f"<b>سفارش #{order_id}</b> ثبت شد.\n\n"
        f"{product_details_text(product)}\n\n"
        f"<b>پرداخت فقط با {safe_text(PAYMENT_NETWORK)}</b>\n"
        f"آدرس: <code>{safe_text(PAYMENT_ADDRESS)}</code>\n\n"
        f"{safe_text(PAYMENT_NOTES)}\n\n"
        "بعد از پرداخت، هش تراکنش را بفرست یا روی دکمه زیر بزن."
    )
    await callback.message.edit_text(text, reply_markup=order_keyboard(order_id))


@user_router.callback_query(F.data.startswith("paydone:"))
async def ask_tx_hash(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    order_id = int(callback.data.split(":", 1)[1])
    await state.set_state(UserFlow.waiting_tx_hash)
    await state.update_data(order_id=order_id)
    await callback.message.answer("هش تراکنش یا TX Hash را ارسال کن.")


@user_router.message(UserFlow.waiting_tx_hash)
async def receive_tx_hash(message: Message, state: FSMContext, pool: asyncpg.Pool, bot: Bot):
    data = await state.get_data()
    order_id = int(data.get("order_id", 0))
    tx_hash = (message.text or "").strip()
    if len(tx_hash) < 8:
        await message.answer("هش معتبر نیست. دوباره بفرست.")
        return

    order = await get_order(pool, order_id)
    if not order or int(order["user_tg_id"]) != message.from_user.id:
        await message.answer("سفارش پیدا نشد.")
        await state.clear()
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET tx_hash = $1, status = 'awaiting_review' WHERE id = $2",
            tx_hash,
            order_id,
        )

    await state.clear()

    admin_text = (
        f"<b>پرداخت جدید برای بررسی</b>\n\n"
        f"سفارش: #{order_id}\n"
        f"کاربر: <code>{message.from_user.id}</code>\n"
        f"TX: <code>{safe_text(tx_hash)}</code>\n\n"
        f"{order_details_text(order)}"
    )
    await send_to_admins(bot, admin_text, reply_markup=admin_order_keyboard(order_id, "awaiting_review"))
    await message.answer("پرداخت شما ثبت شد و در انتظار تایید ادمین است.")


@user_router.callback_query(F.data.startswith("support:"))
async def support_callbacks(callback: CallbackQuery, pool: asyncpg.Pool):
    await callback.answer()
    action = callback.data.split(":", 1)[1]
    if action == "close":
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE support_tickets SET status='closed', closed_at=NOW() WHERE user_tg_id = $1 AND status='open'",
                callback.from_user.id,
            )
        await callback.message.answer("تیکت بسته شد.", reply_markup=main_menu_keyboard())


@user_router.message(Command("paysupport"))
async def pay_support(message: Message):
    await message.answer("درخواست پشتیبانی پرداخت ثبت شد. همینجا جزئیات را ارسال کن.")


@user_router.message()
async def catch_all_user(message: Message, state: FSMContext, pool: asyncpg.Pool, bot: Bot):
    # If user is in support mode, anything they send is relayed.
    current = await state.get_state()
    if current == UserFlow.waiting_support_message.state:
        await user_support_message(message, pool, bot)
        return

    if message.text and message.text.startswith("/"):
        return
    await message.answer("از منو یکی از گزینه‌ها را انتخاب کن.", reply_markup=main_menu_keyboard())


# =========================
# Admin
# =========================

@admin_router.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("پنل ادمین", reply_markup=admin_menu_keyboard())


@admin_router.message(F.text == UIText.ADMIN_USERS)
async def admin_users(message: Message, pool: asyncpg.Pool):
    if not is_admin(message.from_user.id):
        return
    count = await get_user_count(pool)
    await message.answer(f"تعداد کاربران: {count}")


@admin_router.message(F.text == UIText.ADMIN_ORDERS)
async def admin_orders(message: Message, pool: asyncpg.Pool):
    if not is_admin(message.from_user.id):
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT o.id, o.status, o.total_price_toman, p.title, o.user_tg_id
            FROM orders o
            JOIN products p ON p.id = o.product_id
            ORDER BY o.id DESC
            LIMIT 10
            """
        )
    if not rows:
        await message.answer("سفارشی وجود ندارد.")
        return
    for r in rows:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="باز کردن", callback_data=f"admin_order:{r['id']}")]]
        )
        await message.answer(
            f"#{r['id']} — {safe_text(r['title'])} — {money_fmt(int(r['total_price_toman']))}\n"
            f"کاربر: <code>{r['user_tg_id']}</code>\n"
            f"وضعیت: <code>{safe_text(r['status'])}</code>",
            reply_markup=kb,
        )


@admin_router.message(F.text == UIText.ADMIN_PRODUCTS)
async def admin_products(message: Message, pool: asyncpg.Pool):
    if not is_admin(message.from_user.id):
        return
    products = await get_active_products(pool)
    out = ["<b>محصولات فعال</b>"]
    for p in products:
        out.append(f"• #{p.id} — {safe_text(p.title)} — {money_fmt(p.price_toman)}")
    await message.answer("\n".join(out))


@admin_router.message(F.text == UIText.ADMIN_SUPPORT)
async def admin_support(message: Message, pool: asyncpg.Pool):
    if not is_admin(message.from_user.id):
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, user_tg_id, status, created_at FROM support_tickets ORDER BY id DESC LIMIT 10"
        )
    if not rows:
        await message.answer("تیکتی وجود ندارد.")
        return
    for r in rows:
        await message.answer(
            f"تیکت #{r['id']}\nکاربر: <code>{r['user_tg_id']}</code>\nوضعیت: <code>{safe_text(r['status'])}</code>"
        )


@admin_router.message(F.text == UIText.ADMIN_BROADCAST)
async def admin_broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminFlow.waiting_broadcast)
    await message.answer("متن ارسال همگانی را بفرست.")


@admin_router.message(AdminFlow.waiting_broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext, pool: asyncpg.Pool, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    text = message.text or ""
    if not text:
        await message.answer("فقط متن ارسال کن.")
        return
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT tg_id FROM users WHERE is_blocked = FALSE")
    sent = 0
    for row in rows:
        try:
            await bot.send_message(int(row["tg_id"]), text)
            sent += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(f"ارسال شد برای {sent} کاربر.")


@admin_router.callback_query(F.data.startswith("admin_order:"))
async def admin_open_order(callback: CallbackQuery, pool: asyncpg.Pool):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(pool, order_id)
    if not order:
        await callback.message.answer("سفارش پیدا نشد.")
        return
    await callback.message.answer(order_details_text(order), reply_markup=admin_order_keyboard(order_id, order["status"]))


@admin_router.callback_query(F.data.startswith("admin_approve:"))
async def admin_approve(callback: CallbackQuery, pool: asyncpg.Pool, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(pool, order_id)
    if not order:
        await callback.message.answer("سفارش پیدا نشد.")
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status='paid_confirmed', approved_at=NOW() WHERE id = $1",
            order_id,
        )
    await bot.send_message(
        int(order["user_tg_id"]),
        f"پرداخت سفارش #{order_id} تایید شد.\nاکنون منتظر ارسال کانفیگ هستی.",
    )
    await callback.message.answer(
        f"پرداخت سفارش #{order_id} تایید شد.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=UIText.SEND_CONFIG, callback_data=f"admin_sendcfg:{order_id}")]]
        ),
    )


@admin_router.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject(callback: CallbackQuery, pool: asyncpg.Pool, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    order_id = int(callback.data.split(":", 1)[1])
    order = await get_order(pool, order_id)
    if not order:
        await callback.message.answer("سفارش پیدا نشد.")
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status='payment_rejected' WHERE id = $1",
            order_id,
        )
    await bot.send_message(int(order["user_tg_id"]), f"پرداخت سفارش #{order_id} رد شد. لطفاً دوباره بررسی کن.")
    await callback.message.answer(f"پرداخت سفارش #{order_id} رد شد.")


@admin_router.callback_query(F.data.startswith("admin_sendcfg:"))
async def admin_send_config_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    order_id = int(callback.data.split(":", 1)[1])
    await state.set_state(AdminFlow.waiting_config_text)
    await state.update_data(order_id=order_id)
    await callback.message.answer("کانفیگ را به صورت متن بفرست. بعد از ارسال، برای کاربر فرستاده می‌شود.")


@admin_router.message(AdminFlow.waiting_config_text)
async def admin_send_config_finish(message: Message, state: FSMContext, pool: asyncpg.Pool, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    order_id = int(data.get("order_id", 0))
    order = await get_order(pool, order_id)
    if not order:
        await message.answer("سفارش پیدا نشد.")
        await state.clear()
        return

    config_text = message.text or ""
    if not config_text:
        await message.answer("فقط متن کانفیگ را ارسال کن.")
        return

    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE orders SET status='delivered', delivered_at=NOW(), admin_note = $1 WHERE id = $2",
            config_text,
            order_id,
        )

    await bot.send_message(
        int(order["user_tg_id"]),
        f"<b>کانفیگ سفارش #{order_id}</b>\n\n<code>{safe_text(config_text)}</code>",
    )
    await state.clear()
    await message.answer(f"کانفیگ برای سفارش #{order_id} ارسال شد.")


@admin_router.message(F.reply_to_message)
async def admin_support_reply(message: Message, pool: asyncpg.Pool, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    replied_id = message.reply_to_message.message_id
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_tg_id, ticket_id FROM support_links WHERE admin_tg_id = $1 AND admin_message_id = $2 ORDER BY id DESC LIMIT 1",
            message.from_user.id,
            replied_id,
        )
    if not row:
        return
    if not message.text:
        await message.answer("فعلاً پاسخ متنی ارسال کن.")
        return
    try:
        await bot.send_message(int(row["user_tg_id"]), f"<b>پاسخ پشتیبانی</b>\n\n{safe_text(message.text)}")
        await message.answer("ارسال شد.")
    except Exception as exc:
        await message.answer(f"خطا در ارسال: {exc}")


@admin_router.message(F.text == UIText.ADMIN_STATS)
async def admin_stats(message: Message, pool: asyncpg.Pool):
    if not is_admin(message.from_user.id):
        return
    users = await get_user_count(pool)
    orders = await get_order_count(pool)
    await message.answer(f"کاربران: {users}\nسفارش‌ها: {orders}")


@admin_router.message()
async def admin_fallback(message: Message):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.startswith("/"):
        return
    await message.answer("از پنل ادمین یکی از گزینه‌ها را انتخاب کن.", reply_markup=admin_menu_keyboard())


# =========================
# App bootstrap
# =========================

async def main() -> None:
    bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    await init_db(pool)

    dp = Dispatcher()
    dp.include_router(admin_router)
    dp.include_router(user_router)

    try:
        await dp.start_polling(bot, pool=pool)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
