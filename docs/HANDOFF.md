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
| **Datos de ejemplo** en la parte pública: `src/markethub/sample.py` y `/api/public/{overview,chart,quote,news}`. Paseo aleatorio por símbolo con semilla fija (el histórico no cambia de un día a otro y crece una barra por sesión), titulares genéricos con fuentes inventadas ("Sample Wire"). Toda respuesta lleva `"sample": true` y cada página pública lo avisa con una franja | **Conectar datos reales**: sustituir `sample.py` por un proveedor (FMP para precios, un proveedor de noticias) manteniendo la forma de las respuestas; la web no cambia. Quitar entonces la franja `sample` de las páginas |
| `Makefile`, `Dockerfile`, `scripts/deploy-cloudrun.sh` (crea la base de Firestore `market-hub` en europe-west1, secretos, despliegue) | |
| **Desplegado en Cloud Run** (2026-10-05): servicio `market-hub`, europe-west1, revisión `market-hub-00002-j4g` (el rediseño, commit `e0a4af8` de `main`), https://market-hub-818229650855.europe-west1.run.app (también https://market-hub-3qwezbjyfq-ew.a.run.app). Arranca bien según los logs; secretos `market-hub-session-secret` y `market-hub-fmp-api-key` | Añadir las dos URL a los orígenes del cliente OAuth y probar el login y el dashboard en la URL pública (desde el entorno en la nube el proxy bloquea `*.run.app` y FMP). Rotar la clave de FMP, que pasó por el chat, y subirla como versión nueva del secreto |
| Cliente OAuth creado (2026-10-05): `818229650855-3dq57ote5eq25hhdmru29k3mg852jpnb.apps.googleusercontent.com`, público, en `.env.example`. `make env` (lo lanzan `install`, `api`, `serve` y `deploy`) crea `.env` con él y un `SESSION_SECRET` nuevo | Probar el login real en `localhost` (desde el entorno en la nube Google devuelve 403 en el botón y no se pudo distinguir si es el proxy o los orígenes) |
| Repo en GitHub: `alejandrorodriguezalvarez884-dot/market-hub-landing` (el código se movió aquí desde `market-hub` el 2026-10-05, con su historial); código en `main` | |
| **Login único con las herramientas (2026-10-05)**: dominio `themarkethub.app` (comprado por el usuario). La cookie de sesión lleva `Domain=themarkethub.app` (`MARKETHUB_COOKIE_DOMAIN`), solo en peticiones que llegan por ese dominio (`HostScopedCookieDomain`; en `*.run.app` queda en el host). El login acepta volver a `https://<sub>.themarkethub.app/...`. Fundamentals Lab (`fundamentals.`) y el Earnings Radar del hub (`radar.`, servicio `earnings-radar-hub`) leen esa cookie con el mismo secreto (`market-hub-session-secret`) y piden login. `earningsradar.app` sigue público y sin tocar | Verificar `themarkethub.app` en Search Console, crear los mapeos de dominio de Cloud Run y añadir los DNS; añadir `https://themarkethub.app` a los orígenes del cliente OAuth |

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
