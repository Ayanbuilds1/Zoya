import asyncio
from datetime import datetime

from app.memory.manager import MemoryManager


class ReminderScheduler:
    def __init__(self, bot) -> None:
        self.bot = bot
        self.memory = MemoryManager()
        self.running = False

    async def start(self) -> None:
        if self.running:
            return

        self.running = True

        print("⏰ Reminder scheduler started.")

        while self.running:
            try:
                await self.check_reminders()

            except Exception as error:
                print(
                    f"❌ Reminder scheduler error: {error}"
                )

            await asyncio.sleep(10)

    async def check_reminders(self) -> None:
        now = datetime.utcnow()

        reminders = self.memory.get_due_reminders(now)

        for reminder in reminders:
            channel = self.bot.get_channel(
                reminder.channel_id
            )

            if channel is None:
                continue

            await channel.send(
                f"⏰ **Reminder:** {reminder.message}"
            )

            self.memory.complete_reminder(
                reminder.reminder_id
            )