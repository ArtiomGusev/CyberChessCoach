from sqlalchemy import create_engine
from .effectiveness import build_effectiveness_report

DATABASE_URL = "sqlite:///data/seca.db"


def main():
    engine = create_engine(DATABASE_URL)
    report = build_effectiveness_report(engine)

    print("\n=== SECA Learning Effectiveness ===")
    for k, v in report.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
