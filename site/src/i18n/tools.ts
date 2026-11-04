// About the tools (views/Tools.astro): what each analysis tool of the brand does. The names of the
// tools are brands and stay as they are.
import { words } from ".";

type Tool = { about: string; points: string[] };

export const tools = words(
  {
    title: "Tools",
    description:
      "The analysis tools of The Market Hub: Fundamentals Lab, Earnings Radar, Peer Map, Options Lab and Playground, for US-listed companies and the market.",
    h1: "The analysis tools",
    lede: "Five tools for US-listed companies and the market. They open with your Market Hub sign-in.",
    open: (name: string) => `Open ${name}`,
    fundamentals: {
      about: "The numbers",
      points: [
        "Statements, margins and returns on capital, year by year",
        "Valuation against the company's own history",
        "Forward multiples from the analysts' consensus",
        "Technical picture and side-by-side comparison of up to five companies",
        "An AI reading that comments the numbers and invents none",
      ],
    } as Tool,
    radar: {
      about: "The results release",
      points: [
        "Reads a company's latest results release when you ask",
        "Is guidance raised or cut, is demand weakening, are margins under pressure",
        "Which themes the company talks about",
        "Trends across 99 large companies since 2021",
      ],
    } as Tool,
    peers: {
      about: "Who does the same thing",
      points: [
        "The 1,500 largest US companies on one map, each next to the ones whose annual report describes the most similar business",
        "Each company's ten closest peers, and how alike they are",
        "Coloured by how far each price has moved: the day, the week, the month, the year to date or one year",
      ],
    } as Tool,
    options: {
      about: "Options, read in detail",
      points: [
        "Calls and puts with implied volatility, the Greeks, breakeven and risk-neutral odds",
        "The volatility smile, open interest and the term structure",
        "Strategies of up to eight legs: payoff, breakevens, Greeks and probability of profit",
        "Save your strategies and come back to them",
      ],
    } as Tool,
    playground: {
      about: "A market board you ask for",
      points: [
        "Ask in plain words for the charts and tables you want to see",
        "Price charts, comparisons, the day's moves on one scale and tables of figures, side by side on one board",
        "Every figure comes from market data, not from the AI",
      ],
    } as Tool,
  },
  {
    title: "Herramientas",
    description:
      "Las herramientas de análisis de The Market Hub: Fundamentals Lab, Earnings Radar, Peer Map, Options Lab y Playground, para las empresas que cotizan en EE. UU. y el mercado.",
    h1: "Las herramientas de análisis",
    lede: "Cinco herramientas para las empresas que cotizan en EE. UU. y el mercado. Se abren con tu cuenta de Market Hub.",
    open: (name: string) => `Abrir ${name}`,
    fundamentals: {
      about: "Las cifras",
      points: [
        "Estados financieros, márgenes y rentabilidad sobre el capital, año a año",
        "La valoración frente a la propia historia de la empresa",
        "Múltiplos a futuro según el consenso de analistas",
        "El análisis técnico y la comparación lado a lado de hasta cinco empresas",
        "Una lectura con IA que comenta las cifras y no se inventa ninguna",
      ],
    },
    radar: {
      about: "El comunicado de resultados",
      points: [
        "Lee el último comunicado de resultados de una empresa cuando lo pides",
        "Si sube o recorta sus previsiones, si se debilita la demanda, si los márgenes están bajo presión",
        "De qué temas habla la empresa",
        "Tendencias en 99 grandes empresas desde 2021",
      ],
    },
    peers: {
      about: "Quién hace lo mismo",
      points: [
        "Las 1.500 mayores empresas de EE. UU. en un mapa, cada una junto a aquellas cuyo informe anual describe el negocio más parecido",
        "Las diez empresas más parecidas a cada una, y cuánto se parecen",
        "Coloreado según cuánto se ha movido cada precio: el día, la semana, el mes, lo que va de año o un año",
      ],
    },
    options: {
      about: "Opciones, leídas con detalle",
      points: [
        "Calls y puts con volatilidad implícita, griegas, punto de equilibrio y probabilidades neutrales al riesgo",
        "La sonrisa de volatilidad, el interés abierto y la estructura temporal",
        "Estrategias de hasta ocho patas: perfil de pagos, puntos de equilibrio, griegas y probabilidad de beneficio",
        "Guarda tus estrategias y vuelve a ellas",
      ],
    },
    playground: {
      about: "Un tablero de mercado que pides tú",
      points: [
        "Pide con tus palabras los gráficos y las tablas que quieres ver",
        "Gráficos de precios, comparaciones, los movimientos del día en una misma escala y tablas de cifras, lado a lado en un tablero",
        "Todas las cifras salen de los datos de mercado, no de la IA",
      ],
    },
  },
);
