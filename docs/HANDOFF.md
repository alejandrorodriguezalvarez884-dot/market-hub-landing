# Estado del proyecto y cómo continuar

Última actualización: 2026-10-07.

## Qué se pidió

El usuario está montando una marca con varias herramientas de IA para inversión. Ya existen el
Earnings Radar (`decision-signal-lab`, desplegado en https://earningsradar.app/) y Fundamentals
Lab (`fundamentals-lab`, sin desplegar). Este repo es **el portal global** (2026-10-05):

- el usuario entra con Gmail;
- pone su cartera de acciones si la tiene; si no, sus acciones favoritas;
- se abre un dashboard de inicio para seguirlas;
- desde ahí accede a las dos herramientas.

Decisiones del usuario:
- Nombre del producto: **Market Hub**. El código vive en el repo `market-hub-landing`; el repo
  `market-hub` es desde el 2026-10-05 el workspace que junta todos los repos como submódulos.
- Login: **Sign in with Google verificado en la API + Firestore** en el mismo proyecto de GCP, con el
  mismo stack que las herramientas.
- Cada posición guarda **acciones y precio medio**; los favoritos son solo tickers.

## Dónde estamos

| Hecho | Pendiente |
|---|---|
| API (`src/markethub/`): login con Google (`auth.py`), sesión firmada, documento por usuario en Firestore/archivo/memoria (`users.py`), precios de FMP y buscador de la SEC (`market.py`), dashboard (`dashboard.py`), API (`api.py`) con control de `Origin` en las escrituras, borrado de cuenta y límite por IP | Probarla con Google, FMP y Firestore reales (la red del entorno bloquea FMP y la SEC) |
| 25 tests en verde, sin red: tokens buenos y malos, aislamiento entre usuarios, CSRF, cookie `HttpOnly`/`Lax`, validación del portfolio, cálculos del dashboard | |
| **Rediseño 2026-10-05: portal público + área privada.** Estética inspirada en TradingView (tema oscuro, tokens de color en `site/src/styles/global.css`: `page`, `panel`, `line`, `ink`, `muted`, `accent`, `up`, `down`), gráficos con Lightweight Charts de TradingView (Apache-2.0, logo de atribución activo y crédito en el pie). **Público** (`components/Site.astro`, con cinta de cotizaciones y buscador): portada estilo Morningstar (gráfico de índices, noticias, sectores, movers, panel de mercados), `/markets/`, `/news/`, `/quote/?t=` (gráfico de velas o línea, cifras clave, rentabilidades, herramientas, "Add to watchlist"), `/tools/`, `/privacy/`. **Privado** (`components/App.astro`, barra lateral, "Private area"): `/dashboard/`, `/portfolio/`, `/account/`. El login pasa a `/signin/`. Revisada en Chromium a 1366 y 390 px con Google y FMP simulados, sin desbordes | Revisarla con el botón real de Google |
| **Datos reales en el portal público (2026-10-05)**: `src/markethub/live.py` sirve la portada, `/markets/`, los gráficos y la ficha de valor con FMP, con la misma forma que `sample.py`. Índices, materias primas, divisas y cripto en una llamada de cotizaciones; tipos (`treasury-rates`), sectores (`sector-performance-snapshot`), movers (`biggest-gainers/losers`, `most-actives`), gráficos diarios (`historical-price-eod/full`) e intradía (`historical-chart/5min` y `30min`). Caché en memoria: el resumen cada `PUBLIC_MARKETS_TTL_SECONDS` (15 min por defecto), el diario 6 h, el intradía 5 min. Cada parte cae por su cuenta: si el plan no la da, se sirve la última buena o la de ejemplo, y el panel lleva la marca "Sample"; sin intradía el gráfico pasa a 1M. Los titulares siguen siendo de ejemplo. `httpx` ya no registra URLs (llevaban la clave de FMP) | **Lo que da el plan de FMP del usuario** (probado en producción el 2026-10-05 con un Cloud Build que pidió la web): divisas, cripto, `treasury-rates`, sectores, movers, cotización y perfil de acciones y cierres diarios (`historical-price-eod/*`) **sí**; cotización de índices (`^GSPC`…) y materias primas (`GCUSD`…) **no**, así que su precio y cambio del día salen de los dos últimos cierres (`PUBLIC_CLOSES_TTL_SECONDS`, 1 h); intradía (`historical-chart/*`) **no**, y el gráfico abre en 1M. Movers por debajo de 5 $ fuera. Cada llamada a FMP queda en el log como `fmp <ruta> -> <código>` (sin la clave): sirve para medir el gasto. Conectar un proveedor de noticias. Si el plan es el gratuito (250 llamadas/día, compartidas con el dashboard), contar llamadas en el log y subir los TTL o pasar a Starter |
| **Datos de ejemplo** en la parte pública: `src/markethub/sample.py` y `/api/public/{overview,chart,quote,news}`. Paseo aleatorio por símbolo con semilla fija (el histórico no cambia de un día a otro y crece una barra por sesión), titulares genéricos con fuentes inventadas ("Sample Wire"). Toda respuesta lleva `"sample": true` y cada página pública lo avisa con una franja | **Conectar datos reales**: sustituir `sample.py` por un proveedor (FMP para precios, un proveedor de noticias) manteniendo la forma de las respuestas; la web no cambia. Quitar entonces la franja `sample` de las páginas |
| `Makefile`, `Dockerfile`, `scripts/deploy-cloudrun.sh` (crea la base de Firestore `market-hub` en europe-west1, secretos, despliegue) | |
| **Desplegado en Cloud Run** (2026-10-05): servicio `market-hub`, europe-west1, revisión `market-hub-00002-j4g` (el rediseño, commit `e0a4af8` de `main`), https://market-hub-818229650855.europe-west1.run.app (también https://market-hub-3qwezbjyfq-ew.a.run.app). Arranca bien según los logs; secretos `market-hub-session-secret` y `market-hub-fmp-api-key` | Añadir las dos URL a los orígenes del cliente OAuth y probar el login y el dashboard en la URL pública (desde el entorno en la nube el proxy bloquea `*.run.app` y FMP). Rotar la clave de FMP, que pasó por el chat, y subirla como versión nueva del secreto |
| Cliente OAuth creado (2026-10-05): `818229650855-3dq57ote5eq25hhdmru29k3mg852jpnb.apps.googleusercontent.com`, público, en `.env.example`. `make env` (lo lanzan `install`, `api`, `serve` y `deploy`) crea `.env` con él y un `SESSION_SECRET` nuevo | Probar el login real en `localhost` (desde el entorno en la nube Google devuelve 403 en el botón y no se pudo distinguir si es el proxy o los orígenes) |
| Repo en GitHub: `alejandrorodriguezalvarez884-dot/market-hub-landing` (el código se movió aquí desde `market-hub` el 2026-10-05, con su historial); código en `main` | |
| **Login único con las herramientas (2026-10-05)**: dominio `themarkethub.app` (comprado por el usuario). La cookie de sesión lleva `Domain=themarkethub.app` (`MARKETHUB_COOKIE_DOMAIN`), solo en peticiones que llegan por ese dominio (`HostScopedCookieDomain`; en `*.run.app` queda en el host). El login acepta volver a `https://<sub>.themarkethub.app/...`. Fundamentals Lab (`fundamentals.`) y el Earnings Radar del hub (`radar.`, servicio `earnings-radar-hub`) leen esa cookie con el mismo secreto (`market-hub-session-secret`) y piden login. `earningsradar.app` sigue público y sin tocar | Verificar `themarkethub.app` en Search Console, crear los mapeos de dominio de Cloud Run y añadir los DNS; añadir `https://themarkethub.app` a los orígenes del cliente OAuth |

### Widgets de TradingView y precios de Yahoo (2026-10-07; desplegado como `market-hub-00020-fkm`)

**Desplegado el 2026-10-07 a petición del usuario**, tras comparar `.env` con el servicio (ningún
secreto recibió versión nueva; solo cambian `MARKET_DATA=yahoo` y la memoria, 1 Gi). **Yahoo
responde desde Cloud Run**: `/api/public/overview` da `source: Yahoo Finance` sin ninguna parte de
ejemplo (7 s en frío), la ficha de AAPL trae PER y BPA, y en los logs hay 34 lecturas de Yahoo
correctas y ningún fallo. Sin comprobar: My Hub con una sesión real y los widgets pintados en un
navegador (el agente no pudo ver el lienzo).

El usuario decidió dejar de depender de FMP (cuota de 250 llamadas al día y licencia de uso
personal; FMP no contestó a su petición de licencia): gráficos con los widgets gratuitos de
TradingView y, para todo lo que necesita el número en el servidor, "yfinance o la mejor opción gratis".

- **Proveedor por defecto: Yahoo Finance, con la librería `yfinance`** (`src/markethub/yahoo.py`).
  Sin clave y sin cuota diaria. `Yahoo` responde lo mismo que `market.Fmp` (`quotes`, `history`,
  `profile`) y `YahooMarkets` es `live.LiveMarkets` leyendo de él: índices, materias primas (futuros
  `GC=F`…), divisas, cripto, movers (las listas del día de Yahoo) y sectores (**por su fondo SPDR**,
  no por la media de sus acciones; **la web no lo dice, por decisión del usuario**: "US sectors" va
  sin nota). Un símbolo se lee en una sola
  petición (5 años de barras diarias, que traen la cotización), se guarda en memoria y sirve a la
  cotización, al histórico y al gráfico. Tras un rechazo de Yahoo no se pregunta en 5 minutos (1
  minuto tras cualquier otro fallo). La ficha gana PER y BPA.
- **Tipos del Tesoro: del propio Tesoro** (CSV diario de `home.treasury.gov`), no de Yahoo.
- **`MARKET_DATA`** elige el proveedor: `yahoo` (por defecto; si hay `FMP_API_KEY`, FMP queda detrás
  para My Hub con `yahoo.Fallback`) o `fmp` (todo como antes). `make deploy` ya no exige la clave de FMP.
- **Avisado al usuario, que decidió seguir**: yfinance no es una API oficial y las condiciones de
  Yahoo son de uso personal (la misma pega de licencia que el plan Starter de FMP); y Yahoo puede
  rechazar las IP de un centro de datos. Si un día Yahoo deja de responder desde Cloud Run, el resumen público cae a cifras de ejemplo marcadas y My Hub a FMP (si hay clave) o a
  ejemplo. Entonces: `MARKET_DATA=fmp` y redesplegar. Comprobado contra Yahoo desde el equipo
  Windows: resumen completo en frío en unos 12 s, ficha en 1 s, cartera de 3 valores en 1 s.
- **Memoria**: `yfinance` trae pandas y numpy. El servicio pasa de 512 Mi a **1 Gi** a petición del
  usuario (`scripts/deploy-cloudrun.sh`, y aplicado al servicio en marcha el 2026-10-07).
- **Widgets de TradingView** (`site/src/lib/tv.ts`): el gráfico de `/today/` y el de la ficha son el
  widget "Advanced Chart"; `/markets/` gana el mapa del S&P 500 ("Stock Heatmap"), cuyos bloques
  abren la ficha de aquí (`?tvwidgetsymbol=`). Los widgets **no dan los índices oficiales** ni los
  futuros: cada índice se dibuja con el contrato que lo sigue (`FOREXCOM:SPXUSD`…, tabla `SYMBOLS`),
  y **la web no lo dice, por decisión del usuario** (bajo el gráfico solo va "Chart by TradingView"). Las acciones salen **marcadas como retrasadas ("D")**. Los tipos no
  tienen widget y conservan el gráfico propio (`lwc.ts`), que también sigue en My Hub. Se evitaron
  a propósito los widgets de análisis técnico y de brokers (recomiendan). `/privacy/` lo cuenta.
- **Frases del estado del mercado** (`site/src/lib/session.ts`): nunca usaron IA; eran unas 5 por
  momento. Ahora son 136 escritas a mano y cambian cada 20 minutos, sin repetir la anterior.
- Las cifras de `/today/` (la regla) y de la ficha salen de Yahoo; el gráfico, de TradingView: pueden
  diferir un poco, sobre todo en los índices.
- 173 tests en verde (`tests/test_yahoo.py`, sin red), `astro check` y build en verde. Los widgets
  se comprobaron en local cargando con datos; el lienzo no se pudo ver pintado (la vista previa
  estaba en segundo plano). **Revisar en el navegador antes de desplegar.**

### Desplegado todo el 2026-10-07 (`market-hub-00018-n9s`)

A petición del usuario se desplegaron a la vez los cuatro servicios, desde el equipo Windows y
tras comparar cada `.env` con su servicio: el portal (`market-hub-00018-n9s`: la competición, los
menús de los filtros de noticias y el contador de visitas), Fundamentals Lab
(`fundamentals-lab-00011-kmr`), el radar del hub (`earnings-radar-hub-00008-m7x`) y el radar
público (`earnings-radar-00004-jc2`). Los tres primeros en paralelo, sin choques de IAM. Variables,
topes, memoria y escalado quedaron como estaban, y ningún secreto recibió versión nueva.
Comprobado en el portal sin sesión: las páginas nuevas responden, `/api/competitions*` pide sesión
(401), el hilo de un mes no se sirve por el punto público de Opinión (404), y el HTML lleva el
script de Cloudflare. **Sin comprobar**: la competición con una sesión real en producción (el
agente no puede iniciar sesión) y que Cloudflare empiece a contar.

### Contar visitas: Cloudflare Web Analytics (2026-10-07; desplegado)

- Las webs no llevaban analítica. `site/src/layouts/Layout.astro` carga ahora el script de
  Cloudflare Web Analytics (sin cookies), solo cuando el host es `themarkethub.app` o un
  subdominio: en local y en `*.run.app` no se carga. El token va en el HTML, no es un secreto.
  Un mismo token vale para todo el dominio, así que Fundamentals Lab y el radar del hub usan el
  mismo sitio de Cloudflare ("the market hub"); `earningsradar.app` tiene el suyo.
- El DNS está en Cloudflare en modo "solo DNS" (lo piden los mapeos de dominio de Cloud Run), por
  eso la medición automática de Cloudflare daba 0 y hace falta el script.
- `/privacy/` lo dice (qué recibe Cloudflare y qué no).
- Se mira en Cloudflare, en el menú de la cuenta: Analytics & Logs → Web Analytics. No hay
  histórico anterior al despliegue. Para lo anterior, los logs de peticiones de Cloud Run
  (`run.googleapis.com/requests`, 30 días): entre el 5 y el 7 de octubre, unas 100 visitas de
  navegador real al portal y unas 80 a `earningsradar.app`.

### Medido desde local (2026-10-05, tarde)

- **Portada y `/markets/` revisadas en el navegador** a 1366 y 375 px: valores reales, ninguna
  marca "Sample" (solo la franja de las noticias), sin desbordes. La leyenda del gráfico da el
  cambio del rango (desde la apertura de la primera barra), no el del día.
- **El plan de FMP es el gratuito** (250 llamadas/día, dicho por el usuario). Una portada en frío
  cuesta unas 29 llamadas y `/markets/` añade 18 históricos. Unas 10 de cada refresco son 402 que
  se repiten: `batch-quote` (4, el plan no lo da), `quote` de índices y materias primas (2) y los
  cierres de `^NDX`, `CLUSD`, `NGUSD` y `HGUSD` (4; los fallos no se guardan en caché). La caché
  es de memoria y el servicio escala a cero: cada arranque en frío paga la portada entera. Con
  visitas continuas son unas 90 llamadas/hora.
- **Símbolos alternativos que sí da el plan** (cierres diarios): `^IXIC` (Nasdaq Composite) y
  `BZUSD` (Brent). `PLUSD` y `^NYA` dan 402. El usuario decidió no tocar `INSTRUMENTS` por ahora.
- **Movers con `batch-quote`: descartado**, da 402.
- **Noticias en FMP con este plan:** `news/general-latest`, `news/stock-latest` y `news/stock` dan
  402; solo responde `fmp-articles` (artículos propios de FMP sobre ratings de analistas, que
  chocan con "describir, no recomendar"). Starter incluye "Financial Market News".
- **Licencia:** la página de precios de FMP dice que los planes son de uso personal y que mostrar
  o redistribuir sus datos exige un acuerdo aparte ("Data Display and Licensing Agreement").
  Pendiente de que el usuario lo aclare con FMP antes de dar a conocer el portal.

### Rediseño y ahorro de llamadas (2026-10-05, noche; desplegado)

El usuario pidió seguir en el plan gratuito de FMP y un rediseño "con menos AI slop, más intuitivo
e innovador". En `main` y **desplegado como `market-hub-00006-tvq`** con su visto bueno; `make check`
en verde (44 tests). Comprobado en producción: páginas, resumen con datos reales, ficha del
S&P 500 y `/news/` ya en 404.

- **Identidad nueva** (`site/src/styles/global.css`): ya no es el tema de TradingView. Página casi
  negra, texto blanco cálido, IBM Plex Sans y Plex Mono para las cifras. **Sin color de marca: el
  verde y el rojo solo significan subida y bajada**; lo seleccionado y los botones van en el color
  del texto. Sin cajas: cada sección es una regla fina y un título (`.sec`). Logo nuevo (una línea
  de cero y una marca a su derecha).
- **Portada** (`pages/index.astro`): abre con una frase escrita a partir de las cifras
  (`lib/lede.ts`: "US stocks are higher. The S&P 500 is up 0.87% at…"), solo descriptiva. Debajo,
  un gráfico y **"Today, on one scale"**: todos los instrumentos en una misma regla (cero en el
  centro, a la izquierda baja, a la derecha sube; `track`, `rulerRow` en `lib/widgets.ts`). Elegir
  una fila la lleva al gráfico. Los sectores usan la misma regla. Los tipos van en puntos básicos.
- **Fuera**: la cinta de cotizaciones, las noticias de ejemplo (página `/news/`, bloque de la
  portada, titulares de la ficha y la franja naranja) y los movers de la portada (siguen en
  `/markets/`). `/api/public/news` sigue existiendo. Vuelven cuando haya un proveedor real.
- **Resto**: `/markets/`, `/quote/`, `/tools/` y `/signin/` rehechos con el mismo sistema; "/"
  enfoca el buscador. El área privada (`App.astro`, dashboard, portfolio, account) hereda colores
  y tipografía pero **no se ha revisado en el navegador** (hace falta login).
- **Ahorro de llamadas a FMP** (`market.py`, `live.py`): una llamada que el plan rechaza (402) no
  se repite en 6 h (`NotInPlan`, `REFUSED_TTL_SECONDS`); el resumen pasa a 1 h y los cierres a 6 h
  por defecto; el resumen dice `intraday: false` cuando el plan no da intradía y la web deja de
  pedir 1D; `as_of` es la hora en que se leyeron los datos, no la de la respuesta; la ficha de un
  índice o materia prima sale de los cierres diarios cuando no hay cotización (antes fallaba).
  Con cierres a 6 h, el precio de índices y materias primas puede ir hasta 6 h por detrás.
- Pendiente del rediseño: llevar `global.css`, el logo y los colores de `lwc.ts` a
  `fundamentals-lab` y `decision-signal-lab`, que siguen con el tema anterior.

### Las herramientas, como secciones del portal (2026-10-05, noche; desplegado)

El usuario pidió que las herramientas no parezcan páginas aparte. Hecho en los tres repos:

- **Una sola cabecera en los tres sitios**: logo de Market Hub y las mismas tres secciones,
  `Markets · Fundamentals · Earnings` (`components/Site.astro` aquí; `Page.astro` en las
  herramientas, con sus páginas propias en una segunda línea). El buscador de la cabecera abre la
  empresa en la sección donde estás. Las direcciones son constantes en `lib/site.ts`
  (`FUNDAMENTALS_URL`, `RADAR_URL`; se cambian con `PUBLIC_FUNDAMENTALS_URL` y `PUBLIC_RADAR_URL`).
- **Pestañas de empresa** en la ficha (`pages/quote.astro`): `Price · Fundamentals · Results
  release`, las mismas en Fundamentals Lab y en el análisis del radar, para pasar de una vista a
  otra de la misma empresa. Sustituyen al bloque "Read this company in depth". En fondos no sale
  la de resultados. Ojo: abrir "Results release" de una empresa nueva lanza una lectura del modelo
  (≈ $0.0015, dentro de los topes del radar), igual que hacía el enlace anterior.
- `/tools/` sigue existiendo, enlazada desde el pie y la portada.
- Desplegado en los tres con el visto bueno del usuario (hub, `fundamentals-lab` y `make deploy-hub`
  del radar); `earningsradar.app` no se ha tocado.

### Landing, pestaña Today y vídeo (2026-10-05, noche; desplegado como `market-hub-00007-6xh`)

- **La portada (`pages/index.astro`) es ahora una landing**: el logo, qué es Market Hub, un vídeo
  de un minuto, cada parte con su descripción, su captura y su enlace, My Hub y tres compromisos
  (describe y no recomienda; los números salen del código; tus datos son tuyos). **No pide datos
  de mercado**: visitarla no gasta llamadas a FMP.
- **Lo que era la portada vive en `/today/`** (`pages/today.astro`). La cabecera de los tres sitios
  pasa a `Today · Markets · Fundamentals · Earnings`; el área privada sigue arriba a la derecha
  ("Sign in", y con sesión "My Hub" y el avatar).
- **Gráficos de precio en velas por defecto**, con el selector `Candles · Line` (`lib/lwc.ts`).
- **Vídeo** `site/public/film.webm` (65 s, 1280×720, 5,8 MB, sin sonido, WebM/VP8) con su póster
  `film-poster.jpg`, y capturas en `site/public/shots/`. Se grabó con un script de Playwright sobre
  el Chrome del equipo (no está en el repo): el hub con las cifras públicas de producción, la
  ficha de AAPL de Fundamentals Lab y el análisis de AAPL del radar servido desde
  `radar/releases.json`. Para rehacerlo hay que volver a grabar; no hay ffmpeg completo en el
  equipo, así que no hay versión MP4 (Safari antiguo en iOS puede no reproducir WebM y verá el
  póster).
- **Cuota de FMP agotada (429)**: tras ese error no se llama al proveedor durante 15 minutos
  (`QUOTA_PAUSE_SECONDS`). El 2026-10-05 a las 18 h UTC se repitieron 209 llamadas con 429.
- 45 tests en verde. Comprobado en producción: las páginas responden, el vídeo se sirve con
  peticiones por rangos y las capturas cargan.

### Noticias, y las herramientas fuera de la cabecera pública (2026-10-06; desplegado como `market-hub-00010-s6d`)

El usuario pidió quitar las herramientas de la cabecera pública y añadir noticias que se actualicen
solas; la sección de opinión vendrá después y saldrá de las noticias.

- **Cabecera pública** (`Site.astro`): `Today · Markets · News`. `Fundamentals` y `Earnings` solo
  están en la barra lateral de My Hub (`App.astro`, grupo "Tools"). La landing sigue describiendo
  las dos herramientas en el cuerpo. La cabecera de las dos herramientas conserva sus cuatro
  secciones y gana `News`.
- **Tres capas de noticias** (`src/markethub/newsfeeds.py`, `news.py`):
  1. *Documentos oficiales*: 8-K de la SEC de las 500 mayores empresas (`NEWS_UNIVERSE`; la lista
     de la SEC viene ordenada por capitalización), Fed (solo política monetaria y anuncios; fuera
     órdenes, sanciones y regulación bancaria), BLS (empleo, IPC, IPP, JOLTS) y BEA. Cada noticia
     enlaza a su documento.
  2. *El mercado del día*, escrito por código desde `overview()`: índices, sectores y mayores
     movimientos. Tres noticias por sesión que se reescriben en el sitio (el id lleva el día). Nunca
     a partir de cifras de ejemplo.
  3. *Prensa*: titulares de feeds RSS (por defecto cuatro de CNBC, `NEWS_PRESS_FEEDS`). Solo
     titular, medio y enlace; nunca el texto. Se descartan los titulares que suenan a consejo
     (precios objetivo, "stocks to buy", subidas y bajadas de recomendación).
- **Quién escribe** (`newswriter.py`): con `ANTHROPIC_API_KEY`, Claude Haiku 4.5 escribe titular y
  resumen de cada 8-K y de los comunicados de política monetaria, solo con lo que dice el
  documento. De un 8-K lee el formulario desde su primer "Item" (ahí la empresa cuenta qué pasó) y
  después el primer anexo 99 (la nota de prensa, con las cifras); en total, los primeros 16.000
  caracteres. Solo puede descartar como "no es noticia" un 8-K que no tenga más que los apartados
  comodín 7.01 y 8.01; ese no se muestra ni se vuelve a leer. Sin clave, o si la respuesta falla o
  suena a consejo, queda el titular que escribe el código ("Apple Inc. published results").
  **Sin tope de gasto, por decisión del usuario** (el tope es el crédito de la cuenta); cada
  llamada deja en el log tokens y coste (`news written …`). Medido en producción: entre 0,2 y 0,4
  céntimos por 8-K. Si la API rechaza la clave o la cuenta, no se llama durante 15 minutos.
- **La web no dice cómo está hecha, por decisión del usuario (2026-10-06)**: pidió quitar de
  `/news/` la sección "How this page is made", la nota bajo "In the press" y la etiqueta "AI summary
  of the document" de cada noticia. La API sigue diciendo quién escribió cada una (`written_by`).
  Queda avisado de que el Reglamento europeo de IA (art. 50) pide señalar el texto generado por IA
  que informa al público salvo que una persona lo revise y asuma la responsabilidad editorial.
- **Actualización sin nada programado**: la portada de noticias es un documento (`news_state/front`
  en Firestore; `data/news/front.json` en local) y cada noticia se archiva además en `news/{id}`.
  `GET /api/public/news` lo sirve con `stale: true` si tiene más de `NEWS_TTL_SECONDS` (15 min). La
  página (`watchNews` en `lib/market.ts`) pide entonces `POST /api/public/news/refresh`, que lee
  las fuentes dentro de esa petición (tope de 30 s para empezar documentos; lo que quede se lee en
  el siguiente refresco) y vuelve a pintar. Sin visitas no hay refresco. Un refresco en marcha en
  otra instancia se respeta 3 minutos (`started_utc`).
- **Dónde salen**: `/news/` (por día, con filtro por tipo, sector, sentimiento y día, y la prensa al lado), bloque "Latest
  news" en `/today/`, "From its filings" en la ficha de valor, y "News on your stocks" en My Hub
  (`GET /api/news/mine`, las de las empresas de la cartera y los favoritos; no guarda nada nuevo).
- **Despliegue**: la clave de Anthropic sale de Secret Manager. `ANTHROPIC_SECRET` nombra el
  secreto; en producción es `ANTHROPIC_API_KEY`, el mismo que usa Fundamentals Lab, así que las
  noticias gastan de esa misma cuenta. Una clave puesta en `.env` se guarda antes en ese secreto.
- 69 tests en verde (`tests/test_news.py`, sin red), `astro check` y build en verde.
- **Comprobado en producción**: el primer refresco tardó 10 s y los siguientes 7 s (Cloud Run
  corta a los 60 s); Firestore guarda `news_state/front`; el `POST` sin cuerpo que hace el
  navegador pasa (con `curl -X POST` sin `-d ''` el frontal de Google contesta 411); `/news/`
  pinta las noticias escritas por el modelo. Las dos herramientas se redesplegaron con el enlace
  `News` (`fundamentals-lab-00005-7vw`, `earnings-radar-hub-00003-w8t`) y su configuración y sus
  topes quedaron idénticos; `earningsradar.app` no se tocó.
- **Dos fallos del modelo vistos el primer día, ya corregidos**: descartó un 8-K de AbbVie que
  rebajaba previsiones (solo había leído el anexo, una tabla; de ahí que ahora lea también el
  formulario y que no pueda descartar resultados) y deshizo mal la sigla "IPR&D" (ahora se le pide
  dejar siglas y términos como los escribe el documento). Conviene repasar de vez en cuando lo que
  escribe.
- En el equipo local del usuario (Windows) los `.env` de los tres repos se reconstruyeron desde la
  configuración de los servicios y Secret Manager. `uv` necesita ahí `UV_LINK_MODE=copy`, y el
  `launch.json` del workspace no arranca porque su `bash` es el de WSL (ver los filtros de
  noticias, 2026-10-07: hay una configuración aparte para Windows).

Pendiente:
- **Las noticias del mercado del día no han salido aún en producción**: la cuota de FMP estaba
  agotada (429) y con cifras de ejemplo no se escriben. Mirarlo un día con cuota.
- "News on your stocks" de My Hub no se ha visto en el navegador (pide login de Google); su API
  está testeada.
- **Licencia de la prensa**: los feeds de CNBC son para uso personal según sus condiciones. Se
  muestra solo titular y enlace, pero conviene revisarlo antes de dar a conocer el portal, igual
  que la licencia de FMP. `NEWS_PRESS_FEEDS=` vacío los apaga.
- GDELT se descartó: devolvió 429 en todas las pruebas. El feed de notas del Tesoro no responde.
- La landing no tiene bloque ni captura de News (el vídeo nuevo sí la enseña).

### Opinión, con comentarios (2026-10-06; desplegado como `market-hub-00013-4pm`)

El usuario pidió una pestaña de opinión: artículos generados con IA a partir de las noticias y de
otras fuentes, en un repo aparte, que se actualizan con una skill de Claude Code cuando él lo pide
("añade tantos"), y con comentarios tipo Reddit que piden login para escribir y no para leer.

- **Los artículos no se escriben aquí.** Viven en el repo `market-hub-opinion` (hermano de este en
  el workspace), un Markdown por artículo. Su skill `update-opinion` los escribe, `make check` los
  valida y `make publish` los sube a Firestore: `opinion/{slug}` y `opinion_state/front` (las
  fichas de todos, para que la lista sea una lectura). **Publicar un artículo no pide redesplegar.**
  Este servicio solo los lee (`src/markethub/opinion.py`). En local: `make preview` allí los deja
  en `data/opinion/`.
- **Web**: pestaña `Opinion` en la cabecera pública y en la navegación de My Hub; `/opinion/` (el
  más nuevo arriba, el resto a dos columnas) y `/opinion/article/?slug=` (texto, valores, fuentes
  y comentarios). El texto es un Markdown reducido que se pinta como elementos, nunca como HTML.
- **Comentarios** (`opinion_comments/{id}`): hilos con respuestas hasta seis niveles. Leer no pide
  cuenta; escribir y responder, sí (`POST /api/opinion/comments`, con el control de `Origin` de
  siempre). 2.000 caracteres, 20 por usuario y hora, 1.000 por artículo, solo texto. Cada uno borra
  los suyos; el hueco queda vacío en el hilo para que las respuestas sigan teniendo sentido.
  **Moderación**: con una cuenta de `MARKETHUB_ADMINS` (correos separados por comas; el script de
  deploy la pasa) se borra cualquiera. No hay votos ni avisos por correo.
- **Privacidad**: de quien comenta se guarda su id de cuenta (para que pueda borrar lo suyo) y el
  **nombre de pila**, que es lo único que se muestra: ni apellido, ni correo, ni foto. Borrar la
  cuenta vacía sus comentarios. Está dicho en `/privacy/` y `/account/` (que los lista y los
  incluye en la descarga). El texto de los comentarios no va a los logs.
- 76 tests en verde (`tests/test_opinion.py`). Probado en local con capturas; el flujo de comentar
  con sesión real de Google no se ha probado en el navegador.

- Desplegado y comprobado en producción: los seis artículos iniciales están publicados, la lista
  y los artículos se leen sin cuenta, y comentar sin sesión devuelve 401. `MARKETHUB_ADMINS` es
  el correo de Google del usuario. El repo `market-hub-opinion` está en GitHub y es un submódulo
  del workspace.

Pendiente:
- **Comentar con una sesión real de Google** no se ha probado en el navegador (el agente no puede
  iniciar sesión): que el usuario escriba un comentario, lo responda y lo borre.
- La landing y la película no enseñan Opinión.

### Artículos de noticias, con su tono y su sector (2026-10-06; desplegado como `market-hub-00012-w8l`)

El usuario pidió que un titular no lleve directamente a la fuente sino a un artículo propio, con
la fuente enlazada dentro, y que en la lista se vea si la noticia es bullish, bearish o neutral y
a qué sector afecta, o si es macro.

- **El modelo escribe ahora, de cada documento**: titular, resumen, **artículo** (de tres a cinco
  párrafos), **tono** (`bullish`, `bearish`, `neutral`) y **sector** (los once del portal, o
  `Macro`). También de los comunicados del BLS, del BEA y de todos los de la Fed, que antes solo
  llevaban el texto del feed. Un comunicado de una agencia es siempre `Macro`. Las tres noticias
  del mercado del día las sigue escribiendo el código: su tono sale de las cifras (el S&P 500 a
  más de una décima de cero; tres cuartos de los sectores hacia un lado) y su artículo es su
  resumen. Una noticia que el modelo no escribió no lleva tono ni sector: no se afirma nada.
- **Ojo con la regla "describir, no recomendar"**: el tono lo pidió el usuario. Al modelo se le
  dice que clasifica la noticia del documento y que no es una previsión de ningún precio; el
  filtro de consejos se aplica también al artículo. La landing sigue diciendo "no predictions".
- **Dónde vive**: el artículo solo está en el archivo (`news/{id}`); la portada de noticias, que
  se lee en cada visita, lleva lo demás. `GET /api/public/news/item?id=` devuelve una noticia
  entera. La página es `/news/article/?id=`: tono y sector, titular, resumen, artículo, valores y,
  al final, "Source" con el enlace al documento. Los titulares de `/news/`, de Today, de la ficha
  y de My Hub llevan ahí. **Los de prensa no**: de ellos solo hay el titular y siguen abriendo en
  su medio.
- El tono se dibuja con la marca del sitio: el punto a la derecha de la línea (verde), a la
  izquierda (rojo) o sobre ella.
- Coste: cada documento pide ahora unos 500 tokens de salida más; del orden de medio céntimo a un
  céntimo por noticia.

### Community en dos secciones: compartir la cartera y la competición mensual (2026-10-07; desplegado como `market-hub-00018-n9s`)

El usuario pidió que Community tenga secciones (de momento dos): compartir tu cartera, exigiendo
tenerla, y competiciones mensuales con clasificación del mes, histórico y comentarios para debatir.

- **Dos páginas, una navegación** (`communityNav` en `lib/hub.ts`, dos puertas bajo el título):
  `/community/` (compartir) y `/community/competitions/` (la competición). La barra lateral sigue
  con un solo "Community", así que los `HubNav.astro` de las herramientas no cambian.
- **Compartir** (`pages/community.astro`): abre con el bloque de compartir, en tres pasos. **Sin
  cartera no hay formulario**: solo "Add your portfolio", que lleva a `/portfolio/`. Debajo, "Where
  you stand" (solo con cartera) y el tablero de siempre.
- **La competición** (`src/markethub/competitions.py`, `pages/community/competitions.astro`):
  - *Reglas*: cada mes natural es una competición. La entrada es una cartera de **3 a 10 acciones
    individuales** (fuera fondos: los de `market.EXTRA` y lo que la ficha del proveedor marca
    `is_etf`), cada una con entre **5 % y 50 %**, en porcentajes enteros que suman 100. Se envía y se
    cambia **hasta el final del último día del mes anterior, hora de Nueva York**; después queda fija.
    Se mide del último cierre del mes anterior al último cierre de su mes, comprada al inicio y sin
    tocar, sin dividendos. Gana la mayor rentabilidad; en empate, la entrada cambiada antes. **Los
    números (3–10, 5–50) los eligió el agente**: están en `config.py` (`COMPETITION_*`).
  - *Nombre*: se juega con un nombre propio (las mismas reglas que el de compartir); no puede ser el
    de otro jugador del mes ni el que otro usa al compartir cartera. No hace falta compartir la
    cartera real para jugar: la entrada no tiene nada que ver con las posiciones.
  - *El mes en curso*: podio, gráfico "session by session" (la rentabilidad de cada cartera desde el
    cierre de partida; se eligen hasta seis líneas desde la tabla, más el S&P 500), clasificación con
    la regla de cero en el centro, y cada línea se abre a sus acciones (peso, rentabilidad y puntos
    que aporta). Se calcula **con cierres diarios, no con cotizaciones**: es la clasificación del
    último cierre, y cuesta una llamada de histórico por ticker distinto cada 6 h (más la de SPY).
  - *Tu entrada*: constructor con buscador, barra de la mezcla, deslizadores, "Equal weights" (los
    pesos se reparten solos mientras no se toquen a mano) y la lista de lo que falta para poder
    enviar. Hasta que empieza el mes nadie ve la entrada de otro: solo cuántas hay.
  - *Histórico*: el récord de todos (meses jugados, **meses ganados** y **rentabilidad media de los
    meses jugados**, mejor mes; se ordena por la columna que se pulse), tu récord, y cada mes
    terminado tal como acabó.
  - *Comentarios*: un hilo por mes (`competition-2026-11`) en el mismo almacén que los de Opinión
    (`opinion_comments`), con el mismo código de hilos (`lib/thread.ts`, que ahora usan las dos
    páginas). Solo para usuarios con sesión: el hilo público de Opinión no los sirve. Se firman con
    el nombre con el que se juega (o el de pila si aún no hay). Se escribe en el mes en curso y en
    el que está abierto.
- **Cierre de un mes, sin nada programado**: la primera visita tras acabar el mes lo liquida
  (`_settle`) y guarda `competition_results/{mes}`; desde ahí no cambia. Solo con datos reales
  (nunca con cifras de ejemplo), solo cuando ya hay un cierre del mes siguiente, y esperando hasta
  5 días a que todas las acciones tengan su último cierre.
- **Con cifras de ejemplo** (proveedor sin contestar, o `MARKETHUB_SAMPLE_MARKETS=1`) salen
  jugadores de relleno marcados "sample" en el mes y cuatro meses pasados de relleno; nada de eso
  se guarda y desaparece con datos reales. **En producción con datos reales la página estará vacía
  hasta noviembre**: octubre de 2026 no tiene inscritos (el plazo acabó el 30 de septiembre) y la
  primera competición es noviembre, con inscripción abierta hasta el 31 de octubre.
- **Datos**: `competition_entries/{mes}_{id}` (id de cuenta, nombre, acciones y pesos) y
  `competition_results/{mes}`. El id de cuenta no sale del servidor. Borrar la cuenta borra las
  entradas; en un mes ya liquidado su línea queda sin nombre ("Former member") y fuera del récord.
  Dicho en `/privacy/` y en `/account/` (que lista las entradas y las incluye en la descarga).
- **API**: `GET /api/competitions`, `PUT`/`DELETE /api/competitions/entry`,
  `GET`/`POST /api/competitions/comments`, `GET /api/competitions/mine`.
- 163 tests en verde (27 nuevos en `tests/test_competitions.py`), `astro check` y build en verde.
  **Probado en local** (cifras de ejemplo, cuenta de prueba, 1366 y 375 px): las tres vistas,
  elegir líneas del gráfico, comentar y responder, construir una entrada, que un fondo se rechaza,
  enviarla, el estado vacío, la puerta de "añade tu cartera", el hilo de un artículo de Opinión
  tras el cambio, la página de cuenta, y que borrar la cuenta se lleva entradas y comentarios.
- **Sin probar**: con datos reales de FMP y con Firestore (las consultas son por un solo campo,
  `month` o `user_id`, sin índices compuestos); la liquidación de un mes solo está probada en tests.
- **Pendiente / a decidir**: con muchos jugadores el plan gratuito de FMP no llega (una llamada de
  histórico por ticker distinto); no hay moderación de nombres más allá de los reservados; el
  ganador no recibe nada ni se anuncia; la landing y la película no enseñan la competición.

### Filtros de noticias: sector, sentimiento y día (2026-10-07; desplegado como `market-hub-00017-bx9`)

El usuario pidió filtrar las noticias por sector, por sentimiento y por fecha.

- **`/news/`** (`pages/news.astro`) tiene, bajo las pestañas de tipo: el sentimiento, que se elige
  pulsando su marca (las tres de los artículos, `toneMark` en `lib/news.ts`: Bullish, Bearish,
  Neutral; pulsar la elegida la suelta; el usuario pidió que no fuera un desplegable), y dos
  menús, `Any sector` (los sectores que tienen alguna noticia, y `Macro` al final) y
  `Any day` (los días que hay, en la hora del lector). Se combinan entre sí y con las pestañas.
  **Los menús son propios, no `<select>`**: al usuario la lista del navegador le salía blanca y
  no pegaba con la web. Son un botón y un panel con el estilo del menú de la cuenta
  (`bg-panel`, `border-line-strong`); uno abierto a la vez, se cierran al pulsar fuera o con
  Escape, y las flechas recorren las opciones. Si hace falta otro menú en la web, sale de ahí.
  (Los menús se desplegaron en `00018-n9s`.) Con algún filtro puesto salen "Clear filters" y la cuenta ("3 of 25"); sin resultados,
  "No news matches these filters.".
- **Se filtra en el navegador**, sobre lo que ya se había pedido: no hay llamadas nuevas ni gasto.
  La página pide ahora la portada entera (`limit=200`, que es `NEWS_FRONT_ITEMS`; el tope de
  `/api/public/news` sube de 100 a 200). **Lo que ya salió de la portada (más de 200 noticias
  atrás) no se puede filtrar**: está en el archivo (`news/{id}`), que la página no lee. Buscar ahí
  por fecha pediría consultas a Firestore y sus índices.
- **Lo elegido va en la dirección** (`?kind=&sector=&sentiment=&day=2026-10-06`), así que volver de
  un artículo o compartir la página lo conserva. Un valor de la dirección que ya no existe se queda
  en su desplegable y la lista sale vacía, con el botón de limpiar.
- Una noticia sin tono ni sector (las que el modelo no escribió) no entra en esos dos filtros. Los
  titulares de prensa no se filtran.
- 136 tests, `astro check` y build en verde. Probado en local a 1366 y 375 px con una copia de las
  noticias públicas de producción: combinaciones, limpiar, abrir con filtros en la dirección, sin
  desbordes.
- **Desplegado el 2026-10-07** desde el equipo Windows, tras comparar su `.env` con el servicio
  (idénticos). Comprobado en producción: `/news/` sirve el script con los filtros,
  `/api/public/news?limit=200` responde y con 201 da 422, `/api/config` sigue en
  `registration: captcha`, y el servicio conserva variables, secretos, memoria y escalado. Los
  filtros no se han pulsado en producción con un navegador, solo en local.
- **Arrancar en local en Windows**: en ese equipo `bash` es el de WSL, no Git Bash; por eso el
  `launch.json` del workspace no arrancaba. Hay una configuración `hub-sample-windows` que llama a
  Git Bash por su ruta. **No lanzar `uv` desde WSL en esta carpeta**: rehace `.venv` para Linux y
  rompe el de Windows (se arregla con `UV_LINK_MODE=copy uv sync --reinstall`).

### Estado del mercado en Today y vuelta a la portada desde My Hub (2026-10-06; desplegado)

- **Today** abre con el estado de la bolsa de EE. UU. en vez de la frase escrita con las cifras
  ("US stocks are higher. The S&P 500 is up…"), que al usuario le parecía horrible; con ella se
  fueron la fecha de encima y `lib/lede.ts`. El estado: `Closed`, `Pre-market`,
  `Open` o `After hours`, una frase con el ánimo de la hora (varias por estado, y propias para la
  primera media hora, la última hora, el fin de semana y los festivos; cambia cada hora) y lo que
  falta para la próxima campana. Se calcula en el navegador con la hora de Nueva York
  (`lib/session.ts`), sin llamar al proveedor. **Los festivos y los cierres a las 13:00 están
  escritos a mano para 2026 y 2027**: hay que añadir cada año antes de que empiece.
- **El emblema** (`components/MarketSession.astro`) es un dial de 24 horas con el logo en el
  centro: su línea, y su tallo hasta un punto en el borde, que marca la hora de Nueva York como
  una aguja. El arco grueso es la sesión, los finos el pre-market y el after hours. El punto late
  mientras se negocia.
- **En la película**, la escena de la frase (segundos 11,6 a 15,5) es ahora la del dial: la aguja
  recorre un día entero y pasa por los cuatro estados con su frase ("And where the market is,
  right now.").
- **My Hub** tiene un botón "Back to the home page" al pie de la barra lateral ("← Home" en la
  barra de pantallas estrechas), también en los `HubNav.astro` de las dos herramientas.

### Media (2026-10-06; desplegada como `market-hub-00016-gjv`)

El usuario pidió una pestaña Media con tres secciones grandes: YouTube (por listas de
reproducción, dejando claro que vendrán más), Instagram y X (las dos, para cuentas que dará más
adelante).

- **`/media/`** (`pages/media.astro`) es estática: no llama a la API ni a YouTube. Los datos están
  a mano en `lib/media.ts` (el canal, cada lista con sus vídeos y sus Shorts, cuántas listas
  vienen, y las cuentas de Instagram y X, hoy vacías). **Cada vídeo nuevo se añade ahí** cuando
  se publica (su dirección está en `the-market-hub-media`, en el `published.json` del vídeo),
  con su carátula en `site/public/media/` (la miniatura que dibuja ese repo; para un Short, un
  fotograma suyo a 540x960).
- **YouTube**: cada lista tiene un reproductor y la relación de sus vídeos; el más nuevo abre en
  el reproductor. Las carátulas son archivos nuestros: **la página no pide nada a YouTube hasta
  que se pulsa play**, y entonces carga el vídeo desde `youtube-nocookie.com`. `/privacy/` lo
  dice. Los Shorts enlazan a YouTube. Dos huecos "Another subject" dicen que vienen más listas,
  sin prometer cuáles ni cuándo.
- **Instagram y X**: la sección, su texto y unos huecos vacíos, con "Account coming soon". Al
  poner el usuario en `INSTAGRAM.handle` o `X.handle` sale el enlace a la cuenta. **Enseñar los
  posts está sin hacer**: depende de la cuenta. Instagram no deja leer los posts de una cuenta
  sin una aplicación de Meta y su token (o incrustando post a post con su script); X solo ofrece
  su widget de cronología, que carga su script y falla a menudo para quien no tiene sesión. Hay
  que decidirlo con el usuario cuando dé las cuentas, y añadirlo a `/privacy/`.
- **Navegación**: "Media" en la cabecera pública (`Site.astro`), en "Explore" de la barra de My
  Hub (`App.astro`) y en los `HubNav.astro` de `fundamentals-lab` y `decision-signal-lab`.
- **Desplegado el 2026-10-06** con el visto bueno del usuario: el portal (`market-hub-00016-gjv`)
  y Fundamentals Lab (`fundamentals-lab-00010-pnk`), desde el Mac del usuario. Comprobado en
  producción: `/media/` responde con sus tres secciones, la portada enlaza a ella, las carátulas
  se sirven, `/api/config` sigue dando `registration: captcha`, y los dos servicios conservan
  las mismas variables, topes y escalado que antes.
- **El radar del hub (`earnings-radar-hub`) no se desplegó**: sigue sin el enlace a Media en su
  barra lateral. La clave de Perplexity del `.env` de ese Mac no es la que hay en Secret Manager,
  y `make deploy-hub` la habría sustituido. Lo decide el usuario: cuál de las dos es la buena.
- **Antes de desplegar desde otra máquina, comparar su `.env` con el servicio**: el script pone
  todas las variables a partir del `.env` local. En ese Mac faltaban `MARKETHUB_ADMINS` y
  `ANTHROPIC_SECRET=ANTHROPIC_API_KEY`; sin ellas el despliegue habría dejado el portal sin
  moderadores y sin el redactor de noticias. Se copiaron del servicio a su `.env` antes de
  desplegar.
- **Comprobado en local** (`hub-sample`): la página a 1366 y 375 px sin desbordes, la pestaña
  marcada, y que al elegir un vídeo el reproductor pide su dirección de `youtube-nocookie.com`
  (las dos responden 200). Que el vídeo se reproduzca dentro de la página no se pudo ver en el
  navegador de pruebas. `make check` en verde (136 tests).

### Las herramientas, dentro de My Hub (2026-10-06; desplegado)

El usuario pidió que Fundamentals y Earnings queden integradas en el área privada, porque solo se
consultan desde ahí. En los dos repos la cabecera del portal se sustituyó por la navegación de My
Hub (`HubNav.astro`, copia de la barra lateral de `App.astro`: "Your space", "Tools" con la
herramienta marcada, "Explore", el aviso de área privada y el usuario), con la barra propia de
cada herramienta encima de la página. En `earningsradar.app` el radar sigue con su cabecera. Un
cambio en la barra lateral de `App.astro` hay que llevarlo a los `HubNav.astro` de los otros dos.

### Película nueva de la landing (2026-10-06; desplegada como `market-hub-00011-pms`)

El usuario pidió rehacer el vídeo: que no sea una demo grabada de la app, sino una pieza hecha de
cero que juegue con el logo, con sonido, y que enseñe todo lo que hace el portal. Sustituye a la
grabación con Playwright descrita más arriba.

- **Qué es**: 60 s, 1920×1080, 30 fps. Parte del logo (la línea de cero y el punto: "This is zero.
  This is a move. Left is down. Right is up.") y esa marca se convierte en cada parte: la regla de
  Today y su frase, las velas de Markets, News con su filtro, My Hub (diez segundos: el punto es
  el ojo de un candado; valor de la cartera, posiciones, su año frente al S&P 500 y las noticias
  de sus empresas) y las herramientas de IA (once segundos, **en general y sin nombrar ninguna,
  porque irán cambiando**: el punto lee un documento y responde preguntas, y luego es una
  herramienta entre varias, cada una para un trabajo, con un hueco "More to come"). Cierra en el
  logo con el nombre y "At last, all the information and all the power in your hands.". Entre
  partes, lo que hay en pantalla se recoge en el punto, que viaja. Todas las cifras son
  ilustrativas y fijas.
- **Segunda versión, a petición del usuario tras ver la primera** (le gustó el resto): cambió la
  frase final (antes "It describes. It never tells you what to buy."), dio más peso a la cartera
  propia y sustituyó las dos escenas de Fundamentals y Earnings por la general de herramientas.
- **Sonido**: sintetizado entero, sin grabaciones ni música de terceros (`film/audio.js`). Un fondo
  de acordes lento y, encima, lo que "toca" la imagen: una nota por fila de la regla (más aguda si
  sube), la gráfica sonando a la altura de sus cierres, un deslizamiento cuando el punto se mueve,
  aire cuando viaja. Imagen y sonido salen de la misma lista (`EVENTS` en `film/film.js`).
  El agente no puede oírlo: lo comprobó con números (60 s, estéreo, pico 0,89, sin saturar, fondo
  unos 6 dB por debajo de las notas). El usuario vio y oyó la primera versión y la dio por buena.
- **Cómo se hace**: `make film`. `film/render.mjs` abre el Chrome del equipo con `playwright-core`,
  la página dibuja cada fotograma en un canvas y el propio Chrome codifica (WebCodecs), así que
  sigue sin hacer falta ffmpeg. Salen `site/public/film.webm` (VP9 + Opus, 7,5 MB),
  `film.mp4` (H.264 + AAC, 6,4 MB, para los Safari que no leen WebM: ya hay versión MP4) y
  `film-poster.jpg`. `film/check.mjs` reabre los dos archivos como lo haría un navegador y deja
  hojas de contacto en `film/out/`; `node render.mjs --stills` las saca sin codificar. Abrir
  `film/film.html` con un servidor local la reproduce con sonido.
- En la landing el vídeo sigue arrancando solo y en silencio (los navegadores no dejan otra cosa);
  el sonido se activa en los controles. La nota pasa de "No sound" a "With sound".
- `film/` no se sube a Cloud Run (`.gcloudignore`, `.dockerignore`).
- **Prueba con otra música (2026-10-07; sin publicar)**: el usuario pidió probar la película con
  una música que motive y suene a progreso en vez de la actual (que oye como relajante), y que los
  movimientos la acompañen. Es un segundo montaje, **sin tocar el primero**:
  `make film CUT=progress` lo deja en `film/out/film-progress.{webm,mp4}` (no en la web).
  - **Primer intento, descartado por el usuario** ("no me gusta"): una banda a 128 pulsos con
    batería, bajo, notas cortas rápidas y campanas agudas (commit `51a251d`, `adventure*.js`). Pidió
    cambiar "las teclas, ese sonido agudo" por algo **más grave y solemne, que motive y suene a
    progreso**.
  - **Segundo intento** (`film/progress-audio.js`): grave, lento y ancho. Las cuerdas bajas marcan
    un pulso constante, **el bajo sube un escalón en cada cambio de acorde** (re, fa, si bemol, do,
    y vuelta a empezar; al final cae en fa), un tambor grande marca los compases, la orquesta crece
    por partes y desde My Hub las trompas llevan una melodía lenta. Sin platos rápidos ni caja. Las
    notas que "toca" la imagen son ahora una cuerda grave pulsada, dos octavas por debajo.
  - `film/progress.js`: no redibuja nada. **Dobla el reloj** de `film.js`: cada momento que la
    imagen marca (una fila, un titular, el comienzo de una parte) se lleva a su sitio en la rejilla
    de la música (`ANCHORS`), y entre uno y otro la película corre más o menos deprisa (entre 0,6 y
    2 veces). Encima, el cuadro entero crece un poco con cada golpe del tambor y más donde cae una
    parte, y una línea abajo lleva el punto de la primera parte a la última.
  - El agente no puede oírlo. Medido por compases: pico 0,89, unos −15 dB de media, graves unos 5 dB
    por debajo del total y agudos unos 16 (oscuro, como se pidió).
  - Si se adopta: pesa el doble que la actual (16 MB en WebM, 13 en MP4), porque el cuadro se mueve
    entero en cada pulso; habría que bajar el `bitrate` en `film/page.js` o suavizar ese movimiento.

### Desplegado el 2026-10-06, y despliegues en paralelo

- **En producción**: My Hub nuevo (Overview, Analysis, Community), el login con email y contraseña y
  el captcha del registro. Revisiones `market-hub-00015-gj9`, `fundamentals-lab-00009-94c` y
  `earnings-radar-hub-00007-rdt`. La configuración de las dos herramientas (variables, topes,
  escalado) quedó idéntica a la de antes; en el portal solo cambian las tres variables nuevas
  (`MARKETHUB_PASSWORD_LOGIN` y las dos claves de Turnstile, leídas de Secret Manager).
- **Comprobado en producción sin sesión**: `/api/config` da `registration: captcha`; registrarse sin
  captcha da 400; entrar con un email que no existe da el mensaje genérico; `/analysis/` y
  `/community/` cargan y sus datos piden sesión; las herramientas mandan a `/signin/`;
  `earningsradar.app` sigue igual. **Sin comprobar por el agente**: crear una cuenta con el captcha
  real y entrar con Google (lo revisa el dueño).
- **Despliegues en paralelo**: `scripts/deploy-cloudrun.sh` ya solo escribe un permiso cuando falta (`grant`): antes cada
  despliegue reescribía la política IAM del proyecto y dos a la vez chocaban ("concurrent policy
  changes"). Ahora los despliegues de los tres servicios pueden lanzarse en paralelo. Comprobado
  contra el proyecto sin escribir nada; aún no se ha hecho un despliegue en paralelo de verdad.
  Desde la raíz del workspace:
  `(cd market-hub-landing && make deploy) & (cd fundamentals-lab && make deploy) & (cd decision-signal-lab && make deploy-hub) & wait`

### Login propio: email y contraseña (2026-10-06)

El usuario pidió poder entrar sin Google, con un login gestionado por nosotros.

- **`src/markethub/accounts.py`**: registro (email, nombre, contraseña), entrada y cambio de
  contraseña. De la contraseña se guarda solo un hash scrypt con sal y con su coste escrito
  (`scrypt$15$8$3$sal$hash`: 32 MB y un cuarto de segundo, el tercer ajuste de OWASP); un hash hecho
  a un coste anterior se rehace en la siguiente entrada. Colección `logins` en Firestore, con la
  clave `sha256(email en minúsculas)`: el email no va en el nombre del documento y `Ana@x` y
  `ana@x` son la misma cuenta. El id del usuario se genera aquí (`mh_...`), nunca es el email.
- **API**: `POST /api/auth/register`, `POST /api/auth/password`, `PUT /api/auth/password`. La sesión
  es la misma cookie firmada, con `"provider": "password"` (las de Google llevan `"google"`; una
  sesión antigua sin el campo es de Google). Las herramientas no cambian: solo miran que haya
  sesión. `MARKETHUB_PASSWORD_LOGIN=0` lo apaga y deja Google como única entrada.
- **Frenos**: contraseña de 10 a 200 caracteres, fuera las más comunes y la que es el propio email;
  8 contraseñas malas por email en 15 minutos y esa dirección espera (aunque llegue la buena); 30
  intentos y 5 cuentas nuevas por IP y hora. La respuesta a un email que no existe y a una
  contraseña mala es la misma, y tarda lo mismo. Los contadores son en memoria, por instancia.
- **Lo que no hace, y hay que saber**:
  - **No envía correo, así que el email no se verifica**: quien lo registra primero se lo queda.
    Por eso un email de cuenta propia no da ningún derecho: `Opinion.can_moderate` solo vale para
    cuentas de Google (hay test: registrar el email del dueño no te hace moderador), y una cuenta
    propia es otra cuenta distinta de la de Google con el mismo email.
  - **No hay "he olvidado mi contraseña"**. La página lo dice antes de elegirla. Para tenerlo hace
    falta un proveedor de correo (clave y coste nuevos): decisión del usuario.
  - **Cambiar la contraseña no cierra las otras sesiones**: la sesión es una cookie firmada sin
    estado; dura hasta 30 días.
- **Captcha en el registro** (`src/markethub/captcha.py`, Cloudflare Turnstile): crear una cuenta
  lleva un token que la página saca del widget y el servidor comprueba con Cloudflare **antes** de
  mirar nada más (sin token válido no se dice nada del email ni de la contraseña). Si Cloudflare
  no contesta, cuenta como fallo. Entrar no pide captcha (tiene sus propios frenos). Estados que
  da `/api/config` en `registration`: `captcha` (hay claves), `closed` (no hay: no se crean
  cuentas; Google sigue igual) y `open` (solo con `MARKETHUB_OPEN_REGISTRATION=1`, para una
  máquina de desarrollo). **Las dos claves viven solo en Secret Manager**
  (`market-hub-turnstile-site-key` y `market-hub-turnstile-secret`, guardadas el 2026-10-06; el
  dueño pidió que no estén en `.env`): `make deploy` no las copia, apunta el servicio a ellas con
  `--set-secrets`, y si faltan despliega con el registro cerrado y lo avisa. Para cambiar una:
  `printf '%s' '<clave>' | gcloud secrets versions add market-hub-turnstile-secret --data-file=-`
  y volver a desplegar. Probado en local con las claves de prueba públicas de Cloudflare (las que
  siempre pasan), nunca con un reto real.
- **Web**: `/signin/` tiene, bajo el botón de Google, un formulario que sirve para entrar y para
  crear la cuenta; `/account/` dice cómo entra la cuenta y deja cambiar la contraseña; `/privacy/`
  dice qué se guarda. Borrar la cuenta borra también su entrada en `logins`.
- **Tests**: 136 en verde (30 nuevos en `tests/test_accounts.py`). Probado en local en el
  navegador: crear cuenta, contraseña débil, cambiarla, salir, entrar con la vieja (no) y con la
  nueva (sí), mismo email otra vez (no), borrar.

### My Hub a fondo: análisis de cartera, frases con IA, comunidad (2026-10-06)

El usuario pidió mejorar mucho My Hub: mucha más información de la cartera (aunque hubiera que
simular datos, porque FMP está sin cuota), frases escritas con IA que la analicen, verla agrupada
por sector, volatilidad, país..., compartir carteras (solo si el usuario quiere) con una
clasificación que diga si estás por encima de la media (día, 1 mes, 3 meses, YTD, 1 año) y
gráficas comparadas con los índices. **Hecho y probado en local; sin commit ni despliegue.**

- **Tres páginas** en la barra de My Hub: `Overview` (`/dashboard/`, rehecha), `Analysis`
  (`/analysis/`, nueva) y `Community` (`/community/`, nueva), además de `Portfolio` y `Account`.
  `HubNav.astro` de `fundamentals-lab` y `decision-signal-lab` lleva los dos enlaces nuevos.
- **Datos con respaldo** (`src/markethub/holdings.py`): `gather()` pide cotizaciones, cierres y
  ficha a FMP; si no contesta (o no da ni un precio), toda la respuesta sale de los datos de ejemplo
  (`SampleData`, sobre `sample.py`) y lleva `"sample": true`. Nunca se mezclan. Las páginas lo
  dicen con la etiqueta "sample figures" junto al título. `/api/dashboard` ya no da 503 por FMP.
  `MARKETHUB_SAMPLE_MARKETS=1` fuerza el ejemplo. Los datos de ejemplo ahora se sostienen: las
  acciones y los índices comparten el movimiento del mercado (`MARKET_SEED`, `beta_of` en
  `sample.py`), así que una cesta tiene beta y menos volatilidad que sus partes; las empresas
  conocidas tienen su sector y su país (`SAMPLE_SECTOR_OF`, `SAMPLE_COUNTRIES`).
- **Análisis** (`dashboard.py`): por posición, país, beta, volatilidad anualizada del último año y
  su tramo (baja <20 %, media, alta ≥35 %), tamaño por capitalización, rentabilidad por dividendo,
  distancia al máximo de 52 semanas y los puntos que aporta al movimiento del día. `groups`: las
  posiciones agrupadas por sector, país, volatilidad y tamaño, cada grupo con su peso y sus
  rentabilidades ponderadas. `performance`: la cartera frente a S&P 500, Nasdaq 100, Dow Jones y
  Russell 2000 (por sus fondos SPY, QQQ, DIA, IWM) en los cinco periodos. `risk`: volatilidad, beta
  frente al S&P 500, mayor caída desde un máximo, días al alza, mejor y peor día, peso de la mayor
  y de las tres mayores, "se comporta como N posiciones iguales" (1/Σw²) y dividendo ponderado.
  **Toda rentabilidad de la cartera es la de las posiciones de hoy mantenidas durante el periodo**
  (no se guardan operaciones), y las páginas lo dicen.
- **Frases** (`insights.py`): dos redactores de lo mismo. `sentences()` es código: sale con el
  dashboard, gratis y siempre. `InsightWriter` es Claude Haiku 4.5 (misma clave que las noticias):
  la página pinta las del código y pide `/api/insights`; si el modelo contesta, las sustituye. Al
  modelo solo va `facts()`: tickers, pesos y rentabilidades en porcentaje; **nunca** identidad,
  número de acciones, costes ni importes (hay un test que lo comprueba). Lo que escribe pasa un
  filtro de consejos (`reads_as_advice`): la frase que aconseja se descarta. Una cartera sin
  cambios se lee una vez al día y como mucho `INSIGHTS_PER_USER_PER_DAY` (6) veces por usuario; la
  caché es en memoria, así que un arranque en frío la vuelve a pedir. Cada lectura cuesta medio
  céntimo (unos 3.900 tokens de entrada y 330 de salida); el coste va al log. No se guarda nada de
  lo que escribe. En la página no se dice que lo escribe una IA (el dueño no quiere notas de cómo
  está hecho); sí en `/privacy/`, porque es un dato que sale del servidor.
- **Comunidad** (`community.py`): compartir está apagado hasta que el usuario lo enciende y elige
  un nombre (3 a 20 caracteres, único). Se guarda un documento aparte (`shared_portfolios/{id}`,
  el id de la cuenta no sale del servidor) con el nombre, los tickers con su peso, las
  rentabilidades y las "unidades" (peso/precio), que permiten recalcular sin saber el tamaño de
  nada. Lo ven solo usuarios con sesión. Sigue a la cartera (se rehace al guardar y al abrir el
  dashboard; las viejas de más de 6 h, cuatro por visita al tablero), y desaparece al apagarlo, al
  vaciar la cartera o al borrar la cuenta. El tablero ordena por la rentabilidad del periodo,
  intercala los cuatro índices y la media, y dice a cada usuario, comparta o no, su puesto, si
  está por encima de la media y por cuántos puntos. **Mientras los datos son de ejemplo se añaden
  doce carteras de relleno** (`SAMPLE_NAMES`), marcadas "sample" una a una: no son personas, y
  desaparecen en cuanto las cifras son reales. Con datos reales y pocos usuarios el tablero estará
  casi vacío: es lo honesto.
- **Privacidad y cuenta**: `/privacy/` dice lo que se comparte y lo que va al modelo; `/account/`
  muestra si la cartera está compartida y lo incluye en la descarga; borrar la cuenta la quita.
- **Tests**: 106 en verde (29 nuevos en `tests/test_myhub.py`).
- **Probado** en local con Chrome a 1440 y 390 px, con una sesión de prueba y datos de ejemplo:
  las tres páginas, sin desbordes. Una llamada real al modelo para ver la calidad de las frases
  (dos, 0,01 USD en total): las cifras que escribió coincidían con los datos.
- **Pendiente**: verlo con el login real de Google; moderación de nombres del tablero (hoy solo
  se rechazan los reservados; un admin no puede quitar uno); la clasificación compara carteras
  "como están hoy", no lo que cada uno ganó de verdad; revisar con FMP real el campo `country` y
  la capitalización de la ficha (`profile`), que hasta ahora no se leían.

### Portadas de noticias y de opinión (2026-10-06)

El usuario pidió imágenes en noticias y en opinión, **generadas en local con Claude Code, sin
Hugging Face ni ningún otro servicio de imágenes** (lo dijo expresamente tras un primer intento
con HF, que se retiró).

- **Noticias: una biblioteca, no una imagen por noticia.** `covers/` construye con three.js una
  escena por ámbito (los once sectores y `Macro`), la fotografía desde dos sitios y bajo tres
  luces, que son la lectura de la noticia: sol bajo y cálido (bullish), anochecer frío con lluvia
  (bearish), día nublado (neutral). 12 x 3 x 2 = 72 imágenes en `site/public/covers/news/`
  (1280x720 y una `-s` de 480x270 para las listas; unos 12 MB) y el índice
  `site/src/lib/news-covers.json`. Las dibuja el Chrome del equipo (`playwright-core`):
  `make covers`, o `make covers ONLY=Energy`. `covers/out/` (hojas de contacto) no se sube.
- **Cómo se asigna**: `cover()` en `site/src/lib/news.ts` elige por `scope` y `sentiment` de la
  noticia, y el id de la noticia decide cuál de las vistas: una noticia tiene siempre la misma
  imagen, en la lista (`/news/`, miniatura a la derecha) y en su página (bajo la entradilla). Los
  titulares de prensa, que no tienen ni ámbito ni lectura, no llevan imagen.
- **Skill `news-covers`** (`.claude/skills/news-covers/SKILL.md`): cómo añadir vistas o escenas y
  qué mirar en las hojas. Para más variedad basta una tercera cámara por escena y añadir `3` a
  `VIEWS` en `covers/render.mjs`.
- **Son escenas renderizadas por código, no fotografías.** El resultado es cinematográfico
  (siluetas, bruma, reflejos en suelo mojado), no fotorrealista: es el techo de lo que se puede
  generar en local sin un modelo de imagen. Las más flojas: `Healthcare` (laboratorio) y
  `Consumer Cyclical` (calle).
- **Opinión**: las portadas las dibuja la skill `update-opinion` en el repo `market-hub-opinion`
  (un SVG o HTML por artículo, cada uno de un estilo) y las publica como JPEG en Firestore
  (`opinion_covers/{slug}`). Aquí: `cover()` en los almacenes y en `Opinion`
  (`src/markethub/opinion.py`, con una pequeña caché en memoria), `GET
  /api/public/opinion/cover?slug=&v=` (el único punto de `/api/` que un navegador puede guardar:
  con `v`, un año e `immutable`; el resto sigue en `no-store`), y la imagen en `/opinion/` (el
  primero a dos columnas, el resto encima del título) y en el artículo. 77 tests en verde.
- **Desplegado y publicado el 2026-10-06** (revisión `market-hub-00014-f8z`; después, `make publish`
  en `market-hub-opinion`). Comprobado en producción con un navegador: `/news/` carga las ocho
  portadas de las noticias del día y `/opinion/` las seis, sin ninguna rota; el artículo de opinión
  muestra la suya con su texto alternativo; la portada con `v` sale con `immutable` y el resto de
  `/api/` sigue en `no-store`.
- Ojo al añadir carpetas a `.gcloudignore`: un patrón sin barra inicial (`covers/`) vale a cualquier
  profundidad y dejaría fuera `site/public/covers/`. Por eso es `/covers/`.

## Cómo está hecho

- **Login:** la web carga Google Identity Services, que devuelve un ID token. `POST /api/auth/google`
  lo verifica con `google-auth` contra `GOOGLE_CLIENT_ID` y comprueba emisor y email verificado.
  La sesión (`mh_session`) es la cookie firmada de Starlette (`SessionMiddleware`) con el id, el
  nombre, el email y la foto; el token no se guarda.
- **CSRF:** la cookie es `SameSite=Lax` y además toda escritura en `/api/` exige un `Origin` del
  propio sitio (o de `MARKETHUB_ALLOWED_ORIGINS` en desarrollo).
- **Datos:** `users/{sub}` en una base de Firestore propia, `market-hub` (europe-west1), no en la
  `(default)` del proyecto, que es de otras apps y está en us-central1. Cada documento lleva
  `positions` (`ticker`, `shares`, `avg_cost` opcional), `watchlist`, `email`, `name`, `picture` y fechas. Tickers validados contra la lista de la SEC más
  unos ETF; tickers repetidos se funden con su coste medio ponderado. Máximo 50 + 50.
- **Dashboard:** valor a precio actual, ganancia frente al coste (solo de las posiciones con coste),
  cambio del día, pesos, sectores (ETF como "ETF / fund"), rentabilidades de 1 mes a 1 año y la
  serie de "posiciones actuales mantenidas un año" frente a SPY, rotulada como tal: no es la
  rentabilidad real del usuario, porque no se registran operaciones.
- **Portal público:** las páginas piden a `/api/public/*` (sin login). La forma de cada respuesta
  está en `site/src/lib/market.ts`; un proveedor real solo tiene que devolver lo mismo. Las
  noticias de ejemplo no recomiendan nada (hay un test que lo comprueba) y los valores que no
  están en la tabla de `sample.py` se generan de forma estable a partir del ticker.
- **Estilo:** este repo estrena el tema oscuro; `fundamentals-lab` y `decision-signal-lab` siguen
  con el claro anterior. Para unificar la marca, el siguiente paso es llevar `global.css`, `Logo`,
  `lwc.ts` y los componentes de tabla a esos dos repos.
- **Llamadas a FMP por carga del dashboard:** una de cotizaciones en bloque (o una por ticker si el
  plan no la incluye), una de histórico por ticker (en caché 6 horas) y una de perfil por posición
  (en caché 7 días). Con 10 tickers, unas 20 llamadas la primera vez y 1 después. El plan
  gratuito (250 al día) basta para probar; para usuarios reales hace falta el plan Starter.

## Siguientes pasos, en orden

1. ~~Crear el cliente OAuth~~ (hecho; `make env` rellena `GOOGLE_CLIENT_ID` y `SESSION_SECRET`).
2. `FMP_API_KEY` y `SEC_USER_AGENT` en `.env`; `make serve` y probar el flujo completo.
3. ~~`make deploy`~~ (hecho); añadir la URL de Cloud Run a los orígenes del cliente OAuth y, si el
   usuario quiere, un dominio. En el entorno en la nube, `gcloud` necesita
   `env -u CLOUDSDK_AUTH_ACCESS_TOKEN` para usar la cuenta del usuario. La pantalla de consentimiento de OAuth tiene que pasar a "In production"
   para que entren usuarios fuera de la lista de prueba.
4. Desplegar Fundamentals Lab y poner su URL en `FUNDAMENTALS_LAB_URL`.
