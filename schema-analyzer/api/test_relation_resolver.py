"""
Tests unitaires pour relation_resolver.py (livraison #5, backlog
BACKLOG.md -- "Interface de gestion (affectation des relations)").
Fonctions PURES : testables sans mock réseau/base, avec un `executor`
factice injecté directement.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from relation_resolver import (
    resolve_foreign_key,
    resolve_row_relations,
    assign_foreign_key,
)
from relation_validator import extract_candidate_ids


def make_executor(data):
    """Crée un executor factice à partir d'un dict
    {sql_string: {"columns": [...], "rows": [...], "row_count": N}}.
    Les requêtes IN avec plusieurs valeurs sont normalisées (tri) pour
    correspondre indépendamment de l'ordre."""
    def executor(sql):
        # Normalise les requêtes IN pour matcher indépendamment de l'ordre
        for key in data:
            if _normalize_in_clause(key) == _normalize_in_clause(sql):
                return data[key]
        # Par défaut : liste vide
        return {"columns": [], "rows": [], "row_count": 0}
    return executor


def _normalize_in_clause(sql):
    """Extrait et trie les valeurs d'un IN (...) pour comparaison
    indépendante de l'ordre."""
    import re
    match = re.search(r"IN \(([^)]+)\)", sql)
    if not match:
        return sql
    inner = match.group(1)
    values = sorted(v.strip().strip("'\"") for v in inner.split(","))
    return sql[:match.start()] + "IN (" + ", ".join(f"'{v}'" for v in values) + ")" + sql[match.end():]


class TestExtractCandidateIds(unittest.TestCase):
    def test_single_value(self):
        self.assertEqual(extract_candidate_ids("42", "foreign_key"), ["42"])

    def test_list_value(self):
        self.assertEqual(extract_candidate_ids("1, 2, 5", "list"), ["1", "2", "5"])

    def test_none(self):
        self.assertEqual(extract_candidate_ids(None, "foreign_key"), [])

    def test_empty_string(self):
        self.assertEqual(extract_candidate_ids("", "foreign_key"), [])


class TestResolveForeignKey(unittest.TestCase):
    def test_single_match(self):
        executor = make_executor({
            "SELECT * FROM clients WHERE id IN ('42')": {
                "columns": ["id", "name"],
                "rows": [[42, "Alice"]],
                "row_count": 1,
            }
        })
        result = resolve_foreign_key(executor, "42", "clients", "id")
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["rows"][0][1], "Alice")

    def test_no_match(self):
        executor = make_executor({
            "SELECT * FROM clients WHERE id IN ('999')": {
                "columns": ["id", "name"],
                "rows": [],
                "row_count": 0,
            }
        })
        result = resolve_foreign_key(executor, "999", "clients", "id")
        self.assertEqual(result["row_count"], 0)

    def test_none_value(self):
        executor = make_executor({})
        result = resolve_foreign_key(executor, None, "clients", "id")
        self.assertEqual(result["row_count"], 0)

    def test_empty_value(self):
        executor = make_executor({})
        result = resolve_foreign_key(executor, "", "clients", "id")
        self.assertEqual(result["row_count"], 0)

    def test_list_column(self):
        executor = make_executor({
            "SELECT * FROM sites WHERE id IN ('1', '2', '5')": {
                "columns": ["id", "label"],
                "rows": [[1, "Paris"], [2, "Lyon"], [5, "Marseille"]],
                "row_count": 3,
            }
        })
        result = resolve_foreign_key(executor, "1,2,5", "sites", "id", relation_type="list")
        self.assertEqual(result["row_count"], 3)

    def test_list_partial_match(self):
        executor = make_executor({
            "SELECT * FROM sites WHERE id IN ('1', '2', '99')": {
                "columns": ["id", "label"],
                "rows": [[1, "Paris"], [2, "Lyon"]],
                "row_count": 2,
            }
        })
        result = resolve_foreign_key(executor, "1,2,99", "sites", "id", relation_type="list")
        self.assertEqual(result["row_count"], 2)


class TestResolveRowRelations(unittest.TestCase):
    def test_full_resolution(self):
        executor = make_executor({
            "SELECT * FROM tickets WHERE id = '5'": {
                "columns": ["id", "client_id", "site_ids"],
                "rows": [[5, 42, "1,2,5"]],
                "row_count": 1,
            },
            "SELECT * FROM clients WHERE id IN ('42')": {
                "columns": ["id", "name"],
                "rows": [[42, "Alice"]],
                "row_count": 1,
            },
            "SELECT * FROM sites WHERE id IN ('1', '2', '5')": {
                "columns": ["id", "label"],
                "rows": [[1, "Paris"], [2, "Lyon"], [5, "Marseille"]],
                "row_count": 3,
            },
        })
        tables = {
            "tickets": {"columns": [
                {"name": "id", "primary_key": True},
                {"name": "client_id"},
                {"name": "site_ids"},
            ]},
            "clients": {"columns": [{"name": "id", "primary_key": True}, {"name": "name"}]},
            "sites": {"columns": [{"name": "id", "primary_key": True}, {"name": "label"}]},
        }
        relations = [
            {"status": "confirmed", "from_table": "tickets", "from_column": "client_id",
             "to_table": "clients", "to_column": "id", "relation_type": "foreign_key"},
            {"status": "confirmed", "from_table": "tickets", "from_column": "site_ids",
             "to_table": "sites", "to_column": "id", "relation_type": "list"},
        ]
        result = resolve_row_relations(executor, tables, relations, "tickets", "id", 5)
        self.assertIsNotNone(result)
        self.assertEqual(result["row"]["id"], 5)
        self.assertIn("client_id", result["resolved"])
        self.assertIn("site_ids", result["resolved"])
        self.assertEqual(result["resolved"]["client_id"]["target"]["row_count"], 1)
        self.assertEqual(result["resolved"]["site_ids"]["target"]["row_count"], 3)

    def test_row_not_found(self):
        executor = make_executor({
            "SELECT * FROM tickets WHERE id = '999'": {
                "columns": ["id", "client_id"],
                "rows": [],
                "row_count": 0,
            }
        })
        tables = {"tickets": {"columns": [{"name": "id", "primary_key": True}]}}
        result = resolve_row_relations(executor, tables, [], "tickets", "id", 999)
        self.assertIsNone(result)

    def test_ignores_proposed_relations(self):
        executor = make_executor({
            "SELECT * FROM tickets WHERE id = '5'": {
                "columns": ["id", "client_id"],
                "rows": [[5, 42]],
                "row_count": 1,
            },
        })
        tables = {
            "tickets": {"columns": [{"name": "id", "primary_key": True}, {"name": "client_id"}]},
        }
        relations = [
            {"status": "proposed", "from_table": "tickets", "from_column": "client_id",
             "to_table": "clients", "to_column": "id", "relation_type": "foreign_key"},
        ]
        result = resolve_row_relations(executor, tables, relations, "tickets", "id", 5)
        self.assertEqual(len(result["resolved"]), 0)

    def test_ignores_empty_values(self):
        executor = make_executor({
            "SELECT * FROM tickets WHERE id = '5'": {
                "columns": ["id", "client_id", "site_ids"],
                "rows": [[5, None, ""]],
                "row_count": 1,
            },
        })
        tables = {
            "tickets": {"columns": [{"name": "id", "primary_key": True}, {"name": "client_id"}, {"name": "site_ids"}]},
        }
        relations = [
            {"status": "confirmed", "from_table": "tickets", "from_column": "client_id",
             "to_table": "clients", "to_column": "id", "relation_type": "foreign_key"},
            {"status": "confirmed", "from_table": "tickets", "from_column": "site_ids",
             "to_table": "sites", "to_column": "id", "relation_type": "list"},
        ]
        result = resolve_row_relations(executor, tables, relations, "tickets", "id", 5)
        self.assertEqual(len(result["resolved"]), 0)


class TestAssignForeignKey(unittest.TestCase):
    def test_success(self):
        import unittest.mock as mock
        with mock.patch("relation_resolver.requests") as mock_requests:
            mock_resp = mock.Mock()
            mock_resp.status_code = 200
            mock_requests.put.return_value = mock_resp
            result = assign_foreign_key(
                "http://dba-api:5000", 1, "mydb", "tickets", "id", 5, "client_id", "42"
            )
            self.assertEqual(result["status"], "ok")
            mock_requests.put.assert_called_once()

    def test_error(self):
        import unittest.mock as mock
        with mock.patch("relation_resolver.requests") as mock_requests:
            mock_resp = mock.Mock()
            mock_resp.status_code = 400
            mock_resp.json.return_value = {"error": "ligne introuvable"}
            mock_requests.put.return_value = mock_resp
            result = assign_foreign_key(
                "http://dba-api:5000", 1, "mydb", "tickets", "id", 5, "client_id", "42"
            )
            self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
