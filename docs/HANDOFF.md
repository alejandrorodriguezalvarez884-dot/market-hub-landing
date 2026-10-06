# Estado del proyecto y cómo continuar

Última actualización: 2026-10-06.

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
- **Dónde salen**: `/news/` (por día, con filtro por tipo y la prensa al lado), bloque "Latest
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
  `launch.json` del workspace no arranca porque su bash no encuentra `uv`.

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
- **Opinión**: una pieza diaria generada desde el archivo `news/` y las cifras del día, con las
  dos lecturas posibles y sin elegir ninguna, marcada como escrita por IA y con enlaces a sus
  noticias. Sin empezar.

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
