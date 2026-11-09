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
