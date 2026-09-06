"""
Export du graphe relationnel (livraison #154, backlog BACKLOG.md #5,
étape suivante après l'éditeur de relations #152-#153). Produit une
représentation JSON ET XML des tables (noeuds) et des relations
CONFIRMÉES (arêtes) -- jamais les relations "proposed"/"rejected",
qui ne représentent pas encore un schéma validé par une personne.

Fonctions PURES (build_graph) ou quasi-pures (graph_to_xml, aucun
accès réseau/base) -- testables directement.
"""
import xml.etree.ElementTree as ET


def build_graph(connection_id, database, tables, relations):
    """`tables` : dict {nom_table: {"columns": [...]}} (voir
    schema_client.fetch_tables_and_columns). `relations` : liste de
    dicts (voir relations_store.list_relations) -- SEULES celles avec
    status="confirmed" deviennent des arêtes ; "proposed"/"rejected"
    sont exclues du graphe (pas encore/plus une relation validée)."""
    confirmed = [r for r in relations if r.get("status") == "confirmed"]
    return {
        "connection_id": connection_id,
        "database": database,
        "nodes": [
            {"table": tname, "columns": tinfo.get("columns", [])}
            for tname, tinfo in sorted(tables.items())
        ],
        "edges": [
            {
                "from_table": r["from_table"],
                "from_column": r["from_column"],
                "to_table": r["to_table"],
                "to_column": r["to_column"],
                "relation_type": r["relation_type"],
            }
            for r in confirmed
        ],
    }


def graph_to_xml(graph):
    """Renvoie une chaîne XML (déclaration `<?xml ...?>` incluse) --
    `xml.etree.ElementTree`, bibliothèque STANDARD, jamais une
    dépendance externe pour ça. Attributs pour les scalaires, un
    élément `<column>` par colonne (une LISTE ne se prête pas
    naturellement à un attribut XML)."""
    root = ET.Element("graph")
    if graph.get("connection_id") is not None:
        root.set("connection_id", str(graph["connection_id"]))
    if graph.get("database"):
        root.set("database", str(graph["database"]))

    nodes_el = ET.SubElement(root, "nodes")
    for node in graph["nodes"]:
        table_el = ET.SubElement(nodes_el, "table", name=node["table"])
        for col in node["columns"]:
            col_el = ET.SubElement(table_el, "column", name=str(col.get("name", "")))
            if col.get("type"):
                col_el.set("type", str(col["type"]))
            col_el.set("primary_key", "true" if col.get("primary_key") else "false")
            col_el.set("nullable", "true" if col.get("nullable", True) else "false")

    edges_el = ET.SubElement(root, "edges")
    for edge in graph["edges"]:
        ET.SubElement(
            edges_el, "relation",
            from_table=edge["from_table"], from_column=edge["from_column"],
            to_table=edge["to_table"], to_column=edge["to_column"],
            type=edge["relation_type"],
        )

    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")
