# Metodologia - Monitor mensual de costo de cobertura USDCOP (edicion 2026-10)

## Fuentes (D019: primarias, descargadas en la sesion; URL y fecha de consulta en `data/summary_2026-10.json > sources` y `raw/manifest_*.json`)
| Serie | Fuente | Endpoint |
|---|---|---|
| TRM | Superfinanciera via datos.gov.co, dataset 32sa-8pi3 | https://www.datos.gov.co/resource/32sa-8pi3.json |
| IBR ON/1M/3M/6M/12M | Banco de la Republica, SDMX DF_IBR | https://totoro.banrep.gov.co/sdmx/rest/data/BANREP.CIE,DF_IBR/ |
| SOFR ON | NY Fed Markets Data API | https://markets.newyorkfed.org/api/rates/secured/sofr/search.json |
| SOFR Averages 30/90/180 | NY Fed Markets Data API | https://markets.newyorkfed.org/api/rates/secured/sofrai/search.json |
| Contraste TRM (solo QA) | BanRep SDMX DF_TRM | https://totoro.banrep.gov.co/sdmx/rest/data/BANREP.CIE,DF_TRM/ |

## Convenciones
- **TRM**: una fila por vigencia (desde/hasta); fines de semana y festivos comparten fila. El valor de la fecha t es la TRM vigente en t. Se excluyen filas con vigencia posterior al as_of.
- **IBR**: se usa la medida NR = tasa nominal, base 360 (fichas SUAMECA 241-243 confirman "Tasa nominal, base 360" para ON, 1M, 3M; 6M y 12M se toman del mismo dataflow SDMX con medida NR, sin ficha propia consultada). La efectiva anual (ER) queda en el raw, no se usa.
- **SOFR averages**: promedios compuestos de SOFR sobre 30/90/180 dias calendario, interes simple anualizado ACT/360 (metodologia NY Fed, pagina guardada en raw/). Son **promedios hacia atras**, proxy del tipo a plazo; **no son Term SOFR**. El valor de fecha t usa el average con effectiveDate <= t (publicado en t). SOFR ON usa effectiveDate < t (publicado en la manana de t). Columnas `sofr_on_fecha` y `sofr_avg_fecha` registran la fecha efectiva usada.
- **Calendario del CSV**: fechas de publicacion del IBR (habiles Colombia) con TRM vigente, desde 2024-10-01. Tolerancia de rezago SOFR: 7 dias; si no hay dato queda vacio (nunca se rellena con estimaciones).

## Formulas (d = 30, 90, 180, 360 para 1M, 3M, 6M, 12M; tasas en % / 100)
- F = S x (1 + i_COP x d/360) / (1 + i_USD x d/360); S = TRM del dia; i_COP = IBR nominal del plazo; i_USD = SOFR avg 30 / 90 / 180 para 1M / 3M / 6M.
- Puntos forward teoricos = F - S (COP).
- Costo anualizado de cobertura = (F/S - 1) x 360/d (en %). Positivo = comprar USD a plazo cuesta mas que spot.
- Carry = IBR(plazo) - SOFR avg(plazo), en puntos porcentuales; `carry_on` = IBR ON - SOFR ON.
- Vol realizada anualizada = desviacion estandar muestral (ddof=1) de log-retornos de la TRM x sqrt(252), en %, sobre las ultimas 21 y 63 observaciones. Una observacion = una TRM nueva (fila del dataset), es decir un retorno por dia habil colombiano; el lunes usa la TRM nueva vs la del viernes (fin de semana = misma fila).
- Serie mensual: ultima fecha disponible de cada mes (ultimo dia habil), ultimos 24 meses (2024-11 a 2026-10; octubre 2026 llega al as_of 2026-10-27).

## Limitaciones
1. **Proxy SOFR**: averages compuestos hacia atras, no tasas a plazo prospectivas; el costo teorico se desvia del Term SOFR real cuando la curva USD se mueve.
2. **12M = NO_DATA** (sin Term SOFR gratuito): f, puntos, costo y carry 12M no se calculan.
3. **Sin basis cross-currency**: la CIP pura ignora el basis USD/COP, primas de liquidez/credito, impuestos y costos de la contraparte; los forwards cotizados difieren del teorico.
4. **Sin puntos forward observados ni vol implicita** (NO_DATA, requieren terminal/banco): no hay validacion contra mercado.
5. **IBR nominal con interes simple base 360**: el IBR a plazos se cotiza nominal con periodicidad propia (p.ej. mes vencido); tratarlo como simple d/360 es la convencion pedida y es una aproximacion (diferencia nominal vs efectiva anual de ~0.1-0.2 pp a 12M, no relevante a 1-6M).
6. IBR y TRM son del mismo dia de publicacion; la TRM de t refleja operaciones del dia habil anterior.
7. El servidor suameca/totoro.banrep.gov.co envia la cadena TLS sin el intermedio; `fetch.py` descarga el intermedio indicado en el AIA del certificado y lo anade a un bundle local, manteniendo la verificacion TLS activa.

## Como reproducir
```bash
cd monitor/
python3 -I calc.py            # self-test (3 grupos de asserts)
python3 -I fetch.py           # solo descarga -> raw/ + raw/manifest_<ts>.json
python3 -I run.py             # descarga + calculo + data/*.csv, data/*.json, QA.md
python3 -I run.py --no-fetch  # recalcula desde el ultimo raw/
# fijar corte distinto: MONITOR_END=2026-10-27 python3 -I run.py
```
Requiere pandas y requests; usa REQUESTS_CA_BUNDLE (por defecto /root/.ccr/ca-bundle.crt).
