# JournalFX Documentation

Comprehensive product overview for the current JournalFX beta.

**Version:** `1.0.0-beta.1`  
**Status:** Active beta  
**Platform:** Web

## Overview

JournalFX is a trading journal built for traders who want to log execution, review performance, manage rules, and sync activity from external trading platforms.

The app currently focuses on:

- trade journaling and review
- performance analytics
- notes and playbooks
- chart analysis
- automated trade sync through the desktop bridge
- AI-assisted trade and note workflows
- backtesting and strategy review

## Current App Surface

These are the main areas available in the app right now:

- Dashboard
- Log Trade
- Journal
- Analytics
- Notebook
- Desktop Bridge
- Market Grid
- Backtest Lab
- AI Assistant
- Broker
- Settings

## Getting Started

### Account Setup

1. Create or sign in with your JournalFX account.
2. Complete onboarding with:
   - trading style
   - experience level
   - initial balance
   - base currency
3. Choose an avatar and finish profile setup.

### Settings Tabs

The Settings area currently includes:

- Trading Persona
- Account Config
- Appearance
- Plan & Billing
- Security
- Help & Feedback

## Core Features

### Dashboard

- daily trade summary
- win rate and P&L snapshot
- daily bias tracking
- quick access to journaling actions
- performance widgets and recent activity
- demo-mode sample data when enabled

### Journal

- full trade history
- create, edit, and review trades
- notes, tags, and trade comments
- screenshots and attachments
- trade cleanup and deduplication tools
- offline queue support when network sync fails

### Analytics

Analytics currently includes multiple views and widgets:

- overview
- trades
- psychology
- time analysis
- advanced analytics
- comparison
- cash transactions
- reports
- session performance

Common metrics and charts include:

- win/loss breakdowns
- drawdown analysis
- equity curve
- performance by session
- performance by pair and symbol
- mindset and plan-adherence analysis
- mistake tracking
- strategy performance
- trade grade distribution
- time-based analysis
- cash transaction reporting

### Notebook

The notebook supports richer note workflows:

- create and edit notes
- pin, archive, and trash notes
- labels and search
- list-style notes
- tables and images
- note ordering and filtering
- Gemini-assisted note generation

### Charts

Charting includes:

- multi-chart layouts
- persistent chart configuration
- focus mode
- TradingView integration
- drawings and annotations
- multi-timeframe review

### Rules and Playbook

The playbook is for documenting trading logic:

- hard rules
- soft rules
- setup definitions
- setup images and phase images
- setup rating and review
- logic rules grouped by phase

### Backtest Lab

Backtest Lab is used to review strategies historically:

- saved backtest sessions
- drawing history and undo/redo
- trade replay-style analysis
- session persistence

### AI Assistant

The AI assistant supports:

- trade review and analysis
- strategy planning
- journaling help
- note generation
- voice note transcription support
- research and mentor-style workflows

### Desktop Bridge

Desktop Bridge is the MT5 sync workflow.

Current behavior:

- generates a sync key
- connects JournalFX to MT5 through the bridge
- supports live heartbeat and status monitoring
- can work with local headless MT5 data when available
- supports trade syncing into the journal

### Broker

The Broker section is currently present, but the page indicates the integration is under maintenance.

## Import, Sync, and Automation

JournalFX currently supports:

- manual trade entry
- trade import from files
- automatic journaling through the desktop bridge
- Supabase-backed real-time sync
- offline queue fallback when the app is offline

## Current Plan Limits

Plan names and limits currently defined in the app:

| Plan | Trades / Month | Notes | Images | AI Insights | Broker Sync |
| --- | ---: | ---: | ---: | --- | --- |
| Free Tier (Journaler) | 50 | 1 | 0 | No | No |
| Pro Tier (Analysts) | 500 | Unlimited | 1000 | No | No |
| Premium (Masters) | Unlimited | Unlimited | Unlimited | Yes | Yes |

Additional Premium capabilities include:

- comparison analytics
- multi-chart layouts
- voice notes
- robustness analytics
- headless MT5 support

## Keyboard Shortcuts

Current shortcuts exposed in the app include:

- `Ctrl + 1` Dashboard
- `Ctrl + 2` Journal
- `Ctrl + 3` Analytics
- `Ctrl + 4` Notes
- `T` New trade
- `N` New note
- `S` Screenshot
- `A` AI Assistant
- `D` Dashboard
- `J` Journal
- `Esc` Close modal or drawer

## Current Tech Notes

The app currently uses:

- React 19
- TypeScript
- Vite
- Supabase
- Gemini API
- TradingView widgets
- Recharts
- TipTap
- DnD Kit
- Motion
- Mermaid

## Troubleshooting

### Charts not loading

- disable `Keep Charts Alive` in Appearance
- refresh the page
- confirm no ad blocker is blocking TradingView

### Trades not syncing

- verify the sync key in JournalFX Bridge
- confirm MT5 is running
- check internet connectivity
- inspect bridge logs and heartbeat status

### Export problems

- go to Analytics > Reports
- choose the date range
- select CSV or PDF
- confirm the browser download is allowed

### Login problems

- clear cache and cookies
- try incognito mode
- reset password
- confirm Supabase config and env vars

### Performance problems

- reduce the number of open chart layouts
- disable persistent chart loading if needed
- clear browser cache
- use demo mode only for viewing sample data

## FAQ

### How do I sync trades from MT5?

Go to `Settings > Account Config`, generate a sync key, enter it in JournalFX Bridge, and enable auto-journaling.

### Can I export my data?

Yes. Use `Analytics > Reports` and export as CSV or PDF.

### Is Broker Connect working?

The current UI shows Broker Connect as under maintenance.

### Is demo mode read-only?

Yes. Demo mode is for viewing sample trades, notes, and analytics without changing live data.

## Glossary

- `P&L`: Profit and loss.
- `EA`: Expert Advisor.
- `MT5`: MetaTrader 5.
- `Sync Key`: The key used to connect the bridge to your account.
- `Daily Bias`: Your planned direction for the trading day.
- `Plan Adherence`: How closely the trade followed your rules.

## Notes

- `DOCUMENTATION.md` is now the single merged product document.
- `FEATURES.md` has been removed to avoid duplicate stale content.
- This document reflects the current app surface as implemented in the codebase.
- For a screen-by-screen and widget-by-widget breakdown, see [DEEP_DIVE.md](C:/Users/phemelo/OneDrive/Desktop/jfxbetav7/DEEP_DIVE.md).
