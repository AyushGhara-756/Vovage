const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      (data as { error?: string }).error ?? `request failed (${res.status})`;
    throw new Error(msg.split(";")[0]);
  }
  return data as T;
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

/* ------------------------------------------------------------------ live search (SerpApi) */

export type AirportHit = {
  code: string;
  name: string;
  city: string;
  country: string;
};

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
  cached: boolean;
  fetched_on: string;
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
  cached: boolean;
  fetched_on: string;
  q: string;
  count: number;
  properties: StayOption[];
};

export const searchLiveFlights = (p: {
  origin: string;
  destination: string;
  outbound_date: string;
  return_date: string;
  travel_class: string;
  adults: number;
  children: number;
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
  return get<FlightSearch>(`/flight/search?${qs}`);
};

export const searchLiveStays = (p: {
  q: string;
  check_in_date: string;
  check_out_date: string;
  adults: number;
  children: number;
  sort_by: string;
}) => {
  const qs = new URLSearchParams({
    q: p.q,
    check_in_date: p.check_in_date,
    check_out_date: p.check_out_date,
    adults: String(p.adults),
    children: String(p.children),
    sort_by: p.sort_by,
  });
  return get<StaySearch>(`/hotel/search?${qs}`);
};

/* ------------------------------------------------------------------ packages */

export type PackageFlight = {
  dep_time: string | null;
  arr_time: string | null;
  dep_code: string | null;
  arr_code: string | null;
  airline: string | null;
  nonstop: boolean;
  stops: number;
  duration: number | null;
  airline_logo: string | null;
};

export type PackageStay = {
  name: string | null;
  type: string | null;
  link: string | null;
  rating: number | null;
  reviews: number | null;
  class_num: number | null;
  stars: number;
  amenities: string[];
  image: string | null;
  area: string | null;
  hotel_total: number;
  per_night_estimate: boolean;
  nightly_note: string;
};

export type PackageTier = "saver" | "balanced" | "comfort";

export type PackageOffer = {
  tier: PackageTier;
  total: number;
  breakdown: { flight: number; hotel: number };
  within_budget: boolean;
  headroom: number | null;
  over_by: number | null;
  flight: PackageFlight;
  stay: PackageStay;
};

export type PackageBoard = {
  cached: boolean;
  fetched_on: string;
};

export type PackageSearch = {
  currency: string;
  budget: number;
  trip_budget: number;
  nights: number;
  party: { adults: number; children: number; travellers: number };
  q: string | null;
  trip: FlightSearch["trip"] | null;
  packages: PackageOffer[];
  boards: { flight: PackageBoard; hotel: PackageBoard };
};

export const searchPackages = (p: {
  origin: string;
  destination: string;
  q: string;
  outbound_date: string;
  return_date: string;
  budget: number;
  travel_class: string;
  adults: number;
  children: number;
}) => {
  const qs = new URLSearchParams({
    origin: p.origin,
    destination: p.destination,
    q: p.q,
    outbound_date: p.outbound_date,
    return_date: p.return_date,
    budget: String(p.budget),
    cabin: p.travel_class,
    adults: String(p.adults),
    children: String(p.children),
  });
  return get<PackageSearch>(`/package/search?${qs}`);
};
