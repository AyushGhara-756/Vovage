"""Package builder — turns two already-shaped search boards into priced
trip packages.

Ground rules of the logic:

- It never touches the network. It consumes the shaped flight payload
  (round-trip fares) and shaped hotel payload (whole-stay rates) that
  ``serp_service.run_search`` already fetched or replayed, and computes
  package tiers from those. Every tier therefore costs zero additional
  SerpApi calls.
- Flight cost = cheapest round-trip fare × travellers. SerpApi fares are
  quoted per traveller, so the whole party's fare is fare × adults+children.
- Hotel cost = the board's whole-stay rate for the exact dates. When a
  property only exposes a per-night rate, it's nights × rate — labelled
  honestly.
- Three fixed tiers give the tradeoff curve in one shot:
    saver    — cheapest flight + cheapest stay
    balanced — cheapest flight + highest-rated stay that fits the budget
    comfort  — highest-rated stay even if it pushes the total (flagged)
"""


class PackageError(Exception):
    """Raised when the boards can't produce any package."""


def _fares(flight):
    """Round-trip fare candidates, cheapest-first board order."""
    for key in ("selected", "best", "others"):
        fares = [o for o in (flight.get(key) or []) if o.get("price")]
        if fares:
            return fares
    raise PackageError("flight board came back without any farespairs")


def _cheapest_fare(flight):
    return min(_fares(flight), key=lambda o: o["price"])


def _stay_options(hotel, nights):
    """Candidates: (stay card, whole-stay rate, nightly flag)."""
    out = []
    for s in hotel.get("properties") or []:
        total, nightly = s.get("total_price"), False
        if not total:
            per_night = s.get("price")
            if not per_night:
                continue
            total, nightly = per_night * nights, True
        if total > 0:
            out.append((s, total, nightly))
    if not out:
        raise PackageError("hotel board came back without any priced stays")
    return out


def _flight_digest(option):
    legs = option.get("legs") or []
    first = legs[0] if legs else {}
    last = legs[-1] if legs else {}
    return {
        "dep_time": first.get("dep_time"),
        "arr_time": last.get("arr_time"),
        "dep_code": first.get("dep_code"),
        "arr_code": last.get("arr_code"),
        "airline": first.get("airline"),
        "nonstop": len(legs) <= 1,
        "stops": option.get("layovers") and len(option["layovers"]) or 0,
        "duration": option.get("duration"),
        "airline_logo": option.get("logo") or first.get("logo"),
    }


def _stay_digest(stay, total, nightly, nights):
    return {
        "name": stay.get("name"),
        "type": stay.get("type"),
        "link": stay.get("link"),
        "rating": stay.get("rating"),
        "reviews": stay.get("reviews"),
        "class_num": stay.get("class_num"),
        "stars": stay.get("class_num") or 0,
        "amenities": (stay.get("amenities") or [])[:4],
        "image": (stay.get("images") or [{}])[0].get("thumb"),
        "area": (stay.get("nearby") or [{}])[0].get("name"),
        "hotel_total": total,
        "per_night_estimate": nightly,  # rate × nights fallback, not a quote
        "nightly_note": "whole-stay rate" if not nightly
        else f"rate × {nights} nights",
    }


def _pack(tier, fare, choice, flight_cost, budget, nights):
    stay, total, nightly = choice
    stay_cost = total
    fare_total = flight_cost
    package_total = flight_cost + total
    within = package_total <= budget
    return {
        "tier": tier,
        "total": package_total,
        "breakdown": {"flight": fare_total, "hotel": stay_cost},
        "within_budget": within,
        "headroom": budget - package_total if within else None,
        "over_by": None if within else package_total - budget,
        "flight": _flight_digest(fare),
        "stay": _stay_digest(stay, stay_cost, nightly, nights),
    }


def build_packages(flight, hotel, budget, *, nights, adults=2, children=0):
    """Compose the three package tiers from the two shaped boards."""
    budget = int(budget)
    if budget <= 0:
        raise PackageError("budget must be a positive number of rupees")
    if nights < 1:
        raise PackageError("trip must include at least one night")

    travellers = adults + children
    fare = _cheapest_fare(flight)
    flight_cost = fare["price"] * travellers
    candidates = _stay_options(hotel, nights)

    cheapest_stay = min(candidates, key=lambda t: t[1])
    best_rated = max(candidates, key=lambda t: (t[0].get("rating") or 0, -t[1]))
    balanced = None
    for stay, total, nightly in sorted(
            candidates, key=lambda t: (-(t[0].get("rating") or 0), t[1])):
        if flight_cost + total <= budget:
            balanced = (stay, total, nightly)
            break

    packages = []

    def add(tier, choice):
        packages.append(_pack(tier, fare, choice, flight_cost, budget, nights))

    add("saver", cheapest_stay)
    if balanced:
        add("balanced", balanced)
    add("comfort", best_rated)

    return {
        "currency": (flight.get("currency")
                     or hotel.get("currency") or "INR"),
        "budget": budget,
        "nights": nights,
        "party": {"adults": adults, "children": children,
                  "travellers": travellers},
        "q": hotel.get("q"),
        "trip": flight.get("trip"),
        "packages": packages,
    }
