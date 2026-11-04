// The words of the markets page (views/Markets.astro), and the names of the market's fixed things
// the server sends in English: sectors, news kinds, what a fund holds and the instruments of the
// overview. A name the lists below do not know is shown as it came.
import { lang, words, type Lang } from ".";

export const markets = words(
  {
    title: "Markets",
    description: "US and world indices, rates, commodities, currencies, crypto, sectors and the day's movers.",
    sections: "Sections",
    tabs: { indices: "Indices", map: "Map", sectors: "Sectors", rates: "Rates", commodities: "Commodities", currencies: "Currencies", movers: "Movers" },
    indices: "Stock indices",
    map: "The S&P 500, company by company",
    mapNote: "Sized by market value, coloured by today's move",
    sectors: "US sectors",
    rates: "Treasury yields",
    ratesNote: "Change in basis points",
    commodities: "Commodities",
    currencies: "Currencies and crypto",
    movers: "Movers",
    moversNote: "US-listed stocks and funds above $5, as the data provider lists them",
    gainers: "Largest rises",
    losers: "Largest falls",
    active: "Most traded",
    asOf: (when: string) => `Figures read ${when}. They can be delayed.`,
  },
  {
    title: "Mercados",
    description: "Índices de EE. UU. y del mundo, tipos, materias primas, divisas, cripto, sectores y los valores que más se mueven en el día.",
    sections: "Secciones",
    tabs: { indices: "Índices", map: "Mapa", sectors: "Sectores", rates: "Tipos", commodities: "Materias primas", currencies: "Divisas", movers: "Más movidos" },
    indices: "Índices bursátiles",
    map: "El S&P 500, empresa a empresa",
    mapNote: "Tamaño según el valor en bolsa, color según el movimiento de hoy",
    sectors: "Sectores de EE. UU.",
    rates: "Rentabilidad de la deuda de EE. UU.",
    ratesNote: "Cambio en puntos básicos",
    commodities: "Materias primas",
    currencies: "Divisas y cripto",
    movers: "Los que más se mueven",
    moversNote: "Acciones y fondos que cotizan en EE. UU. por encima de 5 $, según los lista el proveedor de datos",
    gainers: "Mayores subidas",
    losers: "Mayores caídas",
    active: "Más negociados",
    asOf: (when: string) => `Cifras leídas el ${when}. Pueden llegar con retraso.`,
  },
);

// --- names the server sends in English -----------------------------------------------------------

const SECTORS: Record<string, string> = {
  Technology: "Tecnología",
  "Communication Services": "Comunicaciones",
  "Consumer Cyclical": "Consumo cíclico",
  "Consumer Defensive": "Consumo defensivo",
  "Financial Services": "Servicios financieros",
  Healthcare: "Salud",
  Industrials: "Industria",
  Energy: "Energía",
  Utilities: "Servicios públicos",
  "Real Estate": "Inmobiliario",
  "Basic Materials": "Materiales básicos",
  Macro: "Macro",
};

// The kinds of news (the news page's tabs).
const CATEGORIES: Record<string, string> = {
  Markets: "Mercados",
  Economy: "Economía",
  Companies: "Empresas",
  Earnings: "Resultados",
  Technology: "Tecnología",
  Commodities: "Materias primas",
};

// What a fund holds (its asset mix).
const ASSETS: Record<string, string> = {
  Stocks: "Acciones",
  Bonds: "Bonos",
  Cash: "Liquidez",
  Preferred: "Preferentes",
  Convertible: "Convertibles",
  Other: "Otros",
};

// The overview's instruments that have a name of their own in Spanish, by symbol. Indices, pairs
// and coins keep theirs.
const INSTRUMENTS: Record<string, string> = {
  VIX: "Índice de volatilidad CBOE",
  GOLD: "Oro",
  SILVER: "Plata",
  WTI: "Petróleo (WTI)",
  NATGAS: "Gas natural",
  COPPER: "Cobre",
  US10Y: "Bono de EE. UU. a 10 años",
  US2Y: "Bono de EE. UU. a 2 años",
};

const named = (table: Record<string, string>) => (name: string, l: Lang = lang()) => (l === "es" ? table[name] ?? name : name);
export const sectorName = named(SECTORS);
export const categoryName = named(CATEGORIES);
export const assetName = named(ASSETS);
export const instrumentName = (symbol: string, name: string, l: Lang = lang()) => (l === "es" ? INSTRUMENTS[symbol.toUpperCase()] ?? name : name);
// "ETF" or "Mutual fund", as the quote says what kind of fund it is.
export const fundTypeName = (type: string, l: Lang = lang()) => (l === "es" && type === "Mutual fund" ? "Fondo de inversión" : type);
