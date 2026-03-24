"""CLI for booking automation.

Usage:
    python -m scheduler.booking times --url URL --date YYYY-MM-DD
    python -m scheduler.booking book  --url URL --date YYYY-MM-DD --time TIME --name NAME --email EMAIL
"""

import argparse
import asyncio
from datetime import date


def main():
    parser = argparse.ArgumentParser(description="Booking automation for Calendly / Cal.com")
    sub = parser.add_subparsers(dest="command", required=True)

    times_parser = sub.add_parser("times", help="Get available time slots")
    times_parser.add_argument("--url", required=True)
    times_parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    times_parser.add_argument("--no-headless", action="store_true")

    book_parser = sub.add_parser("book", help="Book a time slot")
    book_parser.add_argument("--url", required=True)
    book_parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    book_parser.add_argument("--time", required=True, help="e.g. 9:00am, 2:30pm")
    book_parser.add_argument("--name", required=True)
    book_parser.add_argument("--email", required=True)
    book_parser.add_argument("--title", default="", help="Meeting title (required for Cal.com)")
    book_parser.add_argument("--no-headless", action="store_true")

    args = parser.parse_args()

    if args.command == "times":
        from scheduler.booking import get_available_times

        target = date.fromisoformat(args.date)
        result = asyncio.run(get_available_times(args.url, target, headless=not args.no_headless))
        if result.error_detail:
            print(f"Error: {result.error_detail}")
        elif not result.times:
            print(f"No available times on {result.date}")
        else:
            print(f"Available times on {result.date}:")
            for t in result.times:
                print(f"  {t}")

    elif args.command == "book":
        from scheduler.booking import book_slot

        target = date.fromisoformat(args.date)
        result = asyncio.run(
            book_slot(
                args.url, target, args.time, args.name, args.email,
                headless=not args.no_headless,
                title=args.title,
            )
        )
        print(f"Status: {result.status.value}")
        if result.confirmation_message:
            print(f"Confirmation: {result.confirmation_message}")
        if result.error_detail:
            print(f"Error: {result.error_detail}")


if __name__ == "__main__":
    main()
