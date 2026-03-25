"""Deterministic Playwright scripts for Calendly and Cal.com booking pages.

Uses hardcoded selectors discovered via page exploration. Fast and free —
no LLM calls. Falls back to browser-use (see fallback.py) when selectors break.
"""

from __future__ import annotations

import calendar as cal_module
import logging
from datetime import date

from playwright.async_api import Page, async_playwright

from scheduler.booking.models import (
    BookingPlatform,
    BookingResult,
    BookingStatus,
    detect_platform,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Calendly selectors
# ---------------------------------------------------------------------------
# Date buttons live in a <table> and carry an aria-label like:
#   "Wednesday, March 25 - Times available"
#   "Sunday, March 1 - No times available"
# Month navigation: button[aria-label='Go to next month']
# Time slots after date click: button[data-start-time] with text like "4:00pm"
# After clicking a time, a "Next" button appears.
# Form: input[name='full_name'], input[name='email']
# Submit: button[type='submit'] ("Schedule Event")

# ---------------------------------------------------------------------------
# Cal.com selectors
# ---------------------------------------------------------------------------
# Date buttons: button[data-testid='day'] — disabled attr marks unavailable
# Month label: [data-testid='selected-month-label'] (e.g. "March 2026")
# Month nav: button[data-testid='incrementMonth'] / 'decrementMonth'
# Time slots: button[data-testid='time'] with text like "9:00am"
# Form: input[name='name'], input[name='email']
# Submit: button[data-testid='confirm-book-button'] ("Confirm")


async def _navigate_to_month(page: Page, target_date: date, platform: BookingPlatform):
    """Click next/prev month arrows until the calendar shows the target month."""
    max_clicks = 12
    for _ in range(max_clicks):
        if platform == BookingPlatform.CALENDLY:
            # Calendly: header data-testid='title' contains "March 2026"
            header = await page.query_selector("[data-testid='title']")
        else:
            header = await page.query_selector("[data-testid='selected-month-label']")

        if not header:
            break
        header_text = (await header.text_content() or "").strip()
        target_month_name = cal_module.month_name[target_date.month]
        target_label = f"{target_month_name} {target_date.year}"

        if target_label in header_text:
            return  # already on the right month

        # Determine direction
        # Parse current month/year from header
        for m_idx, m_name in enumerate(cal_module.month_name):
            if m_name and m_name in header_text:
                current_month = m_idx
                break
        else:
            # Can't parse, just click forward
            current_month = 0

        current_year = target_date.year
        for token in header_text.split():
            if token.isdigit() and len(token) == 4:
                current_year = int(token)

        current_ord = current_year * 12 + current_month
        target_ord = target_date.year * 12 + target_date.month

        if target_ord > current_ord:
            if platform == BookingPlatform.CALENDLY:
                await page.click("button[aria-label='Go to next month']")
            else:
                await page.click("button[data-testid='incrementMonth']")
        else:
            if platform == BookingPlatform.CALENDLY:
                await page.click("button[aria-label='Go to previous month']")
            else:
                await page.click("button[data-testid='decrementMonth']")

        await page.wait_for_timeout(800)


async def _select_date_calendly(page: Page, target_date: date):
    """Click the target date on a Calendly calendar."""
    await _navigate_to_month(page, target_date, BookingPlatform.CALENDLY)

    # Calendly date buttons have aria-labels like "Wednesday, March 25 - Times available"
    day_str = str(target_date.day)
    buttons = await page.query_selector_all("table button[aria-label]")
    for btn in buttons:
        text = (await btn.text_content() or "").strip()
        aria = await btn.get_attribute("aria-label") or ""
        if text == day_str and "Times available" in aria:
            await btn.click()
            await page.wait_for_timeout(2000)
            return
    raise RuntimeError(f"Calendly: date {target_date} not available or not found")


async def _select_date_calcom(page: Page, target_date: date):
    """Click the target date on a Cal.com calendar."""
    await _navigate_to_month(page, target_date, BookingPlatform.CAL_COM)

    day_str = str(target_date.day)
    buttons = await page.query_selector_all("button[data-testid='day']:not([disabled])")
    for btn in buttons:
        text = (await btn.text_content() or "").strip()
        if text == day_str:
            await btn.click()
            await page.wait_for_timeout(2000)
            return
    raise RuntimeError(f"Cal.com: date {target_date} not available or not found")


async def _get_times_calendly(page: Page) -> list[str]:
    """Scrape available time slots from Calendly after a date is selected."""
    slots = await page.query_selector_all("button[data-start-time]")
    times = []
    for slot in slots:
        text = (await slot.text_content() or "").strip()
        if text:
            times.append(text)
    return times


async def _get_times_calcom(page: Page) -> list[str]:
    """Scrape available time slots from Cal.com after a date is selected."""
    slots = await page.query_selector_all("button[data-testid='time']")
    times = []
    for slot in slots:
        text = (await slot.text_content() or "").strip()
        # Filter out non-time elements (e.g. timezone text also has testid='time')
        if text and ("am" in text.lower() or "pm" in text.lower()) and len(text) < 15:
            times.append(text)
    return times


async def _click_time_calendly(page: Page, time: str):
    """Click a specific time slot on Calendly and advance to the form."""
    time_lower = time.lower().replace(" ", "")
    slots = await page.query_selector_all("button[data-start-time]")
    for slot in slots:
        text = (await slot.text_content() or "").strip().lower().replace(" ", "")
        if text == time_lower:
            await slot.click()
            await page.wait_for_timeout(1500)
            # Click "Next" button that appears
            next_btn = await page.query_selector("button:has-text('Next')")
            if next_btn:
                await next_btn.click()
                await page.wait_for_timeout(2000)
            return
    raise RuntimeError(f"Calendly: time slot '{time}' not found")


async def _click_time_calcom(page: Page, time: str):
    """Click a specific time slot on Cal.com to reveal the form."""
    time_lower = time.lower().replace(" ", "")
    slots = await page.query_selector_all("button[data-testid='time']")
    for slot in slots:
        text = (await slot.text_content() or "").strip().lower().replace(" ", "")
        if text == time_lower:
            await slot.click()
            await page.wait_for_timeout(2000)
            return
    raise RuntimeError(f"Cal.com: time slot '{time}' not found")


async def _fill_and_submit_calendly(page: Page, name: str, email: str):
    """Fill the Calendly booking form and submit.

    Calendly has an invisible reCAPTCHA. It usually passes automatically for
    non-suspicious traffic. If it blocks us, the page stays on the form
    instead of navigating to the confirmation URL.
    """
    await page.fill("input[name='full_name']", name)
    await page.fill("input[name='email']", email)

    # Capture the URL before submit to detect navigation
    url_before = page.url
    await page.click("button[type='submit']")

    # Wait for either a URL change (success) or an error element (failure).
    # Calendly redirects to a confirmation page on success.
    try:
        await page.wait_for_function(
            "() => window.location.href !== arguments[0]",
            url_before,
            timeout=15000,
        )
    except Exception:
        pass  # URL didn't change — could be reCAPTCHA block or error


async def _fill_and_submit_calcom(page: Page, name: str, email: str, title: str = ""):
    """Fill the Cal.com booking form and submit.

    Cal.com has a required "What is this meeting about?" title field.
    """
    await page.fill("input[name='name']", name)
    await page.fill("input[name='email']", email)

    # Fill the required title field if present
    title_input = await page.query_selector("input[name='title']")
    if title_input:
        await page.fill("input[name='title']", title or "Meeting")

    # Capture URL before submit
    url_before = page.url
    await page.click("button[data-testid='confirm-book-button']")

    # Cal.com navigates to /booking/<id> on success
    try:
        await page.wait_for_function(
            "() => window.location.href !== arguments[0]",
            url_before,
            timeout=15000,
        )
    except Exception:
        pass


async def _check_confirmation_calendly(page: Page) -> BookingResult:
    """Check if Calendly shows a booking confirmation.

    Verification signals (strongest to weakest):
    1. URL contains "/invitees/" — Calendly's confirmed booking URL pattern
    2. Page contains "You are scheduled" heading
    3. Page title changes to include "Confirmed"
    """
    url = page.url
    content = await page.content()
    title = await page.title()

    if "/invitees/" in url:
        return BookingResult(
            status=BookingStatus.SUCCESS,
            confirmation_message="Meeting scheduled on Calendly",
        )
    if "You are scheduled" in content:
        return BookingResult(
            status=BookingStatus.SUCCESS,
            confirmation_message="Meeting scheduled on Calendly",
        )
    if "confirmed" in title.lower():
        return BookingResult(
            status=BookingStatus.SUCCESS,
            confirmation_message="Meeting scheduled on Calendly",
        )

    # Detect specific failures
    if "recaptcha" in content.lower() and "Schedule Event" in content:
        return BookingResult(
            status=BookingStatus.ERROR,
            error_detail="Blocked by reCAPTCHA — try running with --no-headless",
        )

    error_el = await page.query_selector("[data-component='error-message']")
    if error_el:
        error_text = await error_el.text_content()
        return BookingResult(status=BookingStatus.SLOT_TAKEN, error_detail=error_text)

    return BookingResult(
        status=BookingStatus.ERROR,
        error_detail=f"Could not confirm booking. Final URL: {url}",
    )


async def _check_confirmation_calcom(page: Page) -> BookingResult:
    """Check if Cal.com shows a booking confirmation.

    Verification signals:
    1. URL contains "/booking/" — Cal.com's confirmed booking URL pattern
    2. Page contains "This meeting is scheduled" or "is scheduled"
    """
    url = page.url
    content = await page.content()

    if "/booking/" in url:
        return BookingResult(
            status=BookingStatus.SUCCESS,
            confirmation_message="Meeting scheduled on Cal.com",
        )
    if "is scheduled" in content.lower():
        return BookingResult(
            status=BookingStatus.SUCCESS,
            confirmation_message="Meeting scheduled on Cal.com",
        )

    # Check for validation errors still on the form
    if "confirm-book-button" in content:
        return BookingResult(
            status=BookingStatus.ERROR,
            error_detail="Form submission failed — still on booking form. Check required fields.",
        )

    return BookingResult(
        status=BookingStatus.ERROR,
        error_detail=f"Could not confirm booking. Final URL: {url}",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_times_playwright(
    url: str, target_date: date, headless: bool = True
) -> list[str]:
    """Navigate to a booking page, select a date, and return available time slots."""
    platform = detect_platform(url)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_timeout(3000)

            if platform == BookingPlatform.CALENDLY:
                await _select_date_calendly(page, target_date)
                return await _get_times_calendly(page)
            else:
                await _select_date_calcom(page, target_date)
                return await _get_times_calcom(page)
        finally:
            await browser.close()


async def book_slot_playwright(
    url: str,
    target_date: date,
    time: str,
    name: str,
    email: str,
    headless: bool = True,
    title: str = "",
) -> BookingResult:
    """Navigate to a booking page, select date/time, fill the form, and submit."""
    platform = detect_platform(url)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await page.wait_for_timeout(3000)

            if platform == BookingPlatform.CALENDLY:
                await _select_date_calendly(page, target_date)
                await _click_time_calendly(page, time)
                await _fill_and_submit_calendly(page, name, email)
                return await _check_confirmation_calendly(page)
            else:
                await _select_date_calcom(page, target_date)
                await _click_time_calcom(page, time)
                await _fill_and_submit_calcom(page, name, email, title=title)
                return await _check_confirmation_calcom(page)
        finally:
            await browser.close()
