# USDCOP Hedging Cost Monitor · Monitor de costo de cobertura USDCOP

Monthly, reproducible index of the **theoretical cost of hedging US-dollar exposure in Colombian pesos**, published by [QuantikQI](https://quantikqi.com) (Quantik QI LLC, Delaware; operated from Bogotá). Author: Pablo Toro, Founder & Chief Quantitative Strategist.

- Edition #1 (October 2026): https://quantikqi.com/monitor/cobertura-usdcop/2026-10/ · English: https://quantikqi.com/en/monitor/usdcop-hedging-cost/2026-10/
- Landing / methodology: https://quantikqi.com/monitor/cobertura-usdcop/ · https://quantikqi.com/en/monitor/usdcop-hedging-cost/

## What it measures

For 1, 3 and 6-month tenors, from public primary sources only:

| Metric | Formula |
|---|---|
| Theoretical forward (covered interest parity) | `F = S × (1 + i_COP × d/360) / (1 + i_USD × d/360)` |
| Theoretical forward points (COP) | `F − S` |
| Annualized hedging cost (%) | `(F/S − 1) × 360/d` |
| Carry (pp) | `IBR(tenor) − SOFR average(tenor)` |
| Realized TRM volatility (%, annualized) | std of daily log-returns × √252, 21 and 63 observations |

Inputs: **S** = TRM (official COP/USD rate, calculated and certified by the Superintendencia Financiera de Colombia, published via datos.gov.co dataset `32sa-8pi3`); **i_COP** = IBR nominal rate, 360-day basis, by tenor (Banco de la República, SDMX `DF_IBR`); **i_USD** = SOFR compounded averages 30/90/180d (Federal Reserve Bank of New York). 12-month tenor is `NO_DATA` (CME Term SOFR is licensed; no free public source). Observed forward points and implied volatility are `NO_DATA` (require a market terminal).

Headline figures, as of 2026-10-27: 3M theoretical cost **7.90 %** annualized · 3M carry **7.97 pp** · 21-day realized vol **11.83 %** · TRM 3,157.94.

## Reproduce

```bash
pip install pandas requests
python run.py          # downloads sources into raw/, writes data/monitor_usdcop_YYYY-MM.csv and data/summary_YYYY-MM.json
```

`fetch.py` downloads and hashes every source (manifest in `raw/`); `calc.py` holds the pure functions with asserts; `run.py` orchestrates. Full conventions, limitations and QA in [`METODOLOGIA.md`](METODOLOGIA.md) and [`QA.md`](QA.md). Note: BanRep servers send an incomplete TLS chain; `fetch.py` fetches the intermediate certificate from the AIA URL and keeps verification on.

## Data

`data/monitor_usdcop_2026-10.csv` — 504 daily rows (2024-10-01 → 2026-10-27): TRM, IBR by tenor, SOFR and averages, theoretical forwards, points, annualized cost, carry, realized vol. `data/summary_2026-10.json` — latest values, 24-month month-end series and a `sources` block with URL, consultation timestamp and SHA-256 of each raw download.

## How to cite

QuantikQI (2026). *USDCOP Hedging Cost Monitor, October 2026 edition.* https://quantikqi.com/monitor/cobertura-usdcop/2026-10/

## License

Code: MIT. Data and charts: CC BY 4.0. Informational content; Quantik QI LLC is not a licensed FX intermediary (IMC) in Colombia and does not quote, execute or intermediate derivatives.

---

### Español (resumen)

Índice mensual y reproducible del costo teórico de cubrir una exposición en dólares con un forward USDCOP, calculado por paridad cubierta de tasas con TRM (Superintendencia Financiera), IBR (Banco de la República) y SOFR (NY Fed). Cifras de la edición de octubre 2026 (al 27-oct-2026): costo teórico 3M 7.90 % anualizado, carry IBR–SOFR 7.97 pp, volatilidad realizada 21 días 11.83 %. Metodología completa en `METODOLOGIA.md`. Contenido informativo: QuantikQI no es IMC, no cotiza ni ejecuta derivados.
