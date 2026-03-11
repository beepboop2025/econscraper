# EconScraper

**Source health monitoring for economic data pipelines.** Continuously validates the availability, structure, and freshness of financial data sources across Indian and global markets.

---

## Features

- **Health Checks** -- Concurrent HTTP-based monitoring of all configured data sources with status classification (healthy, warning, degraded, broken).
- **Structure Validation** -- Compares live page structure against saved baselines to detect silent breaking changes such as site redesigns, removed data tables, or altered API schemas.
- **Baseline Management** -- Captures and stores structural fingerprints (HTML selectors, table counts, section headers, JSON schemas, RSS field sets) for drift detection.
- **Data Freshness Tracking** -- Fuzzy date parsing with weekday-aware staleness detection to flag sources that have stopped updating.
- **AI-Powered Analysis** -- Sends health results to an LLM for root cause analysis, urgency assessment, and actionable fix recommendations.
- **Telegram Alerts** -- Sends automated alerts on source breakage, structural changes, or stale data via Telegram Bot API.
- **Scheduler** -- Built-in daemon with quick checks every 6 hours and deep checks daily at 07:00 IST. Optional Celery Beat integration for production deployments.
- **CLI Interface** -- Full command-line interface for manual checks, report generation, baseline updates, and report history browsing.
- **Markdown Reports** -- Generates and archives daily health reports with problem summaries and remediation guidance.

## Tech Stack

| Component       | Technology                          |
|-----------------|-------------------------------------|
| Language        | Python 3.12+                        |
| HTTP Client     | httpx (with HTTP/2 support)         |
| HTML Parsing    | BeautifulSoup 4 + lxml              |
| Async Runtime   | asyncio                             |
| Scheduling      | Built-in async scheduler / Celery Beat |
| Alerting        | Telegram Bot API                    |
| AI Analysis     | Claude (via OpenAI-compatible proxy)|
| Configuration   | YAML                                |
| Date Parsing    | python-dateutil                     |

## Getting Started

### Prerequisites

- Python 3.12 or later
- (Optional) A Telegram bot token and chat ID for alerts
- (Optional) A FRED API key for full API validation

### Installation

```bash
git clone https://github.com/your-username/econscraper.git
cd econscraper
pip install -r requirements.txt
```

### Usage

Run a full health check with structure validation:

```bash
python -m monitoring check
```

Run a quick HTTP-only reachability check:

```bash
python -m monitoring check --quick
```

Generate an AI-analyzed report and save it to `monitoring/reports/`:

```bash
python -m monitoring report
```

Update structural baselines for all sources:

```bash
python -m monitoring baseline
```

Update the baseline for a single source:

```bash
python -m monitoring baseline fred
```

View recent report history:

```bash
python -m monitoring history --days 7
python -m monitoring history --full
```

Start the background scheduler daemon:

```bash
python -m monitoring schedule
```

### Configuration

Set the following environment variables for optional features:

```bash
export FRED_API_KEY="your-fred-api-key"
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
```

Alert behavior is configured in `config/alerts.yaml`.

## Monitored Sources

### Indian Financial Markets

| Source           | Type          | What is Checked                                      |
|------------------|---------------|------------------------------------------------------|
| RBI DBIE         | Government    | Weekly Statistical Supplement availability, data dates |
| RBI Circulars    | Government    | Press releases and notification freshness            |
| NSE India        | Exchange      | Market data page, FII/DII data sections              |
| CCIL             | Clearing House| FBIL reference rates, rate publication dates         |
| SEBI             | Regulator     | Circulars listing page, circular dates               |
| data.gov.in      | Government    | Open data catalog availability                       |

### Global Sources

| Source           | Type          | What is Checked                                      |
|------------------|---------------|------------------------------------------------------|
| FRED API         | Central Bank  | API availability, JSON schema validation, deprecation headers |

### RSS Feeds

| Feed                | Publisher            |
|---------------------|----------------------|
| Reuters Business    | Google News (India)  |
| ET Economy          | Economic Times       |
| Livemint Economy    | Livemint             |
| Business Standard   | Business Standard    |
| Moneycontrol        | Moneycontrol         |

Each RSS feed is validated for XML structure, required fields (title, link, date), entry count, and publication freshness.

## Project Structure

```
econscraper/
  config/
    alerts.yaml              # Alert channel and schedule configuration
  monitoring/
    __init__.py
    __main__.py              # Entry point for python -m monitoring
    source_health_checker.py # Core health check logic for all sources
    structure_validator.py   # Baseline fingerprinting and drift detection
    ai_change_detector.py    # LLM-powered change analysis
    alert_sender.py          # Telegram notification delivery
    health_scheduler.py      # Async scheduler and Celery Beat integration
    cli.py                   # Command-line interface
    baselines/               # Stored structural fingerprints (JSON)
    reports/                 # Archived daily health reports (Markdown)
  requirements.txt
```

## License

This project is licensed under the [MIT License](LICENSE).
