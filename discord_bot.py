"""
discord_bot.py — Discord 알림 및 피드백 수신 봇
"""

import discord
import asyncio
import json
import threading
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))

REVIEWS_DIR = Path(".reviews")
REVIEWS_DIR.mkdir(exist_ok=True)
PENDING_FILE = REVIEWS_DIR / "pending_feedback.json"

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
_bot_loop = None


# ── Discord 메시지 전송 ──────────────────────────────
async def _send_review_results(all_results: dict, all_summaries: str, today: str):
    """모든 파일 리뷰 결과를 Discord로 전송"""
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"❌ 채널 없음: {CHANNEL_ID}")
        return

    file_count = len(all_results)

    # 헤더 전송
    await channel.send(
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **DGReview 코드 리뷰 완료!**\n"
        f"📅 날짜: {today}\n"
        f"📁 리뷰 파일: **{file_count}개**\n"
        f"🕐 완료: {datetime.now().strftime('%H:%M:%S')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    # 파일별 결과 전송
    for filepath, data in all_results.items():
        result = data["result"]

        await channel.send(
            f"\n📄 **파일: `{filepath}`**\n"
            f"{'─'*30}"
        )

        # 토론 히스토리 (각 라운드 요약)
        for h in result["history"]:
            emoji = "🟢" if h["role"] == "Gemma A" else "🔵"
            label = f"{emoji} **[{h['role']} - {h['label']}]**"
            # 너무 길면 자르기
            content = h["content"]
            if len(content) > 800:
                content = content[:800] + "\n...(생략)"
            await channel.send(f"{label}\n{content}")
            await asyncio.sleep(0.3)

        # 파일 요약
        await channel.send(
            f"✅ **[{filepath} 요약]**\n"
            f"{result['summary'][:1000]}"
        )
        await asyncio.sleep(0.5)

    # 전체 종합 요약
    await channel.send(
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **전체 종합 요약 ({file_count}개 파일)**\n"
        f"{all_summaries[:1500]}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    # 피드백 요청 알림
    await channel.send(
        f"🔔 **@여기 검토 요청!**\n\n"
        f"위 리뷰 결과를 확인하고 아래 명령어로 응답해주세요:\n\n"
        f"```\n"
        f"!feedback [피드백 내용]  →  피드백 입력 후 Claude에게 전달\n"
        f"!approve                 →  그대로 승인 (피드백 없이 전달)\n"
        f"!reject                  →  리뷰 결과 무시\n"
        f"```\n"
        f"*(피드백을 보내면 Claude Code가 자동으로 모든 파일을 개선합니다)*"
    )

    # 대기 상태 저장
    pending = {
        "date": today,
        "files": list(all_results.keys()),
        "status": "waiting",
        "feedback": None,
        "timestamp": datetime.now().isoformat()
    }
    PENDING_FILE.write_text(
        json.dumps(pending, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ── Discord 이벤트 ────────────────────────────────
@bot.event
async def on_ready():
    global _bot_loop
    _bot_loop = asyncio.get_event_loop()
    print(f"✅ Discord 봇 시작: {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.channel.id != CHANNEL_ID:
        return

    # ── !feedback ──
    if message.content.startswith("!feedback"):
        feedback_text = message.content[9:].strip()

        if not feedback_text:
            await message.channel.send("❌ 피드백 내용을 입력해주세요.\n예: `!feedback 에러 처리 부분 보완해줘`")
            return

        if not PENDING_FILE.exists():
            await message.channel.send("❌ 대기 중인 리뷰가 없어요.")
            return

        pending = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        pending["status"] = "approved"
        pending["feedback"] = feedback_text
        PENDING_FILE.write_text(
            json.dumps(pending, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        file_list = "\n".join([f"  • `{f}`" for f in pending.get("files", [])])
        await message.channel.send(
            f"✅ **피드백 저장 완료!**\n\n"
            f"💬 피드백: *{feedback_text}*\n\n"
            f"📁 개선될 파일:\n{file_list}\n\n"
            f"🚀 Claude Code가 자동으로 개선을 시작합니다!"
        )

    # ── !approve ──
    elif message.content.strip() == "!approve":
        if not PENDING_FILE.exists():
            await message.channel.send("❌ 대기 중인 리뷰가 없어요.")
            return

        pending = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        pending["status"] = "approved"
        pending["feedback"] = "승인 (피드백 없음 — Gemma 리뷰 그대로 적용)"
        PENDING_FILE.write_text(
            json.dumps(pending, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        file_list = "\n".join([f"  • `{f}`" for f in pending.get("files", [])])
        await message.channel.send(
            f"✅ **승인 완료!**\n\n"
            f"📁 개선될 파일:\n{file_list}\n\n"
            f"🚀 Claude Code가 Gemma 리뷰를 그대로 적용합니다!"
        )

    # ── !reject ──
    elif message.content.strip() == "!reject":
        PENDING_FILE.unlink(missing_ok=True)
        await message.channel.send(
            "🗑️ **리뷰 결과가 무시됐어요.**\n"
            "파일은 변경되지 않습니다."
        )

    # ── !status ──
    elif message.content.strip() == "!status":
        if PENDING_FILE.exists():
            pending = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
            file_list = "\n".join([f"  • `{f}`" for f in pending.get("files", [])])
            await message.channel.send(
                f"📊 **현재 리뷰 상태**\n\n"
                f"상태: `{pending['status']}`\n"
                f"날짜: {pending.get('date', '알 수 없음')}\n"
                f"파일:\n{file_list}"
            )
        else:
            await message.channel.send("ℹ️ 대기 중인 리뷰가 없어요.")

    # ── !help ──
    elif message.content.strip() == "!help":
        await message.channel.send(
            "📌 **DGReview 명령어**\n\n"
            "`!feedback [내용]` — 피드백 입력 후 Claude에게 전달\n"
            "`!approve` — 피드백 없이 Gemma 리뷰 그대로 승인\n"
            "`!reject` — 리뷰 무시\n"
            "`!status` — 현재 리뷰 상태 확인\n"
            "`!help` — 이 도움말"
        )


# ── 봇 실행 ────────────────────────────────────────
def _run_bot():
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN 이 설정되지 않았어요. .env 파일을 확인해주세요.")
        return
    bot.run(DISCORD_TOKEN)


def start_bot():
    """별도 스레드로 Discord 봇 시작"""
    thread = threading.Thread(target=_run_bot, daemon=True)
    thread.start()


def send_to_discord(all_results: dict, all_summaries: str, today: str):
    """review.py에서 호출 — 결과를 Discord로 전송"""
    if not bot.is_ready():
        print("   봇 준비 대기 중...")
        import time
        for _ in range(10):
            time.sleep(1)
            if bot.is_ready():
                break
        else:
            print("❌ Discord 봇 연결 실패")
            return

    future = asyncio.run_coroutine_threadsafe(
        _send_review_results(all_results, all_summaries, today),
        bot.loop
    )
    future.result(timeout=60)
