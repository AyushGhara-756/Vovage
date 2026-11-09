"use client";

import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Chrome, Ticker } from "./chrome";
import {
  fetchBudget,
  fetchFlightOptions,
  fetchStayOptions,
  predictFlight,
  predictStay,
  searchAirports,
  searchLiveFlights,
  searchLiveStays,
  searchPackages,
  type AirportHit,
  type Budget,
  type FlightOption,
  type FlightOptions,
  type FlightQuery,
  type FlightSearch,
  type HotelOptions,
  type LiveFeed,
  type PackageOffer,
  type PackageSearch,
  type PackageTier,
  type StayOption,
  type StaySearch,
} from "@/lib/api";

/* ---------------------------------------------------------------- primitives */

const CITIES = ["Delhi", "Mumbai", "Bangalore", "Kolkata", "Chennai", "Hyderabad"];

function Field({
  n,
  cap,
  className,
  aside,
  children,
}: {
  n: string;
  cap: string;
  className: string;
  aside?: string;
  children: ReactNode;
}) {
  return (
    <label className={`field ${className}`}>
      <span className="cap mini">
        {cap}
        <i>{aside ?? n}</i>
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
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
}) {
  const clamp = (v: number) => Math.min(max, Math.max(min, v));
  return (
    <div className="stepper">
      <button
        type="button"
        aria-label="decrease"
        disabled={value <= min}
        onClick={() => onChange(clamp(value - 1))}
      >
        –
      </button>
      <span className="val">{value}</span>
      <button
        type="button"
        aria-label="increase"
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
  n,
  cap,
  value,
  onPick,
}: {
  n: string;
  cap: string;
  value: AirportHit | null;
  onPick: (a: AirportHit | null) => void;
}) {
  const [text, setText] = useState(value?.code ?? "");
  const [hits, setHits] = useState<AirportHit[]>([]);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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
          setOpen(true);
          setErr(r.results.length ? null : `no airports match “${q}”`);
        })
        .catch((e) => {
          if (!alive) return;
          setHits([]);
          setOpen(true);
          setErr((e as Error).message || "airport lookup failed");
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

  return (
    <Field n={n} cap={cap} className="select span5 ac" aside={value?.city ?? n}>
      <input
        className="control display"
        value={text}
        placeholder="city, airport, code"
        autoCapitalize="characters"
        spellCheck={false}
        onChange={(e) => {
          setText(e.target.value);
          onPick(null);
        }}
        onFocus={() => hits.length > 0 && setOpen(true)}
        onBlur={close}
      />
      {open && hits.length > 0 && (
        <div className="ac-list display" role="listbox">
          {hits.map((h) => (
            <div
              key={h.code}
              className="ac-item"
              role="option"
              aria-selected={false}
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

/* board badges (LIVE / CACHE / REPLAY + spend-note) */
function Tags({ search }: { search: { mock?: boolean; cached?: boolean; fetched_on: string } }) {
  const kind = search.mock ? "sample replay" : search.cached ? "cache — no call spent" : "live board";
  const cls = search.mock ? "tag" : search.cached ? "tag hot" : "tag live";
  return (
    <div className="board-tags">
      <span className={cls}>{kind}</span>
      <span className="tag dim">fetched {search.fetched_on}</span>
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
  ["DEL", "BOM", "4,222", "VISTARA · ECON · 30 DAYS OUT"],
  ["BLR", "CCU", "8,131", "AIR INDIA · BUSINESS"],
  ["MAA", "HYD", "1,758", "INDIGO · NON-STOP"],
  ["DEL", "BOM", "49,987", "VISTARA · BUSINESS · TOMORROW"],
  ["CCU", "BLR", "6,060", "SPICEJET · DIRECT"],
  ["HYD", "DEL", "12,482", "GO FIRST · 2 STOPS"],
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
            each leg: {legs.map((l) => hm(l.duration)).join(" + ")}
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
        <div className="mini dim"><i>{s.type} · Reviews: {(s.reviews ?? 0).toLocaleString("en-US")}</i></div>
        <div className="stay-rate">
          <span className="p display">
            <i>{cur}</i>
            {s.price != null ? s.price.toLocaleString("en-IN") : s.price_display ?? "—"}
          </span>
          <span className="sub mini">/ night</span>
        </div>
        {s.total_display && (
          <div className="mini dim">full stay — {s.total_display}</div>
        )}
        <div className="chiprow">
          {s.amenities.slice(0, 4).map((a) => (
            <span className="chip mini" key={a}>{a}</span>
          ))}
        </div>
        <div className="stay-foot mini">
          <span>in {s.check_in_time ?? "—"} · out {s.check_out_time ?? "—"}</span>
          {s.location_rating ? <span>loc {s.location_rating}</span> : null}
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
  saver: { label: "Saver", blurb: "cheapest fare + cheapest stay" },
  balanced: { label: "Balanced", blurb: "best-rated stay that still fits the budget" },
  comfort: { label: "Comfort", blurb: "best-rated stay, even if it pushes the total" },
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
                open listing ↗
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
    feed: "replay" as LiveFeed,
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
    feed: "replay" as LiveFeed,
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
    feed: "replay" as LiveFeed,
  };
}

/* ---------------------------------------------------------------- page */

export default function Home() {
  /* ----- global panel ----- */
  const [panel, setPanel] = useState<Panel>("flights");
  const [budget, setBudget] = useState<Budget | null>(null);

  /* ----- live flight search ----- */
  const [flight, setFlight] = useState<FlightSearch | null>(null);
  const [flightError, setFlightError] = useState<string | null>(null);
  const [fPending, setFPending] = useState(false);
  const [fh, setFh] = useState(flightHuntDefaults);
  const flightRef = useRef<HTMLDivElement>(null);
  const [stay, setStay] = useState<StaySearch | null>(null);
  const [stayError, setStayError] = useState<string | null>(null);
  const [sPending, setSPending] = useState(false);
  const [sh, setSh] = useState(stayHuntDefaults);
  const stayRef = useRef<HTMLDivElement>(null);

  /* ----- package builder (flight + stay, priced as tiers) ----- */
  const [pkg, setPkg] = useState<PackageSearch | null>(null);
  const [pkgError, setPkgError] = useState<string | null>(null);
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
    fetchBudget()
      .then(setBudget)
      .catch(() => {});
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
  const runFlight = async () => {
    if (!fh.origin || !fh.destination) {
      setFlightError("pick both airports from the dropdown first");
      return;
    }
    if (fh.feed === "live" && budget && budget.remaining <= 0) {
      setFlightError(
        "lifetime serpapi budget is spent — switch the feed to REPLAY (cached results stay available)",
      );
      return;
    }
    setFPending(true);
    setFlightError(null);
    try {
      const res = await searchLiveFlights({
        origin: fh.origin.code,
        destination: fh.destination.code,
        outbound_date: fh.outbound,
        return_date: fh.ret,
        travel_class: fh.cabin,
        adults: fh.adults,
        children: fh.kids,
        feed: fh.feed,
      });
      setFlight(res);
      setBudget(res.budget);
      requestAnimationFrame(() =>
        flightRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    } catch (e) {
      setFlightError((e as Error).message);
    } finally {
      setFPending(false);
    }
  };

  /* ----- live submit: stays ----- */
  const runStays = async () => {
    if (!sh.q.trim()) {
      setStayError("type a destination for the hotels board");
      return;
    }
    if (sh.feed === "live" && budget && budget.remaining <= 0) {
      setStayError(
        "lifetime serpapi budget is spent — switch the feed to REPLAY (cached results stay available)",
      );
      return;
    }
    setSPending(true);
    setStayError(null);
    try {
      const res = await searchLiveStays({
        q: sh.q.trim(),
        check_in_date: sh.checkIn,
        check_out_date: sh.checkOut,
        adults: sh.adults,
        children: sh.kids,
        sort_by: sh.sort,
        feed: sh.feed,
      });
      setStay(res);
      setBudget(res.budget);
      requestAnimationFrame(() =>
        stayRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    } catch (e) {
      setStayError((e as Error).message);
    } finally {
      setSPending(false);
    }
  };

  /* ----- live submit: packages ----- */
  const runPackages = async () => {
    if (!pk.origin || !pk.destination) {
      setPkgError("pick both airports from the dropdown first");
      return;
    }
    if (!pk.q.trim()) {
      setPkgError("type a destination for the stay board");
      return;
    }
    const tripBudget = Number(pk.budget);
    if (!Number.isFinite(tripBudget) || tripBudget <= 0) {
      setPkgError("enter a positive package budget in rupees");
      return;
    }
    if (pk.feed === "live" && budget && budget.remaining <= 0) {
      setPkgError(
        "lifetime serpapi budget is spent — switch the feed to REPLAY (cached results stay available)",
      );
      return;
    }
    setPPending(true);
    setPkgError(null);
    try {
      const res = await searchPackages({
        origin: pk.origin.code,
        destination: pk.destination.code,
        q: pk.q.trim(),
        outbound_date: pk.outbound,
        return_date: pk.ret,
        budget: tripBudget,
        travel_class: pk.cabin,
        adults: pk.adults,
        children: pk.kids,
        feed: pk.feed,
      });
      setPkg(res);
      setBudget(res.budget);
      requestAnimationFrame(() =>
        pkgRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      );
    } catch (e) {
      setPkgError((e as Error).message);
    } finally {
      setPPending(false);
    }
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
        out.push({ cap: "Fare pairs", list: flight.selected });
      return out;
    }
    const out: { cap: string; list: FlightOption[] }[] = [];
    if (flight.best.length) out.push({ cap: "Top fares", list: flight.best });
    if (flight.others.length) out.push({ cap: "All other fares", list: flight.others });
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
        <div className="hero-grid" />
        <div className="hero-beam" />
        <div className="hero-eyebrow">
          <span className="pulse" />
          <span className="mini">Live market boards — Google Flights · Google Hotels · INR</span>
        </div>
        <h1 className="hero-title">
          <span className="bleed">NEVER OVERPAY</span>
          <span className="solid">
            FOR A SEAT<em>.</em>
          </span>
        </h1>
        <p className="hero-sub">
          Vovage reads the market before you do — Google&rsquo;s live fare
          boards for seats and stays, priced in rupees, cross-checked against
          our own economic models. Flights and stays, one instrument.
        </p>
      </section>

      <Ticker items={TICKER} />

      {/* ------------------------------------------------------- console */}
      <section className="console">
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
            Predict
          </button>
          <div className="console-budget display">
            <span className="mini">live calls</span>
            <b>{budget ? budget.remaining : "—"}/{budget?.max ?? 5}</b>
          </div>
        </div>

        <div className="console-body">
          {/* ================= live flights ================= */}
          {panel === "flights" && (
            <div className="form-grid">
              <AirportField
                n="01"
                cap="Fly from"
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
                n="02"
                cap="Fly to"
                value={fh.destination}
                onPick={(a) => patchFh({ destination: a })}
              />

              <Field n="03" cap="Departs" className="span4">
                <input
                  type="date"
                  value={fh.outbound}
                  min={daystamp(0)}
                  onChange={(e) => patchFh({ outbound: e.target.value })}
                />
              </Field>
              <Field n="04" cap="Returns" className="span4">
                <input
                  type="date"
                  value={fh.ret}
                  min={fh.outbound || daystamp(0)}
                  onChange={(e) => patchFh({ ret: e.target.value })}
                />
              </Field>
              <Field n="05" cap="Cabin" className="span4">
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

              <Field n="06" cap="Adults" className="stepper span2">
                <Stepper
                  value={fh.adults}
                  onChange={(v) => patchFh({ adults: v })}
                  min={1}
                  max={8}
                />
              </Field>
              <Field n="07" cap="Children" className="stepper span2">
                <Stepper
                  value={fh.kids}
                  onChange={(v) => patchFh({ kids: v })}
                  min={0}
                  max={8}
                />
              </Field>
              <Field n="08" cap="Fares feed" className="span4"
                aside={fh.feed === "live" ? "spends budget" : "zero cost"}
              >
                <Seg
                  value={fh.feed}
                  onChange={(v) => patchFh({ feed: v as LiveFeed })}
                  options={["live", "replay"]}
                />
              </Field>

              <div className="launch" style={{ gridColumn: "span 4" }}>
                <div className="launch-inner" style={{ padding: "30px 0 20px" }}>
                  <p className="hint">
                    {fh.feed === "live"
                      ? "One real SerpApi round-trip call — then cached forever."
                      : "Sample board from a captured search — zero calls spent."}
                  </p>
                  <button className="launch-btn" onClick={runFlight} disabled={fPending}>
                    {fPending ? "Reading the board…" : "Search fares"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ================= live stays ================= */}
          {panel === "stays" && (
            <div className="form-grid">
              <Field n="01" cap="Where" className="span6" aside={sh.q ? "google hotels" : "01"}>
                <input
                  className="control display"
                  value={sh.q}
                  placeholder="Bali Resorts, Goa, Shimla —"
                  onChange={(e) => patchSh({ q: e.target.value })}
                />
              </Field>

              <Field n="02" cap="Check-in" className="span3">
                <input
                  type="date"
                  value={sh.checkIn}
                  min={daystamp(0)}
                  onChange={(e) => patchSh({ checkIn: e.target.value })}
                />
              </Field>
              <Field n="03" cap="Check-out" className="span3">
                <input
                  type="date"
                  value={sh.checkOut}
                  min={sh.checkIn || daystamp(0)}
                  onChange={(e) => patchSh({ checkOut: e.target.value })}
                />
              </Field>

              <Field n="04" cap="Adults" className="stepper span2">
                <Stepper
                  value={sh.adults}
                  onChange={(v) => patchSh({ adults: v })}
                  min={1}
                  max={8}
                />
              </Field>
              <Field n="05" cap="Children" className="stepper span2">
                <Stepper
                  value={sh.kids}
                  onChange={(v) => patchSh({ kids: v })}
                  min={0}
                  max={8}
                />
              </Field>
              <Field n="06" cap="Sort" className="select span2">
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

              <Field
                n="07"
                cap="Fares feed"
                className="span4"
                aside={sh.feed === "live" ? "spends budget" : "zero cost"}
              >
                <Seg
                  value={sh.feed}
                  onChange={(v) => patchSh({ feed: v as LiveFeed })}
                  options={["live", "replay"]}
                />
              </Field>

              <div className="launch" style={{ gridColumn: "span 2" }}>
                <div className="launch-inner" style={{ padding: "30px 0 20px" }}>
                  <p className="hint">
                    {sh.feed === "live"
                      ? "One real SerpApi hotels call — the whole board in one shot."
                      : "Sample board from a captured search — zero calls spent."}
                  </p>
                  <button className="launch-btn" onClick={runStays} disabled={sPending}>
                    {sPending ? "Reading the board…" : "Search stays"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ================= package builder ================= */}
          {panel === "packages" && (
            <div className="form-grid">
              <AirportField
                n="01"
                cap="Fly from"
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
                n="02"
                cap="Fly to"
                value={pk.destination}
                onPick={(a) => patchPk({ destination: a })}
              />

              <Field n="03" cap="Stay at" className="span6"
                aside={pk.q ? "google hotels" : "03"}
              >
                <input
                  className="control display"
                  value={pk.q}
                  placeholder="Goa, Bali, Shimla —"
                  onChange={(e) => patchPk({ q: e.target.value })}
                />
              </Field>
              <Field n="04" cap="All-in budget" className="span6"
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

              <Field n="05" cap="Departs" className="span4">
                <input
                  type="date"
                  value={pk.outbound}
                  min={daystamp(0)}
                  onChange={(e) => patchPk({ outbound: e.target.value })}
                />
              </Field>
              <Field n="06" cap="Returns" className="span4">
                <input
                  type="date"
                  value={pk.ret}
                  min={pk.outbound || daystamp(0)}
                  onChange={(e) => patchPk({ ret: e.target.value })}
                />
              </Field>
              <Field n="07" cap="Adults" className="stepper span2">
                <Stepper
                  value={pk.adults}
                  onChange={(v) => patchPk({ adults: v })}
                  min={1}
                  max={8}
                />
              </Field>
              <Field n="08" cap="Children" className="stepper span2">
                <Stepper
                  value={pk.kids}
                  onChange={(v) => patchPk({ kids: v })}
                  min={0}
                  max={8}
                />
              </Field>

              <Field n="09" cap="Cabin" className="span4">
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
              <Field n="10" cap="Fares feed" className="span4"
                aside={pk.feed === "live" ? "spends budget" : "zero cost"}
              >
                <Seg
                  value={pk.feed}
                  onChange={(v) => patchPk({ feed: v as LiveFeed })}
                  options={["live", "replay"]}
                />
              </Field>

              <div className="launch" style={{ gridColumn: "span 4" }}>
                <div className="launch-inner" style={{ padding: "26px 0 20px" }}>
                  <p className="hint">
                    {pk.feed === "live"
                      ? "At most two real calls — one fare board, one stay board. Cache-first."
                      : "Both boards replay from captured searches — zero calls spent."}
                  </p>
                  <button className="launch-btn" onClick={runPackages} disabled={pPending}>
                    {pPending ? "Building packages…" : "Build packages"}
                  </button>
                </div>
              </div>
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
                  <Field n="01" cap="From" className="select span5">
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
                  <Field n="02" cap="To" className="select span5">
                    <Select
                      value={flightPred.destination_city}
                      onChange={(v) => patchFlight({ destination_city: v })}
                      options={CITIES}
                    />
                  </Field>

                  <Field n="03" cap="Departs" className="select span4">
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
                  <Field n="04" cap="Lands" className="select span4">
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
                  <Field n="05" cap="Stops" className="span4">
                    <Seg
                      value={flightPred.stops}
                      onChange={(v) => patchFlight({ stops: v })}
                      options={["zero", "one", "two_or_more"]}
                    />
                  </Field>

                  <Field n="06" cap="Airline" className="select span4">
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
                  <Field n="07" cap="Cabin" className="span4">
                    <Seg
                      value={flightPred.class}
                      onChange={(v) => patchFlight({ class: v })}
                      options={["Economy", "Business"]}
                    />
                  </Field>
                  <Field n="08" cap="Air time, hours" className="span4">
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

                  <Field n="09" cap="Book ahead, days" className="span8">
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

                  <div className="launch" style={{ gridColumn: "span 4" }}>
                    <div className="launch-inner" style={{ padding: "26px 0 20px" }}>
                      <p className="hint">
                        Estimates the fare <em>now</em> from 37 market features —
                        not yesterday&rsquo;s brochure.
                      </p>
                      <button className="launch-btn" onClick={submit} disabled={pending}>
                        {pending ? "Reading the market…" : "Estimate fare"}
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="form-grid">
                  <Field n="01" cap="Property" className="select span4">
                    <Select
                      value={stayPred.hotel}
                      onChange={(v) => patchStay({ hotel: v })}
                      options={stayOptions?.hotel ?? ["City Hotel", "Resort Hotel"]}
                    />
                  </Field>
                  <Field n="02" cap="Month" className="select span4">
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
                  <Field n="03" cap="Year" className="select span4">
                    <Select
                      value={String(stayPred.arrival_date_year)}
                      onChange={(v) => patchStay({ arrival_date_year: +v })}
                      options={["2015", "2016", "2017"]}
                    />
                  </Field>

                  <Field n="04" cap="Arrival week" className="stepper span4">
                    <Stepper
                      value={stayPred.arrival_date_week_number}
                      onChange={(v) => patchStay({ arrival_date_week_number: v })}
                      min={1}
                      max={53}
                    />
                  </Field>
                  <Field n="05" cap="Day of month" className="stepper span4">
                    <Stepper
                      value={stayPred.arrival_date_day_of_month}
                      onChange={(v) => patchStay({ arrival_date_day_of_month: v })}
                      min={1}
                      max={31}
                    />
                  </Field>
                  <Field n="06" cap="Adults" className="stepper span4">
                    <Stepper
                      value={stayPred.adults}
                      onChange={(v) => patchStay({ adults: v })}
                      min={1}
                      max={10}
                    />
                  </Field>

                  <Field n="07" cap="Week-nights" className="stepper span4">
                    <Stepper
                      value={stayPred.stays_in_week_nights}
                      onChange={(v) => patchStay({ stays_in_week_nights: v })}
                      min={0}
                      max={10}
                    />
                  </Field>
                  <Field n="08" cap="Weekend-nights" className="stepper span4">
                    <Stepper
                      value={stayPred.stays_in_weekend_nights}
                      onChange={(v) => patchStay({ stays_in_weekend_nights: v })}
                      min={0}
                      max={10}
                    />
                  </Field>

                  <div className="launch" style={{ gridColumn: "span 4" }}>
                    <div className="launch-inner" style={{ padding: "30px 0 20px" }}>
                      <p className="hint">
                        Everything else — meals, channel, history — is inferred from
                        the booking&rsquo;s own signal.
                      </p>
                      <button className="launch-btn" onClick={submit} disabled={pending}>
                        {pending ? "Reading the market…" : "Estimate night rate"}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {/* ------------------------------------------------------- live: flights board */}
      <div ref={flightRef} id="flight-board">
        {flightError && (
          <section className="board-error flash" role="alert" key="ferr">
            <b>/// </b>
            The board refused this query — {flightError}
          </section>
        )}
        {flight && !flightError && (
          <section className="board flash" key={`fl-${flight.fetched_on}-${flight.cached}`}>
            <div className="board-head">
              <Tags search={flight} />
              {flight.insights?.low == null ? null : (
                <div className="board-grid">
                  <div>
                    <div className="cap mini">cheapest on the {flight.trip.outbound_date} · {flight.trip.return_date} board</div>
                    <span style={{ display: "block" }}>
                      <Money value={flight.insights.low} cur={fCur} locale={fLoc} />
                    </span>
                    {flight.insights.range.length === 2 && (
                      <div className="mini dim" style={{ marginTop: 10 }}>
                        typical {fCur}{flight.insights.range[0]}–{fCur}
                        {flight.insights.range[1]} · market {flight.insights.level}
                      </div>
                    )}
                  </div>
                  <div className="board-spark">
                    <div className="cap mini">fare history · {fCur}</div>
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
              {flight.mock
                ? "sample data — served from the captured fixture, no live call was made"
                : flight.cached
                  ? "served from cache — indexed the day it was fetched"
                  : "live results via SerpApi — one call of the lifetime budget was spent"}
            </div>
          </section>
        )}
      </div>

      {/* ------------------------------------------------------- live: stays board */}
      <div ref={stayRef} id="stay-board">
        {stayError && (
          <section className="board-error flash" role="alert" key="serr">
            <b>/// </b>
            The board refused this query — {stayError}
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
              {stay.mock
                ? "sample data — served from the captured fixture, no live call was made"
                : stay.cached
                  ? "served from cache — indexed the day it was fetched"
                  : "live results via SerpApi — one call of the lifetime budget was spent"}
            </div>
          </section>
        )}
      </div>

      {/* ------------------------------------------------------- live: package board */}
      <div ref={pkgRef} id="package-board">
        {pkgError && (
          <section className="board-error flash" role="alert" key="pkgerr">
            <b>/// </b>
            The package builder refused this query — {pkgError}
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
                  <div className="cap mini">the “{pkg.q}” board</div>
                  <h2 className="pkg-title">Three ways to take this trip.</h2>
                </div>
                <div className="pkg-board-meta">
                  <div>
                    <div className="cap mini">flight board</div>
                    <Tags search={pkg.boards.flight} />
                  </div>
                  <div>
                    <div className="cap mini">stay board</div>
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
              {pkg.boards.flight.mock && pkg.boards.hotel.mock
                ? "sample data — both boards replayed from captured fixtures, no live call was made"
                : pkg.boards.flight.cached && pkg.boards.hotel.cached
                  ? "both boards served from cache — no calls spent"
                  : "live boards via SerpApi — only uncached legs spend from the lifetime budget"}
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
            <b>/// </b>
            The engine refused this query — {result.message}
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
        <span className="mini">
          <b>Vovage</b> — fare &amp; rate intelligence
        </span>
        <span className="mini">
          Live boards through SerpApi · models served on-device. Estimates, not quotes.
        </span>
      </footer>
    </>
  );
}
