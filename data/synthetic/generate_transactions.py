"""
Generate a synthetic dataset of 1000 transactions for development and testing.
Outputs: data/synthetic/transactions.csv
"""

import random
import uuid
from datetime import datetime, timedelta

import pandas as pd

SEED = 42
random.seed(SEED)

N_ROWS = 1000
FRAUD_RATE = 0.08  # 8% fraud

USER_IDS = [f"usr_{str(i).zfill(5)}" for i in range(1, 201)]
MERCHANT_IDS = [f"mrc_{str(i).zfill(5)}" for i in range(1, 51)]
DEVICE_IDS = [f"dev_{uuid.uuid4().hex[:8]}" for _ in range(150)]

CURRENCIES = ["USD", "EUR", "GBP", "CAD"]
PAYMENT_METHODS = ["credit_card", "debit_card", "digital_wallet"]
DEVICE_TYPES = ["mobile", "desktop", "tablet"]
MERCHANT_CATEGORIES = ["electronics", "groceries", "travel", "clothing", "restaurants", "gaming"]
LOCATIONS = [
    ("US", "New York"),
    ("US", "Los Angeles"),
    ("US", "Chicago"),
    ("GB", "London"),
    ("CA", "Toronto"),
    ("DE", "Berlin"),
    ("FR", "Paris"),
    ("RU", "Moscow"),
    ("NG", "Lagos"),
    ("BR", "Sao Paulo"),
    ("MX", "Mexico City"),
]
LOW_RISK_LOCATIONS = [loc for loc in LOCATIONS if loc[0] in {"US", "CA", "GB"}]
HIGH_RISK_LOCATIONS = [loc for loc in LOCATIONS if loc[0] in {"RU", "NG", "BR", "MX"}]

START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2024, 3, 31)


def random_timestamp():
    delta = END_DATE - START_DATE
    return START_DATE + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def random_timestamp_with_hour(hour: int):
    day_delta = (END_DATE.date() - START_DATE.date()).days
    base_day = START_DATE + timedelta(days=random.randint(0, day_delta))
    return base_day.replace(
        hour=hour,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
    )


def random_ip():
    return ".".join(str(random.randint(1, 254)) for _ in range(4))


def generate_transaction(is_fraud: bool) -> dict:
    if is_fraud:
        country, city = random.choice(
            random.choices(
                [HIGH_RISK_LOCATIONS, LOCATIONS],
                weights=[0.60, 0.40],
                k=1,
            )[0]
        )
        hour = random.choices(
            [random.choice([0, 1, 2, 3, 4, 5, 23]), random.randint(6, 22)],
            weights=[0.70, 0.30],
            k=1,
        )[0]
        timestamp = random_timestamp_with_hour(hour)
        payment_method = random.choices(
            PAYMENT_METHODS,
            weights=[0.50, 0.20, 0.30],
            k=1,
        )[0]
        merchant_category = random.choices(
            MERCHANT_CATEGORIES,
            weights=[0.35, 0.07, 0.20, 0.06, 0.07, 0.25],
            k=1,
        )[0]
        device_id = None if random.random() < 0.35 else random.choice(DEVICE_IDS)
    else:
        country, city = random.choice(
            random.choices(
                [LOW_RISK_LOCATIONS, LOCATIONS],
                weights=[0.75, 0.25],
                k=1,
            )[0]
        )
        hour = random.choices(
            [random.randint(8, 20), random.choice([0, 1, 2, 3, 4, 5, 6, 7, 21, 22, 23])],
            weights=[0.80, 0.20],
            k=1,
        )[0]
        timestamp = random_timestamp_with_hour(hour)
        payment_method = random.choices(
            PAYMENT_METHODS,
            weights=[0.30, 0.60, 0.10],
            k=1,
        )[0]
        merchant_category = random.choices(
            MERCHANT_CATEGORIES,
            weights=[0.05, 0.35, 0.05, 0.20, 0.30, 0.05],
            k=1,
        )[0]
        device_id = random.choice(DEVICE_IDS)

    amount = round(random.uniform(500, 3000), 2) if is_fraud else round(random.uniform(5, 800), 2)
    is_international = country != "US"

    return {
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "user_id": random.choice(USER_IDS),
        "merchant_id": random.choice(MERCHANT_IDS),
        "amount": amount,
        "currency": random.choice(CURRENCIES),
        "payment_method": payment_method,
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "country": country,
        "city": city,
        "device_id": device_id,
        "ip_address": random_ip(),
        "device_type": random.choice(DEVICE_TYPES),
        "merchant_category": merchant_category,
        "is_international": is_international,
        "is_fraud": is_fraud,
    }


def main():
    n_fraud = int(N_ROWS * FRAUD_RATE)
    n_normal = N_ROWS - n_fraud

    records = (
        [generate_transaction(is_fraud=False) for _ in range(n_normal)]
        + [generate_transaction(is_fraud=True) for _ in range(n_fraud)]
    )
    random.shuffle(records)

    df = pd.DataFrame(records)
    output_path = "data/synthetic/transactions.csv"
    df.to_csv(output_path, index=False)

    print(f"Generated {len(df)} transactions -> {output_path}")
    print(f"  Normal:      {n_normal}")
    print(f"  Fraudulent:  {n_fraud}")


if __name__ == "__main__":
    main()
