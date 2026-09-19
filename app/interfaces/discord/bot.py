import asyncio
import os
import queue
import re
import time
import traceback
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from app.core.ai import create_ai_provider
from app.memory.extractor import MemoryExtractor
from app.memory.manager import MemoryManager
from app.scheduler import ReminderScheduler


# ============================================================
# DISCORD MESSAGE CONFIGURATION
# ============================================================

# Discord is currently enforcing a 2000-character message limit
# for this bot/channel configuration.
#
# We intentionally stay below that limit to keep a safety margin.
DISCORD_MAX_MESSAGE_LENGTH = 2000
DISCORD_SAFE_MESSAGE_LENGTH = 1800


# ============================================================
# DISCORD MESSAGE HELPERS
# ============================================================

def split_long_message(
    content: str,
    max_length: int = DISCORD_SAFE_MESSAGE_LENGTH,
) -> list[str]:
    """
    Split a long message into Discord-safe chunks.

    Splitting priority:
        1. Paragraph/newline boundary
        2. Space boundary
        3. Hard character split

    Every returned chunk is guaranteed to be <= max_length.
    """

    if content is None:
        return [""]

    content = str(content)

    if max_length <= 0:
        raise ValueError(
            "max_length must be greater than zero."
        )

    if len(content) <= max_length:
        return [content]

    chunks: list[str] = []
    remaining = content

    while len(remaining) > max_length:
        candidate = remaining[:max_length]

        # --------------------------------------------------------
        # Prefer a newline.
        # --------------------------------------------------------

        split_at = candidate.rfind("\n")

        # Ignore a newline if it would create a very tiny chunk.
        if split_at < max_length // 4:
            split_at = -1

        # --------------------------------------------------------
        # Otherwise prefer a space.
        # --------------------------------------------------------

        if split_at == -1:
            split_at = candidate.rfind(" ")

        # --------------------------------------------------------
        # Final fallback: hard split.
        # --------------------------------------------------------

        if split_at <= 0:
            split_at = max_length

        chunk = remaining[:split_at].rstrip()

        if chunk:
            chunks.append(chunk)

        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


async def send_long_message(
    destination,
    content: str,
    max_length: int = DISCORD_SAFE_MESSAGE_LENGTH,
):
    """
    Safely send a potentially long response to Discord.

    Long AI responses are automatically split into multiple
    messages so Discord never receives a message above the
    configured safe limit.
    """

    chunks = split_long_message(
        content,
        max_length=max_length,
    )

    for chunk in chunks:
        await destination.send(chunk)


# ============================================================
# STREAMING RESPONSE HELPER
# ============================================================

DISCORD_STREAM_UPDATE_INTERVAL_SECONDS = 0.6


async def stream_ai_response(
    destination,
    ai,
    prompt: str,
    max_length: int = DISCORD_SAFE_MESSAGE_LENGTH,
) -> str:
    """
    Stream an AI response to Discord without blocking the event loop.

    The provider SDKs are synchronous, so the generator is consumed in a
    worker thread. Discord receives progressive message edits rather than
    waiting for the complete response.
    """

    stream_queue: queue.Queue[tuple[str, object | None]] = queue.Queue()

    def worker() -> None:
        try:
            for chunk in ai.stream_message(prompt):
                if chunk:
                    stream_queue.put(("chunk", str(chunk)))

            stream_queue.put(("done", None))

        except Exception as error:
            stream_queue.put(("error", error))

    worker_task = asyncio.create_task(
        asyncio.to_thread(worker)
    )

    current_message = None
    current_text = ""
    full_response_parts: list[str] = []
    last_update_time = 0.0
    has_sent_message = False

    while True:
        kind, payload = await asyncio.to_thread(
            stream_queue.get
        )

        if kind == "error":
            await worker_task
            raise payload

        if kind == "done":
            break

        chunk = str(payload or "")

        if not chunk:
            continue

        full_response_parts.append(chunk)

        pending = current_text + chunk

        while len(pending) > max_length:
            safe_chunks = split_long_message(
                pending,
                max_length=max_length,
            )

            completed = safe_chunks[0]

            if current_message is None:
                current_message = await destination.send(
                    completed
                )
            else:
                await current_message.edit(
                    content=completed
                )

            has_sent_message = True
            current_message = None

            pending = pending[len(completed):].lstrip()

        current_text = pending

        if not current_text:
            continue

        now = time.monotonic()

        if current_message is None:
            current_message = await destination.send(
                current_text
            )
            has_sent_message = True
            last_update_time = now

        elif (
            now - last_update_time
            >= DISCORD_STREAM_UPDATE_INTERVAL_SECONDS
        ):
            await current_message.edit(
                content=current_text
            )
            last_update_time = now

    await worker_task

    final_response = "".join(full_response_parts)

    if current_text:
        if current_message is None:
            await destination.send(current_text)
            has_sent_message = True
        else:
            await current_message.edit(
                content=current_text
            )
    elif not has_sent_message:
        raise RuntimeError(
            "AI provider returned an empty streamed response."
        )

    return final_response


# ============================================================
# BOT CREATION
# ============================================================

def create_bot():
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
    )

    # ------------------------------------------------------------
    # Core services
    # ------------------------------------------------------------

    ai = create_ai_provider()
    memory = MemoryManager()
    extractor = MemoryExtractor()

    ai_chat_mode = os.getenv(
        "AI_CHAT_MODE",
        "normal",
    ).lower()

    # Discord user ID -> conversation ID
    active_user_sessions: dict[int, int] = {}

    reminder_scheduler = ReminderScheduler(bot)

    # ============================================================
    # EVENTS
    # ============================================================

    @bot.event
    async def on_ready():
        print(f"✅ {bot.user} is online!")
        print(f"   Bot ID: {bot.user.id}")
        print("   Discord connection successful.")
        print(f"   AI Provider: {ai.__class__.__name__}")
        print(f"   AI Chat Mode: {ai_chat_mode}")

        if not reminder_scheduler.running:
            asyncio.create_task(
                reminder_scheduler.start()
            )

    # ============================================================
    # BASIC COMMANDS
    # ============================================================

    @bot.command()
    async def ping(ctx):
        await ctx.send(
            "🏓 Pong! Zoya is online."
        )

    @bot.command()
    async def status(ctx):
        configured = [
            name
            for name, _ in ai.providers
        ]

        active = ai.active_provider

        provider_status = ", ".join(
            provider.capitalize()
            for provider in configured
        )

        await ctx.send(
            "✅ Zoya is working correctly.\n"
            f"🤖 Active provider: **{active.capitalize()}**\n"
            f"🔌 Configured providers: **{provider_status}**"
        )

    # ============================================================
    # MEMORY COMMANDS
    # ============================================================

    @bot.command()
    async def remember(ctx, *, content: str):
        try:
            user_id = ctx.author.id

            memory.get_or_create_user(
                user_id=user_id,
                name=ctx.author.display_name,
            )

            memories = extractor.extract(
                f"yaad rakho {content}"
            )

            if not memories:
                await ctx.send(
                    "Mujhe samajh nahi aaya ki kya yaad rakhna hai."
                )
                return

            saved = 0

            for item in memories:
                memory.save_memory(
                    user_id=user_id,
                    category=item["category"],
                    key=item["key"],
                    value=item["value"],
                    importance=item["importance"],
                    confidence=item["confidence"],
                    source="manual",
                )

                saved += 1

            await ctx.send(
                f"✅ Done! Maine {saved} memory save kar li."
            )

        except Exception:
            print("\n❌ REMEMBER COMMAND ERROR")
            traceback.print_exc()

            await ctx.send(
                "Sorry, memory save karte waqt problem aayi."
            )

    @bot.command()
    async def forget(ctx, *, key: str):
        try:
            user_id = ctx.author.id

            memory_key = key.strip().lower()

            aliases = {
                "naam": "name",
                "name": "name",
                "hinglish": "communication_language",
                "language": "communication_language",
                "favourite color": "favorite_color",
                "favorite color": "favorite_color",
                "cricket": "likes",
                "pasand": "likes",
            }

            memory_key = aliases.get(
                memory_key,
                memory_key,
            )

            deleted = memory.delete_memory(
                user_id=user_id,
                key=memory_key,
            )

            if deleted:
                await ctx.send(
                    f"✅ `{memory_key}` wali memory delete kar di."
                )
            else:
                await ctx.send(
                    f"❌ Mujhe `{memory_key}` naam ki memory nahi mili."
                )

        except Exception:
            print("\n❌ FORGET COMMAND ERROR")
            traceback.print_exc()

            await ctx.send(
                "Sorry, memory delete karte waqt problem aayi."
            )

    @bot.command(name="memory")
    async def show_memory(ctx):
        try:
            user_id = ctx.author.id

            memories = memory.get_memories(
                user_id=user_id,
                min_importance=1,
            )

            if not memories:
                await ctx.send(
                    "🧠 Abhi meri memory mein tumhare baare mein "
                    "kuch saved nahi hai."
                )
                return

            lines = [
                "🧠 **Meri saved memories:**"
            ]

            for item in memories:
                lines.append(
                    f"• `{item.key}` → {item.value}"
                )

            await send_long_message(
                ctx,
                "\n".join(lines),
            )

        except Exception:
            print("\n❌ MEMORY COMMAND ERROR")
            traceback.print_exc()

            await ctx.send(
                "Sorry, memory read karte waqt problem aayi."
            )

    # ============================================================
    # REMINDER COMMANDS
    # ============================================================

    @bot.command()
    async def remind(
        ctx,
        minutes: int,
        *,
        content: str,
    ):
        try:
            if minutes <= 0:
                await ctx.send(
                    "⏱️ Minutes 1 ya usse zyada hone chahiye."
                )
                return

            remind_at = datetime.utcnow() + timedelta(
                minutes=minutes
            )

            reminder = memory.create_reminder(
                user_id=ctx.author.id,
                channel_id=ctx.channel.id,
                message=content,
                remind_at=remind_at,
            )

            await ctx.send(
                f"✅ Reminder set: **{content}** "
                f"in **{minutes} minute(s)**.\n"
                f"🆔 Reminder ID: `{reminder.reminder_id}`"
            )

        except ValueError:
            await ctx.send(
                "Usage: `!remind <minutes> <message>`"
            )

        except Exception:
            print("\n❌ REMINDER COMMAND ERROR")
            traceback.print_exc()

            await ctx.send(
                "Sorry, reminder set karte waqt problem aayi."
            )

    @bot.command()
    async def reminders(ctx):
        try:
            pending = memory.get_pending_reminders(
                user_id=ctx.author.id
            )

            if not pending:
                await ctx.send(
                    "⏰ Tumhare koi pending reminders nahi hain."
                )
                return

            lines = [
                "⏰ **Pending reminders:**"
            ]

            for reminder in pending:
                lines.append(
                    f"• `#{reminder.reminder_id}` → "
                    f"{reminder.message}"
                )

            await send_long_message(
                ctx,
                "\n".join(lines),
            )

        except Exception:
            print("\n❌ REMINDERS COMMAND ERROR")
            traceback.print_exc()

            await ctx.send(
                "Sorry, reminders read karte waqt problem aayi."
            )

    # ============================================================
    # !ASK COMMAND
    # ============================================================

    @bot.command()
    async def ask(ctx, *, content: str):
        try:
            user_id = ctx.author.id

            # ----------------------------------------------------
            # Make sure user exists.
            # ----------------------------------------------------

            memory.get_or_create_user(
                user_id=user_id,
                name=ctx.author.display_name,
            )

            # ----------------------------------------------------
            # Get or create active conversation.
            # ----------------------------------------------------

            conversation_id = active_user_sessions.get(
                user_id
            )

            if conversation_id is None:
                conversation = memory.create_conversation(
                    user_id=user_id,
                )

                conversation_id = (
                    conversation.conversation_id
                )

                active_user_sessions[user_id] = (
                    conversation_id
                )

            # ----------------------------------------------------
            # Save user message.
            # ----------------------------------------------------

            memory.save_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=content,
            )

            # ----------------------------------------------------
            # Load recent conversation.
            # ----------------------------------------------------

            recent_messages = (
                memory.get_recent_messages(
                    conversation_id=conversation_id,
                    limit=10,
                )
            )

            # ----------------------------------------------------
            # Load persistent memories.
            # ----------------------------------------------------

            stored_memories = memory.get_memories(
                user_id=user_id,
                min_importance=1,
            )

            memory_lines = [
                f"- {item.key}: {item.value}"
                for item in stored_memories
            ]

            context_lines = [
                f"{item.role}: {item.content}"
                for item in recent_messages
            ]

            # ----------------------------------------------------
            # Build AI input.
            # ----------------------------------------------------

            ai_message = (
                content
                + "\n\nPersistent memories:\n"
                + "\n".join(memory_lines)
                + "\n\nRecent conversation:\n"
                + "\n".join(context_lines)
            )

            # ----------------------------------------------------
            # IMPORTANT:
            #
            # AI SDKs currently used by Zoya are synchronous.
            # Run the blocking network operation in a worker
            # thread so Discord's event loop remains responsive.
            # ----------------------------------------------------

            async with ctx.channel.typing():
                reply = await stream_ai_response(
                    ctx,
                    ai,
                    ai_message,
                )

            # ----------------------------------------------------
            # Save assistant response.
            # ----------------------------------------------------

            memory.save_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=reply,
            )

            # Streaming helper has already delivered the response to Discord.
            # Do not send the complete response again.

        except Exception as error:
            print("\n" + "=" * 60)
            print("❌ ZOYA AI ERROR")
            print("=" * 60)

            print(
                f"Error type: {type(error).__name__}"
            )

            print(
                f"Error message: {error}"
            )

            print("\nFull traceback:")
            traceback.print_exc()

            print("=" * 60 + "\n")

            error_text = str(error).lower()

            if (
                "429" in error_text
                or "quota" in error_text
                or "rate limit" in error_text
                or "too many requests" in error_text
            ):
                await ctx.send(
                    "⚠️ AI providers temporarily unavailable."
                )

            else:
                await ctx.send(
                    "Sorry, abhi AI response generate nahi ho paaya."
                )

    # ============================================================
    # NORMAL MESSAGE HANDLER
    # ============================================================

    @bot.event
    async def on_message(message):
        # --------------------------------------------------------
        # Ignore messages sent by bots.
        # --------------------------------------------------------

        if message.author.bot:
            return

        # --------------------------------------------------------
        # Process Discord commands.
        # --------------------------------------------------------

        await bot.process_commands(message)

        # --------------------------------------------------------
        # Don't process commands as normal AI chat.
        # --------------------------------------------------------

        if message.content.startswith("!"):
            return

        try:
            user_id = message.author.id
            user_name = message.author.display_name

            # ----------------------------------------------------
            # Make sure user exists.
            # ----------------------------------------------------

            memory.get_or_create_user(
                user_id=user_id,
                name=user_name,
            )

            # ====================================================
            # NATURAL-LANGUAGE MEMORY DELETION
            # ====================================================

            forget_patterns = [
                r"^(?:zoya[, ]*)?(?:mera|meri|mere)\s+(.+?)\s+(?:bhool jao|forget kar do)$",
                r"^(?:zoya[, ]*)?(?:ye|is)\s+(.+?)\s+(?:bhool jao|forget kar do)$",
                r"^(?:zoya[, ]*)?(?:bhool jao|forget kar do)\s+(.+)$",
            ]

            forget_key = None

            for pattern in forget_patterns:
                match = re.match(
                    pattern,
                    message.content.strip(),
                    re.IGNORECASE,
                )

                if match:
                    forget_key = (
                        match.group(1)
                        .strip()
                        .lower()
                    )
                    break

            if forget_key:
                aliases = {
                    "naam": "name",
                    "name": "name",
                    "hinglish": "communication_language",
                    "language": "communication_language",
                    "favourite color": "favorite_color",
                    "favorite color": "favorite_color",
                    "cricket": "likes",
                    "pasand": "likes",
                }

                memory_key = aliases.get(
                    forget_key,
                    forget_key,
                )

                deleted = memory.delete_memory(
                    user_id=user_id,
                    key=memory_key,
                )

                if deleted:
                    await message.channel.send(
                        f"✅ `{memory_key}` wali memory bhool gayi."
                    )
                else:
                    await message.channel.send(
                        f"❌ `{memory_key}` naam ki memory nahi mili."
                    )

                return

            # ====================================================
            # COMMAND MODE
            # ====================================================

            if ai_chat_mode == "command":
                extracted_memories = (
                    extractor.extract(
                        message.content
                    )
                )

                if extracted_memories:
                    for item in extracted_memories:
                        memory.save_memory(
                            user_id=user_id,
                            category=item["category"],
                            key=item["key"],
                            value=item["value"],
                            importance=item["importance"],
                            confidence=item["confidence"],
                            source=item["source"],
                        )

                    await message.channel.send(
                        "✅ Yaad rakh liya."
                    )

                else:
                    await message.channel.send(
                        "💡 AI response ke liye `!ask` use karo."
                    )

                return

            # ====================================================
            # NORMAL AI CHAT MODE
            # ====================================================

            conversation_id = (
                active_user_sessions.get(
                    user_id
                )
            )

            # ----------------------------------------------------
            # Create conversation if necessary.
            # ----------------------------------------------------

            if conversation_id is None:
                conversation = memory.create_conversation(
                    user_id=user_id,
                )

                conversation_id = (
                    conversation.conversation_id
                )

                active_user_sessions[user_id] = (
                    conversation_id
                )

            # ----------------------------------------------------
            # Save user message.
            # ----------------------------------------------------

            memory.save_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=message.content,
            )

            # ----------------------------------------------------
            # Extract possible memories.
            # ----------------------------------------------------

            extracted_memories = (
                extractor.extract(
                    message.content
                )
            )

            for item in extracted_memories:
                memory.save_memory(
                    user_id=user_id,
                    category=item["category"],
                    key=item["key"],
                    value=item["value"],
                    importance=item["importance"],
                    confidence=item["confidence"],
                    source=item["source"],
                )

            # ----------------------------------------------------
            # Load recent conversation.
            # ----------------------------------------------------

            recent_messages = (
                memory.get_recent_messages(
                    conversation_id=conversation_id,
                    limit=10,
                )
            )

            # ----------------------------------------------------
            # Load persistent memories.
            # ----------------------------------------------------

            stored_memories = memory.get_memories(
                user_id=user_id,
                min_importance=1,
            )

            memory_context = ""

            if stored_memories:
                memory_lines = [
                    f"- {item.key}: {item.value}"
                    for item in stored_memories
                ]

                memory_context = (
                    "\n\nPersistent memories "
                    "about the user:\n"
                    + "\n".join(memory_lines)
                )

            # ----------------------------------------------------
            # Build recent conversation context.
            # ----------------------------------------------------

            conversation_context = ""

            if recent_messages:
                context_lines = [
                    f"{item.role}: {item.content}"
                    for item in recent_messages
                ]

                conversation_context = (
                    "\n\nRecent conversation:\n"
                    + "\n".join(context_lines)
                )

            # ----------------------------------------------------
            # Build final AI input.
            # ----------------------------------------------------

            ai_message = (
                message.content
                + memory_context
                + conversation_context
            )

            # ----------------------------------------------------
            # IMPORTANT:
            #
            # Move blocking AI SDK call away from Discord's
            # event loop.
            # ----------------------------------------------------

            async with message.channel.typing():
                reply = await stream_ai_response(
                    message.channel,
                    ai,
                    ai_message,
                )

            # ----------------------------------------------------
            # Save assistant response.
            # ----------------------------------------------------

            memory.save_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=reply,
            )

            # Streaming helper has already delivered the response to Discord.
            # Do not send the complete response again.

        except Exception as error:
            print("\n" + "=" * 60)
            print("❌ ZOYA MESSAGE ERROR")
            print("=" * 60)

            print(
                f"Error type: {type(error).__name__}"
            )

            print(
                f"Error message: {error}"
            )

            print("\nFull traceback:")
            traceback.print_exc()

            print("=" * 60 + "\n")

            # ----------------------------------------------------
            # Error messages are intentionally short.
            # ----------------------------------------------------

            try:
                await message.channel.send(
                    "Sorry, mujhe abhi response generate "
                    "karne mein problem aa rahi hai."
                )
            except Exception:
                print(
                    "❌ Failed to send error message to Discord."
                )

    return bot


# ============================================================
# BOT STARTUP
# ============================================================

def start_bot(token: str):
    bot = create_bot()
    bot.run(token)