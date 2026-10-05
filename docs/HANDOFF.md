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
| 17 tests en verde, sin red: tokens buenos y malos, aislamiento entre usuarios, CSRF, cookie `HttpOnly`/`Lax`, validación del portfolio, cálculos del dashboard | |
| Web (`site/`): portada con login, bienvenida "¿tienes cartera?", editor de posiciones y favoritos, dashboard, herramientas, cuenta (ver, descargar y borrar datos) y privacidad. Revisada en Chromium a 1280 y 390 px con Google y FMP simulados | Revisarla con el botón real de Google |
| `Makefile`, `Dockerfile`, `scripts/deploy-cloudrun.sh` (crea Firestore en europe-west1, secretos, despliegue) | Crear el cliente OAuth y desplegar |
| Repo en GitHub: `alejandrorodriguezalvarez884-dot/market-hub-landing` (el código se movió aquí desde `market-hub` el 2026-10-05, con su historial); código en `main` | |
| | La herramienta Fundamentals Lab no tiene URL todavía: el dashboard la muestra como "Coming soon" hasta que se ponga `FUNDAMENTALS_LAB_URL` |

## Cómo está hecho

- **Login:** la web carga Google Identity Services, que devuelve un ID token. `POST /api/auth/google`
  lo verifica con `google-auth` contra `GOOGLE_CLIENT_ID` y comprueba emisor y email verificado.
  La sesión (`mh_session`) es la cookie firmada de Starlette (`SessionMiddleware`) con el id, el
  nombre, el email y la foto; el token no se guarda.
- **CSRF:** la cookie es `SameSite=Lax` y además toda escritura en `/api/` exige un `Origin` del
  propio sitio (o de `MARKETHUB_ALLOWED_ORIGINS` en desarrollo).
- **Datos:** `users/{sub}` en Firestore con `positions` (`ticker`, `shares`, `avg_cost` opcional),
  `watchlist`, `email`, `name`, `picture` y fechas. Tickers validados contra la lista de la SEC más
  unos ETF; tickers repetidos se funden con su coste medio ponderado. Máximo 50 + 50.
- **Dashboard:** valor a precio actual, ganancia frente al coste (solo de las posiciones con coste),
  cambio del día, pesos, sectores (ETF como "ETF / fund"), rentabilidades de 1 mes a 1 año y la
  serie de "posiciones actuales mantenidas un año" frente a SPY, rotulada como tal: no es la
  rentabilidad real del usuario, porque no se registran operaciones.
- **Llamadas a FMP por carga del dashboard:** una de cotizaciones en bloque (o una por ticker si el
  plan no la incluye), una de histórico por ticker (en caché 6 horas) y una de perfil por posición
  (en caché 7 días). Con 10 tickers, unas 20 llamadas la primera vez y 1 después. El plan
  gratuito (250 al día) basta para probar; para usuarios reales hace falta el plan Starter.

## Siguientes pasos, en orden

1. Crear el cliente OAuth (Google Auth Platform → Clients → Web application) en el proyecto
   `arctic-robot-474306-g3`, con los orígenes de desarrollo; poner `GOOGLE_CLIENT_ID` y un
   `SESSION_SECRET` en `.env`.
2. `FMP_API_KEY` y `SEC_USER_AGENT` en `.env`; `make serve` y probar el flujo completo.
3. `make deploy`, añadir la URL de Cloud Run a los orígenes del cliente OAuth y, si el usuario
   quiere, un dominio. La pantalla de consentimiento de OAuth tiene que pasar a "In production"
   para que entren usuarios fuera de la lista de prueba.
4. Desplegar Fundamentals Lab y poner su URL en `FUNDAMENTALS_LAB_URL`.
