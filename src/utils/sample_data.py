"""
sample_data.py
Synthetic Superstore Dataset Generator

Generates a realistic 2,000-row Superstore-style DataFrame with seeded RNG
for reproducibility. Used for testing and demo fallback when the real CSV
is unavailable.

Usage:
    from src.utils.sample_data import load_sample_data
    df = load_sample_data()            # cached after first call
    df = load_sample_data(force=True)  # regenerate
"""

import os

import numpy as np
import pandas as pd

_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
_CACHE_PATH = os.path.join(_DATA_DIR, "sample.csv")

_REGIONS = ["West", "East", "Central", "South"]

_STATES_BY_REGION = {
    "West":    ["California", "Washington", "Oregon", "Nevada", "Arizona", "Colorado"],
    "East":    ["New York", "Pennsylvania", "Virginia", "Florida", "New Jersey", "Massachusetts"],
    "Central": ["Texas", "Illinois", "Ohio", "Michigan", "Wisconsin", "Missouri"],
    "South":   ["Georgia", "North Carolina", "Tennessee", "Alabama", "Louisiana", "Mississippi"],
}

_CITIES_BY_STATE = {
    "California": ["Los Angeles", "San Francisco", "San Diego"],
    "Washington": ["Seattle", "Spokane"],
    "Oregon": ["Portland", "Eugene"],
    "Nevada": ["Las Vegas", "Reno"],
    "Arizona": ["Phoenix", "Tucson"],
    "Colorado": ["Denver", "Colorado Springs"],
    "New York": ["New York City", "Buffalo", "Albany"],
    "Pennsylvania": ["Philadelphia", "Pittsburgh"],
    "Virginia": ["Richmond", "Norfolk"],
    "Florida": ["Miami", "Orlando", "Tampa"],
    "New Jersey": ["Newark", "Jersey City"],
    "Massachusetts": ["Boston", "Worcester"],
    "Texas": ["Houston", "Dallas", "Austin"],
    "Illinois": ["Chicago", "Springfield"],
    "Ohio": ["Columbus", "Cleveland"],
    "Michigan": ["Detroit", "Grand Rapids"],
    "Wisconsin": ["Milwaukee", "Madison"],
    "Missouri": ["Kansas City", "St. Louis"],
    "Georgia": ["Atlanta", "Savannah"],
    "North Carolina": ["Charlotte", "Raleigh"],
    "Tennessee": ["Nashville", "Memphis"],
    "Alabama": ["Birmingham", "Montgomery"],
    "Louisiana": ["New Orleans", "Baton Rouge"],
    "Mississippi": ["Jackson", "Gulfport"],
}

_CATEGORIES = {
    "Furniture": {
        "sub_categories": ["Chairs", "Tables", "Bookcases", "Furnishings"],
        "products": {
            "Chairs":      ["Task Chair Pro", "Ergonomic Mesh Chair", "Executive Chair", "Folding Chair Pack"],
            "Tables":      ["Folding Table", "Conference Table", "Writing Desk", "Standing Desk"],
            "Bookcases":   ["5-Shelf Bookcase", "Glass-Door Bookcase", "Corner Bookcase"],
            "Furnishings": ["Lamp Set", "Curtain Panels", "Area Rug", "Picture Frame Set"],
        },
        "base_price": 80, "price_scale": 900,
        "margin_lo": -0.08, "margin_hi": 0.18,
    },
    "Office Supplies": {
        "sub_categories": ["Binders", "Paper", "Storage", "Art", "Labels", "Envelopes", "Fasteners", "Supplies"],
        "products": {
            "Binders":    ["Heavy Duty Binder", "Round Ring Binder", "View Binder 3-pack"],
            "Paper":      ["Copy Paper Ream", "Legal Pad Pack", "Cardstock Pack"],
            "Storage":    ["Mobile File Cabinet", "Storage Box Set", "Magazine Files 6-pack"],
            "Art":        ["Sketch Pad Set", "Watercolor Kit", "Drawing Pencil Set"],
            "Labels":     ["Address Labels 250-ct", "File Folder Labels", "Name Badge Holders"],
            "Envelopes":  ["Business Envelopes 100-ct", "Catalog Envelopes", "Padded Mailers 10-ct"],
            "Fasteners":  ["Electric Stapler", "Binder Clips Assorted", "Rubber Band Bag"],
            "Supplies":   ["Scissors 3-pack", "Tape Dispenser Set", "Correction Tape 4-pack"],
        },
        "base_price": 4, "price_scale": 110,
        "margin_lo": 0.18, "margin_hi": 0.48,
    },
    "Technology": {
        "sub_categories": ["Phones", "Machines", "Accessories", "Copiers"],
        "products": {
            "Phones":      ["Cisco Desk Phone", "Poly BT Headset", "Conference Speaker 360"],
            "Machines":    ["Brother HL Printer", "HP LaserJet Pro", "Epson WorkForce Scanner"],
            "Accessories": ["Monitor Arm Stand", "7-Port USB Hub", "HDMI Cable 3-pack"],
            "Copiers":     ["Canon imageRunner", "Xerox WorkCentre 6515", "Ricoh MP C307"],
        },
        "base_price": 30, "price_scale": 2200,
        "margin_lo": 0.02, "margin_hi": 0.28,
    },
}

_SEGMENTS = ["Consumer", "Corporate", "Home Office"]
_SHIP_MODES = ["Standard Class", "Second Class", "First Class", "Same Day"]
_DISCOUNT_POOL = [0.0] * 6 + [0.1, 0.1, 0.2, 0.3, 0.4, 0.5]


def _make_row(rng: np.random.Generator, order_id: str, order_date: str) -> dict:
    region = rng.choice(_REGIONS)
    state = rng.choice(_STATES_BY_REGION[region])
    city = rng.choice(_CITIES_BY_STATE[state])
    category = rng.choice(list(_CATEGORIES.keys()))
    cfg = _CATEGORIES[category]
    sub_cat = rng.choice(cfg["sub_categories"])
    product = rng.choice(cfg["products"][sub_cat])
    discount = rng.choice(_DISCOUNT_POOL)
    quantity = int(rng.integers(1, 14))

    unit_price = cfg["base_price"] + rng.random() * cfg["price_scale"]
    sales = round(unit_price * quantity * (1.0 - discount), 2)
    margin = cfg["margin_lo"] + rng.random() * (cfg["margin_hi"] - cfg["margin_lo"])
    profit = round(sales * margin, 2)

    return {
        "Order ID": order_id,
        "Order Date": order_date,
        "Ship Mode": rng.choice(_SHIP_MODES),
        "Customer ID": f"CG-{int(rng.integers(10000, 99999))}",
        "Segment": rng.choice(_SEGMENTS),
        "City": city,
        "State": state,
        "Region": region,
        "Product Name": product,
        "Category": category,
        "Sub-Category": sub_cat,
        "Sales": sales,
        "Quantity": quantity,
        "Discount": discount,
        "Profit": profit,
    }


def generate_superstore_data(n_rows: int = 2000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_orders = max(1, n_rows // 3)
    order_ids = [f"CA-{2015 + int(rng.integers(0, 4))}-{100000 + i}" for i in range(n_orders)]

    start = pd.Timestamp("2015-01-01")
    date_range = (pd.Timestamp("2018-12-31") - start).days

    rows = []
    for _ in range(n_rows):
        oid = order_ids[int(rng.integers(0, n_orders))]
        days_off = int(rng.integers(0, date_range))
        order_date = (start + pd.Timedelta(days=days_off)).strftime("%m/%d/%Y")
        rows.append(_make_row(rng, oid, order_date))

    return pd.DataFrame(rows).sort_values("Order Date").reset_index(drop=True)


def load_sample_data(
    cache_path: str = _CACHE_PATH,
    n_rows: int = 2000,
    force: bool = False,
) -> pd.DataFrame:
    os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
    if not force and os.path.exists(cache_path):
        return pd.read_csv(cache_path)
    df = generate_superstore_data(n_rows=n_rows)
    df.to_csv(cache_path, index=False)
    return df
