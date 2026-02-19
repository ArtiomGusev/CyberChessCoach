from sqlalchemy import create_engine
from .retention import build_retention_report

DATABASE_URL = "sqlite:///data/seca.db"


def main():
    engine = create_engine(DATABASE_URL)
    report = build_retention_report(engine)

    print("\n=== SECA Retention Report ===")
    for k, v in report.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
