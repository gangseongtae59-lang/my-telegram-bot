import logging
import os
import threading
import time

from flask import Flask
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN이 없습니다. Render의 Environment에 BOT_TOKEN을 입력하세요."
    )

# 채팅 횟수를 저장하는 공간
chat_database = {}

# --------------------------------------------------
# Render 확인용 웹 서버
# --------------------------------------------------

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Telegram ranking bot is running!", 200


@web_app.route("/health")
def health():
    return "OK", 200


def run_web_server():
    port = int(os.environ.get("PORT", "10000"))

    web_app.run(
        host="0.0.0.0",
        port=port,
        use_reloader=False,
    )


# --------------------------------------------------
# 사용자 이름 만들기
# --------------------------------------------------

def get_user_name(user):
    if user.username:
        return f"@{user.username}"

    if user.full_name:
        return user.full_name

    return f"사용자 {user.id}"


# --------------------------------------------------
# 일반 채팅 횟수 집계
# --------------------------------------------------

async def check_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    if user.is_bot:
        return

    # 개인 채팅은 세지 않고 그룹 채팅만 셉니다.
    if chat.type not in ("group", "supergroup"):
        return

    chat_id = chat.id
    user_id = user.id
    user_name = get_user_name(user)

    # 그룹마다 기록을 따로 저장합니다.
    if chat_id not in chat_database:
        chat_database[chat_id] = {}

    if user_id not in chat_database[chat_id]:
        chat_database[chat_id][user_id] = {
            "name": user_name,
            "count": 0,
        }

    # 사용자가 텔레그램 이름을 변경하면 최신 이름으로 바꿉니다.
    chat_database[chat_id][user_id]["name"] = user_name
    chat_database[chat_id][user_id]["count"] += 1


# --------------------------------------------------
# 랭킹 보기: /rank
# --------------------------------------------------

async def show_ranking(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat = update.effective_chat
    message = update.effective_message

    if not chat or not message:
        return

    group_data = chat_database.get(chat.id, {})

    if not group_data:
        await message.reply_text(
            "아직 집계된 채팅이 없습니다.\n"
            "그룹에서 채팅을 시작해 주세요 😊"
        )
        return

    sorted_users = sorted(
        group_data.values(),
        key=lambda item: item["count"],
        reverse=True,
    )

    rank_marks = [
        "🥇",
        "🥈",
        "🥉",
        "#4",
        "#5",
        "#6",
        "#7",
        "#8",
        "#9",
        "#10",
    ]

    lines = [
        "🔥 일일 채팅왕 랭킹 🔥",
        "",
    ]

    for index, user_data in enumerate(sorted_users[:10]):
        lines.append(
            f"{rank_marks[index]} {user_data['name']}"
        )
        lines.append(
            f"💬 {user_data['count']:,}회"
        )
        lines.append("")

    lines.append("오늘도 열심히 채팅하고 순위에 도전하세요! 🎉")

    await message.reply_text("\n".join(lines))


# --------------------------------------------------
# 내 채팅 횟수 보기: /my
# --------------------------------------------------

async def show_my_count(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat = update.effective_chat
    user = update.effective_user
    message = update.effective_message

    if not chat or not user or not message:
        return

    user_data = chat_database.get(chat.id, {}).get(user.id)

    if not user_data:
        await message.reply_text(
            "아직 집계된 채팅 기록이 없습니다."
        )
        return

    await message.reply_text(
        f"💬 {user_data['name']}님의 채팅 횟수는 "
        f"{user_data['count']:,}회입니다."
    )


# --------------------------------------------------
# 관리자 확인
# --------------------------------------------------

async def is_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return False

    try:
        member = await context.bot.get_chat_member(
            chat_id=chat.id,
            user_id=user.id,
        )

        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )

    except Exception:
        logger.exception("관리자 확인 중 오류가 발생했습니다.")
        return False


# --------------------------------------------------
# 기록 초기화: /reset
# --------------------------------------------------

async def reset_ranking(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat = update.effective_chat
    message = update.effective_message

    if not chat or not message:
        return

    if not await is_admin(update, context):
        await message.reply_text(
            "🔒 이 명령어는 그룹 관리자만 사용할 수 있습니다."
        )
        return

    chat_database.pop(chat.id, None)

    await message.reply_text(
        "✅ 이 그룹의 채팅 기록이 모두 초기화되었습니다!\n"
        "새로운 이벤트를 시작합니다. 🏁"
    )


# --------------------------------------------------
# 오류 기록
# --------------------------------------------------

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.error(
        "봇에서 오류가 발생했습니다.",
        exc_info=context.error,
    )


# --------------------------------------------------
# 텔레그램 봇 실행
# --------------------------------------------------

def run_telegram_bot():
    while True:
        try:
            application = Application.builder().token(TOKEN).build()

            application.add_handler(
                CommandHandler("rank", show_ranking)
            )

            application.add_handler(
                CommandHandler("my", show_my_count)
            )

            application.add_handler(
                CommandHandler("reset", reset_ranking)
            )

            application.add_handler(
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    check_chat,
                )
            )

            application.add_error_handler(error_handler)

            logger.info("텔레그램 채팅왕 봇을 시작합니다.")

            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False,
            )

        except Exception:
            logger.exception(
                "텔레그램 연결에 실패했습니다. 10초 뒤 다시 시도합니다."
            )
            time.sleep(10)


# --------------------------------------------------
# 프로그램 시작
# --------------------------------------------------

if __name__ == "__main__":
    telegram_thread = threading.Thread(
        target=run_telegram_bot,
        daemon=True,
    )
    telegram_thread.start()

    run_web_server()
