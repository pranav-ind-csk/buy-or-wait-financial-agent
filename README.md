# 💳 Buy or Wait? — AI Financial Decision Agent

[![Author](https://img.shields.io/badge/Author-Pranav%20Bisen-blue.svg)](https://github.com/pranav-ind-csk)
[![HackerRank](https://img.shields.io/badge/HackerRank-Orchestrate%20Sept%202026-brightgreen.svg)](https://www.hackerrank.com/orchestrate-september2026)
[![Python](https://img.shields.io/badge/Python-3.10%2B-yellow.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Dashboard](https://img.shields.io/badge/UI-Live%20Dashboard-orange.svg)](#-interactive-web-dashboard)

An autonomous, deterministic, multimodal financial decision engine built for the **HackerRank Orchestrate (September 2026)** hackathon challenge: *"Buy or Wait?"*.

---

## 🎯 Project Overview

When a user asks: **"Can I afford this purchase right now?"**, simply inspecting their current bank balance is insufficient. The user has upcoming rent, bills, recurring living expenses, pending payments, confirmed future salary, and critical context buried in ungrounded receipts and messages.

This project delivers an end-to-end intelligent decision engine that simulates a user's financial life over a **90-day cash-flow forecast**, deterministically enforcing safety margins to guarantee they never drop below their `minimum_balance_to_keep`.

For every purchase request, the agent determines:
1. **`amount_safe_to_pay`**: The maximum amount safe to spend *today* without violating the 90-day minimum balance constraint.
2. **`affordability_status`**: `affordable_now`, `affordable_with_plan`, `affordable_later`, or `not_affordable`.
3. **`recommended_payment_method`**: `full_payment`, `installments`, `partial_payment`, `wait`, or `not_recommended`.
4. **`payment_plan`**: Exact payment schedule (`YYYY-MM-DD:amount|...`) strictly matching supplied financing options.
5. **`earliest_date_for_full_payment`**: First future date where paying the full amount in a single payment is safe.
6. **`spending_changes_needed`**: Targeted recommendations (`stop:<id>` / `reduce_to:<id>:<amt>`) for flexible expenses.
7. **`decision_explanation`**: Clear, grounded financial rationale explaining the recommendation.

---

## 🏗️ Architecture & Core Components

```
Financial Dataset (Profiles, Events, Options, Rates) + Multimodal Media (Receipts, Messages)
                                       │
                                       ▼
                     [ Multimodal Evidence Extractor ]
               (Deterministic OCR, Salary notes, Rent revisions)
                                       │
                                       ▼
                     [ 90-Day Cash-Flow Event Resolver ]
               (Median smoothing on variable categories, recurring pay)
                                       │
                                       ▼
                     [ Deterministic Cash-Flow Simulator ]
               (Daily penny-accurate balance trajectories)
                                       │
                                       ▼
                   [ Affordability Engine & Plan Ranker ]
          (6-Tier HackerRank priority hierarchy & spending optimizer)
                                       │
                                       ▼
                      [ 7-Point Safety & Format Validator ]
               (100% schema compliance & zero invented installments)
                                       │
                                       ▼
               Root output.csv + Interactive Web Dashboard UI
```

### Module Breakdown (`code/`)

- **`models.py`**: Strongly-typed dataclasses (`FinancialProfile`, `FinancialEvent`, `PaymentOption`, `CandidatePlan`, `DecisionResult`).
- **`currency.py`**: Date-aware historical currency converter supporting INR, ZAR, IDR, USD, and EUR.
- **`data_loader.py`**: Ingests all 275 user profiles, 25,300+ events, and automatically links media images for blank amount transactions.
- **`evidence_extractor.py`**: Deterministic multilingual fact extractor parsing Indonesian/English payroll adjustments, rent increase letters, and receipt arrears.
- **`event_resolver.py`**: Projects recurring paydays and living expenses into the 90-day horizon with median amount aggregation to eliminate single-outlier distortions.
- **`simulator.py`**: Evaluates daily cash balances with intra-day credit priority (credits post before debits).
- **`affordability.py`**: Generates and ranks eligible plans following the strict 6-tier preference ordering.
- **`validator.py`**: Independent safety validator asserting 7 formal invariant rules before writing output.
- **`explainer.py`**: Generates contextual, plain-language decision explanations.
- **`main.py`**: Production runner evaluating all 250 evaluation requests.

---

## 🌐 Interactive Web Dashboard

To explore the decisions visually, a built-in dashboard is included with instant search, status filtering, and live KPI cards:

```bash
# Start the local dashboard server
python web/server.py
```
Open **[http://localhost:8080](http://localhost:8080)** in Chrome to interact with the decisions!

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+ (Standard library only — zero external pip packages required!).

### 2. Run the Full Production Pipeline
To evaluate all 250 requests in `dataset/requests.csv` and generate root `output.csv`:

```bash
python code/main.py
```
*Executes in ~5–8 seconds with 100% safety validation pass rate.*

### 3. Run the Evaluation Benchmark
To test the engine against the 25 known sample requests:

```bash
python code/evaluation/evaluate.py
```

---

## 📊 Benchmark Evaluation Results

Tested against `dataset/sample_requests.csv`:
- **Schema & Safety Validation Pass Rate**: **100.0% (25/25)**
- **Payment Method Accuracy**: **80.0% (20/25)**
- **Spending Changes Match Rate**: **88.0% (22/25)**
- **Earliest Full Date Accuracy**: **76.0% (19/25)**
- **Affordability Status Accuracy**: **76.0% (19/25)**
- **Total LLM Token Cost**: **$0.00** *(Pure deterministic execution)*

---

## 📦 Repository Structure

```text
buy-or-wait-financial-agent/
├── README.md                         # Project documentation
├── problem_statement.md              # HackerRank challenge specifications
├── AGENTS.md                         # AI agent protocol & guidelines
├── output.csv                        # Final 250 evaluation predictions
├── code.zip                          # Packaged submission archive
├── log.txt                           # Full development audit log
├── code/
│   ├── main.py                       # Main production pipeline
│   ├── models.py                     # Domain data models
│   ├── data_loader.py                # Dataset ingestion
│   ├── currency.py                   # Currency exchange converter
│   ├── evidence_extractor.py         # Multimodal receipt/message parser
│   ├── event_resolver.py             # 90-day cash flow resolver
│   ├── simulator.py                  # Deterministic balance simulator
│   ├── affordability.py              # Candidate plan generator & ranker
│   ├── explainer.py                  # Explanation generator
│   ├── validator.py                  # Safety & schema validator
│   └── evaluation/
│       ├── evaluate.py               # Benchmark evaluation suite
│       └── usage_report.md           # Token & cost report
└── web/
    ├── index.html                    # Dashboard UI
    └── server.py                     # Local HTTP server
```

---

## 👤 Author

**Pranav Bisen**  
- GitHub: [@pranav-ind-csk](https://github.com/pranav-ind-csk)  
- Email: pranavbisen2010@gmail.com
