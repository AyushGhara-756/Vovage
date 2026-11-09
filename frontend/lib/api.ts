const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`request failed (${res.status})`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      (data as { error?: string }).error ?? `request failed (${res.status})`;
    // Flask validation messages are long; first clause stays readable
    throw new Error(msg.split(";")[0]);
  }
  return data as T;
}

export type FlightOptions = {
  options: {
    airline: string[];
    source_city: string[];
    destination_city: string[];
    departure_time: string[];
    arrival_time: string[];
    stops: string[];
    class: string[];
  };
  duration_range: [number, number];
  days_left_range: [number, number];
};

export type FlightQuery = {
  airline: string;
  source_city: string;
  departure_time: string;
  stops: string;
  arrival_time: string;
  destination_city: string;
  class: string;
  duration: number;
  days_left: number;
};

export const fetchFlightOptions = () =>
  get<FlightOptions>("/flight/options").then(normalizeFlightOptions);

// some Flask responses nest options flat vs. nested — be tolerant
function normalizeFlightOptions(o: FlightOptions): FlightOptions {
  return o;
}

export const predictFlight = (query: FlightQuery) =>
  post<{ predicted_price: number[] }>("/flight/predict", query);

export type HotelOptions = {
  [key: string]: string[];
};

export type HotelQuery = {
  hotel: string;
  arrival_date_year: number;
  arrival_date_month: string;
  arrival_date_week_number: number;
  arrival_date_day_of_month: number;
  stays_in_weekend_nights: number;
  stays_in_week_nights: number;
  adults: number;
};

export const predictStay = (query: HotelQuery) =>
  post<{ adr: number[] }>("/hotel/predict", query);

export const fetchStayOptions = () => get<HotelOptions>("/hotel/options");

/* ------------------------------------------------------------------ live board (SerpApi) */

export type Budget = {
  max: number;
  used: number;
  remaining: number;
  calls: { ts: number; kind: string; key: string }[];
};

export type AirportHit = {
  code: string;
  name: string;
  city: string;
  country: string;
};

export const fetchBudget = () => get<Budget>("/serp/budget");

export const searchAirports = (q: string) =>
  get<{ results: AirportHit[] }>(
    `/flight/airports?q=${encodeURIComponent(q)}&limit=8`,
  );

export type FlightLeg = {
  dep_code: string;
  dep_name: string;
  dep_time: string;
  arr_code: string;
  arr_name: string;
  arr_time: string;
  duration: number;
  airplane: string;
  airline: string;
  logo: string;
  cabin: string;
  flight: string;
  legroom: string;
  overnight: boolean;
};

export type FlightOption = {
  price: number;
  legs: FlightLeg[];
  layovers: { duration: number; name: string; overnight: boolean }[];
  duration: number;
  logo: string;
  carbon: number | null;
  token: string;
};

export type Insights = {
  low: number;
  level: string;
  range: number[];
  history: [number, number][];
};

export type FlightSearch = {
  currency: string;
  mock: boolean;
  cached: boolean;
  fetched_on: string;
  budget: Budget;
  insights: Insights | null;
  departures: FlightOption[];
  returns: FlightOption[];
  selected: FlightOption[];
  best: FlightOption[];
  others: FlightOption[];
  trip: {
    origin: string;
    destination: string;
    outbound_date: string;
    return_date: string;
  };
};

export type StayOption = {
  name: string;
  type: string;
  link: string;
  hotel_class: string;
  class_num: number;
  rating: number;
  reviews: number;
  location_rating: number;
  check_in_time: string;
  check_out_time: string;
  price: number;
  price_display: string;
  unit_price: number;
  total_price: number;
  total_display: string;
  deal: string | null;
  deal_description: string | null;
  amenities: string[];
  images: { thumb: string; full: string }[];
  nearby: { name: string; by: string | null }[];
  desc: string;
  coords: { latitude: number; longitude: number };
};

export type StaySearch = {
  currency: string;
  mock: boolean;
  cached: boolean;
  fetched_on: string;
  budget: Budget;
  q: string;
  count: number;
  properties: StayOption[];
};

export type LiveFeed = "live" | "replay";

export const searchLiveFlights = (p: {
  origin: string;
  destination: string;
  outbound_date: string;
  return_date: string;
  travel_class: string;
  adults: number;
  children: number;
  feed: LiveFeed;
}) => {
  const qs = new URLSearchParams({
    origin: p.origin,
    destination: p.destination,
    outbound_date: p.outbound_date,
    return_date: p.return_date,
    travel_class: p.travel_class,
    adults: String(p.adults),
    children: String(p.children),
  });
  if (p.feed === "replay") qs.set("mock", "1");
  return get<FlightSearch>(`/flight/search?${qs}`);
};

export const searchLiveStays = (p: {
  q: string;
  check_in_date: string;
  check_out_date: string;
  adults: number;
  children: number;
  sort_by: string;
  feed: LiveFeed;
}) => {
  const qs = new URLSearchParams({
    q: p.q,
    check_in_date: p.check_in_date,
    check_out_date: p.check_out_date,
    adults: String(p.adults),
    children: String(p.children),
    sort_by: p.sort_by,
  });
  if (p.feed === "replay") qs.set("mock", "1");
  return get<StaySearch>(`/hotel/search?${qs}`);
};
