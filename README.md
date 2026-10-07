# Market Hub

**El portal de las herramientas de IA para inversión.** Tiene dos partes:

- **Portal público**, sin cuenta: mercados (índices, tipos, materias primas, divisas, cripto,
  sectores y movers), noticias, y una ficha por valor con gráfico, cifras clave y enlaces a las
  herramientas. Por ahora con **datos de ejemplo** (`src/markethub/sample.py`), rotulados como tales.
- **My Hub**, el área privada: el usuario entra con su cuenta de Google (Gmail), añade su cartera
  (acciones y precio medio) o, si no tiene, las acciones que sigue, y llega a un dashboard que las sigue:

- valor de la cartera, movimiento del día y ganancia o pérdida frente a su propio precio medio;
- cada posición con su peso, rentabilidad a un año y minigráfico de tres meses;
- reparto por posición y por sector;
- cómo habrían ido las posiciones actuales en el último año frente al S&P 500;
- favoritos con día, mes, año y distancia al máximo de 52 semanas.

Desde cada acción se abre en las herramientas: [Fundamentals Lab](https://github.com/alejandrorodriguezalvarez884-dot/fundamentals-lab)
(números, valoración, múltiplos futuros, técnico) y el [Earnings Radar](https://earningsradar.app/)
(lo que dice su último comunicado de resultados).

> Describe, no recomienda. No hay código que envíe órdenes ni que se conecte a un broker.

## Cómo funciona

| Pieza | Qué hace |
|---|---|
| Login | Botón "Sign in with Google" (Google Identity Services). La API verifica el ID token (firma, audiencia, emisor, caducidad, email verificado) y guarda solo el id del usuario en una cookie de sesión firmada, `HttpOnly`, `SameSite=Lax`, de 30 días |
| Datos del usuario | Un documento por usuario en Firestore (región europe-west1): nombre, email, foto, posiciones y favoritos. Se pueden descargar y borrar desde la web |
| Precios | Financial Modeling Prep: cotización, cierres diarios y sector; en memoria unos minutos. El portal público usa datos de ejemplo (`/api/public/*`) hasta conectar un proveedor |
| Gráficos | Lightweight Charts de TradingView (Apache-2.0) |
| Buscador | Lista de empresas de la SEC, más los ETF más comunes |
| Seguridad | Las escrituras exigen que el `Origin` sea el propio sitio (CSRF); cada usuario solo lee su documento; límite de peticiones por IP |

Web Astro en `site/`, API FastAPI en `src/markethub/`, un contenedor en Cloud Run.

## Puesta en marcha

```bash
make install             # dependencias, y crea .env con GOOGLE_CLIENT_ID y un SESSION_SECRET nuevo
                         # (a mano solo queda SEC_USER_AGENT; FMP_API_KEY es opcional)
make test
make api                 # API en :8000
make dev                 # web en :4321 (en otra terminal)
```

El cliente OAuth se crea en Google Cloud Console → Google Auth Platform → Clients → *Web
application*, con `http://localhost:4321`, `http://localhost:8080` y la URL pública en
*Authorised JavaScript origins*. No hace falta *redirect URI*: el login es por ventana emergente.

## Despliegue

`make deploy`: activa Firestore (europe-west1) si no existe, guarda el secreto de sesión (y la
clave de FMP, si hay) en Secret Manager y despliega en Cloud Run. Los precios salen de Yahoo Finance
(`yfinance`, sin clave); con clave de FMP, FMP queda detrás por si Yahoo no responde. Nada está programado ni en GitHub Actions.
