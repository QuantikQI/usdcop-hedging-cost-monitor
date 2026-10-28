# QA - Monitor USDCOP edicion 2026-10

as_of: **2026-10-27** - filas diarias: 504 (2024-10-01 a 2026-10-27) - generado 2026-10-27T23:30:09+00:00

## 1. Cifras titulares del mes
- Costo anualizado de cobertura 3M (CIP, IBR 3M nominal vs SOFR avg 90d): **7.90 %**
- Carry IBR 3M - SOFR avg 90d: **7.97 pp**
- Volatilidad realizada TRM 21 dias: **11.83 %**

Insumos del ultimo dia: TRM 3157.94; IBR 3M 11.735; SOFR avg90 3.76556 (publicado 2026-10-27).

## 2. Comparacion de la TRM del ultimo dia con superfinanciera.gov.co
- Consulta (WebFetch, 2026-10-27) de https://www.superfinanciera.gov.co/publicaciones/60819/trm/ : **la pagina NO muestra cifras de TRM** (solo descripcion, ultima modificacion 23/09/2026 y enlaces a un reporte PowerBI, al calendario de publicacion y al "Historico de la TRM" en datos.gov.co). Por tanto **no fue posible comparar el valor del ultimo dia contra la pagina de la SFC**; el PowerBI es dinamico y no se pudo leer.
- Sustituto verificable: el "Historico de la TRM" que enlaza la propia SFC es el dataset datos.gov.co `32sa-8pi3` (el usado aqui). TRM vigente 2026-10-27 en el dataset = **3157.94 COP/USD**. El contraste independiente con el SDMX del Banco de la Republica (seccion 3) coincide al centavo. Nota: el dataset ya trae una fila con vigencia 2026-10-28 (3148.02), excluida por ser posterior al as_of.
- Pendiente para el humano: contraste visual con el PowerBI de la SFC.


## 3. Contraste independiente TRM (datos.gov.co/SFC vs BanRep SDMX)
- Fechas comparadas: 879; diferencia absoluta maxima: 0.0000 COP; fechas con diferencia > 0.005: 0.

## 4. Rango sano
- Ceros en columnas numericas: ninguno.
- Celdas vacias en columnas con dato: 0 (ninguna).
- TRM: 568 observaciones desde 2024-06-01; maximo salto diario absoluto 3.49 %; saltos > 10 %: ninguno.
- Fechas IBR sin fila en el CSV (sin TRM vigente): ninguna.

| Serie | min | max |
|---|---|---|
| trm | 3048.1200 | 4478.2100 |
| ibr_on | 8.5520 | 11.4200 |
| ibr_1m | 8.6020 | 11.5830 |
| ibr_3m | 8.6140 | 11.8330 |
| ibr_6m | 8.4510 | 12.1350 |
| ibr_12m | 7.9910 | 12.8100 |
| sofr_on | 3.5000 | 5.0500 |
| sofr_avg30 | 3.5897 | 5.1513 |
| sofr_avg90 | 3.6252 | 5.3050 |
| sofr_avg180 | 3.6577 | 5.3649 |
| costo_anual_1m | 4.1585 | 7.9383 |
| costo_anual_3m | 3.8006 | 8.1339 |
| costo_anual_6m | 3.2152 | 8.3186 |
| carry_3m | 3.8490 | 8.2076 |
| vol21 | 6.1702 | 19.2467 |
| vol63 | 8.8795 | 15.5372 |

## 5. NO_DATA declarados
- Term SOFR 12M / SOFR average 12M: CME Term SOFR es licenciado; no existe fuente publica gratuita; el NY Fed solo publica promedios 30/90/180d. Afecta f_12m, puntos_12m, costo_anual_12m, carry_12m.
- Puntos forward USDCOP observados (mercado): requiere terminal de mercado o pantalla de banco; sin fuente publica gratuita; no se intento scraping de brokers.
- Volatilidad implicita USDCOP: requiere terminal de mercado o pantalla de banco; sin fuente publica gratuita; no se intento scraping de brokers.
