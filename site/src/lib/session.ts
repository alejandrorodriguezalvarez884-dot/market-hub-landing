// Where the US stock market is in its day: closed, pre-market, open or after hours, by the clock
// of New York. It is computed here from the time alone, with no call to the data provider.
// The hours are the exchanges' regular ones: pre-market from 4:00, the session from 9:30 to
// 16:00 (13:00 on an early close), after hours for four hours more.

export type Session = "closed" | "pre" | "open" | "after";
export type Status = {
  session: Session;
  label: string; // "Closed", "Pre-market", "Open", "After hours"
  line: string; // the mood of the hour
  next: string; // what comes next and when: "Opens Monday at 9:30 AM New York time"
  wait: string; // how long until then: "in 13h 20m"
  hour: number; // the hour in New York, with its fraction: where the dial's hand points
  hours: { pre: number; open: number; close: number; after: number } | null; // today's, or null on a day without a session
};

// Days the exchanges do not open, and the days they close at 13:00. Add a year before it starts.
const HOLIDAYS = new Set([
  "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
  "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
]);
const EARLY = new Set(["2026-11-27", "2026-12-24", "2027-11-26"]);

// The lines of each mood, written by hand. The page picks among them by the clock; nothing writes them anew.
const LINES: Record<string, string[]> = {
  closed: [
    "The thrill is gone. It's going to be a long wait.",
    "Lights out. The tape has gone quiet.",
    "Nothing moves until the bell. Breathe.",
    "The floor is empty. See you at the open.",
    "Silence. The market is asleep.",
    "The screens are dark. The numbers can wait.",
    "Even tickers need their sleep.",
    "No bids, no asks, no noise.",
    "The market clocked out. Fair enough.",
    "Somewhere, a trader is finally having dinner.",
    "Closed. The charts will still be there tomorrow.",
    "The bell is resting. So is everything else.",
    "Quiet hours. Prices are holding their breath.",
    "Nothing to see here until the morning.",
    "The tape stopped. The world did not.",
    "Night shift: nobody. Next shift: 4 AM.",
    "The order book is shut for the night.",
    "Asleep at the exchange. Do not disturb.",
    "All quiet on Wall Street.",
    "The closing bell had the last word.",
    "Out of office until the pre-market.",
    "The market is off the clock.",
    "Stillness. Yesterday's prices, frozen in place.",
    "The numbers are parked for the night.",
  ],
  weekend: [
    "It's the weekend. Even the market rests.",
    "Two days without a bell. You will survive.",
    "No bell today. Go outside.",
    "Weekend rules: no ticks, no tape.",
    "The market is away until its next session.",
    "Closed for the weekend. The charts will keep.",
    "No opening bell today. Enjoy the silence.",
    "Wall Street is out. Back after the weekend.",
    "A weekend is one long candle with no wicks.",
    "The tape is on a break. Take one too.",
    "Nothing trades today. Something else can happen.",
    "The next bell will come soon enough.",
    "Prices are frozen until the next bell.",
    "The exchange is dark. The sun is not.",
  ],
  holiday: [
    "A holiday. The bell stays silent today.",
    "The market took the day off. So can you.",
    "Holiday hours: none.",
    "No session today. The calendar says rest.",
    "Closed for the holiday. Back next session.",
    "The exchanges are celebrating. Nothing trades.",
    "A day off for the tape.",
    "Today the bell gets a holiday too.",
  ],
  pre: [
    "Engines warming up.",
    "Hold on tight, it's about to begin.",
    "Coffee first. The bell is close.",
    "The early birds are already at it.",
    "Stretching before the bell.",
    "The first orders are trickling in.",
    "Lights on. The floor is filling up.",
    "Thin trading, big anticipation.",
    "The overture before the opening bell.",
    "Screens on, sleeves up.",
    "The day is loading.",
    "Early prints. The real show starts at the bell.",
    "The market is clearing its throat.",
    "Pre-market: the rehearsal before the play.",
    "Quiet moves before the loud ones.",
    "The countdown to the bell is on.",
    "Somewhere, a second coffee is being poured.",
    "Warming up. Volume comes later.",
    "The tape is awake, barely.",
    "Dawn on Wall Street.",
    "A few early trades are testing the water.",
    "Almost time. Almost.",
    "The bell is tuning up.",
    "Headlines first, prices next.",
  ],
  opening: [
    "And they're off.",
    "The bell just rang. Here we go.",
    "Open. The first minutes are always loud.",
    "The opening rush is on.",
    "Doors open. Everybody in at once.",
    "First prints of the day.",
    "The session has begun.",
    "Out of the gate.",
  ],
  open: [
    "The bell has rung. Eyes on the tape.",
    "It's on. Stay sharp.",
    "Every tick counts now.",
    "Full focus. The market is talking.",
    "Heads down. These are the hours that matter.",
    "The tape is running at full speed.",
    "Buyers and sellers, hard at work.",
    "Prices are being made right now.",
    "The session is in full swing.",
    "Live from the floor: everything.",
    "The tape never idles.",
    "Millions of orders, one price at a time.",
    "The market is thinking out loud.",
    "This is the part with all the moving numbers.",
    "Open for business.",
    "The numbers are alive.",
    "Nothing is settled until the close.",
    "The crowd is in. The tape is busy.",
    "Tick by tick, the day takes shape.",
    "The ticker has a lot to say today.",
    "Bids up, offers down, repeat.",
    "The floor is humming.",
    "Somewhere a chart is being redrawn.",
    "In session. The story is still being written.",
  ],
  closing: [
    "Last hour. This is where days are decided.",
    "The final stretch. Nobody blinks now.",
    "Closing time is coming.",
    "The last hour. Volume is back.",
    "One hour to go. The tape speeds up.",
    "The day is running out of minutes.",
    "The closing bell is warming up.",
    "Final laps.",
    "The home stretch of the session.",
    "Whatever today was, it's almost written.",
  ],
  after: [
    "Time to reflect.",
    "Time to think through tomorrow's move.",
    "The bell rang. Now, the replay.",
    "The noise fades. What did today say?",
    "Deep breath. Tomorrow starts tonight.",
    "The closing bell has spoken.",
    "After hours: the encore nobody asked for.",
    "The crowd went home. A few stayed.",
    "Earnings season lives in these hours.",
    "Thin trading, long shadows.",
    "The day is in the books.",
    "The score is in. The talk begins.",
    "Lights dimming on the floor.",
    "The session is over. The tape is not, quite.",
    "A quieter market, still awake.",
    "The close is behind us. The numbers are settling.",
    "Late prints for the night owls.",
    "Today's candle is closed.",
    "The bell rang. The story continues in small print.",
    "Evening on Wall Street.",
    "Winding down, one trade at a time.",
    "What moved today has moved.",
    "The day's final answer is in.",
    "Stragglers only from here.",
  ],
};
const LABEL: Record<Session, string> = { closed: "Closed", pre: "Pre-market", open: "Open", after: "After hours" };

const clock = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York", hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit", weekday: "long",
});

// The wall clock of New York at an instant.
function newYork(at: Date) {
  const p = Object.fromEntries(clock.formatToParts(at).map((x) => [x.type, x.value]));
  return { day: `${p.year}-${p.month}-${p.day}`, weekday: p.weekday, hour: +p.hour + +p.minute / 60 + +p.second / 3600 };
}

const hoursOf = (day: string, weekday: string) =>
  weekday === "Saturday" || weekday === "Sunday" || HOLIDAYS.has(day) ? null
    : { pre: 4, open: 9.5, close: EARLY.has(day) ? 13 : 16, after: EARLY.has(day) ? 17 : 20 };

const oclock = (h: number) => `${Math.floor(h) % 12 || 12}:${String(Math.round((h % 1) * 60)).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;

function waitFor(hours: number): string {
  const m = Math.max(1, Math.round(hours * 60));
  const [d, h, min] = [Math.floor(m / 1440), Math.floor((m % 1440) / 60), m % 60];
  return `in ${d ? `${d}d ${h}h` : h ? `${h}h ${String(min).padStart(2, "0")}m` : `${min}m`}`;
}

// A line holds for twenty minutes and then gives way to another: picked from the day and the time,
// so everybody reads the same one, and never the one that was just up.
const TURNS_AN_HOUR = 3;
function pick(lines: string[], day: string, hour: number, mood: string): string {
  const at = (turn: number) => {
    let n = 0;
    for (const c of `${day} ${turn} ${mood}`) n = (n * 31 + c.charCodeAt(0)) >>> 0;
    return n % lines.length;
  };
  const turn = Math.floor(hour * TURNS_AN_HOUR);
  const i = at(turn);
  return lines[lines.length > 1 && i === at(turn - 1) ? (i + 1) % lines.length : i];
}

export function status(at = new Date()): Status {
  const now = newYork(at);
  const hours = hoursOf(now.day, now.weekday);
  const session: Session = !hours || now.hour < hours.pre || now.hour >= hours.after ? "closed"
    : now.hour < hours.open ? "pre" : now.hour < hours.close ? "open" : "after";

  let next: string, wait: number, mood: string = session;
  if (session === "pre") [next, wait] = [`Opens at ${oclock(hours!.open)} New York time`, hours!.open - now.hour];
  else if (session === "open") {
    [next, wait] = [`Closes at ${oclock(hours!.close)} New York time`, hours!.close - now.hour];
    mood = now.hour - hours!.open < 0.5 ? "opening" : hours!.close - now.hour <= 1 ? "closing" : "open";
  } else if (session === "after") [next, wait] = [`After-hours trading ends at ${oclock(hours!.after)} New York time`, hours!.after - now.hour];
  else {
    // The next day with a session: today, before the pre-market, or the first one after today.
    let [days, open] = [0, hours && now.hour < hours.pre ? hours.open : 0];
    let weekday = now.weekday;
    while (!open && days < 10) {
      const then = newYork(new Date(at.getTime() + ++days * 86400e3));
      open = hoursOf(then.day, then.weekday)?.open ?? 0;
      weekday = then.weekday;
    }
    [next, wait] = [`Opens ${days === 0 ? "today" : days === 1 ? "tomorrow" : weekday} at ${oclock(open)} New York time`, days * 24 + open - now.hour];
    mood = hours ? "closed" : HOLIDAYS.has(now.day) ? "holiday" : "weekend";
  }
  return { session, label: LABEL[session], line: pick(LINES[mood], now.day, now.hour, mood), next, wait: waitFor(wait), hour: now.hour, hours };
}
