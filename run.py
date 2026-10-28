#!/usr/bin/env python3
"""run.py - orquesta fetch -> calc -> outputs (CSV, JSON, QA.md). Uso: python3 -I run.py [--no-fetch]"""
import os, sys, glob, json, io, datetime as dt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import calc
import fetch

ED = "2026-10"
START = "2024-10-01"
DATA = os.path.join(HERE, "data")

def latest(prefix):
    fs = sorted(glob.glob(os.path.join(HERE, "raw", prefix + "_2*.*")))
    if not fs:
        raise FileNotFoundError(prefix)
    return fs[-1]

def load_raw():
    trm = pd.DataFrame(json.load(open(latest("trm_sfc_datosgov"))))
    trm = pd.DataFrame({"desde": pd.to_datetime(trm["vigenciadesde"]).dt.normalize(),
                        "hasta": pd.to_datetime(trm["vigenciahasta"]).dt.normalize(),
                        "valor": trm["valor"].astype(float)})
    ibr = pd.read_csv(latest("ibr_banrep_sdmx"))
    ibr = ibr[ibr["UNIT_MEASURE"] == "NR"]
    tmap = {"IRIBRM00": "ON", "IRIBRM01": "1M", "IRIBRM03": "3M", "IRIBRM06": "6M", "IRIBRM12": "12M"}
    ibr_long = pd.DataFrame({"date": pd.to_datetime(ibr["TIME_PERIOD"]), "tenor": ibr["MEASURE"].map(tmap),
                             "nr": ibr["OBS_VALUE"].astype(float)})
    assert ibr_long["tenor"].notna().all()
    sofr = pd.DataFrame(json.load(open(latest("sofr_nyfed")))["refRates"])
    sofr = pd.DataFrame({"date": pd.to_datetime(sofr["effectiveDate"]), "rate": sofr["percentRate"].astype(float)})
    sai = pd.DataFrame(json.load(open(latest("sofrai_nyfed")))["refRates"])
    sai = pd.DataFrame({"date": pd.to_datetime(sai["effectiveDate"]), "avg30": sai["average30day"].astype(float),
                        "avg90": sai["average90day"].astype(float), "avg180": sai["average180day"].astype(float)})
    trm_x = pd.read_csv(latest("trm_banrep_sdmx"))[["TIME_PERIOD", "OBS_VALUE"]]
    trm_x["TIME_PERIOD"] = pd.to_datetime(trm_x["TIME_PERIOD"])
    return trm, ibr_long, sofr, sai, trm_x

def clean(v):
    if isinstance(v, (float, np.floating)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    return v

def rec(row):
    return {k: clean(v) for k, v in row.items()}

def main():
    calc._selftest()
    if "--no-fetch" not in sys.argv:
        fetch.main()
    trm, ibr_long, sofr, sai, trm_x = load_raw()
    man = json.load(open(sorted(glob.glob(os.path.join(HERE, "raw", "manifest_*.json")))[-1]))

    last_candidates = [trm[trm["desde"] <= pd.Timestamp(fetch.END)]["desde"].max(),
                       ibr_long["date"].max(), sai["date"].max()]
    as_of = min(last_candidates)
    daily = calc.build_daily(trm, ibr_long, sofr, sai, pd.Timestamp(START), as_of)
    os.makedirs(DATA, exist_ok=True)
    csvp = os.path.join(DATA, f"monitor_usdcop_{ED}.csv")
    daily.to_csv(csvp, index=False, float_format="%.6f")
    monthly = calc.monthly_last_bd(daily, 24)
    last = daily.iloc[-1]

    # ---- QA
    qa = {}
    num = daily.drop(columns=["fecha", "sofr_on_fecha", "sofr_avg_fecha"]).replace(calc.NO_DATA, np.nan).astype(float)
    qa["filas"] = int(len(daily)); qa["fecha_min"] = daily["fecha"].iloc[0]; qa["fecha_max"] = daily["fecha"].iloc[-1]
    qa["celdas_nan_en_columnas_con_dato"] = {c: int(num[c].isna().sum()) for c in num.columns
                                             if not c.endswith("_12m") or c == "ibr_12m"}
    qa["ceros"] = {c: int((num[c] == 0).sum()) for c in num.columns if (num[c] == 0).any()}
    qa["rangos"] = {c: [float(num[c].min()), float(num[c].max())] for c in
                    ["trm", "ibr_on", "ibr_1m", "ibr_3m", "ibr_6m", "ibr_12m", "sofr_on", "sofr_avg30", "sofr_avg90",
                     "sofr_avg180", "costo_anual_1m", "costo_anual_3m", "costo_anual_6m", "carry_3m", "vol21", "vol63"]}
    t = trm[trm["desde"] <= as_of].sort_values("desde").reset_index(drop=True)
    ret = t["valor"].pct_change()
    big = t[ret.abs() > 0.10]
    qa["trm_saltos_gt10pct"] = [{"desde": d.strftime("%Y-%m-%d"), "ret": float(r)} for d, r in zip(big["desde"], ret[big.index])]
    qa["trm_max_abs_ret_diario_pct"] = float(ret.abs().max() * 100)
    qa["trm_n_observaciones"] = int(len(t)); qa["trm_primera"] = t["desde"].iloc[0].strftime("%Y-%m-%d")
    # contraste TRM SFC vs BanRep SDMX (dia de vigencia)
    exp = []
    for _, r in t.iterrows():
        for dd in pd.date_range(r["desde"], min(r["hasta"], as_of)):
            exp.append((dd, r["valor"]))
    e = pd.DataFrame(exp, columns=["d", "v"]).drop_duplicates("d", keep="last")
    m = e.merge(trm_x, left_on="d", right_on="TIME_PERIOD", how="inner")
    qa["trm_contraste_banrep"] = {"fechas_comparadas": int(len(m)),
                                  "max_dif_abs": float((m["v"] - m["OBS_VALUE"]).abs().max()),
                                  "n_dif_gt_0.005": int(((m["v"] - m["OBS_VALUE"]).abs() > 0.005).sum())}
    ibr_dates = set(ibr_long["date"]); got = set(pd.to_datetime(daily["fecha"]))
    qa["fechas_ibr_sin_fila"] = sorted(d.strftime("%Y-%m-%d") for d in ibr_dates if pd.Timestamp(START) <= d <= as_of and d not in got)
    head = {"costo_anual_3m_pct": float(last["costo_anual_3m"]), "carry_3m_pp": float(last["carry_3m"]),
            "vol21_pct": float(last["vol21"])}
    qa["titulares"] = head

    # ---- summary
    def lv(cols): return {c: clean(last[c]) if last[c] != calc.NO_DATA else calc.NO_DATA for c in cols}
    latest_vals = lv([c for c in daily.columns])
    nodata = [
        {"serie": "Term SOFR 12M / SOFR average 12M", "valor": "NO_DATA", "razon": "CME Term SOFR es licenciado; no existe fuente publica gratuita; el NY Fed solo publica promedios 30/90/180d. Afecta f_12m, puntos_12m, costo_anual_12m, carry_12m."},
        {"serie": "Puntos forward USDCOP observados (mercado)", "valor": "NO_DATA", "razon": "requiere terminal de mercado o pantalla de banco; sin fuente publica gratuita; no se intento scraping de brokers."},
        {"serie": "Volatilidad implicita USDCOP", "valor": "NO_DATA", "razon": "requiere terminal de mercado o pantalla de banco; sin fuente publica gratuita; no se intento scraping de brokers."},
    ]
    summary = {
        "edicion": ED, "as_of": daily["fecha"].iloc[-1],
        "generado_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "unidades": {"trm": "COP/USD", "ibr_*": "% nominal base 360", "sofr_*": "% anual ACT/360 (promedios compuestos hacia atras)",
                     "f_*": "COP/USD", "puntos_*": "COP", "costo_anual_*": "% anualizado = (F/S-1)*360/d", "carry_*": "pp (IBR - SOFR average)",
                     "vol21/vol63": "% anualizado, std log-retornos TRM x sqrt(252)"},
        "ultimo_dia": latest_vals,
        "titulares": head,
        "serie_mensual_24m": [rec(r) for _, r in monthly.iterrows()],
        "no_data": nodata,
        "sources": [{"serie": m_.get("serie"), "url": m_.get("url"), "fecha_consulta": m_.get("fecha_consulta"),
                     "convencion": m_.get("convencion", m_.get("nota")), "filas_descargadas": m_.get("filas_descargadas"),
                     "archivo_raw": m_.get("archivo"), "sha256": m_.get("sha256"), "status": m_.get("status")} for m_ in man],
    }
    with open(os.path.join(DATA, f"summary_{ED}.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA, f"qa_checks_{ED}.json"), "w") as f:
        json.dump(qa, f, ensure_ascii=False, indent=2)
    write_qa(qa, summary, last)
    print(json.dumps({"as_of": summary["as_of"], "titulares": head, "filas": qa["filas"]}, indent=1))

def write_qa(qa, summary, last):
    manual = ""
    mp = os.path.join(HERE, "qa_manual_superfinanciera.md")
    if os.path.exists(mp):
        manual = open(mp).read()
    h = qa["titulares"]
    L = [f"# QA - Monitor USDCOP edicion {ED}", "",
         f"as_of: **{summary['as_of']}** - filas diarias: {qa['filas']} ({qa['fecha_min']} a {qa['fecha_max']}) - generado {summary['generado_utc']}", "",
         "## 1. Cifras titulares del mes",
         f"- Costo anualizado de cobertura 3M (CIP, IBR 3M nominal vs SOFR avg 90d): **{h['costo_anual_3m_pct']:.2f} %**",
         f"- Carry IBR 3M - SOFR avg 90d: **{h['carry_3m_pp']:.2f} pp**",
         f"- Volatilidad realizada TRM 21 dias: **{h['vol21_pct']:.2f} %**", "",
         f"Insumos del ultimo dia: TRM {last['trm']:.2f}; IBR 3M {last['ibr_3m']:.3f}; SOFR avg90 {last['sofr_avg90']:.5f} (publicado {last['sofr_avg_fecha']}).", "",
         "## 2. Comparacion de la TRM del ultimo dia con superfinanciera.gov.co", manual or "_Pendiente: revisar manualmente._", "",
         "## 3. Contraste independiente TRM (datos.gov.co/SFC vs BanRep SDMX)",
         f"- Fechas comparadas: {qa['trm_contraste_banrep']['fechas_comparadas']}; diferencia absoluta maxima: {qa['trm_contraste_banrep']['max_dif_abs']:.4f} COP; fechas con diferencia > 0.005: {qa['trm_contraste_banrep']['n_dif_gt_0.005']}.", "",
         "## 4. Rango sano",
         f"- Ceros en columnas numericas: {qa['ceros'] if qa['ceros'] else 'ninguno'}.",
         f"- Celdas vacias en columnas con dato: {sum(qa['celdas_nan_en_columnas_con_dato'].values())} ({'ninguna' if sum(qa['celdas_nan_en_columnas_con_dato'].values())==0 else qa['celdas_nan_en_columnas_con_dato']}).",
         f"- TRM: {qa['trm_n_observaciones']} observaciones desde {qa['trm_primera']}; maximo salto diario absoluto {qa['trm_max_abs_ret_diario_pct']:.2f} %; saltos > 10 %: {qa['trm_saltos_gt10pct'] if qa['trm_saltos_gt10pct'] else 'ninguno'}.",
         f"- Fechas IBR sin fila en el CSV (sin TRM vigente): {qa['fechas_ibr_sin_fila'] if qa['fechas_ibr_sin_fila'] else 'ninguna'}.", "",
         "| Serie | min | max |", "|---|---|---|"]
    for k, (a, b) in qa["rangos"].items():
        L.append(f"| {k} | {a:.4f} | {b:.4f} |")
    L += ["", "## 5. NO_DATA declarados"] + [f"- {n['serie']}: {n['razon']}" for n in summary["no_data"]]
    open(os.path.join(HERE, "QA.md"), "w").write("\n".join(L) + "\n")

if __name__ == "__main__":
    main()
