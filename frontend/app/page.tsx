"use client";

import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Chrome, Ticker } from "./chrome";
import {
  fetchFlightOptions,
  fetchStayOptions,
  predictFlight,
  predictStay,
  searchAirports,
  searchLiveFlights,
  searchLiveStays,
  searchPackages,
  type AirportHit,
  type FlightOption,
  type FlightOptions,
  type FlightQuery,
  type FlightSearch,
  type HotelOptions,
  type PackageOffer,
  type PackageSearch,
  type PackageTier,
  type StayOption,
  type StaySearch,
} from "@/lib/api";

/* ---------------------------------------------------------------- primitives */

const CITIES = ["Delhi", "Mumbai", "Bangalore", "Kolkata", "Chennai", "Hyderabad"];

function Field({
  cap,
  className,
  aside,
  children,
}: {
  cap: string;
  className: string;
  aside?: string;
  children: ReactNode;
}) {
  return (
    <label className={`field ${className}`}>
      <span className="cap mini">
        {cap}
        {aside ? <i>{aside}</i> : null}
      </span>
      {children}
    </label>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <select
      className="control display"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {prettify(o)}
        </option>
      ))}
    </select>
  );
}

function prettify(v: string): string {
  const map: Record<string, string> = {
    GO_FIRST: "Go First",
    Air_India: "Air India",
    two_or_more: "2 or more",
    zero: "Non-stop",
    live: "Live",
    replay: "Demo",
    flights: "Flights",
    stays: "Stays",
  };
  return map[v] ?? v.replace(/_/g, " ");
}

function Seg({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <div className="seg" role="radiogroup">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          role="radio"
          aria-checked={value === o}
          className={value === o ? "on" : ""}
          onClick={() => onChange(o)}
        >
          {prettify(o)}
        </button>
      ))}
    </div>
  );
}

function Stepper({
  value,
  onChange,
  min,
  max,
  name,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  name?: string;
}) {
  const clamp = (v: number) => Math.min(max, Math.max(min, v));
  const who = name ? ` ${name.toLowerCase()}` : "";
  return (
    <div className="stepper">
      <button
        type="button"
        aria-label={`Decrease${who}`}
        disabled={value <= min}
        onClick={() => onChange(clamp(value - 1))}
      >
        –
      </button>
      <span className="val" aria-live="polite">
        {value}
      </span>
      <button
        type="button"
        aria-label={`Increase${who}`}
        disabled={value >= max}
        onClick={() => onChange(clamp(value + 1))}
      >
        +
      </button>
    </div>
  );
}

/* count-up numeral */
function Money({
  value,
  cur = "₹",
  locale = "en-IN",
}: {
  value: number;
  cur?: string;
  locale?: string;
}) {
  const [shown, setShown] = useState(0);
  const from = useRef(0);

  useEffect(() => {
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      from.current = value;
      setShown(value);
      return;
    }
    const start = from.current;
    const t0 = performance.now();
    const D = 950;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / D);
      const e = 1 - Math.pow(1 - p, 4);
      const v = start + (value - start) * e;
      setShown(v);
      if (p < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return (
    <span className="result-price">
      <span className="cur">{cur}</span>
      {Math.round(shown).toLocaleString(locale)}
    </span>
  );
}

/* ---------------------------------------------------------------- type-to-search airport */

function AirportField({
  cap,
  value,
  onPick,
}: {
  cap: string;
  value: AirportHit | null;
  onPick: (a: AirportHit | null) => void;
}) {
  const [text, setText] = useState(value?.code ?? "");
  const [hits, setHits] = useState<AirportHit[]>([]);
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(-1);
  const [err, setErr] = useState<string | null>(null);
  const listId = `ac-${cap.toLowerCase().replace(/\s+/g, "-")}`;

  useEffect(() => {
    if (value) setText(value.code);
  }, [value?.code]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const q = text.trim();
    if (!q || (value && q.toUpperCase() === value.code.toUpperCase())) {
      setHits([]);
      setOpen(false);
      setErr(null);
      return;
    }
    let alive = true;
    const t = setTimeout(() => {
      searchAirports(q)
        .then((r) => {
          if (!alive) return;
          setHits(r.results);
          setCursor(-1);
          setOpen(true);
          setErr(r.results.length ? null : `No airports match “${q}”`);
        })
        .catch((e) => {
          if (!alive) return;
          setHits([]);
          setOpen(true);
          setErr((e as Error).message || "Airport lookup failed");
        });
    }, 140);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (h: AirportHit) => {
    setText(h.code);
    setHits([]);
    setCursor(-1);
    setOpen(false);
    onPick(h);
  };

  const close = () => {
    // allow a typed code to resolve itself before the dropdown folds
    setOpen(false);
    const q = text.trim().toUpperCase();
    if (!value && q.length === 3) {
      const exact = hits.find((h) => h.code === q);
      if (exact) pick(exact);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (open && hits.length > 0) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setCursor((c) => {
          const next =
            e.key === "ArrowDown"
              ? c + 1
              : c <= 0
                ? hits.length - 1
                : c - 1;
          return (next + hits.length) % hits.length;
        });
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (cursor >= 0 && cursor < hits.length) {
          pick(hits[cursor]);
          return;
        }
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        setCursor(-1);
        return;
      }
    }
    if (e.key === "Enter") {
      // Enter on a bare input should not submit; fold the list instead
      e.preventDefault();
      close();
    }
  };

  return (
    <Field cap={cap} className="select span5 ac" aside={value?.city}>
      <input
        className="control display"
        id={`in-${listId}`}
        value={text}
        placeholder="city, airport, code"
        autoCapitalize="characters"
        autoCorrect="off"
        spellCheck={false}
        role="combobox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={
          open && cursor >= 0 ? `${listId}-${cursor}` : undefined
        }
        aria-autocomplete="list"
        autoComplete="off"
        onChange={(e) => {
          setText(e.target.value);
          onPick(null);
        }}
        onFocus={() => hits.length > 0 && setOpen(true)}
        onBlur={close}
        onKeyDown={onKeyDown}
      />
      {open && hits.length > 0 && (
        <div
          className="ac-list display"
          id={listId}
          role="listbox"
          aria-labelledby={`in-${listId}`}
        >
          {hits.map((h, i) => (
            <div
              key={h.code}
              id={`${listId}-${i}`}
              className={`ac-item${i === cursor ? " active" : ""}`}
              role="option"
              aria-selected={i === cursor}
              tabIndex={-1}
              onMouseDown={(e) => {
                e.preventDefault(); // keep input focus until picked
                pick(h);
              }}
            >
              <span className="ac-code">{h.code}</span>
              <span className="ac-name">
                {h.name}
                <i>
                  {h.city ?? h.country}
                </i>
              </span>
            </div>
          ))}
        </div>
      )}
      {open && hits.length === 0 && err && (
        <div className="ac-list ac-note display" role="status">
          /// {err}
        </div>
      )}
    </Field>
  );
}

/* ---------------------------------------------------------------- misc formatters */

const CUR_SYMBOL: Record<string, string> = {
  INR: "₹",
  USD: "$",
  EUR: "€",
  GBP: "£",
};

function symbol(currency: string): string {
  return CUR_SYMBOL[currency] ?? `${currency} `;
}

function localeOf(currency: string): string {
  return currency === "INR" ? "en-IN" : "en-US";
}

function clockOf(when: string): string {
  const m = /\b(\d{2}:\d{2})\b/.exec(when ?? "");
  return m ? m[1] : "—";
}

function hm(minutes: number | null): string {
  if (minutes == null) return "—";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h ${m ? `${m}m` : ""}`.trim() : `${m}m`;
}

function daystamp(offset: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/* fare-history sparkline — accent blue, no green */
function Spark({ points }: { points: [number, number][] }) {
  if (points.length < 2) return null;
  const w = 220;
  const h = 56;
  const ys = points.map((p) => p[1]);
  const lo = Math.min(...ys);
  const hi = Math.max(...ys);
  const span = hi - lo || 1;
  const step = w / (points.length - 1);
  const xy = points.map(([_, y], i) => [
    i * step,
    h - 6 - ((y - lo) / span) * (h - 12),
  ]);
  const draw = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const [dx, dy] = xy[xy.length - 1];
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} width={w} height={h}>
      <polyline points={draw} fill="none" />
      <circle cx={dx} cy={dy} r="3.4" />
    </svg>
  );
}

/* board badges (results provenance, phrased for travellers) */
function Tags({ search }: { search: { cached?: boolean; fetched_on: string } }) {
  const kind = search.cached ? "Cached results" : "Live results";
  const cls = search.cached ? "tag" : "tag live";
  return (
    <div className="board-tags">
      <span className={cls}>{kind}</span>
      <span className="tag dim">updated {search.fetched_on}</span>
    </div>
  );
}

/* ---------------------------------------------------------------- page types */

type Panel = "flights" | "stays" | "packages" | "predict";
type Result =
  | { kind: "flight"; price: number; meta: [string, string][] }
  | { kind: "stay"; price: number; meta: [string, string][] }
  | { kind: "error"; message: string };

const TICKER: string[][] = [
  ["Delhi", "Mumbai", "4,222", "Economy · 30 days out"],
  ["Bangalore", "Kolkata", "8,131", "Business cabin"],
  ["Chennai", "Hyderabad", "1,758", "Non-stop"],
  ["Delhi", "Mumbai", "49,987", "Business · tomorrow"],
  ["Kolkata", "Bangalore", "6,060", "Direct"],
  ["Hyderabad", "Delhi", "12,482", "One stop"],
];

/* ---------------------------------------------------------------- flight board row */

function Itin({ o, cur, loc }: { o: FlightOption; cur: string; loc: string }) {
  const legs = o.legs ?? [];
  const first = legs[0];
  const last = legs[legs.length - 1];
  const logo = o.logo ?? first?.logo ?? "";
  const noStop = legs.length <= 1;
  return (
    <div className="itin">
      <div className="itin-left">
        {logo && <img className="itin-logo" src={logo} alt="" loading="lazy" />}
        <div>
          <div className="itin-times">
            <b>{clockOf(first?.dep_time ?? "")}</b>
            <span className="itin-arrow">→</span>
            <b>{clockOf(last?.arr_time ?? "")}</b>
          </div>
          <div className="mini dim">
            {first?.dep_code ?? "?"} — {last?.arr_code ?? "?"} · {hm(o.duration)}
          </div>
        </div>
      </div>
      <div className="itin-mid">
        <div className="itin-airline">{first?.airline ?? "—"}</div>
        <div className="mini dim">
          {legs.map((l) => l.flight).filter(Boolean).join(" · ")}
          {noStop
            ? " · non-stop"
            : ` · ${o.layovers.map((l) => l.name ?? "?").join(", ")}`}
        </div>
        {legs.length > 1 && (
          <div className="mini dim">
            leg times: {legs.map((l) => hm(l.duration)).join(" · ")}
          </div>
        )}
      </div>
      <div className="itin-right">
        <span className="fare display">
          <i>{cur}</i>
          {o.price != null ? o.price.toLocaleString(loc) : "—"}
        </span>
        {o.carbon != null && (
          <span className={`carbon mini ${o.carbon <= 0 ? "" : "over"}`}>
            carbon {o.carbon > 0 ? "+" : ""}
            {o.carbon}%
          </span>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- stay board card */

function StayCard({ s, cur }: { s: StayOption; cur: string }) {
  const pic = s.images[0];
  const body = (
    <div className="stay-card">
      <div className="stay-ph">
        {pic?.thumb ? (
          <img src={pic.thumb} alt={s.name} loading="lazy" />
        ) : null}
        {s.deal && <span className="stay-deal display">{s.deal}</span>}
        {s.rating ? (
          <span className="stay-rating display">
            {s.rating.toFixed(1)}
          </span>
        ) : null}
      </div>
      <div className="stay-body">
        <div className="stay-name">
          {s.class_num ? (
            <span className="stars" aria-label={`${s.class_num}-star`}>
              {"★".repeat(Math.min(5, s.class_num))}
            </span>
          ) : null}
          <b>{s.name}</b>
        </div>
        <div className="mini dim"><i>{s.type} · {(s.reviews ?? 0).toLocaleString("en-US")} reviews</i></div>
        <div className="stay-rate">
          <span className="p display">
            <i>{cur}</i>
            {s.price != null ? s.price.toLocaleString("en-IN") : s.price_display ?? "—"}
          </span>
          <span className="sub mini">/ night</span>
        </div>
        {s.total_display && (
          <div className="mini dim">est. total for the stay — {s.total_display}</div>
        )}
        <div className="chiprow">
          {s.amenities.slice(0, 4).map((a) => (
            <span className="chip mini" key={a}>{a}</span>
          ))}
        </div>
        <div className="stay-foot mini">
          <span>check-in {s.check_in_time ?? "—"} · check-out {s.check_out_time ?? "—"}</span>
          {s.location_rating ? <span>location {s.location_rating}/5</span> : null}
        </div>
      </div>
    </div>
  );
  return s.link ? (
    <a href={s.link} target="_blank" rel="noreferrer">{body}</a>
  ) : body;
}

/* ---------------------------------------------------------------- package tier card */

const TIER_COPY: Record<PackageTier, { label: string; blurb: string }> = {
  saver: { label: "The Essential", blurb: "Our most considered value — the best fare paired with a well-priced stay" },
  balanced: { label: "The Curated", blurb: "The finest-rated stay that still sits comfortably within your budget" },
  comfort: { label: "The Grand", blurb: "The top-rated stay of the collection, whatever the total comes to" },
};

function PackageCard({
  p,
  cur,
  loc,
  budget,
}: {
  p: PackageOffer;
  cur: string;
  loc: string;
  budget: number;
}) {
  const f = p.flight;
  const s = p.stay;
  const money = (v: number) => `${cur}${Math.round(v).toLocaleString(loc)}`;
  return (
    <article className={`pkg-card ${p.tier}${p.within_budget ? "" : " over"}`}>
      <header className="pkg-head">
        <div>
          <div className="cap mini">{TIER_COPY[p.tier].label}</div>
          <span className="pkg-blurb">{TIER_COPY[p.tier].blurb}</span>
        </div>
        <span className={`tag${p.within_budget ? " live" : ""}`}>
          {p.within_budget ? "within budget" : "over budget"}
        </span>
      </header>

      <div className="pkg-total">
        <Money value={p.total} cur={cur} locale={loc} />
        <span className="mini dim">all-in · {p.flight.nonstop ? "non-stop" : `${p.flight.stops} stop${p.flight.stops === 1 ? "" : "s"}`}</span>
      </div>

      <div className="pkg-split mini">
        <span>flight <b>{money(p.breakdown.flight)}</b></span>
        <span className="dot">+</span>
        <span>stay <b>{money(p.breakdown.hotel)}</b></span>
      </div>
      <div className={`pkg-note mini${p.within_budget ? " dim" : " over"}`}>
        {p.within_budget
          ? `${money(p.headroom ?? 0)} left under the ${money(budget)} budget`
          : `${money(p.over_by ?? 0)} over the ${money(budget)} budget`}
      </div>

      <div className="pkg-leg">
        <div className="cap mini">Flight</div>
        <div className="pkg-flight">
          {f.airline_logo ? (
            <img className="itin-logo" src={f.airline_logo} alt="" loading="lazy" />
          ) : null}
          <div>
            <div className="pkg-flight-route">
              <b>{f.dep_code ?? "?"}</b>
              <span className="itin-arrow">→</span>
              <b>{f.arr_code ?? "?"}</b>
              <span className="mini dim">
                {" "}{clockOf(f.dep_time ?? "")} – {clockOf(f.arr_time ?? "")}
              </span>
            </div>
            <div className="mini dim">
              {f.airline ?? "—"} · {f.nonstop
                ? "non-stop"
                : `${f.stops} stop${f.stops === 1 ? "" : "s"}`} · {hm(f.duration)}
            </div>
          </div>
        </div>
      </div>

      <div className="pkg-leg">
        <div className="cap mini">Stay</div>
        <div className="pkg-stay">
          {s.image ? <img src={s.image} alt="" loading="lazy" /> : null}
          <div>
            <div className="pkg-stay-name">
              {s.stars ? (
                <span className="stars" aria-label={`${s.stars}-star`}>
                  {"★".repeat(Math.min(5, s.stars))}
                </span>
              ) : null}
              <b>{s.name ?? "—"}</b>
              {s.rating ? <span className="tag hot">{s.rating.toFixed(1)}</span> : null}
            </div>
            <div className="mini dim">
              {s.type ?? "stay"}{s.area ? ` · near ${s.area}` : ""} · {s.nightly_note}
            </div>
            <div className="chiprow">
              {s.amenities.slice(0, 4).map((a) => (
                <span className="chip mini" key={a}>{a}</span>
              ))}
            </div>
            {s.link ? (
              <a className="pkg-link mini" href={s.link} target="_blank" rel="noreferrer">
                View property ↗
              </a>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}

/* ---------------------------------------------------------------- default form values */

function flightHuntDefaults() {
  return {
    origin: null as AirportHit | null,
    destination: null as AirportHit | null,
    outbound: daystamp(9),
    ret: daystamp(14),
    cabin: "economy",
    adults: 2,
    kids: 0,
  };
}

function stayHuntDefaults() {
  return {
    q: "",
    checkIn: daystamp(9),
    checkOut: daystamp(11),
    adults: 2,
    kids: 0,
    sort: "3",
  };
}

function packageHuntDefaults() {
  return {
    origin: null as AirportHit | null,
    destination: null as AirportHit | null,
    q: "",
    outbound: daystamp(9),
    ret: daystamp(14),
    budget: "60000",
    cabin: "economy",
    adults: 2,
    kids: 0,
  };
}

/* ---------------------------------------------------------------- page */

export default function Home() {
  /* ----- global panel ----- */
  const [panel, setPanel] = useState<Panel>("flights");

  /* ----- live flight search ----- */
  const [flight, setFlight] = useState<FlightSearch | null>(null);
  const [flightError, setFlightError] = useState<string | null>(null);
  const [flightNote, setFlightNote] = useState<string | null>(null);
  const [fPending, setFPending] = useState(false);
  const [fh, setFh] = useState(flightHuntDefaults);
  const flightRef = useRef<HTMLDivElement>(null);
  const [stay, setStay] = useState<StaySearch | null>(null);
  const [stayError, setStayError] = useState<string | null>(null);
  const [stayNote, setStayNote] = useState<string | null>(null);
  const [sPending, setSPending] = useState(false);
  const [sh, setSh] = useState(stayHuntDefaults);
  const stayRef = useRef<HTMLDivElement>(null);

  /* ----- package builder (flight + stay, priced as tiers) ----- */
  const [pkg, setPkg] = useState<PackageSearch | null>(null);
  const [pkgError, setPkgError] = useState<string | null>(null);
  const [pkgNote, setPkgNote] = useState<string | null>(null);
  const [pPending, setPPending] = useState(false);
  const [pk, setPk] = useState(packageHuntDefaults);
  const pkgRef = useRef<HTMLDivElement>(null);

  /* ----- legacy predict console ----- */
  const [predictKind, setPredictKind] = useState<"flights" | "stays">("flights");
  const [flightOptions, setFlightOptions] = useState<FlightOptions | null>(null);
  const [stayOptions, setStayOptions] = useState<HotelOptions | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [pending, setPending] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchFlightOptions()
      .then(setFlightOptions)
      .catch(() => {});
    fetchStayOptions().then(setStayOptions).catch(() => {});
  }, []);

  const patchFh = (kv: Partial<typeof fh>) => setFh((s) => ({ ...s, ...kv }));
  const patchSh = (kv: Partial<typeof sh>) => setSh((s) => ({ ...s, ...kv }));
  const patchPk = (kv: Partial<typeof pk>) => setPk((s) => ({ ...s, ...kv }));

  /* ----- legacy flight state ----- */
  const [flightPred, setFlightPred] = useState<FlightQuery>({
    source_city: "Delhi",
    destination_city: "Mumbai",
    airline: "Vistara",
    departure_time: "Morning",
    arrival_time: "Evening",
    stops: "zero",
    class: "Economy",
    duration: 2.25,
    days_left: 30,
  });

  const patchFlight = (kv: Partial<FlightQuery>) =>
    setFlightPred((f) => ({ ...f, ...kv }));

  const swapCities = () =>
    patchFlight({
      source_city: flightPred.destination_city,
      destination_city: flightPred.source_city,
    });

  /* ----- legacy stays state ----- */
  const [stayPred, setStayPred] = useState({
    hotel: "City Hotel",
    arrival_date_month: "August",
    arrival_date_year: 2016,
    arrival_date_week_number: 27,
    arrival_date_day_of_month: 16,
    stays_in_weekend_nights: 1,
    stays_in_week_nights: 2,
    adults: 2,
  });

  const patchStay = (kv: Partial<typeof stayPred>) =>
    setStayPred((s) => ({ ...s, ...kv }));

  /* ----- live submit: flights ----- */
  const runFlight = () => {
    setFlightNote(null);
    setFlightError(null);
    if (!fh.origin || !fh.destination) {
      setFlightNote("Please choose both a departure and a destination airport.");
      return;
    }
    if (fh.origin.code === fh.destination.code) {
      setFlightNote("Origin and destination cannot be the same airport.");
      return;
    }
    if (!fh.outbound) {
      setFlightNote("Please choose a departure date.");
      return;
    }
    if (!fh.ret) {
      setFlightNote("Please choose a return date.");
      return;
    }
    if (fh.ret < fh.outbound) {
      setFlightNote("The return date cannot be earlier than the departure date.");
      return;
    }
    setFPending(true);
    searchLiveFlights({
      origin: fh.origin.code,
      destination: fh.destination.code,
      outbound_date: fh.outbound,
      return_date: fh.ret,
      travel_class: fh.cabin,
      adults: fh.adults,
      children: fh.kids,
    })
      .then((res) => {
        setFlight(res);
        requestAnimationFrame(() =>
          flightRef.current?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          }),
        );
      })
      .catch((e) => setFlightError((e as Error).message))
      .finally(() => setFPending(false));
  };

  /* ----- live submit: stays ----- */
  const runStays = () => {
    setStayNote(null);
    setStayError(null);
    if (!sh.q.trim()) {
      setStayNote("Tell us where you’d like to stay.");
      return;
    }
    if (!sh.checkIn) {
      setStayNote("Please choose a check-in date.");
      return;
    }
    if (!sh.checkOut) {
      setStayNote("Please choose a check-out date.");
      return;
    }
    if (sh.checkOut < sh.checkIn) {
      setStayNote("The check-out date cannot be earlier than the check-in date.");
      return;
    }
    setSPending(true);
    searchLiveStays({
      q: sh.q.trim(),
      check_in_date: sh.checkIn,
      check_out_date: sh.checkOut,
      adults: sh.adults,
      children: sh.kids,
      sort_by: sh.sort,
    })
      .then((res) => {
        setStay(res);
        requestAnimationFrame(() =>
          stayRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
        );
      })
      .catch((e) => setStayError((e as Error).message))
      .finally(() => setSPending(false));
  };

  /* ----- live submit: packages ----- */
  const runPackages = () => {
    setPkgNote(null);
    setPkgError(null);
    if (!pk.origin || !pk.destination) {
      setPkgNote("Please choose both a departure and a destination airport.");
      return;
    }
    if (pk.origin.code === pk.destination.code) {
      setPkgNote("Origin and destination cannot be the same airport.");
      return;
    }
    if (!pk.q.trim()) {
      setPkgNote("Tell us where you’d like to stay.");
      return;
    }
    if (!pk.outbound) {
      setPkgNote("Please choose a departure date.");
      return;
    }
    if (!pk.ret) {
      setPkgNote("Please choose a return date.");
      return;
    }
    if (pk.ret < pk.outbound) {
      setPkgNote("The return date cannot be earlier than the departure date.");
      return;
    }
    const tripBudget = Number(pk.budget);
    if (!Number.isFinite(tripBudget) || tripBudget <= 0) {
      setPkgNote("Please enter a total budget for the trip.");
      return;
    }
    setPPending(true);
    searchPackages({
      origin: pk.origin.code,
      destination: pk.destination.code,
      q: pk.q.trim(),
      outbound_date: pk.outbound,
      return_date: pk.ret,
      budget: tripBudget,
      travel_class: pk.cabin,
      adults: pk.adults,
      children: pk.kids,
    })
      .then((res) => {
        setPkg(res);
        requestAnimationFrame(() =>
          pkgRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
        );
      })
      .catch((e) => setPkgError((e as Error).message))
      .finally(() => setPPending(false));
  };

  /* ----- legacy submit ----- */
  const submit = async () => {
    setPending(true);
    setResult(null);
    try {
      if (predictKind === "flights") {
        const { predicted_price: p } = await predictFlight(flightPred);
        setResult({
          kind: "flight",
          price: p[0],
          meta: [
            ["Route", `${flightPred.source_city} → ${flightPred.destination_city}`],
            ["Cabin", `${flightPred.airline} · ${flightPred.class}`],
            [
              "Windows",
              `${prettify(flightPred.departure_time)} dep — ${prettify(flightPred.arrival_time)} arr`,
            ],
            [
              "Shape",
              `${prettify(flightPred.stops)} · ${flightPred.duration.toFixed(1)}h · ${flightPred.days_left} days out`,
            ],
          ],
        });
      } else {
        const res = await fetch("/api/hotel/predict", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(stayPred),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "prediction failed");
        const nights = stayPred.stays_in_weekend_nights + stayPred.stays_in_week_nights;
        setResult({
          kind: "stay",
          price: data.adr[0],
          meta: [
            ["Property", stayPred.hotel],
            [
              "Check-in",
              `${stayPred.arrival_date_month} ${stayPred.arrival_date_day_of_month}, ${stayPred.arrival_date_year} · wk ${stayPred.arrival_date_week_number}`,
            ],
            ["Nights", `${nights} (${stayPred.stays_in_week_nights}wk + ${stayPred.stays_in_weekend_nights}end)`],
            ["Party", `${stayPred.adults} adult${stayPred.adults > 1 ? "s" : ""}`],
          ],
        });
      }
      requestAnimationFrame(() =>
        resultRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        })
      );
    } catch (e) {
      setResult({ kind: "error", message: (e as Error).message });
    } finally {
      setPending(false);
    }
  };

  /* ----- board sectioning: round-trip vs sampled one-way ----- */
  const flightSections = (() => {
    if (!flight) return [];
    if (flight.departures.length || flight.returns.length) {
      const out: { cap: string; list: FlightOption[] }[] = [];
      if (flight.departures.length)
        out.push({
          cap: `Outbound — ${flight.trip.origin} → ${flight.trip.destination}`,
          list: flight.departures,
        });
      if (flight.returns.length)
        out.push({
          cap: `Inbound — ${flight.trip.destination} → ${flight.trip.origin}`,
          list: flight.returns,
        });
      if (flight.selected.length)
        out.push({ cap: "Recommended pairs", list: flight.selected });
      return out;
    }
    const out: { cap: string; list: FlightOption[] }[] = [];
    if (flight.best.length) out.push({ cap: "Lowest fares", list: flight.best });
    if (flight.others.length) out.push({ cap: "More fares", list: flight.others });
    return out;
  })();

  const fCur = symbol(flight?.currency ?? "INR");
  const fLoc = localeOf(flight?.currency ?? "INR");
  const sCur = symbol(stay?.currency ?? "INR");

  return (
    <>
      {(pending || fPending || sPending || pPending) && <div className="pending-bar" />}
      <div className="grain" />

      <Chrome />

      {/* ------------------------------------------------------- hero */}
      <section className="hero">
        <div className="hero-media" aria-hidden />
        <div className="hero-scrim" aria-hidden />

        <div className="hero-content">
          <div className="hero-eyebrow">
            <span className="rule" />
            <span className="mini">The world, within reach</span>
            <span className="rule" />
          </div>
          <h1 className="hero-title">
            Where to <em>next?</em>
          </h1>
        </div>

        {/* ------------------------------------------------- search widget */}
        <section className="console" aria-label="Plan your journey">
          <div className="console-tabs">
            <button
              className={`console-tab${panel === "flights" ? " active" : ""}`}
              onClick={() => setPanel("flights")}
            >
              Flights
            </button>
            <button
              className={`console-tab${panel === "stays" ? " active" : ""}`}
              onClick={() => setPanel("stays")}
            >
              Stays
            </button>
            <button
              className={`console-tab${panel === "packages" ? " active" : ""}`}
              onClick={() => setPanel("packages")}
            >
              Packages
            </button>
            <button
              className={`console-tab${panel === "predict" ? " active" : ""}`}
              onClick={() => setPanel("predict")}
            >
              Insights
            </button>
          </div>

        <div className="console-body">
          {/* ================= live flights ================= */}
          {panel === "flights" && (
            <div className="form-grid">
              <AirportField
                cap="From"
                value={fh.origin}
                onPick={(a) => patchFh({ origin: a })}
              />
              <button
                className="swap"
                onClick={() =>
                  patchFh({ origin: fh.destination, destination: fh.origin })
                }
                aria-label="Swap origin and destination"
              >
                ⇄
              </button>
              <AirportField
                cap="To"
                value={fh.destination}
                onPick={(a) => patchFh({ destination: a })}
              />

              <Field cap="Departure" className="span4">
                <input
                  type="date"
                  value={fh.outbound}
                  min={daystamp(0)}
                  onChange={(e) => patchFh({ outbound: e.target.value })}
                />
              </Field>
              <Field cap="Return" className="span4">
                <input
                  type="date"
                  value={fh.ret}
                  min={fh.outbound || daystamp(0)}
                  onChange={(e) => patchFh({ ret: e.target.value })}
                />
              </Field>
              <Field cap="Cabin" className="span4">
                <div className="seg" role="radiogroup">
                  {[
                    ["economy", "Economy"],
                    ["premium_economy", "Premium"],
                    ["business", "Business"],
                    ["first", "First"],
                  ].map(([v, label]) => (
                    <button
                      key={v}
                      type="button"
                      role="radio"
                      aria-checked={fh.cabin === v}
                      className={fh.cabin === v ? "on" : ""}
                      onClick={() => patchFh({ cabin: v })}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </Field>

              <Field cap="Adults" className="count span2">
                <Stepper
                  value={fh.adults}
                  onChange={(v) => patchFh({ adults: v })}
                  min={1}
                  max={8}
                  name="adults"
                />
              </Field>
              <Field cap="Children" className="count span2">
                <Stepper
                  value={fh.kids}
                  onChange={(v) => patchFh({ kids: v })}
                  min={0}
                  max={8}
                  name="children"
                />
              </Field>

              <div className="launch span8">
                <div className="launch-inner" style={{ padding: "30px 0 20px" }}>
                  <p className="hint">
                    Fares straight from the market — every search is kept on
                    file and replayed instantly at no cost.
                  </p>
                  <button
                    className="launch-btn"
                    onClick={runFlight}
                    disabled={fPending}
                  >
                    {fPending ? "Searching…" : "Search flights"}
                  </button>
                </div>
              </div>
              {flightNote && (
                <p className="form-note" role="alert">
                  {flightNote}
                </p>
              )}
            </div>
          )}

          {/* ================= live stays ================= */}
          {panel === "stays" && (
            <div className="form-grid">
              <Field cap="Destination" className="span6" aside={sh.q ? "hotels" : undefined}>
                <input
                  className="control display"
                  value={sh.q}
                  placeholder="Bali, Goa, Shimla —"
                  onChange={(e) => patchSh({ q: e.target.value })}
                />
              </Field>

              <Field cap="Check-in" className="span3">
                <input
                  type="date"
                  value={sh.checkIn}
                  min={daystamp(0)}
                  onChange={(e) => patchSh({ checkIn: e.target.value })}
                />
              </Field>
              <Field cap="Check-out" className="span3">
                <input
                  type="date"
                  value={sh.checkOut}
                  min={sh.checkIn || daystamp(0)}
                  onChange={(e) => patchSh({ checkOut: e.target.value })}
                />
              </Field>

              <Field cap="Adults" className="count span2">
                <Stepper
                  value={sh.adults}
                  onChange={(v) => patchSh({ adults: v })}
                  min={1}
                  max={8}
                  name="adults"
                />
              </Field>
              <Field cap="Children" className="count span2">
                <Stepper
                  value={sh.kids}
                  onChange={(v) => patchSh({ kids: v })}
                  min={0}
                  max={8}
                  name="children"
                />
              </Field>
              <Field cap="Sort" className="select span2">
                <select
                  className="control display"
                  value={sh.sort}
                  onChange={(e) => patchSh({ sort: e.target.value })}
                >
                  <option value="3">Lowest price</option>
                  <option value="8">Highest rating</option>
                  <option value="9">Most reviewed</option>
                </select>
              </Field>

              <div className="launch span6">
                <div className="launch-inner" style={{ padding: "30px 0 20px" }}>
                  <p className="hint">
                    Live availability across our stay partners — kept on file
                    for instant replays.
                  </p>
                  <button
                    className="launch-btn"
                    onClick={runStays}
                    disabled={sPending}
                  >
                    {sPending ? "Searching…" : "Search stays"}
                  </button>
                </div>
              </div>
              {stayNote && (
                <p className="form-note" role="alert">
                  {stayNote}
                </p>
              )}
            </div>
          )}

          {/* ================= package builder ================= */}
          {panel === "packages" && (
            <div className="form-grid">
              <AirportField
                cap="From"
                value={pk.origin}
                onPick={(a) => patchPk({ origin: a })}
              />
              <button
                className="swap"
                onClick={() =>
                  patchPk({ origin: pk.destination, destination: pk.origin })
                }
                aria-label="Swap origin and destination"
              >
                ⇄
              </button>
              <AirportField
                cap="To"
                value={pk.destination}
                onPick={(a) => patchPk({ destination: a })}
              />

              <Field cap="Stay near" className="span6"
                aside={pk.q ? "hotels" : undefined}
              >
                <input
                  className="control display"
                  value={pk.q}
                  placeholder="Goa, Bali, Shimla —"
                  onChange={(e) => patchPk({ q: e.target.value })}
                />
              </Field>
              <Field cap="Total budget" className="span6"
                aside={`${symbol("INR")} total`}
              >
                <input
                  className="control display"
                  type="number"
                  min={1}
                  step={1000}
                  value={pk.budget}
                  onChange={(e) => patchPk({ budget: e.target.value })}
                />
              </Field>

              <Field cap="Departs" className="span4">
                <input
                  type="date"
                  value={pk.outbound}
                  min={daystamp(0)}
                  onChange={(e) => patchPk({ outbound: e.target.value })}
                />
              </Field>
              <Field cap="Returns" className="span4">
                <input
                  type="date"
                  value={pk.ret}
                  min={pk.outbound || daystamp(0)}
                  onChange={(e) => patchPk({ ret: e.target.value })}
                />
              </Field>
              <Field cap="Adults" className="count span2">
                <Stepper
                  value={pk.adults}
                  onChange={(v) => patchPk({ adults: v })}
                  min={1}
                  max={8}
                  name="adults"
                />
              </Field>
              <Field cap="Children" className="count span2">
                <Stepper
                  value={pk.kids}
                  onChange={(v) => patchPk({ kids: v })}
                  min={0}
                  max={8}
                  name="children"
                />
              </Field>

              <Field cap="Cabin" className="span4">
                <div className="seg" role="radiogroup">
                  {[
                    ["economy", "Economy"],
                    ["premium_economy", "Premium"],
                    ["business", "Business"],
                    ["first", "First"],
                  ].map(([v, label]) => (
                    <button
                      key={v}
                      type="button"
                      role="radio"
                      aria-checked={pk.cabin === v}
                      className={pk.cabin === v ? "on" : ""}
                      onClick={() => patchPk({ cabin: v })}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </Field>

              <div className="launch span8">
                <div className="launch-inner" style={{ padding: "26px 0 20px" }}>
                  <p className="hint">
                    One live check for flights and one for stays — both kept
                    on file for instant replays.
                  </p>
                  <button
                    className="launch-btn"
                    onClick={runPackages}
                    disabled={pPending}
                  >
                    {pPending ? "Curating…" : "Find packages"}
                  </button>
                </div>
              </div>
              {pkgNote && (
                <p className="form-note" role="alert">
                  {pkgNote}
                </p>
              )}
            </div>
          )}

          {/* ================= legacy predict ================= */}
          {panel === "predict" && (
            <>
              <div className="predict-kind">
                <Seg
                  value={predictKind}
                  onChange={(v) => setPredictKind(v as "flights" | "stays")}
                  options={["flights", "stays"]}
                />
              </div>
              {predictKind === "flights" ? (
                <div className="form-grid">
                  <Field cap="From" className="select span5">
                    <Select
                      value={flightPred.source_city}
                      onChange={(v) => patchFlight({ source_city: v })}
                      options={CITIES}
                    />
                  </Field>
                  <button
                    className="swap"
                    onClick={swapCities}
                    aria-label="Swap origin and destination"
                  >
                    ⇄
                  </button>
                  <Field cap="To" className="select span5">
                    <Select
                      value={flightPred.destination_city}
                      onChange={(v) => patchFlight({ destination_city: v })}
                      options={CITIES}
                    />
                  </Field>

                  <Field cap="Departs" className="select span4">
                    <Select
                      value={flightPred.departure_time}
                      onChange={(v) => patchFlight({ departure_time: v })}
                      options={
                        flightOptions?.options.departure_time ?? [
                          "Early_Morning", "Morning", "Afternoon", "Evening",
                          "Night", "Late_Night",
                        ]
                      }
                    />
                  </Field>
                  <Field cap="Lands" className="select span4">
                    <Select
                      value={flightPred.arrival_time}
                      onChange={(v) => patchFlight({ arrival_time: v })}
                      options={
                        flightOptions?.options.arrival_time ?? [
                          "Early_Morning", "Morning", "Afternoon", "Evening",
                          "Night", "Late_Night",
                        ]
                      }
                    />
                  </Field>
                  <Field cap="Stops" className="span4">
                    <Seg
                      value={flightPred.stops}
                      onChange={(v) => patchFlight({ stops: v })}
                      options={["zero", "one", "two_or_more"]}
                    />
                  </Field>

                  <Field cap="Airline" className="select span4">
                    <Select
                      value={flightPred.airline}
                      onChange={(v) => patchFlight({ airline: v })}
                      options={
                        flightOptions?.options.airline ?? [
                          "Vistara", "Air_India", "Indigo", "GO_FIRST",
                          "SpiceJet", "AirAsia",
                        ]
                      }
                    />
                  </Field>
                  <Field cap="Cabin" className="span4">
                    <Seg
                      value={flightPred.class}
                      onChange={(v) => patchFlight({ class: v })}
                      options={["Economy", "Business"]}
                    />
                  </Field>
                  <Field cap="Flight time, hours" className="span4">
                    <div className="slider-row">
                      <input
                        className="num"
                        type="number"
                        min={0.8}
                        max={50}
                        step={0.1}
                        value={flightPred.duration}
                        onChange={(e) => {
                          const v = parseFloat(e.target.value);
                          if (!Number.isNaN(v))
                            patchFlight({ duration: Math.min(50, Math.max(0.8, v)) });
                        }}
                      />
                      <input
                        type="range"
                        aria-label="duration"
                        min={0.83}
                        max={49.83}
                        step={0.1}
                        value={flightPred.duration}
                        onChange={(e) => patchFlight({ duration: +e.target.value })}
                      />
                    </div>
                  </Field>

                  <Field cap="Book this many days ahead" className="span8">
                    <div className="slider-row">
                      <input
                        className="num"
                        type="number"
                        min={1}
                        max={49}
                        value={flightPred.days_left}
                        onChange={(e) => {
                          const v = parseInt(e.target.value, 10);
                          if (!Number.isNaN(v))
                            patchFlight({ days_left: Math.min(49, Math.max(1, v)) });
                        }}
                      />
                      <input
                        type="range"
                        aria-label="days left"
                        min={1}
                        max={49}
                        value={flightPred.days_left}
                        onChange={(e) => patchFlight({ days_left: +e.target.value })}
                      />
                    </div>
                  </Field>

                  <div className="launch span4">
                    <div className="launch-inner" style={{ padding: "26px 0 20px" }}>
                      <p className="hint">
                        An indicative fare, modelled on route, timing, season
                        and demand.
                      </p>
                      <button className="launch-btn" onClick={submit} disabled={pending}>
                        {pending ? "Modelling…" : "Estimate fare"}
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="form-grid">
                  <Field cap="Property" className="select span4">
                    <Select
                      value={stayPred.hotel}
                      onChange={(v) => patchStay({ hotel: v })}
                      options={stayOptions?.hotel ?? ["City Hotel", "Resort Hotel"]}
                    />
                  </Field>
                  <Field cap="Month" className="select span4">
                    <Select
                      value={stayPred.arrival_date_month}
                      onChange={(v) => patchStay({ arrival_date_month: v })}
                      options={[
                        "January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November",
                        "December",
                      ]}
                    />
                  </Field>
                  <Field cap="Year" className="select span4">
                    <Select
                      value={String(stayPred.arrival_date_year)}
                      onChange={(v) => patchStay({ arrival_date_year: +v })}
                      options={["2015", "2016", "2017"]}
                    />
                  </Field>

                  <Field cap="Arrival week" className="count span4">
                    <Stepper
                      value={stayPred.arrival_date_week_number}
                      onChange={(v) => patchStay({ arrival_date_week_number: v })}
                      min={1}
                      max={53}
                    />
                  </Field>
                  <Field cap="Day of month" className="count span4">
                    <Stepper
                      value={stayPred.arrival_date_day_of_month}
                      onChange={(v) => patchStay({ arrival_date_day_of_month: v })}
                      min={1}
                      max={31}
                    />
                  </Field>
                  <Field cap="Adults" className="count span4">
                    <Stepper
                      value={stayPred.adults}
                      onChange={(v) => patchStay({ adults: v })}
                      min={1}
                      max={10}
                    />
                  </Field>

                  <Field cap="Week-nights" className="count span4">
                    <Stepper
                      value={stayPred.stays_in_week_nights}
                      onChange={(v) => patchStay({ stays_in_week_nights: v })}
                      min={0}
                      max={10}
                    />
                  </Field>
                  <Field cap="Weekend-nights" className="count span4">
                    <Stepper
                      value={stayPred.stays_in_weekend_nights}
                      onChange={(v) => patchStay({ stays_in_weekend_nights: v })}
                      min={0}
                      max={10}
                    />
                  </Field>

                  <div className="launch span4">
                    <div className="launch-inner" style={{ padding: "30px 0 20px" }}>
                      <p className="hint">
                        An indicative nightly rate, modelled on the season,
                        length of stay and party size.
                      </p>
                      <button className="launch-btn" onClick={submit} disabled={pending}>
                        {pending ? "Modelling…" : "Estimate night rate"}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </section>
      </section>

      <Ticker items={TICKER} />

      {/* ------------------------------------------------------- live: flights board */}
      <div ref={flightRef} id="flight-board">
        {flightError && (
          <section className="board-error flash" role="alert" key="ferr">
            <b>· </b>
            We couldn&rsquo;t complete that search — {flightError}
          </section>
        )}
        {flight && !flightError && (
          <section className="board flash" key={`fl-${flight.fetched_on}-${flight.cached}`}>
            <div className="board-head">
              <Tags search={flight} />
              {flight.insights?.low == null ? null : (
                <div className="board-grid">
                  <div>
                    <div className="cap mini">Lowest fare · {flight.trip.outbound_date} – {flight.trip.return_date}</div>
                    <span style={{ display: "block" }}>
                      <Money value={flight.insights.low} cur={fCur} locale={fLoc} />
                    </span>
                    {flight.insights.range.length === 2 && (
                      <div className="mini dim" style={{ marginTop: 10 }}>
                        typically {fCur}{flight.insights.range[0]}–{fCur}
                        {flight.insights.range[1]} · demand {flight.insights.level}
                      </div>
                    )}
                  </div>
                  <div className="board-spark">
                    <div className="cap mini">fare trend · {fCur}</div>
                    <Spark points={flight.insights.history.slice(-44)} />
                  </div>
                </div>
              )}
            </div>
            {flightSections.map((s) => (
              <div className="flight-col" key={s.cap}>
                <div className="cap mini flight-col-cap">{s.cap}</div>
                {s.list.map((o, i) => (
                  <Itin o={o} cur={fCur} loc={fLoc} key={`${s.cap}-${i}-${o.price}-${o.legs[0]?.flight ?? ""}`} />
                ))}
              </div>
            ))}
            <div className="board-foot mini dim">
              {flight.cached
                ? "Results served from our cache — prices move quickly."
                : "Live results — the freshest prices available."}
            </div>
          </section>
        )}
      </div>

      {/* ------------------------------------------------------- live: stays board */}
      <div ref={stayRef} id="stay-board">
        {stayError && (
          <section className="board-error flash" role="alert" key="serr">
            <b>· </b>
            We couldn&rsquo;t complete that search — {stayError}
          </section>
        )}
        {stay && !stayError && (
          <section className="board flash" key={`st-${stay.fetched_on}-${stay.cached}`}>
            <div className="board-head">
              <Tags search={stay} />
              <div className="cap mini board-capline">
                {stay.count} stays on the “{stay.q}” board
              </div>
            </div>
            <div className="stay-grid">
              {stay.properties.map((s, i) => (
                <StayCard s={s} cur={sCur} key={`${s.name}-${i}`} />
              ))}
            </div>
            <div className="board-foot mini dim">
              {stay.cached
                ? "Results served from our cache — prices move quickly."
                : "Live results — the freshest prices available."}
            </div>
          </section>
        )}
      </div>

      {/* ------------------------------------------------------- live: package board */}
      <div ref={pkgRef} id="package-board">
        {pkgError && (
          <section className="board-error flash" role="alert" key="pkgerr">
            <b>· </b>
            We couldn&rsquo;t build that package — {pkgError}
          </section>
        )}
        {pkg && !pkgError && (
          <section
            className="board flash"
            key={`pk-${pkg.boards.flight.fetched_on}-${pkg.boards.hotel.fetched_on}-${pkg.packages.length}`}
          >
            <div className="board-head">
              <div className="board-tags">
                <span className="tag live">flight + stay · one all-in price</span>
                <span className="tag dim">
                  {pkg.nights} nights · {pkg.party.travellers} traveller
                  {pkg.party.travellers === 1 ? "" : "s"} · budget{" "}
                  {symbol(pkg.currency)}{pkg.trip_budget.toLocaleString(localeOf(pkg.currency))}
                </span>
              </div>
              <div className="pkg-intro">
                <div>
                  <div className="cap mini">stays in “{pkg.q}”</div>
                  <h2 className="pkg-title">Three ways to take this trip.</h2>
                </div>
                <div className="pkg-board-meta">
                  <div>
                    <div className="cap mini">Flight results</div>
                    <Tags search={pkg.boards.flight} />
                  </div>
                  <div>
                    <div className="cap mini">Stay results</div>
                    <Tags search={pkg.boards.hotel} />
                  </div>
                </div>
              </div>
            </div>
            <div className="pkg-grid">
              {pkg.packages.map((p) => (
                <PackageCard
                  key={p.tier}
                  p={p}
                  cur={symbol(pkg.currency)}
                  loc={localeOf(pkg.currency)}
                  budget={pkg.trip_budget}
                />
              ))}
            </div>
            <div className="board-foot mini dim">
              {pkg.boards.flight.cached && pkg.boards.hotel.cached
                ? "Results served from our cache — prices move quickly."
                : "Live results — the freshest prices available."}
            </div>
          </section>
        )}
      </div>

      {/* ------------------------------------------------------- legacy result */}
      {/* key remounts the whole slab per prediction so `flash` replays */}
      <div ref={resultRef} id="result">
        {result === null ? null : result.kind === "error" ? (
          <section
            className="result-error flash"
            key="error"
            role="alert"
          >
            <b>· </b>
            We couldn&rsquo;t estimate that — {result.message}
          </section>
        ) : (
          <section
            className="result flash"
            key={`${result.kind}-${result.price}`}
          >
            <div className="result-inner">
              <div>
                <div className="cap mini">
                  {result.kind === "flight"
                    ? "Predicted passenger fare"
                    : "Predicted per-night rate"}
                </div>
                <span style={{ display: "block" }}>
                  <Money value={result.price} />
                </span>
              </div>
              <div className="result-more">
                {result.meta.map(([k, v]) => (
                  <div className="row" key={k}>
                    {k} — <b>{v}</b>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}
      </div>

      <footer className="footer">
        <span className="wordmark footer-mark">
          VOVAGE<i>.</i>
        </span>
        <span className="mini">
          Prices are estimates, not offers — confirmed only at booking.
        </span>
        <span className="mini">© {new Date().getFullYear()} Vovage</span>
      </footer>
    </>
  );
}
