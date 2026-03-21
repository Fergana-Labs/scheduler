---
slug: scheduled-case-study
title: 'The Tyranny of Scheduling'
description: 'Scheduling is the laundry of startup life. It barely takes any time, but the mental friction is enormous. Here is how we built Scheduled to make it disappear.'
date: '2026-03-20'
author: 'Sam Liu'
category: 'Case Studies'
keywords: 'scheduled case study, ai scheduling assistant results, startup ceo productivity, email scheduling automation, scheduled review'
metaDescription: 'A founder explains why scheduling emails are the worst kind of friction, how existing tools failed him, and how Scheduled finally made the problem disappear.'
---

# The Tyranny of Scheduling

A shocking amount of being a founder is just scheduling meetings. Between recruiting, customer demos, investor calls, user interviews, fundraising, and coffee chats with other founders, my calendar is basically my whole job some weeks. And a lot of those meetings are personal enough that a Calendly link feels wrong, like routing someone through a queue instead of actually talking to them.

The meetings themselves are fine. I like talking to people. The part that slowly drove me insane was the scheduling.

## The laundry problem

I call scheduling the "laundry problem." Physically, it doesn't take that much time. You read an email, check your calendar, propose a couple times, maybe go back and forth once. Five minutes.

But the mental weight is completely disproportionate to the actual effort. It's the same reason laundry can ruin your Sunday even though folding takes ten minutes. It's sitting there in the back of your head. Did that person confirm? Did I forget to reply to the one from yesterday? Is next Tuesday actually free or did I already offer that slot to someone else?

You keep going back to it. You keep context-switching into it. The cost isn't the minutes, it's the attention leak.

## None of the existing tools worked for me

I went through a bunch of them: Howie, Fyxer, Superhuman, Spark. I wanted them to work. They just didn't fit how I actually use email.

I am not an inbox-zero person. I am inbox 100,000. That's not an exaggeration. I read and skim everything in the preview pane without opening most emails. I don't need to action every message to stay on top of things. I can glance at a preview and know whether something needs me now, later, or never.

Most email productivity tools assume you want to process each message through some system: archive, snooze, label, respond. They assume inbox zero is the goal. For me, that workflow adds overhead instead of removing it.

The scheduling features in those tools were never truly end-to-end, either. The AI would draft something, but then I'd have to jump in and fix the times, or manually check my calendar, or tweak the tone. At that point you've just moved the friction around. If I have to get back into the flow of whatever the AI started, it's providing almost no value.

## Why we built it

We have a principle at our company: spend 15% of your time automating your existing work with AI. That's how a small team compounds effort and builds accumulating advantage over time. You don't just work harder, you make the work disappear.

Scheduling was a natural target. It's important (you can't just ignore it), it's annoying (same pattern every time), and it's repetitive in a way that AI should handle well: read email, check calendar, propose times, confirm.

So we built Scheduled for ourselves first. I had a specific list of things I needed from it.

It had to be genuinely end-to-end. I mean: it reads the email, knows my preferences, checks my calendars, writes a reply that sounds like me, and puts a calendar hold in the right place. One flow with no gaps in between where I have to take over.

It had to know how I like my schedule structured. I like meetings grouped together so I can knock them out in a block and then have real uninterrupted time for actual work. If meetings are spread across the day with 45-minute gaps, I can't get into flow on anything, which is worse than having more meetings.

It had to understand my quirks. I wake up late, so I don't love early mornings, but for certain important people I'll happily take a 7am. A rigid "no meetings before 10" rule doesn't capture that. The AI had to learn the difference.

And it had to sound like me. If someone reads a scheduling reply and thinks "that doesn't sound like Sam," the whole thing breaks. This was the feature I cared about most.

## What my mornings look like now

I wake up, check email, and look at my drafts. Scheduled has already gone through everything that came in overnight and written replies for anything scheduling-related.

Most mornings, I just hit approve on all of them. Sometimes I'll tweak a word or adjust the tone for a specific person. One thing I didn't expect to love so much: if I edit the time in the email, the calendar event updates automatically. No switching between tabs to make sure everything matches.

For recruiting, I've set up a fully automated flow where scheduling emails just get handled on autopilot without me thinking about them. It still respects my preferences though, still tries to group the meetings together, still writes in my voice. It's automation without feeling like I handed someone a booking widget.

## The timezone mistake I don't make anymore

There's a week every year when Europe shifts for daylight savings at a different time than the US. For about a week, the offsets are wrong in a way your brain doesn't catch because you're used to the normal gap. I once showed up an hour late (or early? I honestly can't remember which) to an investor call because of exactly this. Embarrassing.

Scheduled handles multi-timezone, multi-calendar scheduling without any mental math. It knows about DST transitions, knows which calendar is in which timezone, knows that London is sometimes five hours ahead and sometimes four. I don't have to think about it or even know it's happening.

## The real value

People always ask how many hours it saves me and I get why, it's an easy metric. But that's not what changed about my life.

What changed is that scheduling no longer occupies background space in my brain. I don't go to bed wondering if I forgot to reply to someone about a meeting. I don't do calendar math while I'm trying to think about product. The open threads closed. Someone took the laundry, folded it, and put it away, and I got back the headspace that was being quietly consumed by knowing it was sitting there.

That's what this actually solves. Not hours on a timesheet, but the low-grade friction that was eating into everything else.

## Try Scheduled

Scheduled is open source under the MIT license. It connects to Gmail and Google Calendar, learns your writing style and scheduling preferences, and handles reply emails for you.

If scheduling is your laundry problem too, give it a shot.

- **GitHub:** [github.com/Fergana-Labs/scheduler](https://github.com/Fergana-Labs/scheduler)
- **Product page:** [scheduler.ferganalabs.com](https://scheduler.ferganalabs.com)
