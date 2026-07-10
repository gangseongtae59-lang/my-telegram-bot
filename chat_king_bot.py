import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatMemberStatus

# 사람들의 채팅 횟수를 기록할 공책이에요.
chat_database = {}
TOKEN = "8573436045:AAFT4Z9_T-JzSgYN9uvp9rj1amZw3LJ1_ug"

# 컴퓨터 창에 실행 상태를 보여주는 설정
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# [기능 1] 방에 대화가 올라올 때마다 숫자를 1씩 더하는 규칙이에요.
async def check_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.is_bot: 
        return
    
    user_id = user.id
    user_name = user.name  # 에러가 절대로 나지 않는 가장 안전한 영어 아이디로 기록해요!

    if user_id not in chat_database:
        chat_database[user_id] = {"name": user_name, "count": 0}
    
    chat_database[user_id]["count"] += 1

# [기능 2] ★누구나★ '/rank'라고 명령어를 치면 순위를 보여주는 규칙이에요.
async def show_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not chat_database:
        await update.message.reply_text("아직 아무도 말을 하지 않았어요 😢")
        return

    # 대화 횟수가 높은 순서대로 10등까지 정렬해요.
    sorted_users = sorted(chat_database.values(), key=lambda x: x['count'], reverse=True)
    
    text = "🔥 일일 채팅왕 랭킹 🔥\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, user_data in enumerate(sorted_users[:10]):
        text += f"{emojis[i]} {user_data['name']} 님\n💬 {user_data['count']}회 기록!\n\n"
    
    text += "채팅참여하시고 포인트 받아가세요!"
    await update.message.reply_text(text)

# [기능 3] ★오직 방 소유자만★ 점수를 다시 0으로 청소할 수 있는 '/reset' 명령어예요.
async def reset_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    try:
        # 명령어를 친 사람이 이 방의 진짜 소유자(방장)인지 신분증을 검사해요!
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status != ChatMemberStatus.OWNER:
            # 소유자가 아니라면 거절 메시지를 보내고 규칙을 무시해요!
            await update.message.reply_text("🔒 이 명령어는 오직 그룹 소유자님만 사용할 수 있습니다!")
            return
            
        # 진짜 방 소유자가 맞다면 깨끗하게 청소해 줍니다!
        global chat_database
        chat_database.clear()
        await update.message.reply_text("채팅 기록이 모두 0으로 초기화되었습니다! 새 게임 시작! 🏁")
        
    except Exception as e:
        logging.error(f"방 소유자 확인 중 에러 발생: {e}")

def main():
    # 최신 방식의 로봇 엔진을 빌드합니다.
    application = Application.builder().token(TOKEN).build()

    # 로봇에게 규칙을 가르쳐 줍니다.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_chat))
    application.add_handler(CommandHandler("rank", show_ranking)) 
    application.add_handler(CommandHandler("reset", reset_ranking)) 

    print("로봇 비서가 열심히 일하는 중입니다... 컴퓨터를 끄지 마세요!")
    
    # 로봇 가동 시작!
    application.run_polling()

if __name__ == '__main__':
    main()
