// The legal pages: Privacy (views/Privacy.astro), Terms (views/Terms.astro) and Contact
// (views/Contact.astro). Each body is the page's markup in one language, with the addresses it
// links to given by the page, and nothing in it comes from a reader. The Spanish says exactly
// what the English says: Privacy is the contract with the user, so a change to one language is
// made in the other in the same commit.
import { words } from ".";

type PrivacyLinks = { account: string; submit: string; contact: string };
type TermsLinks = { author: string; privacy: string; account: string; contact: string };
type ContactLinks = { email: string; terms: string; privacy: string; account: string };

const h2 = (text: string) => `<h2 class="pt-2 text-lg font-bold text-ink-strong">${text}</h2>`;
const out = (href: string, text: string) => `<a href="${href}" class="link" rel="noopener">${text}</a>`;
const to = (href: string, text: string) => `<a href="${href}" class="link">${text}</a>`;
const GOOGLE_PERMISSIONS = "https://myaccount.google.com/permissions";
const YOUTUBE_TERMS = "https://www.youtube.com/t/terms";
const GOOGLE_PRIVACY = "https://policies.google.com/privacy";

export const privacy = words(
  {
    title: "Privacy",
    description: "What Market Hub keeps about you and why.",
    body: (l: PrivacyLinks) => `
<p>Market Hub keeps the least it needs to show you your private dashboard and to let you comment. The public pages (markets, quotes, news, opinion, media) need no account and keep nothing about you.</p>
<p>The Media page shows Market Hub's videos with pictures kept on this site. Only when you press play is the video
loaded from YouTube, at its address without cookies (youtube-nocookie.com); from then on YouTube, which is Google,
sees your IP address and what you watch, as it would on its own site.</p>
<p>Those videos are uploaded to Market Hub's own YouTube channel with a tool of ours that uses YouTube API Services.
Only the channel's owner uses it, signed in with the channel's own Google account. It does not ask you to sign in,
and it does not read, collect or keep anything about you, about viewers or about anybody else's channel. What it
sends to YouTube is our own videos, with their titles, descriptions, thumbnails and captions. The owner can take
the tool's access away at any time on ${out(GOOGLE_PERMISSIONS, "Google's security settings page")}, and the sign-in it keeps on the owner's computer is deleted with it. What you watch on
YouTube is under the ${out(YOUTUBE_TERMS, "YouTube Terms of Service")}
and the ${out(GOOGLE_PRIVACY, "Google Privacy Policy")}.</p>
<p>To know how many people visit, every page loads a small script from Cloudflare Web Analytics. It tells Cloudflare
which page was opened and the page that led to it, the kind of browser and device, the country, and how fast the
page loaded. It sets no cookie and keeps nothing in your browser, and it is told nothing about your account: not
who you are, and nothing of your stocks. Cloudflare sees your IP address when the script is loaded, as any server
does. The analysis tools on their subdomains, and the Earnings Radar at earningsradar.app, count visits the same
way.</p>
<p>The price charts on Today and on a quote's page, and the map on Markets, are widgets of TradingView: frames it fills
with its own data. To show them, TradingView sees your IP address, the address of the page the widget is on and the
symbol it shows. It says its widgets set no cookies. A widget is told nothing about your account.</p>
${h2("What we keep")}
<ul class="list-disc space-y-1 pl-5">
<li>From your Google account, when you sign in with it: your account id, name, email address and profile picture.</li>
<li>From your Apple account, when you sign in with it in the app for iPhone: an account id Apple makes for us alone,
the email address Apple gives us (your own, or one of Apple's relay addresses if you chose to hide it) and the
name you let it share, if any. No picture, and no password. When you delete such an account, the app has your
iPhone ask you once more, and with what Apple hands it we tell Apple to stop listing the app under your Apple
account. We keep neither that nor any token of Apple's.</li>
<li>If you make an account with an email and a password instead: the email address and the name you give, and a scrambled
form of the password (a salted scrypt hash) from which it cannot be read back. We never keep the password as you typed
it. We do not check that the address is yours, and we cannot send you a new password if you forget it. When you
make the account, Cloudflare Turnstile checks that a person is asking: Cloudflare sees your IP address and details
of your browser for that check, and we keep nothing of it.</li>
<li>What you add: the tickers you hold with their number of shares and average cost, and the tickers you follow.</li>
<li>If you choose to share your portfolio, and only then: the name you pick to be shown under, the tickers you hold with each
one's share of the portfolio in percent, and the returns of those holdings. Signed-in members see that on the Community
page. It never includes your name, email or picture, how many shares you hold, what you paid or what it is worth.
It is off until you turn it on, and turning it off removes it at once.</li>
<li>If you enter the monthly competition, and only then: the name you pick to play under, and the stocks you choose for the
month with the share you give each one. Until the month starts nobody sees them; from then on signed-in members see
that name, those stocks and weights and what the mix has returned, and the final standings of a month are kept. It never
includes your name, email or picture, and it has nothing to do with the positions you hold.</li>
<li>If you send in a bot to the bot competition (Bot League, at bots.themarkethub.app, and Community here), and only then:
the first name of your account, which the bot is shown under (never your surname, email or picture), a random id its page
is found by, the bot's rules as you sent them, the companies it could choose from that day, and
its record close by close with what it holds, a log of its rebalances (what it held before and after each), and the
changes you make to it (each version of its rules from the close it applied, the companies you leave out and whether
you paused it). The board is public: anyone, signed in or not, sees that first name, the bot's name and description, its
returns, what it holds and what it bought and sold at each rebalance, and the dates its rules changed; its rules, old
and new, are seen by you alone. It never includes your name, email or picture, and it has nothing to do with the positions you hold. If
you make a key for your AI agent: when it was made and when it was last used. The key itself is kept only scrambled
(a hash), so we cannot show it again; a new key, or taking it back, stops the old one.</li>
<li>The comments you write under opinion articles. They are public, and they are shown with your first name: not with your
surname, your email address or your picture. The comments you write in the competition's discussion are seen by
signed-in members only, with the name you play under (your first name, if you have none).</li>
<li>If you report a comment: with that comment, your account id, so it stays hidden from you and counts once. The
owner sees how many readers reported a comment, never who. If you block a member: your account id, theirs,
the name their comment was shown under and the date, so their comments stay hidden from you and you can unblock
them on your account page. Nobody is told who reported or blocked whom, and both are removed with your account.</li>
<li>If you send an article to Opinion, and only then: its title, summary, text and sources and the name you sign it with,
kept together with your account id, your name, your email address and whether you sign in with Google, with Apple or with a
password, so the editor knows whose it is and can answer you. Nobody else sees it. If it is
published, the article shows the name you signed it with and nothing else of you.</li>
<li>A session cookie, signed by us, that keeps you signed in for up to 30 days. If you choose a language, with or without an account, a cookie that remembers it (mh_lang: English or Spanish) for a year, read by Market Hub and its tools so they open in that language; it says nothing about you. No advertising or tracking cookies.</li>
<li>In the Market Hub app for phones, which is this same private area with this same account: nothing more with us.
On your phone the app keeps your sign-in and nothing else: a token signed by us, good for up to 30 days, with your
name and email address, in the phone's own keychain. Signing out removes it. Nothing of your stocks is kept on
the phone, and the app carries no advertising or analytics kit. It asks you for no permission on your phone: not
your location, your contacts, your photos, your camera or your microphone. Signing in with Google there goes
through your phone's browser, signing in with Apple is done by the iPhone itself, the analysis tools open inside the app in a page of their own (for
that page we set the same session cookie as on this site, and it is gone when you leave the page), and making an account shows the same Cloudflare check as here.</li>
<li>In the Bot League app for iPhone, which plays with this same account: nothing more with us than what your bot already
keeps (above). On your phone the app keeps your sign-in (the same kind of token, in the phone's keychain), the language you
chose, whether you have seen its welcome and, for the summary it shows when you open it, the last close it summed up with your
bot's public id. Signing out removes them. If you turn on its daily notice after the US close, the phone itself schedules it:
no server of ours sends it and we keep nothing for it, its text only says that the close is in, and you can turn it off at any
time. The app asks for that one permission, and only when you turn the notice on: not your location, your contacts, your
photos, your camera or your microphone. Sharing your bot as a picture draws the picture on our server from what the
leaderboard already shows and hands it to your phone's share sheet; we never learn whom you share it with. Your conversation
with Claude about your bot stays on the screen, and what you write is sent as described for Bot League's chat below. The app
carries no advertising or analytics kit. You can delete your account from the app, and everything above goes with it.</li>
<li>In your browser only, not with us: on the Watchlist page, which stocks you chose to see (the ones you looked up there
among them), how many at a time and how the charts are drawn. And on the page where you write for Opinion, the article you are
writing, until you send it. Clearing the site's data in your browser removes it.</li>
<li>In Options Lab, the option strategies you choose to save: the name you give each one, its ticker, its legs (calls,
puts or shares, bought or sold, how many, strike, expiration and the price each was opened at) and when it was saved.
They are kept with your account and nothing else, and only you see them. A strategy you are building but have not saved stays in
your browser only.</li>
<li>Nothing else about you in the analysis tools. Fundamentals Lab, the Earnings Radar, Peer Map, the Playground and Options Lab, on their own
subdomains, read the same session cookie only to check that you are signed in; they do not store your name, email
or stocks. A board you make in the Playground, and what you wrote to make it, live in the page that shows them
and nowhere else: reloading or closing the page clears them.</li>
</ul>
${h2("What we do with it")}
<p>
Show it back to you, and to other members only what you chose to share. To value your positions, the server asks the
market data provider for the prices of your tickers; it does not send your name, email, share counts or costs.
</p>
<p>
The sentences that read your portfolio back to you are written by a language model run by Anthropic. To write them, the
server sends it what your portfolio is made of and how it has moved: the tickers, each one's share in percent, and their
returns. It does not send your name, email or account, how many shares you hold, what you paid or what it is worth, and
we keep nothing of what the model writes. Nothing is sold, and we do not connect to any broker.
</p>
<p>
On the Watchlist page, the server asks the market data provider for the prices of the stocks you look at and for what
analysts estimate of each. The sentences under a stock's figures are written by the same language model: for them the
server sends that one ticker with its market figures, which are the same for everybody, and nothing else. Not who asks,
and not the rest of your list or anything you hold.
</p>
<p>
In the Playground, what you write in the chat is sent to the same language model, together with the board as it
stands (the views on it and their tickers) and the last few messages of that conversation, so that it can change
the board. It does not send your name, email or account, and nothing of your portfolio or your lists. We keep
neither what you write nor what the model answers, and neither goes to our logs. To draw a view, the server asks
the market data provider for the prices of its tickers.
</p>
<p>
In Bot League, the chat on your bot's page sends what you write, the last few messages of that conversation and your
bot's rules (or, while you build one there, its draft and the figures of a backtest you ran) to the same language model,
so that it can propose new rules or a new bot; nothing changes until you apply them or send the bot in. It does
not send your name, email or account. We keep neither what you write nor what the model answers, and neither goes to
our logs.
</p>
${h2("Where it lives")}
<p>In a Google Cloud Firestore database in the European Union (Belgium region), accessible only to the service. The
articles sent in for review are kept apart, in a Google Cloud Storage bucket in the same region that only the
service and the editor reach.</p>
${h2("Your control")}
<p>
On ${to(l.account, "Account and data")} you can see and download everything kept about you, and
delete your account: that removes it from the database at once, takes your portfolio off the Community page, removes your
entries to the competition, your bot and its key, and the strategies you saved in Options Lab, and empties every comment you wrote. In a month of the competition that has already ended, your
line stays where it finished, with no name on it. You can also delete any comment of yours where it stands, and take back
an entry until its month starts. An article you sent in can be taken back on
${to(l.submit, "the page you sent it from")}, and deleting your account removes
the copies kept for review. An article of yours that was already published stays published until you ask us to
take it down.
</p>
<p>To ask about your data, or to have us do any of this for you, see ${to(l.contact, "Contact")}.</p>`,
  },
  {
    title: "Privacidad",
    description: "Qué guarda Market Hub sobre ti y por qué.",
    body: (l: PrivacyLinks) => `
<p>Market Hub guarda lo mínimo que necesita para mostrarte tu panel privado y para dejarte comentar. Las páginas públicas (mercados, cotizaciones, noticias, opinión, media) no necesitan cuenta y no guardan nada sobre ti.</p>
<p>La página Media muestra los vídeos de Market Hub con imágenes guardadas en esta web. Solo cuando le das al play se
carga el vídeo desde YouTube, en su dirección sin cookies (youtube-nocookie.com); desde ese momento YouTube, que es Google,
ve tu dirección IP y lo que ves, como lo vería en su propia web.</p>
<p>Esos vídeos se suben al propio canal de YouTube de Market Hub con una herramienta nuestra que usa YouTube API Services.
Solo la usa el propietario del canal, con la sesión iniciada en la propia cuenta de Google del canal. No te pide que inicies
sesión, y no lee, recoge ni guarda nada sobre ti, sobre los espectadores ni sobre el canal de nadie más. Lo que envía a
YouTube son nuestros propios vídeos, con sus títulos, descripciones, miniaturas y subtítulos. El propietario puede retirar
el acceso de la herramienta en cualquier momento en ${out(GOOGLE_PERMISSIONS, "la página de ajustes de seguridad de Google")}, y con
ello se borra la sesión que la herramienta guarda en el ordenador del propietario. Lo que ves en YouTube se rige por los
${out(YOUTUBE_TERMS, "Términos del Servicio de YouTube")} y la ${out(GOOGLE_PRIVACY, "Política de Privacidad de Google")}.</p>
<p>Para saber cuánta gente nos visita, cada página carga un pequeño script de Cloudflare Web Analytics. Le dice a Cloudflare
qué página se abrió y la página desde la que se llegó a ella, el tipo de navegador y de dispositivo, el país y lo rápido que
cargó la página. No pone ninguna cookie ni guarda nada en tu navegador, y no se le dice nada de tu cuenta: ni quién eres
ni nada de tus acciones. Cloudflare ve tu dirección IP cuando se carga el script, como cualquier servidor. Las herramientas
de análisis en sus subdominios, y Earnings Radar en earningsradar.app, cuentan las visitas de la misma manera.</p>
<p>Los gráficos de precios de Hoy y de la página de cada cotización, y el mapa de Mercados, son widgets de TradingView: marcos
que TradingView llena con sus propios datos. Para mostrarlos, TradingView ve tu dirección IP, la dirección de la página en la
que está el widget y el símbolo que muestra. TradingView dice que sus widgets no ponen cookies. A un widget no se le dice nada
de tu cuenta.</p>
${h2("Qué guardamos")}
<ul class="list-disc space-y-1 pl-5">
<li>De tu cuenta de Google, cuando entras con ella: el identificador de tu cuenta, tu nombre, tu dirección de email y tu foto de perfil.</li>
<li>De tu cuenta de Apple, cuando entras con ella en la app para iPhone: un identificador de cuenta que Apple crea solo para
nosotros, la dirección de email que Apple nos da (la tuya, o una de las direcciones de reenvío de Apple si elegiste ocultarla)
y el nombre que le dejes compartir, si lo hay. Ninguna foto y ninguna contraseña. Cuando borras una cuenta así, la app hace que
tu iPhone te pregunte una vez más, y con lo que Apple le entrega le pedimos a Apple que deje de mostrar la app en tu cuenta de
Apple. No guardamos ni eso ni ningún token de Apple.</li>
<li>Si en lugar de eso creas una cuenta con un email y una contraseña: la dirección de email y el nombre que des, y una forma
irreconocible de la contraseña (un hash scrypt con sal) a partir de la cual no se puede volver a leer. Nunca guardamos la
contraseña tal como la escribiste. No comprobamos que la dirección sea tuya, y no podemos enviarte una contraseña nueva si la
olvidas. Cuando creas la cuenta, Cloudflare Turnstile comprueba que quien la pide es una persona: Cloudflare ve tu dirección IP
y datos de tu navegador para esa comprobación, y nosotros no guardamos nada de ella.</li>
<li>Lo que añades: los tickers que tienes, con su número de acciones y su coste medio, y los tickers que sigues.</li>
<li>Si eliges compartir tu cartera, y solo entonces: el nombre con el que eliges aparecer, los tickers que tienes con el peso de
cada uno en la cartera en porcentaje, y las rentabilidades de esas posiciones. Los miembros con sesión iniciada lo ven en la
página Comunidad. Nunca incluye tu nombre, tu email ni tu foto, cuántas acciones tienes, lo que pagaste ni lo que vale. Está
desactivado hasta que lo activas, y desactivarlo lo quita en el acto.</li>
<li>Si participas en la competición mensual, y solo entonces: el nombre con el que eliges jugar, y las acciones que eliges para el
mes con el peso que le das a cada una. Hasta que empieza el mes nadie las ve; desde entonces los miembros con sesión iniciada
ven ese nombre, esas acciones y pesos y lo que ha rentado la combinación, y se guarda la clasificación final de cada mes. Nunca
incluye tu nombre, tu email ni tu foto, y no tiene nada que ver con las posiciones que tienes.</li>
<li>Si envías un bot a la competición de bots (Bot League, en bots.themarkethub.app, y Comunidad aquí), y solo entonces: el
nombre de pila de tu cuenta, con el que se muestra el bot (nunca tu apellido, tu email ni tu foto), un identificador aleatorio
por el que se encuentra su página, las reglas del bot tal como las enviaste, las empresas entre las que podía elegir ese día, y
su historial cierre a cierre con lo que tiene, un registro de sus rebalanceos (lo que tenía antes y después de cada uno) y los
cambios que le haces (cada versión de sus reglas desde el cierre en que se aplicó, las empresas que excluyes y si lo pusiste en
pausa). La clasificación es pública: cualquiera, con sesión iniciada o sin ella, ve ese nombre de pila, el nombre y la
descripción del bot, sus rentabilidades, lo que tiene y lo que compró y vendió en cada rebalanceo, y las fechas en que
cambiaron sus reglas; sus reglas, antiguas y nuevas, solo las ves tú. Nunca incluye tu nombre completo, tu email ni tu foto, y
no tiene nada que ver con las posiciones que tienes. Si creas una clave para tu agente de IA: cuándo se creó y cuándo se usó
por última vez. La clave en sí solo se guarda de forma irreconocible (un hash), así que no podemos volver a mostrártela; una
clave nueva, o retirarla, deja sin efecto la anterior.</li>
<li>Los comentarios que escribes bajo los artículos de opinión. Son públicos, y se muestran con tu nombre de pila: no con tu
apellido, tu dirección de email ni tu foto. Los comentarios que escribes en el debate de la competición solo los ven los
miembros con sesión iniciada, con el nombre con el que juegas (tu nombre de pila, si no tienes ninguno).</li>
<li>Si denuncias un comentario: junto a ese comentario, el identificador de tu cuenta, para que siga oculto para ti y cuente una
sola vez. El propietario de la web ve cuántos lectores denunciaron un comentario, nunca quiénes. Si bloqueas a un miembro: el
identificador de tu cuenta, el de la suya, el nombre con el que se mostraba su comentario y la fecha, para que sus comentarios
sigan ocultos para ti y puedas desbloquearlo en la página de tu cuenta. A nadie se le dice quién denunció o bloqueó a quién, y
ambas cosas se borran con tu cuenta.</li>
<li>Si envías un artículo a Opinión, y solo entonces: su título, su resumen, su texto y sus fuentes y el nombre con el que lo
firmas, guardados junto con el identificador de tu cuenta, tu nombre, tu dirección de email y si entras con Google, con Apple
o con contraseña, para que el editor sepa de quién es y pueda contestarte. Nadie más lo ve. Si se publica, el artículo muestra
el nombre con el que lo firmaste y nada más de ti.</li>
<li>Una cookie de sesión, firmada por nosotros, que mantiene tu sesión iniciada hasta 30 días. Si eliges un idioma, con cuenta o sin ella, una cookie que lo recuerda (mh_lang: inglés o español) durante un año, que leen Market Hub y sus herramientas para abrirse en ese idioma; no dice nada de ti. Ninguna cookie de publicidad ni de
seguimiento.</li>
<li>En la app de Market Hub para móviles, que es esta misma área privada con esta misma cuenta: nada más en nuestros servidores.
En tu móvil la app guarda tu sesión y nada más: un token firmado por nosotros, válido hasta 30 días, con tu nombre y tu
dirección de email, en el llavero del propio teléfono. Al salir de tu cuenta se borra. No se guarda nada de tus acciones en el
móvil, y la app no lleva ningún kit de publicidad ni de analítica. No te pide ningún permiso en el móvil: ni tu ubicación, ni
tus contactos, ni tus fotos, ni tu cámara, ni tu micrófono. Entrar con Google ahí pasa por el navegador de tu móvil, entrar con
Apple lo hace el propio iPhone, las herramientas de análisis se abren dentro de la app en una página propia (para esa página
ponemos la misma cookie de sesión que en esta web, y desaparece cuando sales de la página), y crear una cuenta muestra la misma
comprobación de Cloudflare que aquí.</li>
<li>En la app de Bot League para iPhone, que juega con esta misma cuenta: nada más en nuestros servidores que lo que ya
guarda tu bot (arriba). En tu móvil la app guarda tu sesión (el mismo tipo de token, en el llavero del teléfono), el idioma que
elegiste, si ya viste su bienvenida y, para el resumen que enseña al abrirla, el último cierre que resumió con el id público de
tu bot. Al salir de tu cuenta se borran. Si enciendes su aviso diario tras el cierre de EE. UU., lo programa el propio teléfono:
no lo envía ningún servidor nuestro ni guardamos nada para ello, su texto solo dice que ya hay cierre, y puedes apagarlo cuando
quieras. La app pide ese único permiso, y solo cuando enciendes el aviso: ni tu ubicación, ni tus contactos, ni tus fotos, ni
tu cámara, ni tu micrófono. Compartir tu bot como imagen dibuja la imagen en nuestro servidor con lo que ya enseña la
clasificación y se la pasa al menú de compartir de tu móvil; nunca sabemos con quién la compartes. Tu conversación con Claude
sobre tu bot se queda en la pantalla, y lo que escribes se envía como se explica más abajo para el chat de Bot League. La app
no lleva ningún kit de publicidad ni de analítica. Puedes borrar tu cuenta desde la app, y con ella todo lo anterior.</li>
<li>Solo en tu navegador, no en nuestros servidores: en la página Seguimiento, qué acciones elegiste ver (entre ellas las que
buscaste ahí), cuántas a la vez y cómo se dibujan los gráficos. Y en la página donde escribes para Opinión, el artículo que estás
escribiendo, hasta que lo envías. Borrar los datos de la web en tu navegador lo elimina.</li>
<li>En Options Lab, las estrategias de opciones que eliges guardar: el nombre que le das a cada una, su ticker, sus patas (calls,
puts o acciones, compradas o vendidas, cuántas, precio de ejercicio, vencimiento y el precio al que se abrió cada una) y cuándo se
guardó. Se guardan con tu cuenta y con nada más, y solo las ves tú. Una estrategia que estás construyendo pero no has guardado
se queda solo en tu navegador.</li>
<li>Nada más sobre ti en las herramientas de análisis. Fundamentals Lab, Earnings Radar, Peer Map, Playground y Options Lab, en
sus propios subdominios, leen la misma cookie de sesión solo para comprobar que has iniciado sesión; no guardan tu nombre, tu
email ni tus acciones. Un tablero que creas en Playground, y lo que escribiste para crearlo, viven en la página que los muestra
y en ningún otro sitio: recargar o cerrar la página los borra.</li>
</ul>
${h2("Qué hacemos con ello")}
<p>
Mostrártelo a ti, y a los demás miembros solo lo que elegiste compartir. Para valorar tus posiciones, el servidor pide al
proveedor de datos de mercado los precios de tus tickers; no le envía tu nombre, tu email, tu número de acciones ni tus costes.
</p>
<p>
Las frases que te describen tu cartera las escribe un modelo de lenguaje gestionado por Anthropic. Para escribirlas, el
servidor le envía de qué está hecha tu cartera y cómo se ha movido: los tickers, el peso de cada uno en porcentaje y sus
rentabilidades. No le envía tu nombre, tu email ni tu cuenta, cuántas acciones tienes, lo que pagaste ni lo que vale, y no
guardamos nada de lo que escribe el modelo. No se vende nada, y no nos conectamos a ningún bróker.
</p>
<p>
En la página Seguimiento, el servidor pide al proveedor de datos de mercado los precios de las acciones que miras y lo que
estiman los analistas de cada una. Las frases bajo las cifras de una acción las escribe el mismo modelo de lenguaje: para ellas
el servidor envía ese único ticker con sus cifras de mercado, que son las mismas para todo el mundo, y nada más. Ni quién
pregunta, ni el resto de tu lista, ni nada de lo que tienes.
</p>
<p>
En Playground, lo que escribes en el chat se envía al mismo modelo de lenguaje, junto con el tablero tal como está (las vistas
que tiene y sus tickers) y los últimos mensajes de esa conversación, para que pueda cambiar el tablero. No se envía tu nombre,
tu email ni tu cuenta, ni nada de tu cartera o de tus listas. No guardamos ni lo que escribes ni lo que contesta el modelo, y
ninguna de las dos cosas va a nuestros registros. Para dibujar una vista, el servidor pide al proveedor de datos de mercado los
precios de sus tickers.
</p>
<p>
En Bot League, el chat de la página de tu bot envía lo que escribes, los últimos mensajes de esa conversación y las reglas de
tu bot (o, mientras construyes uno ahí, su borrador y las cifras de un backtest que hayas hecho) al mismo modelo de lenguaje,
para que pueda proponer reglas nuevas o un bot nuevo; nada cambia hasta que las aplicas o envías el bot. No envía tu nombre,
tu email ni tu cuenta. No guardamos ni lo que escribes ni lo que contesta el modelo, y ninguna de las dos cosas va a nuestros
registros.
</p>
${h2("Dónde se guarda")}
<p>En una base de datos Google Cloud Firestore en la Unión Europea (región de Bélgica), a la que solo accede el servicio. Los
artículos enviados a revisión se guardan aparte, en un bucket de Google Cloud Storage en la misma región al que solo llegan el
servicio y el editor.</p>
${h2("Lo que puedes hacer")}
<p>
En ${to(l.account, "Cuenta y datos")} puedes ver y descargar todo lo que se guarda sobre ti, y borrar tu cuenta: eso la elimina
de la base de datos en el acto, quita tu cartera de la página Comunidad, elimina tus participaciones en la competición, tu bot
y su clave, y las estrategias que guardaste en Options Lab, y vacía todos los comentarios que escribiste. En un mes de la
competición que ya ha terminado, tu línea se queda donde acabó, sin ningún nombre. También puedes borrar cualquier comentario
tuyo allí donde está, y retirar una participación hasta que empiece su mes. Un artículo que enviaste se puede retirar en
${to(l.submit, "la página desde la que lo enviaste")}, y borrar tu cuenta elimina las copias guardadas para su revisión. Un
artículo tuyo que ya se publicó sigue publicado hasta que nos pidas que lo retiremos.
</p>
<p>Para preguntar por tus datos, o para que hagamos cualquiera de estas cosas por ti, mira ${to(l.contact, "Contacto")}.</p>`,
  },
);

export const terms = words(
  {
    title: "Terms",
    description: "The terms Market Hub is offered under.",
    body: (l: TermsLinks) => `
<p>Market Hub is a free site that describes markets, companies and personal finance. It is made and run by one person,
${out(l.author, "Alejandro Rodríguez Álvarez")}, from Spain. By using it you agree to
what this page says. What we keep about you, and why, is on the ${to(l.privacy, "Privacy")} page.</p>
${h2("Nothing here is advice")}
<p>Market Hub describes; it does not recommend. Nothing on the site, in its articles or in its videos is investment
advice, or a recommendation to buy, sell or hold anything. Prices can be delayed, figures come from other
providers and can be wrong, and past returns say nothing about future ones. What you do with your money is your
decision and your responsibility.</p>
${h2("Your account")}
<p>The public pages need no account. If you make one, give a name and an address that are yours, keep your password to
yourself, and use the site as a person would: no automated access that loads it down, and no attempt to reach what
belongs to somebody else. You can delete your account, and everything kept with it, at any time on
${to(l.account, "Account and data")}.</p>
${h2("What you write")}
<p>Your comments are yours and you answer for them. Do not post spam, abuse, anything unlawful, or advice to others
about what to do with their money. There is no place here for abusive or objectionable content: readers can report
a comment and block its author, we review what is reported, and we remove a comment, or close an account, that
breaks this.</p>
<p>An article you send to Opinion must be your own work, with the sources of its facts, and must not tell readers
what to do with their money. Sending it does not publish it: we read it first, we choose what runs, and we may
turn an article down. By sending it you let us edit it for length and clarity and publish it on Market Hub, with
a cover we draw for it, under the name you sign it with. It stays yours: you can publish it anywhere else, and
if you ask us we take it down.</p>
${h2("What comes from others")}
<p>Prices, charts, filings and news on the site come from other providers, and each is under its own terms. We
show them as they arrive and cannot promise they are complete, current or right.</p>
${h2("YouTube")}
<p>Market Hub's videos are on YouTube, and we upload them to our own channel with a tool that uses YouTube API
Services. By watching them, here or there, you agree to be bound by the
${out(YOUTUBE_TERMS, "YouTube Terms of Service")}. What Google does
with what it learns when you watch is in the
${out(GOOGLE_PRIVACY, "Google Privacy Policy")}.</p>
${h2("The site as it is")}
<p>Market Hub is offered as it is, free of charge and with no promise that it will always be there, always work or stay
the same. To the extent the law allows, we are not liable for a loss that comes from using it or from relying on
what it shows.</p>
${h2("Changes, and how to reach us")}
<p>If these terms change, the new ones are published on this page. Last changed on 13 October 2026. To ask anything
about them, see ${to(l.contact, "Contact")}.</p>`,
  },
  {
    title: "Condiciones",
    description: "Las condiciones con las que se ofrece Market Hub.",
    body: (l: TermsLinks) => `
<p>Market Hub es una web gratuita que describe los mercados, las empresas y las finanzas personales. La hace y la gestiona una
sola persona, ${out(l.author, "Alejandro Rodríguez Álvarez")}, desde España. Al usarla aceptas lo que dice esta página. Lo que
guardamos sobre ti, y por qué, está en la página de ${to(l.privacy, "Privacidad")}.</p>
${h2("Nada de esto es asesoramiento")}
<p>Market Hub describe; no recomienda. Nada de lo que hay en la web, en sus artículos o en sus vídeos es asesoramiento de
inversión, ni una recomendación de comprar, vender o mantener nada. Los precios pueden llegar con retraso, las cifras vienen de
otros proveedores y pueden estar mal, y las rentabilidades pasadas no dicen nada de las futuras. Lo que hagas con tu dinero es
decisión tuya y responsabilidad tuya.</p>
${h2("Tu cuenta")}
<p>Las páginas públicas no necesitan cuenta. Si creas una, da un nombre y una dirección que sean tuyos, no compartas tu
contraseña con nadie, y usa la web como lo haría una persona: nada de accesos automatizados que la sobrecarguen, y ningún intento
de llegar a lo que es de otra persona. Puedes borrar tu cuenta, y todo lo que se guarda con ella, en cualquier momento en
${to(l.account, "Cuenta y datos")}.</p>
${h2("Lo que escribes")}
<p>Tus comentarios son tuyos y respondes de ellos. No publiques spam, insultos, nada ilegal ni consejos a otros sobre qué hacer
con su dinero. Aquí no hay sitio para contenido abusivo u ofensivo: los lectores pueden denunciar un comentario y bloquear a su
autor, revisamos lo que se denuncia, y retiramos el comentario, o cerramos la cuenta, que incumpla esto.</p>
<p>Un artículo que envíes a Opinión tiene que ser obra tuya, con las fuentes de sus hechos, y no debe decir a los lectores qué
hacer con su dinero. Enviarlo no lo publica: primero lo leemos, elegimos lo que sale y podemos rechazar un artículo. Al enviarlo
nos permites editarlo para ajustar su extensión y su claridad y publicarlo en Market Hub, con una portada que dibujamos para él,
con el nombre con el que lo firmas. Sigue siendo tuyo: puedes publicarlo en cualquier otro sitio, y si nos lo pides lo
retiramos.</p>
${h2("Lo que viene de otros")}
<p>Los precios, los gráficos, los documentos regulatorios y las noticias de la web vienen de otros proveedores, y cada uno se
rige por sus propias condiciones. Los mostramos tal como llegan y no podemos prometer que estén completos, al día ni que sean
correctos.</p>
${h2("YouTube")}
<p>Los vídeos de Market Hub están en YouTube, y los subimos a nuestro propio canal con una herramienta que usa YouTube API
Services. Al verlos, aquí o allí, aceptas someterte a los ${out(YOUTUBE_TERMS, "Términos del Servicio de YouTube")}. Lo que hace
Google con lo que sabe de ti cuando ves un vídeo está en la ${out(GOOGLE_PRIVACY, "Política de Privacidad de Google")}.</p>
${h2("La web tal como es")}
<p>Market Hub se ofrece tal como es, gratis y sin ninguna promesa de que vaya a estar siempre ahí, de que funcione siempre ni
de que no cambie. En la medida en que lo permita la ley, no respondemos de una pérdida que venga de usarla o de fiarse de lo que
muestra.</p>
${h2("Cambios, y cómo contactarnos")}
<p>Si estas condiciones cambian, las nuevas se publican en esta página. Último cambio: 13 de octubre de 2026. Para preguntar
cualquier cosa sobre ellas, mira ${to(l.contact, "Contacto")}.</p>`,
  },
);

export const contact = words(
  {
    title: "Contact",
    description: "How to reach Market Hub: help with the site or the app, a comment to report, or your data.",
    body: (l: ContactLinks) => `
<p>Market Hub, the site and its app for phones, is made and run by one person. Write to
${to(`mailto:${l.email}`, l.email)} and a person reads it.</p>
${h2("Help")}
<p>Something does not work, a figure looks wrong, or you cannot get into your account: say what you did and what you
saw, and on which page or screen. We cannot send you a new password, because we never keep the one you typed, but
we can help you start again.</p>
${h2("A comment or a member to report")}
<p>Under every comment that is not yours there is <strong>Report</strong> and <strong>Block</strong>, on the site and in
the app. A reported comment is hidden from you at once and we review it; one that breaks the
${to(l.terms, "Terms")} is removed, and we may close the account of somebody who keeps writing them.
Blocking a member hides everything they write from you. If that is not enough, or it is about something other than a
comment, write to the address above.</p>
${h2("Your data")}
<p>What we keep and why is on the ${to(l.privacy, "Privacy")} page. You can see it, download it
and delete your account yourself on ${to(l.account, "Account and data")}, or in the app under
More. If you cannot, write to us from the address of the account and we do it for you.</p>`,
  },
  {
    title: "Contacto",
    description: "Cómo contactar con Market Hub: ayuda con la web o la app, un comentario que denunciar o tus datos.",
    body: (l: ContactLinks) => `
<p>Market Hub, la web y su app para móviles, la hace y la gestiona una sola persona. Escribe a
${to(`mailto:${l.email}`, l.email)} y lo leerá una persona.</p>
${h2("Ayuda")}
<p>Algo no funciona, una cifra parece estar mal o no puedes entrar en tu cuenta: cuenta qué hiciste y qué viste, y en qué
página o pantalla. No podemos enviarte una contraseña nueva, porque nunca guardamos la que escribiste, pero podemos ayudarte a
empezar de nuevo.</p>
${h2("Un comentario o un miembro que denunciar")}
<p>Debajo de cada comentario que no es tuyo tienes <strong>Denunciar</strong> y <strong>Bloquear</strong> en la web, y
<strong>Report</strong> y <strong>Block</strong> en la app. Un comentario denunciado se te oculta en el acto y lo revisamos; si
incumple las ${to(l.terms, "Condiciones")}, se retira, y podemos cerrar la cuenta de quien siga escribiéndolos. Bloquear a un
miembro te oculta todo lo que escribe. Si eso no basta, o se trata de algo que no es un comentario, escribe a la dirección de
arriba.</p>
${h2("Tus datos")}
<p>Lo que guardamos y por qué está en la página de ${to(l.privacy, "Privacidad")}. Puedes verlo, descargarlo y borrar tu cuenta
tú mismo en ${to(l.account, "Cuenta y datos")}, o en la app, en More. Si no puedes, escríbenos desde la dirección de la cuenta y
lo hacemos por ti.</p>`,
  },
);
