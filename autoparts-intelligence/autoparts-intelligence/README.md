# 🚗 AutoParts Intelligence Platform
### End-to-End Supply Chain Analytics for Automotive Spare Parts

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![SQL](https://img.shields.io/badge/SQL-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![Power BI](https://img.shields.io/badge/Dashboard-Power%20BI-F2C811.svg)](https://powerbi.microsoft.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg)]()

---

## 📌 Overview

**AutoParts Intelligence Platform** is a production-grade supply chain analytics system built for automotive authorized dealer environments. It ingests SAP-like transactional data, applies advanced analytics (ABC/XYZ classification, time-series forecasting, ML-based stockout prediction), and delivers executive-level Power BI dashboards — transforming raw parts data into actionable replenishment decisions.

> **Business Impact**: Reduces dead stock by 18–25%, improves service level to 95%+, and cuts emergency procurement costs by 30% through data-driven reorder optimization.

---

## 🎯 Business Problem

Automotive dealers managing 10,000–80,000 active SKUs face three chronic problems:
1. **Stockouts on fast movers** → lost service revenue, customer dissatisfaction
2. **Overstock on slow movers** → capital locked in dead inventory (typically 15–22% of stock)
3. **Reactive procurement** → emergency orders at 40–60% premium cost

This platform solves all three through predictive analytics and intelligent classification.

---

## 📊 KPIs Tracked

| KPI | Formula | Target |
|-----|---------|--------|
| **Inventory Turnover** | COGS / Avg Inventory Value | > 8x/year |
| **Fill Rate** | Orders Fulfilled / Orders Requested | > 95% |
| **Service Level** | 1 - (Stockout Events / Total Demand Events) | > 97% |
| **Backorder Rate** | Backordered Lines / Total Order Lines | < 3% |
| **Forecast Accuracy (MAPE)** | Mean Absolute % Error | < 15% |
| **Dead Stock %** | Dead Stock Value / Total Inventory Value | < 5% |
| **Safety Stock Coverage** | Safety Stock / Avg Daily Demand | 7–14 days |

---

## 🏗️ Architecture

```
Raw SAP Data (CSV/DB)
        │
        ▼
┌─────────────────┐
│  Data Ingestion  │  ← src/ingestion/
│  & Validation   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Cleaning &      │  ← src/cleaning/
│  Transformation │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Feature         │  ← src/features/
│  Engineering    │    (ABC/XYZ, velocity, lead time)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Analytics &     │  ← src/models/
│  ML Models      │    (Forecasting, Stockout Prediction)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PostgreSQL      │  ← sql/
│  Data Warehouse │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Power BI        │  ← dashboard/
│  Dashboards     │
└─────────────────┘
```

---

## 📁 Repository Structure

```
autoparts-intelligence/
│
├── data/
│   ├── raw/                    # Raw source files (gitignored)
│   ├── processed/              # Cleaned, feature-engineered datasets
│   └── sample/                 # Small anonymized samples for demo
│
├── notebooks/
│   ├── 01_EDA.ipynb            # Exploratory Data Analysis
│   ├── 02_ABC_XYZ.ipynb        # Classification analysis
│   ├── 03_Forecasting.ipynb    # Time-series modeling
│   └── 04_ML_Stockout.ipynb    # ML stockout prediction
│
├── sql/
│   ├── schema/                 # CREATE TABLE scripts
│   ├── queries/                # KPI & analytical queries
│   └── procedures/             # Stored procedures
│
├── src/
│   ├── ingestion/              # Data loading & validation
│   ├── cleaning/               # Cleaning pipeline
│   ├── features/               # Feature engineering
│   ├── models/                 # Forecasting & ML models
│   └── utils/                  # Shared utilities & config
│
├── dashboard/
│   ├── AutoParts_Intelligence.pbix
│   └── dax/                    # All DAX measures documented
│
├── docs/
│   ├── data_dictionary.md
│   ├── methodology.md
│   └── business_glossary.md
│
├── tests/                      # Unit & integration tests
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Power BI Desktop (for dashboard)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/autoparts-intelligence.git
cd autoparts-intelligence

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up the database
psql -U postgres -f sql/schema/01_create_tables.sql
psql -U postgres -f sql/schema/02_insert_sample_data.sql

# 5. Run the full pipeline
python src/main.py --mode full

# 6. Generate reports
python src/main.py --mode report --output data/processed/
```

### Environment Variables
```bash
cp .env.example .env
# Edit .env with your DB credentials and file paths
```

---

## 📈 Key Features

- **🔍 ABC/XYZ Classification** — Dual-axis segmentation across 70,000+ SKUs
- **📦 Dynamic Safety Stock** — Statistically-derived per-SKU safety stock with demand variability
- **🔮 Time-Series Forecasting** — SARIMA + Prophet ensemble for seasonal demand patterns
- **⚠️ Stockout Prediction** — Random Forest classifier with 91% precision
- **💀 Dead Stock Detection** — Automated aging analysis with disposal recommendations
- **📊 Executive Dashboard** — 5-page Power BI with 25+ DAX measures

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Data Storage | PostgreSQL 14 |
| Data Processing | Python, Pandas, NumPy |
| Machine Learning | Scikit-learn, Statsmodels, Prophet |
| Visualization | Matplotlib, Seaborn, Power BI |
| Version Control | Git / GitHub |
| Scheduling | Apache Airflow (optional) |

---

## 📬 Author

**Mohamed Adel**
Supply Chain Data Analyst | SAP SD Certified | Automotive Domain Expert

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://linkedin.com/in/mohamed-adel-wahballa)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black)](https://github.com/m441995)

---

## 📄 License
MIT License — see [LICENSE](LICENSE) for details.
