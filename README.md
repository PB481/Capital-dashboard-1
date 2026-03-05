# Fund Administration — Client Pricing Model (Streamlit)

Interactive fee structuring engine for Irish-domiciled UCITS & AIF fund administration mandates.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run fund_admin_pricing_app.py
```

The app will open at `http://localhost:8501`.

## Tabs & Features

### 💰 Pricing Summary

Configure a single fund in the sidebar (type, AUM, services, NAV frequency, share classes, term) and see real-time pricing output including a discount waterfall, service-level fee composition, and revenue vs cost economics.

### 📈 Sensitivity Analysis

AUM sensitivity charts showing revenue growth, effective rate compression at volume tier thresholds ($500M / $2B / $5B / $15B), and the margin curve that reveals FA operating leverage at scale.

### ⚔️ Negotiation Scenarios

Side-by-side comparison of Standard, Competitive Bid, Strategic Win, and Retention pricing. Includes walk-away analysis with per-bps revenue impact, floor price (15% margin), and breakeven rate.

### 📋 Portfolio View

Blended economics across a multi-fund client relationship. Add/remove funds dynamically. Shows fund-level detail, aggregate revenue, composite margin, and AUM/revenue distribution.

## Pricing Engine Logic

|Driver             |Detail                                                         |
|-------------------|---------------------------------------------------------------|
|**Fund complexity**|×0.85 (MMF) to ×1.75 (Hedge) multiplier on base service rates  |
|**Service modules**|8 modules with base bps rates; NAV and Compliance are mandatory|
|**Volume tiers**   |0% / 8% / 15% / 22% / 30% at AUM thresholds                    |
|**NAV frequency**  |Daily (1.0×), Weekly (0.85×), Monthly (0.70×)                  |
|**Share classes**  |First 3 included; +0.08 bps per extra class × complexity       |
|**Term discount**  |3% for 3+ years, 5% for 5+ years                               |
|**Negotiation**    |0% / 12% / 20% / 25% by scenario                               |
|**Minimum fee**    |$50K annual floor                                              |
|**Cost model**     |$85K fully-loaded per FTE (Ireland-based)                      |