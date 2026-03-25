"""AI-powered browser-use fallback for when Playwright selectors break.

Only imported and used when the deterministic Playwright flow fails.
"""

from __future__ import annotations

import logging
from datetime import date

from scheduler.booking.models import BookingResult, BookingStatus

logger = logging.getLogger(__name__)


async def get_times_fallback(url: str, target_date: date) -> list[str]:
    """Use browser-use to get available time slots when Playwright selectors break."""
    from browser_use import Agent, Browser, BrowserConfig
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model_name="claude-sonnet-4-6")
    browser = Browser(config=BrowserConfig(headless=True))

    formatted = target_date.strftime("%B %d, %Y")
    task = (
        f"Go to {url}. Select the date {formatted}. "
        f"Navigate to the correct month if needed. "
        f"Once you see the available time slots, list ALL of them exactly as displayed. "
        f"Return ONLY a comma-separated list of times like: 9:00am, 9:30am, 10:00am"
    )

    try:
        agent = Agent(task=task, llm=llm, browser=browser, max_actions=10)
        result = await agent.run()
        final_text = result.final_result() if hasattr(result, "final_result") else str(result)
        return [t.strip() for t in final_text.split(",") if t.strip()]
    finally:
        await browser.close()


async def book_slot_fallback(
    url: str, target_date: date, time: str, name: str, email: str
) -> BookingResult:
    """Use browser-use to book a slot when Playwright selectors break."""
    from browser_use import Agent, Browser, BrowserConfig
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model_name="claude-sonnet-4-6")
    browser = Browser(config=BrowserConfig(headless=True))

    formatted = target_date.strftime("%B %d, %Y")
    task = (
        f"Go to {url}. Select the date {formatted}. "
        f"Navigate to the correct month if needed. "
        f"Click the time slot for {time}. "
        f"Fill in the name field with '{name}' and the email field with '{email}'. "
        f"Click the confirm/schedule button. "
        f"Report whether the booking was confirmed."
    )

    try:
        agent = Agent(task=task, llm=llm, browser=browser, max_actions=15)
        result = await agent.run()
        final_text = result.final_result() if hasattr(result, "final_result") else str(result)
        if any(
            kw in final_text.lower()
            for kw in ["confirm", "scheduled", "booked", "success"]
        ):
            return BookingResult(
                status=BookingStatus.SUCCESS, confirmation_message=final_text
            )
        return BookingResult(status=BookingStatus.ERROR, error_detail=final_text)
    finally:
        await browser.close()
