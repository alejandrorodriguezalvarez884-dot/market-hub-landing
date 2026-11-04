// Where the US stock market is in its day: closed, pre-market, open or after hours, by the clock
// of New York. It is computed here from the time alone, with no call to the data provider.
// The hours are the exchanges' regular ones: pre-market from 4:00, the session from 9:30 to
// 16:00 (13:00 on an early close), after hours for four hours more. Its words, and the lines of
// each mood, are in i18n/session.ts, in the page's language.
import { lang } from "../i18n";
import { session as sessionWords } from "../i18n/session";

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

// The weekdays as the clock below names them, Sunday first.
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

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

function waitFor(hours: number): string {
  const m = Math.max(1, Math.round(hours * 60));
  return sessionWords[lang()].wait(Math.floor(m / 1440), Math.floor((m % 1440) / 60), m % 60);
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

  const t = sessionWords[lang()];
  let next: string, wait: number, mood: string = session;
  if (session === "pre") [next, wait] = [t.opensToday(t.oclock(hours!.open)), hours!.open - now.hour];
  else if (session === "open") {
    [next, wait] = [t.closes(t.oclock(hours!.close)), hours!.close - now.hour];
    mood = now.hour - hours!.open < 0.5 ? "opening" : hours!.close - now.hour <= 1 ? "closing" : "open";
  } else if (session === "after") [next, wait] = [t.afterEnds(t.oclock(hours!.after)), hours!.after - now.hour];
  else {
    // The next day with a session: today, before the pre-market, or the first one after today.
    let [days, open] = [0, hours && now.hour < hours.pre ? hours.open : 0];
    let weekday = now.weekday;
    while (!open && days < 10) {
      const then = newYork(new Date(at.getTime() + ++days * 86400e3));
      open = hoursOf(then.day, then.weekday)?.open ?? 0;
      weekday = then.weekday;
    }
    const when = days === 0 ? t.today : days === 1 ? t.tomorrow : t.weekdays[WEEKDAYS.indexOf(weekday)];
    [next, wait] = [t.opens(when, t.oclock(open)), days * 24 + open - now.hour];
    mood = hours ? "closed" : HOLIDAYS.has(now.day) ? "holiday" : "weekend";
  }
  return { session, label: t.label[session], line: pick(t.lines[mood], now.day, now.hour, mood), next, wait: waitFor(wait), hour: now.hour, hours };
}
