"""
Quick test — run this to verify the database layer works correctly.
Run from the SpectraSoft folder:  python test_db.py

Expected output:
  Database created at: ...data.db
  Table created: analytical_groups
  Created group: LAS 2023 (id=1)
  Loaded group: LAS 2023
  Updated group name test passed
  Deleted group test passed
  All database tests passed.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import init_db, get_session, DB_PATH
from core.models import AnalyticalGroup


def test_database():
    print(f"Database will be created at: {DB_PATH}")

    # 1. Create tables
    init_db()
    print("Tables created: analytical_groups")

    session = get_session()
    try:
        # 2. Create a group
        group = AnalyticalGroup(
            name="LAS 2023",
            display_order=1,
            page_01_condition={
                "analytical_method": "P:PDA+Integ. Mode",
                "purge_seq1": "3",
                "source_seq1": "3 Peak Spark",
                "source_seq2": "Normal Spark",
                "source_seq3": "Lamp",
                "source_clean": "Cleaning",
                "preburn_seq1": "200",
                "preburn_seq2": "200",
                "preburn_seq3": "0",
                "integ_seq1": "300",
                "integ_seq2": "23",
                "integ_seq3": "0",
            }
        )
        session.add(group)
        session.commit()
        session.refresh(group)
        print(f"Created group: {group.name} (id={group.id})")

        # 3. Load it back
        loaded = session.query(AnalyticalGroup).filter_by(name="LAS 2023").first()
        assert loaded is not None
        assert loaded.page_01_condition["source_seq1"] == "3 Peak Spark"
        print(f"Loaded group: {loaded.name}")

        # 4. Update
        loaded.name = "LAS 2023 UPDATED"
        session.commit()
        check = session.query(AnalyticalGroup).filter_by(name="LAS 2023 UPDATED").first()
        assert check is not None
        print("Updated group name test passed")

        # 5. Delete
        session.delete(check)
        session.commit()
        gone = session.query(AnalyticalGroup).filter_by(name="LAS 2023 UPDATED").first()
        assert gone is None
        print("Deleted group test passed")

        print("\nAll database tests passed.")

    except Exception as e:
        session.rollback()
        print(f"\nTest FAILED: {e}")
        raise
    finally:
        session.close()
        # Clean up test db file
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            print("Test database file cleaned up.")


if __name__ == "__main__":
    test_database()