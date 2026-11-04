// The words of the shared widgets (lib/widgets.ts): the tables of instruments and movers, the
// ruler's basis points and the states of a block (sample figures, not available).
import { words } from ".";

export const widgets = words(
  {
    quoteHead: { name: "Name", last: "Last", change: "Change", today: "Today", m1: "1 month", ytd: "YTD", y1: "1 year", d30: "30 days" },
    moversHead: { stock: "Stock", price: "Price", today: "Today" },
    bp: "bp",
    sample: "sample figures",
    sampleTitle: "The data provider did not answer this part: these figures are placeholders, not the market.",
    unavailable: "Not available right now.",
  },
  {
    quoteHead: { name: "Nombre", last: "Último", change: "Cambio", today: "Hoy", m1: "1 mes", ytd: "En el año", y1: "1 año", d30: "30 días" },
    moversHead: { stock: "Valor", price: "Precio", today: "Hoy" },
    bp: "pb",
    sample: "cifras de ejemplo",
    sampleTitle: "El proveedor de datos no ha respondido para esta parte: estas cifras son de relleno, no el mercado.",
    unavailable: "No está disponible ahora mismo.",
  },
);
