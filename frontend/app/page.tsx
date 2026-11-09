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
  type FlightOptions,
  type FlightQuery,
  type HotelOptions,
} from "@/lib/api";

/* ---------------------------------------------------------------- primitives */

const CITIES = ["Delhi", "Mumbai", "Bangalore", "Kolkata", "Chennai", "Hyderabad"];

function Field({
  n,
  cap,
  className,
  children,
}: {
  n: string;
  cap: string;
  className: string;
  children: ReactNode;
}) {
  return (
    <label className={`field ${className}`}>
      <span className="cap mini">
        {cap}
        <i>{n}</i>
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
function Money({ value }: { value: number }) {
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
      <span className="cur">₹</span>
      {Math.round(shown).toLocaleString("en-IN")}
    </span>
  );
}

/* ---------------------------------------------------------------- page types */

type Mode = "flights" | "stays";
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

export default function Home() {
  const [mode, setMode] = useState<Mode>("flights");
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

  /* ----- flights state ----- */
  const [flight, setFlight] = useState<FlightQuery>({
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
    setFlight((f) => ({ ...f, ...kv }));

  const swapCities = () =>
    patchFlight({
      source_city: flight.destination_city,
      destination_city: flight.source_city,
    });

  /* ----- stays state ----- */
  const [stay, setStay] = useState({
    hotel: "City Hotel",
    arrival_date_month: "August",
    arrival_date_year: 2016,
    arrival_date_week_number: 27,
    arrival_date_day_of_month: 16,
    stays_in_weekend_nights: 1,
    stays_in_week_nights: 2,
    adults: 2,
  });

  const patchStay = (kv: Partial<typeof stay>) =>
    setStay((s) => ({ ...s, ...kv }));

  /* ----- submit ----- */
  const submit = async () => {
    setPending(true);
    setResult(null);
    try {
      if (mode === "flights") {
        const { predicted_price: p } = await predictFlight(flight);
        setResult({
          kind: "flight",
          price: p[0],
          meta: [
            ["Route", `${flight.source_city} → ${flight.destination_city}`],
            ["Cabin", `${flight.airline} · ${flight.class}`],
            [
              "Windows",
              `${prettify(flight.departure_time)} dep — ${prettify(flight.arrival_time)} arr`,
            ],
            [
              "Shape",
              `${prettify(flight.stops)} · ${flight.duration.toFixed(1)}h · ${flight.days_left} days out`,
            ],
          ],
        });
      } else {
        const res = await fetch("/api/hotel/predict", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(stay),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "prediction failed");
        const nights = stay.stays_in_weekend_nights + stay.stays_in_week_nights;
        setResult({
          kind: "stay",
          price: data.adr[0],
          meta: [
            ["Property", stay.hotel],
            [
              "Check-in",
              `${stay.arrival_date_month} ${stay.arrival_date_day_of_month}, ${stay.arrival_date_year} · wk ${stay.arrival_date_week_number}`,
            ],
            ["Nights", `${nights} (${stay.stays_in_week_nights}wk + ${stay.stays_in_weekend_nights}end)`],
            ["Party", `${stay.adults} adult${stay.adults > 1 ? "s" : ""}`],
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

  return (
    <>
      {pending && <div className="pending-bar" />}
      <div className="grain" />

      <Chrome />

      {/* ------------------------------------------------------- hero */}
      <section className="hero">
        <div className="hero-grid" />
        <div className="hero-beam" />
        <div className="hero-eyebrow">
          <span className="pulse" />
          <span className="mini">Live fare engine — trained nightly, served on-device</span>
        </div>
        <h1 className="hero-title">
          <span className="bleed">NEVER OVERPAY</span>
          <span className="solid">
            FOR A SEAT<em>.</em>
          </span>
        </h1>
        <p className="hero-sub">
          Vovage reads the market before you do — airline economics, demand
          windows, cabin pressure on price — and tells you what tomorrow&rsquo;s
          ticket should cost. Flights and stays, one instrument.
        </p>
      </section>

      <Ticker items={TICKER} />

      {/* ------------------------------------------------------- console */}
      <section className="console">
        <div className="console-tabs">
          <button
            className={`console-tab${mode === "flights" ? " active" : ""}`}
            onClick={() => setMode("flights")}
          >
            Flights
          </button>
          <button
            className={`console-tab${mode === "stays" ? " active" : ""}`}
            onClick={() => setMode("stays")}
          >
            Stays
          </button>
        </div>

        <div className="console-body">
          {mode === "flights" ? (
            <div className="form-grid">
              <Field n="01" cap="From" className="select span5">
                <Select
                  value={flight.source_city}
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
                  value={flight.destination_city}
                  onChange={(v) => patchFlight({ destination_city: v })}
                  options={CITIES}
                />
              </Field>

              <Field n="03" cap="Departs" className="select span4">
                <Select
                  value={flight.departure_time}
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
                  value={flight.arrival_time}
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
                  value={flight.stops}
                  onChange={(v) => patchFlight({ stops: v })}
                  options={["zero", "one", "two_or_more"]}
                />
              </Field>

              <Field n="06" cap="Airline" className="select span4">
                <Select
                  value={flight.airline}
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
                  value={flight.class}
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
                    value={flight.duration}
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
                    value={flight.duration}
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
                    value={flight.days_left}
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
                    value={flight.days_left}
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
                  value={stay.hotel}
                  onChange={(v) => patchStay({ hotel: v })}
                  options={stayOptions?.hotel ?? ["City Hotel", "Resort Hotel"]}
                />
              </Field>
              <Field n="02" cap="Month" className="select span4">
                <Select
                  value={stay.arrival_date_month}
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
                  value={String(stay.arrival_date_year)}
                  onChange={(v) => patchStay({ arrival_date_year: +v })}
                  options={["2015", "2016", "2017"]}
                />
              </Field>

              <Field n="04" cap="Arrival week" className="stepper span4">
                <Stepper
                  value={stay.arrival_date_week_number}
                  onChange={(v) => patchStay({ arrival_date_week_number: v })}
                  min={1}
                  max={53}
                />
              </Field>
              <Field n="05" cap="Day of month" className="stepper span4">
                <Stepper
                  value={stay.arrival_date_day_of_month}
                  onChange={(v) => patchStay({ arrival_date_day_of_month: v })}
                  min={1}
                  max={31}
                />
              </Field>
              <Field n="06" cap="Adults" className="stepper span4">
                <Stepper
                  value={stay.adults}
                  onChange={(v) => patchStay({ adults: v })}
                  min={1}
                  max={10}
                />
              </Field>

              <Field n="07" cap="Week-nights" className="stepper span4">
                <Stepper
                  value={stay.stays_in_week_nights}
                  onChange={(v) => patchStay({ stays_in_week_nights: v })}
                  min={0}
                  max={10}
                />
              </Field>
              <Field n="08" cap="Weekend-nights" className="stepper span4">
                <Stepper
                  value={stay.stays_in_weekend_nights}
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
        </div>
      </section>

      {/* ------------------------------------------------------- result */}
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
          Estimates, not quotes. Neural models served on-device.
        </span>
      </footer>
    </>
  );
}
