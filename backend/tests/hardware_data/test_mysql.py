"""Set RUN_MYSQL_TESTS=1 to exercise real constraints; all DML is rolled back."""

import os
import unittest
import uuid
from copy import deepcopy

import mysql.connector

from app.core.parts_database import get_connection
from app.domains.hardware.ingestion.common import DATA, read_json
from app.domains.hardware.ingestion.import_compatibility import upsert_compatibility
from app.domains.hardware.ingestion.import_parts import upsert_parts


@unittest.skipUnless(os.getenv("RUN_MYSQL_TESTS") == "1", "MySQL 통합 검사는 명시적으로 실행")
class MySQLTests(unittest.TestCase):
    def setUp(self):
        self.connection = get_connection()
        self.cursor = self.connection.cursor()

    def tearDown(self):
        self.connection.rollback()
        self.cursor.close()
        self.connection.close()

    def make_quotes(self):
        self.cursor.execute(
            "INSERT INTO users (display_name) VALUES (%s)", ("__rollback_test_" + uuid.uuid4().hex,)
        )
        uid = self.cursor.lastrowid
        self.cursor.execute(
            "INSERT INTO consultations (user_id,purpose,requirements) VALUES (%s,'test',JSON_OBJECT())",
            (uid,),
        )
        cid = self.cursor.lastrowid
        ids = []
        for _ in range(2):
            self.cursor.execute("INSERT INTO quotes (consultation_id) VALUES (%s)", (cid,))
            ids.append(self.cursor.lastrowid)
        self.cursor.execute("SELECT part_id FROM parts ORDER BY part_id LIMIT 1")
        return ids, self.cursor.fetchone()[0]

    def test_item_cannot_reference_another_quote(self):
        quotes, part = self.make_quotes()
        self.cursor.execute(
            "INSERT INTO quote_items (quote_id,part_id,part_name_snapshot,quantity,configuration) VALUES (%s,%s,'test',1,JSON_OBJECT())",
            (quotes[0], part),
        )
        item = self.cursor.lastrowid
        with self.assertRaises(mysql.connector.IntegrityError):
            self.cursor.execute(
                "INSERT INTO quote_validations (quote_id,quote_version,item_a_id,check_type,result,reason,input_snapshot,evidence_snapshot) VALUES (%s,1,%s,'SOCKET','UNKNOWN','test',JSON_OBJECT(),JSON_OBJECT())",
                (quotes[1], item),
            )

    def test_zero_quantity_is_rejected(self):
        quotes, part = self.make_quotes()
        with self.assertRaises(mysql.connector.Error):
            self.cursor.execute(
                "INSERT INTO quote_items (quote_id,part_id,part_name_snapshot,quantity,configuration) VALUES (%s,%s,'test',0,JSON_OBJECT())",
                (quotes[0], part),
            )

    def test_repeated_import_keeps_ids_and_rows(self):
        parts = read_json(DATA / "processed/parts.json")["parts"]
        evidence = read_json(DATA / "processed/compatibility.json")["records"]

        def identities():
            self.cursor.execute("SELECT part_id FROM parts ORDER BY part_id")
            p = self.cursor.fetchall()
            self.cursor.execute(
                "SELECT compatibility_id FROM part_compatibility ORDER BY compatibility_id"
            )
            return p, self.cursor.fetchall()

        before = identities()
        for _ in range(2):
            self.assertEqual(upsert_parts(self.connection, parts)["inserted"], 0)
            self.assertEqual(
                upsert_compatibility(self.connection, evidence, "2026-11-11T06:00:00Z")["inserted"],
                0,
            )
        self.assertEqual(before, identities())

    def test_failed_price_refresh_preserves_previous_price_and_quote(self):
        quotes, part = self.make_quotes()
        self.cursor.execute("SELECT name FROM parts WHERE part_id=%s", (part,))
        name = self.cursor.fetchone()[0]
        self.cursor.execute(
            "UPDATE parts SET current_price=100,price_source_url='https://example.com/test',price_checked_at='2026-11-11 06:00:00' WHERE part_id=%s",
            (part,),
        )
        self.cursor.execute(
            "INSERT INTO quote_items (quote_id,part_id,part_name_snapshot,quantity,unit_price,price_source_url,price_checked_at,configuration) VALUES (%s,%s,%s,1,80,'https://example.com/old','2026-11-10 06:00:00',JSON_OBJECT())",
            (quotes[0], part, name),
        )
        records = deepcopy(read_json(DATA / "processed/parts.json")["parts"])
        row = next(r for r in records if r["name"] == name)
        row.update(current_price=None, price_source_url=None, price_checked_at=None)
        upsert_parts(self.connection, [row])
        self.cursor.execute("SELECT current_price FROM parts WHERE part_id=%s", (part,))
        self.assertEqual(self.cursor.fetchone()[0], 100)
        row.update(
            current_price="120",
            price_source_url="https://example.com/new",
            price_checked_at="2026-11-11T07:00:00Z",
        )
        upsert_parts(self.connection, [row])
        self.cursor.execute("SELECT unit_price FROM quote_items WHERE quote_id=%s", (quotes[0],))
        self.assertEqual(self.cursor.fetchone()[0], 80)


if __name__ == "__main__":
    unittest.main()
