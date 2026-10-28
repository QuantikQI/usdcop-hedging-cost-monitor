#!/usr/bin/env python3
"""fetch.py - descarga series primarias publicas y las guarda en raw/ con timestamp.
Regla D019: nada se estima; cada descarga queda en raw/manifest_<ts>.json con URL exacta,
fecha_consulta (UTC), filas y sha256. Si una descarga falla se registra status=ERROR/NO_DATA.
"""
import os, sys, json, hashlib, datetime as dt, ssl
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
START = "2024-06-01"          # holgura para ventanas de vol (>=63 obs antes de 2024-10-01)
END = os.environ.get("MONITOR_END", "2026-10-27")
UA = {"User-Agent": "Mozilla/5.0 (QuantikQI monitor)"}
BASE_CA = os.environ.get("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
# Intermedio faltante en la cadena que sirven suameca/totoro.banrep.gov.co (URL AIA del certificado hoja)
AIA_INTERMEDIATE = "http://cacerts.digicert.com/GeoTrustEVRSACAG2.crt"

def _ts():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def bundle_plus():
    """Bundle = CA del proxy + intermedio AIA. Mantiene verificacion TLS activa."""
    p = os.path.join(RAW, "ca_bundle_plus.pem")
    if not os.path.exists(p):
        r = requests.get(AIA_INTERMEDIATE, timeout=30, verify=BASE_CA, headers=UA)
        r.raise_for_status()
        der = r.content
        pem = ssl.DER_cert_to_PEM_cert(der) if not der.startswith(b"-----") else der.decode()
        with open(BASE_CA) as f:
            base = f.read()
        with open(p, "w") as f:
            f.write(base + "\n" + pem)
    return p

def get(url, **kw):
    """GET con verificacion TLS; si falla la cadena, reintenta con bundle_plus (nunca verify=False)."""
    try:
        return requests.get(url, timeout=90, verify=BASE_CA, headers=UA, **kw)
    except requests.exceptions.SSLError:
        return requests.get(url, timeout=90, verify=bundle_plus(), headers=UA, **kw)

def save(name, ext, content, url, serie, convencion, nrows, manifest, status="OK", note=""):
    ts = _ts()
    fn = f"{name}_{ts}.{ext}"
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    with open(os.path.join(RAW, fn), "wb") as f:
        f.write(data)
    manifest.append({"serie": serie, "archivo": "raw/" + fn, "url": url,
                     "fecha_consulta": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                     "convencion": convencion, "filas_descargadas": nrows,
                     "sha256": hashlib.sha256(data).hexdigest(), "status": status, "nota": note})

def main():
    os.makedirs(RAW, exist_ok=True)
    man = []
    # 1) TRM - Superfinanciera via datos.gov.co (Socrata 32sa-8pi3)
    u = ("https://www.datos.gov.co/resource/32sa-8pi3.json?$limit=50000&$order=vigenciadesde"
         f"&$where=vigenciadesde>='{START}'")
    r = get(u); r.raise_for_status()
    n = len(r.json())
    save("trm_sfc_datosgov", "json", r.content, u, "TRM USD/COP (Superfinanciera, datos.gov.co 32sa-8pi3)",
         "COP por USD; cada fila = TRM vigente desde/hasta (fines de semana y festivos en una sola fila)", n, man)
    # TRM contraste independiente (BanRep SDMX DF_TRM) - solo para QA
    u = (f"https://totoro.banrep.gov.co/sdmx/rest/data/BANREP.CIE,DF_TRM/?startPeriod={START}&endPeriod=2026-12-31&format=csv")
    r = get(u); r.raise_for_status()
    save("trm_banrep_sdmx", "csv", r.content, u, "TRM USD/COP contraste (BanRep SDMX DF_TRM)",
         "COP por USD; fecha = dia de vigencia", max(0, len(r.text.strip().splitlines()) - 1), man)
    meta_u = "https://www.datos.gov.co/api/views/32sa-8pi3.json"
    r = get(meta_u); r.raise_for_status()
    save("trm_sfc_datosgov_meta", "json", r.content, meta_u, "TRM metadatos dataset", "metadatos", 1, man)

    # 2) IBR - Banco de la Republica SDMX (totoro.banrep.gov.co), DF_IBR, nominal (NR) y efectiva (ER)
    u = (f"https://totoro.banrep.gov.co/sdmx/rest/data/BANREP.CIE,DF_IBR/?startPeriod={START}"
         f"&endPeriod={END}&format=csv")
    r = get(u); r.raise_for_status()
    n = max(0, len(r.text.strip().splitlines()) - 1)
    save("ibr_banrep_sdmx", "csv", r.content, u, "IBR overnight/1M/3M/6M/12M (BanRep SDMX DF_IBR)",
         "NR = tasa nominal base 360 (usada); ER = efectiva anual (solo referencia)", n, man)
    # evidencia de convencion: fichas de series 241-243 (suameca REST)
    for sid in (241, 242, 243):
        mu = ("https://suameca.banrep.gov.co/estadisticas-economicas-back/rest/"
              f"estadisticaEconomicaRestService/consultaInformacionBasicaSerie?idSerie={sid}")
        try:
            r = get(mu); r.raise_for_status()
            save(f"ibr_ficha_serie{sid}", "json", r.content, mu, f"IBR ficha SUAMECA serie {sid}", "metadatos", 1, man)
        except Exception as e:
            man.append({"serie": f"IBR ficha SUAMECA serie {sid}", "url": mu, "status": "ERROR", "nota": str(e)})

    # 3) SOFR y SOFR averages - NY Fed Markets Data API
    for key, path, nm in (("sofr", "sofr", "SOFR overnight"), ("sofrai", "sofrai", "SOFR Averages 30/90/180 + Index")):
        u = (f"https://markets.newyorkfed.org/api/rates/secured/{path}/search.json?startDate={START}&endDate={END}")
        r = get(u); r.raise_for_status()
        n = len(r.json()["refRates"])
        save(f"{key}_nyfed", "json", r.content, u, f"{nm} (NY Fed)",
             "porcentaje anual; averages = promedios compuestos hacia atras 30/90/180 dias calendario", n, man)
    mu = "https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates"
    r = get(mu); r.raise_for_status()
    save("sofr_metodologia_nyfed", "html", r.content, mu, "NY Fed metodologia SOFR averages", "texto metodologico", 1, man)

    # 4) Opcionales sin fuente publica gratuita
    man.append({"serie": "Puntos forward USDCOP observados", "status": "NO_DATA",
                "nota": "requiere terminal de mercado o pantalla de banco; sin fuente publica gratuita; no se intento scraping"})
    man.append({"serie": "Volatilidad implicita USDCOP", "status": "NO_DATA",
                "nota": "requiere terminal de mercado o pantalla de banco; sin fuente publica gratuita; no se intento scraping"})
    man.append({"serie": "Term SOFR 12M", "status": "NO_DATA",
                "nota": "CME Term SOFR es licenciado; no hay fuente publica gratuita; 12M queda NO_DATA"})
    mf = os.path.join(RAW, f"manifest_{_ts()}.json")
    with open(mf, "w") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    print("manifest:", mf)
    for m in man:
        print(m["status"], m["serie"], m.get("filas_descargadas", ""))

if __name__ == "__main__":
    main()
