// The home page (views/Home.astro): the promise and the film, the five tools, My Hub, what the AI
// is for the reader, the rest of the site and what it commits to. The names of My Hub's sections
// and of the public pages are the shell's (i18n/layout.ts).
import { words } from ".";

export const home = words(
  {
    title: "Your portfolio, powered by AI",
    description:
      "AI portfolio analysis: a clear, personal reading of your own stocks in seconds, on the web and on iPhone. The Market Hub describes; it never tells you what to buy.",
    headline: "Your portfolio, powered by AI.",
    lede: "AI portfolio analysis, on your own stocks. Add what you hold or follow and get a clear, personal reading of your portfolio in seconds, on the web and on your iPhone.",
    openFree: "Open My Hub, it's free",
    exploreFive: "Explore the 5 AI tools",
    signInWith: "Sign in with Google or your email. Also on iPhone:",
    getIt: "download it on the App Store",
    noFilm: "Your browser cannot play this film. Open today's market instead.",
    filmName: "Market Hub in a minute",
    withSound: "With sound",
    seeTools: "See the tools",
    // The tools.
    toolsTitle: "Five AI tools to go deep on any US company.",
    toolsNote: "One sign-in opens them all",
    toolsLede:
      "From a company's numbers to what it just told its investors, who it really competes with and how its options are priced. Pick one and start.",
    tools: {
      fundamentals: ["The numbers", "Statements, valuation, forward multiples and an AI reading of any US company."],
      radar: ["The results release", "What a company just told its investors: guidance, demand, margins and its themes."],
      peers: ["Who does the same thing", "1,500 US companies, each next to the ones whose business reads the most alike."],
      options: ["Options, read in detail", "Implied volatility, the Greeks, and strategies of up to eight legs with their payoff."],
      playground: ["A board you ask for", "Ask in plain words for the charts and tables you want, side by side on one board."],
    },
    openTool: (name: string) => `Open ${name}`,
    toolsLive: "They live in My Hub, behind one free sign-in.",
    eachTool: "What each tool does",
    // My Hub.
    hubTitle: "Your private space, with everything inside.",
    hubLede:
      "Add the stocks you hold or follow, and My Hub turns them into your own dashboard, with the five AI tools one click away. Free, and only you see it.",
    inside: {
      overview: "What your portfolio is worth today, how it reads and how it stands against the indices.",
      analysis: "Your portfolio taken apart: what it is made of and how it moves.",
      watchlist: "The stocks you follow, side by side, with their charts and how each one stands.",
    },
    fiveTools: "Five AI tools",
    fiveToolsAbout: "Fundamentals Lab, Earnings Radar, Peer Map, Options Lab and Playground, ready to open.",
    hubSmall: "Google or email. Delete it all whenever you like.",
    ai: "AI",
    // What the AI is for the reader.
    aiTitle: "Your own AI analysis. Personal, fast, cutting-edge.",
    aiNote: "On the web and on iPhone",
    reading: [
      ["Personal", "Built around you", "No generic market talk. The AI works on your own stocks and shows you what is really going on in your portfolio."],
      ["Effortless", "Clarity in seconds", "Forget the spreadsheets and the endless charts. Open Market Hub and understand your portfolio at a glance, in plain words."],
      ["State of the art", "Cutting-edge AI, working for you", "Powered by the latest generation of AI, the kind that is changing how people understand their money. And what is yours stays yours."],
    ],
    storeLabel: "Download Market Hub on the App Store",
    downloadOnThe: "Download on the",
    phones: {
      analysis: "The Analysis screen of the app: a portfolio taken apart by sector.",
      overview: "The Overview screen of the app: a portfolio's value, its move today and a reading of it in plain sentences.",
      watchlist: "The Watchlist screen of the app: the stocks followed, each with its chart and how it stands.",
    },
    // The rest of the site.
    restTitle: "And there is more to Market Hub",
    daily: "The market, every day",
    dailyText: "Follow the day as it happens, with the news, opinion and video that matter. Open to everyone.",
    pocket: "In your pocket",
    pocketText: "Take it all with you. Market Hub is on iPhone.",
    downloadApp: "Download on the App Store",
    // What it commits to.
    promisesTitle: "What you can count on",
    promises: [
      ["It describes. It does not advise.", "No buy or sell calls, no price targets, no predictions. The AI says what the numbers and the filings show, and stops there."],
      ["The numbers come from code.", "Prices, statements and ratios are computed the same way for every company. The AI comments on them and invents none."],
      ["What you add is yours.", "My Hub keeps your name and email and the stocks you add. Never your password as you typed it, and you can delete all of it at any time."],
    ],
    startTitle: "Add your stocks. The AI does the rest.",
    exploreTools: "Explore the AI tools",
    // The dock, for visitors.
    dockAbout: " · your portfolio and five AI tools",
    free: " · free",
    openHub: "Open My Hub",
  },
  {
    title: "Tu cartera, impulsada por la IA",
    description:
      "Análisis de cartera con IA: una lectura clara y personal de tus propias acciones en segundos, en la web y en el iPhone. The Market Hub describe; nunca te dice qué comprar.",
    headline: "Tu cartera, impulsada por la IA.",
    lede: "Análisis de cartera con IA, sobre tus propias acciones. Añade lo que tienes o lo que sigues y obtén en segundos una lectura clara y personal de tu cartera, en la web y en tu iPhone.",
    openFree: "Abre My Hub, es gratis",
    exploreFive: "Las 5 herramientas de IA",
    signInWith: "Entra con Google o con tu email. También en iPhone:",
    getIt: "descárgalo en el App Store",
    noFilm: "Tu navegador no puede reproducir este vídeo. Abre el mercado de hoy.",
    filmName: "Market Hub en un minuto",
    withSound: "Con sonido",
    seeTools: "Ver las herramientas",
    toolsTitle: "Cinco herramientas de IA para conocer a fondo cualquier empresa de EE. UU.",
    toolsNote: "Un solo acceso las abre todas",
    toolsLede:
      "De las cifras de una empresa a lo que acaba de contar a sus inversores, con quién compite de verdad y a qué precio cotizan sus opciones. Elige una y empieza.",
    tools: {
      fundamentals: ["Las cifras", "Estados financieros, valoración, múltiplos a futuro y una lectura con IA de cualquier empresa de EE. UU."],
      radar: ["El comunicado de resultados", "Lo que una empresa acaba de contar a sus inversores: previsiones, demanda, márgenes y sus temas."],
      peers: ["Quién hace lo mismo", "1.500 empresas de EE. UU., cada una junto a las que describen su negocio de forma más parecida."],
      options: ["Opciones, leídas con detalle", "Volatilidad implícita, griegas y estrategias de hasta ocho patas con su perfil de pagos."],
      playground: ["Un tablero a la carta", "Pide con tus palabras los gráficos y las tablas que quieras, uno junto a otro en un mismo tablero."],
    },
    openTool: (name: string) => `Abrir ${name}`,
    toolsLive: "Están en My Hub, tras un único acceso gratuito.",
    eachTool: "Qué hace cada herramienta",
    hubTitle: "Tu espacio privado, con todo dentro.",
    hubLede:
      "Añade las acciones que tienes o que sigues y My Hub las convierte en tu propio panel, con las cinco herramientas de IA a un clic. Gratis, y solo lo ves tú.",
    inside: {
      overview: "Lo que vale hoy tu cartera, cómo se lee y cómo va frente a los índices.",
      analysis: "Tu cartera desmontada pieza a pieza: de qué está hecha y cómo se mueve.",
      watchlist: "Las acciones que sigues, una junto a otra, con sus gráficos y cómo está cada una.",
    },
    fiveTools: "Cinco herramientas de IA",
    fiveToolsAbout: "Fundamentals Lab, Earnings Radar, Peer Map, Options Lab y Playground, listas para abrir.",
    hubSmall: "Con Google o con tu email. Bórralo todo cuando quieras.",
    ai: "IA",
    aiTitle: "Tu propio análisis con IA. Personal, rápido y de vanguardia.",
    aiNote: "En la web y en el iPhone",
    reading: [
      ["Personal", "Hecho a tu medida", "Nada de charla genérica sobre el mercado. La IA trabaja con tus propias acciones y te enseña lo que de verdad pasa en tu cartera."],
      ["Sin esfuerzo", "Claridad en segundos", "Olvídate de las hojas de cálculo y de los gráficos sin fin. Abre Market Hub y entiende tu cartera de un vistazo, con palabras sencillas."],
      ["Lo último", "IA de vanguardia, trabajando para ti", "Con la última generación de IA, la que está cambiando cómo entiende la gente su dinero. Y lo tuyo sigue siendo tuyo."],
    ],
    storeLabel: "Descarga Market Hub en el App Store",
    downloadOnThe: "Descárgalo en el",
    phones: {
      analysis: "La pantalla de análisis de la app: una cartera desglosada por sectores.",
      overview: "La pantalla de resumen de la app: el valor de una cartera, su movimiento de hoy y una lectura en frases sencillas.",
      watchlist: "La pantalla de seguimiento de la app: las acciones que se siguen, cada una con su gráfico y cómo está.",
    },
    restTitle: "Y Market Hub tiene más",
    daily: "El mercado, cada día",
    dailyText: "Sigue el día según ocurre, con las noticias, la opinión y los vídeos que importan. Abierto a todos.",
    pocket: "En tu bolsillo",
    pocketText: "Llévatelo todo contigo. Market Hub está en el iPhone.",
    downloadApp: "Descárgalo en el App Store",
    promisesTitle: "Con qué puedes contar",
    promises: [
      ["Describe. No aconseja.", "Ni recomendaciones de compra o venta, ni precios objetivo, ni predicciones. La IA dice lo que muestran las cifras y los informes oficiales, y ahí se queda."],
      ["Las cifras salen del código.", "Precios, estados financieros y ratios se calculan igual para todas las empresas. La IA los comenta y no se inventa ninguno."],
      ["Lo que añades es tuyo.", "My Hub guarda tu nombre, tu email y las acciones que añades. Nunca tu contraseña tal como la escribiste, y puedes borrarlo todo cuando quieras."],
    ],
    startTitle: "Añade tus acciones. La IA hace el resto.",
    exploreTools: "Ver las herramientas de IA",
    dockAbout: " · tu cartera y cinco herramientas de IA",
    free: " · gratis",
    openHub: "Abrir My Hub",
  },
);
