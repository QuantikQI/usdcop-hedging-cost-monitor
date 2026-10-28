#!/usr/bin/env python3
"""calc.py - funciones puras del Monitor de costo de cobertura USDCOP.
Tasas en % anual (como las publican las fuentes). Ningun valor se estima: si falta un insumo => NO_DATA.
"""
import math
import numpy as np
import pandas as pd

NO_DATA = "NO_DATA"
TENORS = {"1M": 30, "3M": 90, "6M": 180, "12M": 360}          # d en dias, base 360
USD_AVG_COL = {"1M": "sofr_avg30", "3M": "sofr_avg90", "6M": "sofr_avg180", "12M": None}  # 12M: sin Term SOFR publico

def forward_cip(S, i_cop_pct, i_usd_pct, d):
    """F = S * (1 + i_COP*d/360) / (1 + i_USD*d/360); tasas en % nominal simple, base 360."""
    return S * (1 + i_cop_pct / 100 * d / 360) / (1 + i_usd_pct / 100 * d / 360)

def forward_points(F, S):
    """Puntos forward teoricos en COP: F - S."""
    return F - S

def hedge_cost_annualized_pct(F, S, d):
    """Costo anualizado de cobertura en %: (F/S - 1) * 360/d * 100."""
    return (F / S - 1) * 360 / d * 100

def carry_pp(i_cop_pct, i_usd_pct):
    """Carry IBR - SOFR (diferencial simple) en puntos porcentuales."""
    return i_cop_pct - i_usd_pct

def realized_vol_pct(values, window):
    """Vol realizada anualizada en %: std muestral (ddof=1) de log-retornos x sqrt(252), ultimos `window` retornos.
    values: serie de TRM (una observacion por TRM nueva). Devuelve Series alineada al indice."""
    v = pd.Series(values, dtype="float64")
    r = np.log(v / v.shift(1))
    return r.rolling(window, min_periods=window).std(ddof=1) * math.sqrt(252) * 100

def _selftest():
    # 1) paridad: tasas iguales => F = S ; puntos 0 ; costo 0
    assert abs(forward_cip(4000.0, 5.0, 5.0, 90) - 4000.0) < 1e-9
    # 2) caso manual: S=4000, COP 10%, USD 4%, d=90 => 4000*1.025/1.01 = 4059.405940...
    F = forward_cip(4000.0, 10.0, 4.0, 90)
    assert abs(F - 4059.4059405940595) < 1e-9
    assert abs(forward_points(F, 4000.0) - 59.4059405940595) < 1e-9
    assert abs(hedge_cost_annualized_pct(F, 4000.0, 90) - 5.940594059405940) < 1e-9
    assert abs(carry_pp(10.0, 4.0) - 6.0) < 1e-12
    # 3) vol: retornos +/- 1% alternados => std ~ 0.01 => ~15.87% anualizado
    s = [100.0]
    for k in range(30):
        s.append(s[-1] * (1.01 if k % 2 == 0 else 1 / 1.01))
    v21 = realized_vol_pct(s, 21).iloc[-1]
    assert abs(v21 - 0.01 * math.sqrt(252) * 100) < 0.5, v21
    return True

# ---------------------------------------------------------------- tabla diaria
def build_daily(trm_rows, ibr_long, sofr, sofrai, start, as_of):
    """trm_rows: DataFrame[desde, hasta, valor]; ibr_long: DataFrame[date, tenor, nr]; sofr: DataFrame[date, rate];
    sofrai: DataFrame[date, avg30, avg90, avg180]. Devuelve DataFrame diario (fechas habiles IBR) start..as_of."""
    trm_rows = trm_rows.sort_values("desde").reset_index(drop=True)
    trm_rows = trm_rows[trm_rows["desde"] <= as_of].copy()
    trm_rows["vol21"] = realized_vol_pct(trm_rows["valor"], 21)
    trm_rows["vol63"] = realized_vol_pct(trm_rows["valor"], 63)

    ibr = ibr_long.pivot(index="date", columns="tenor", values="nr").sort_index()
    ibr.columns = ["ibr_" + c.lower() for c in ibr.columns]
    ibr = ibr.reset_index().rename(columns={"date": "fecha"})
    ibr = ibr[(ibr["fecha"] >= start) & (ibr["fecha"] <= as_of)].sort_values("fecha")

    d = pd.merge_asof(ibr, trm_rows.rename(columns={"desde": "fecha"}), on="fecha", direction="backward")
    d.loc[d["hasta"] < d["fecha"], ["valor", "vol21", "vol63"]] = np.nan     # TRM fuera de vigencia => sin dato
    d = d.rename(columns={"valor": "trm"}).drop(columns=["hasta"])

    so = sofr.sort_values("date").rename(columns={"date": "sofr_on_fecha", "rate": "sofr_on"})
    d = pd.merge_asof(d, so, left_on="fecha", right_on="sofr_on_fecha", direction="backward",
                      allow_exact_matches=False, tolerance=pd.Timedelta(days=7))       # SOFR ON t-1 publicado en t
    sa = sofrai.sort_values("date").rename(columns={"date": "sofr_avg_fecha", "avg30": "sofr_avg30",
                                                    "avg90": "sofr_avg90", "avg180": "sofr_avg180"})
    d = pd.merge_asof(d, sa, left_on="fecha", right_on="sofr_avg_fecha", direction="backward",
                      tolerance=pd.Timedelta(days=7))
    d = d.dropna(subset=["trm"]).reset_index(drop=True)

    for tn, days in TENORS.items():
        t = tn.lower()
        icol = f"ibr_{t}"
        ucol = USD_AVG_COL[tn]
        if ucol is None:
            for c in (f"f_{t}", f"puntos_{t}", f"costo_anual_{t}", f"carry_{t}"):
                d[c] = NO_DATA
            continue
        F = forward_cip(d["trm"], d[icol], d[ucol], days)
        d[f"f_{t}"] = F
        d[f"puntos_{t}"] = forward_points(F, d["trm"])
        d[f"costo_anual_{t}"] = hedge_cost_annualized_pct(F, d["trm"], days)
        d[f"carry_{t}"] = carry_pp(d[icol], d[ucol])
    d["carry_on"] = carry_pp(d["ibr_on"], d["sofr_on"])
    d["fecha"] = d["fecha"].dt.strftime("%Y-%m-%d")
    for c in ("sofr_on_fecha", "sofr_avg_fecha"):
        d[c] = pd.to_datetime(d[c]).dt.strftime("%Y-%m-%d")
    cols = (["fecha", "trm", "ibr_on", "ibr_1m", "ibr_3m", "ibr_6m", "ibr_12m", "sofr_on", "sofr_on_fecha",
             "sofr_avg30", "sofr_avg90", "sofr_avg180", "sofr_avg_fecha"]
            + [f"{p}_{t}" for t in ("1m", "3m", "6m", "12m") for p in ("f", "puntos", "costo_anual", "carry")]
            + ["carry_on", "vol21", "vol63"])
    return d[cols]

def monthly_last_bd(daily, n_months=24):
    """Ultimo dia habil (ultima fecha disponible) de cada mes; ultimos n_months meses."""
    x = daily.copy()
    x["mes"] = x["fecha"].str[:7]
    last = x.groupby("mes", as_index=False).tail(1)
    return last.tail(n_months).drop(columns=["mes"]).reset_index(drop=True)

if __name__ == "__main__":
    print("selftest:", _selftest())
