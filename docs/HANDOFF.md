# Estado del proyecto y cómo continuar

Última actualización: 2026-10-05.

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
