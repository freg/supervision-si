// Matrice des droits (livraison #559) : un tableau qui décline TOUT ce qui se
// paramètre dans le hub (chaque tuile de chaque thématique : voir ; et, pour
// les tuiles dont l'API vérifie un droit, gérer) × des sujets (groupes
// Keycloak et personnes). Ligne « accès restreint » par sujet : coché, le
// sujet ne voit que les cases accordées ; décoché (défaut), il voit tout
// comme avant. Les groupes et comptes viennent d'accounts-api quand il est
// là, sinon des groupes connus. Logique pure dans rightsCatalog.js.
import React, { useEffect, useMemo, useState } from "react";
import { buildCatalog, grantIndex, cellState, grantFor, columnSubjects, subjectKey } from "./rightsCatalog.js";
import { fetchMatrix, putCatalog, putMatrix, putRestriction } from "./rightsClient.js";

const KNOWN_GROUPS = ["administrateurs", "admin_hub", "techniciens", "demandeurs", "direction", "supervision", "service", "maitre_clefs", "projeqtor"];
const ALWAYS_ALL = new Set(["admin_hub", "administrateurs"]);

async function getJson(url) {
  try { const r = await fetch(url, { credentials: "include" }); return r.ok ? await r.json() : null; } catch { return null; }
}

export default function RightsMatrix({ rightsApiBase, accountsApiBase, groups, login }) {
  const catalog = useMemo(() => buildCatalog(), []);
  const [matrix, setMatrix] = useState(null);
  const [kcGroups, setKcGroups] = useState([]);
  const [kcUsers, setKcUsers] = useState([]);
  const [pickedUsers, setPickedUsers] = useState([]);
  const [userInput, setUserInput] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");
  const [showManage, setShowManage] = useState(true);

  const load = async () => {
    setBusy(true); setError(null);
    const m = await fetchMatrix(rightsApiBase);
    if (m?.error) setError(m.error); else setMatrix(m);
    setBusy(false);
  };
  useEffect(() => {
    (async () => {
      const c = await putCatalog(rightsApiBase, groups, login, catalog.map(({ identifier, label, theme, actions }) => ({ identifier, label, theme, actions })));
      if (c?.error) setError(c.error);
      await load();
      if (accountsApiBase) {
        const [g, u] = await Promise.all([getJson(`${accountsApiBase}/groups`), getJson(`${accountsApiBase}/users`)]);
        if (g?.groups) setKcGroups(g.groups.map((x) => x.name));
        if (u?.users) setKcUsers(u.users.map((x) => x.username));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rightsApiBase, accountsApiBase]);

  const idx = useMemo(() => grantIndex(matrix?.permissions), [matrix]);
  const restricted = useMemo(() => new Set(matrix?.restricted || []), [matrix]);
  const subjects = useMemo(() => columnSubjects({ groups: kcGroups.length ? kcGroups : KNOWN_GROUPS, users: pickedUsers, known: matrix?.subjects || [] }), [kcGroups, pickedUsers, matrix]);
  const rows = useMemo(() => catalog.filter((c) => !filter || `${c.label} ${c.identifier} ${c.theme}`.toLowerCase().includes(filter.toLowerCase())), [catalog, filter]);

  const apply = async (grants) => {
    setBusy(true); setError(null);
    const r = await putMatrix(rightsApiBase, groups, login, grants);
    if (r?.error) setError(r.error);
    await load();
  };
  const toggleRestriction = async (s) => {
    setBusy(true); setError(null);
    const key = s.kind === "user" ? `user:${s.name}` : `group:${s.name}`;
    const r = await putRestriction(rightsApiBase, groups, login, key, !restricted.has(key));
    if (r?.error) setError(r.error);
    await load();
  };
  const isRestricted = (s) => restricted.has(s.kind === "user" ? `user:${s.name}` : `group:${s.name}`);

  if (!matrix && !error) return <p className="muted">Chargement de la matrice…</p>;
  const themes = [...new Set(rows.map((r) => r.theme))];
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Une ligne par tuile du hub, une colonne par groupe ou personne. <strong>Voir</strong> = la tuile apparaît ; <strong>Gérer</strong> = les actions d'écriture de son API (import, suppression…) sont permises.
        Par défaut tout le monde voit tout : cocher <strong>accès restreint</strong> sous un sujet pour qu'il ne voie que ses cases. Une personne est restreinte si son compte l'est ou si tous ses groupes le sont ; admin_hub et administrateurs voient toujours tout.
      </p>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <input placeholder="Filtrer les tuiles" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <label className="muted"><input type="checkbox" checked={showManage} onChange={(e) => setShowManage(e.target.checked)} /> colonne Gérer</label>
        <span style={{ flex: 1 }} />
        <input placeholder="ajouter une personne (identifiant)" list="rights-users" value={userInput} onChange={(e) => setUserInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && userInput.trim()) { setPickedUsers([...new Set([...pickedUsers, userInput.trim()])]); setUserInput(""); } }} />
        <datalist id="rights-users">{kcUsers.map((u) => <option key={u} value={u} />)}</datalist>
        <button type="button" className="secondary" disabled={!userInput.trim()} onClick={() => { setPickedUsers([...new Set([...pickedUsers, userInput.trim()])]); setUserInput(""); }}>Ajouter la colonne</button>
        <button type="button" className="secondary" disabled={busy} onClick={load}>Actualiser</button>
      </div>
      <div style={{ overflow: "auto", maxHeight: "70vh", border: "1px solid var(--border)", borderRadius: 8 }}>
        <table style={{ width: "100%", textAlign: "left", borderCollapse: "collapse" }}>
          <thead style={{ position: "sticky", top: 0, background: "var(--panel)", zIndex: 1 }}>
            <tr style={{ textAlign: "left" }}>
              <th style={{ minWidth: 220 }}>Tuile</th>
              {subjects.map((s) => <th key={subjectKey(s)} style={{ whiteSpace: "nowrap", textAlign: "left" }}>{s.kind === "user" ? <span title="personne">👤 {s.name}</span> : s.name}</th>)}
            </tr>
            <tr style={{ textAlign: "left" }}>
              <th className="muted" style={{ fontWeight: 400 }}>accès restreint</th>
              {subjects.map((s) => <th key={subjectKey(s)} style={{ fontWeight: 400 }}>{ALWAYS_ALL.has(s.name) && s.kind === "group" ? <span className="muted">toujours tout</span> : <label style={{ fontWeight: 400 }}><input type="checkbox" checked={isRestricted(s)} disabled={busy} onChange={() => toggleRestriction(s)} /> <span className="muted">{isRestricted(s) ? "oui" : "non"}</span></label>}</th>)}
            </tr>
            <tr style={{ textAlign: "left" }}>
              <th className="muted" style={{ fontWeight: 400 }}>tout voir</th>
              {subjects.map((s) => { const k = subjectKey(s); const all = rows.every((r) => cellState(idx, r, k, "view").allowed); return <th key={k} style={{ fontWeight: 400 }}>{ALWAYS_ALL.has(s.name) && s.kind === "group" ? "" : <button type="button" className="secondary" style={{ fontSize: 11 }} disabled={busy} onClick={() => apply(rows.map((r) => grantFor(r, k, "view", !all)))}>{all ? "tout décocher" : "tout cocher"}</button>}</th>; })}
            </tr>
          </thead>
          <tbody>
            {themes.map((t) => (
              <React.Fragment key={t}>
                <tr><td colSpan={subjects.length + 1} style={{ background: "var(--panel)", fontWeight: 600, paddingTop: 8 }}>{t}</td></tr>
                {rows.filter((r) => r.theme === t).map((r) => (
                  <tr key={r.identifier}>
                    <td>{r.label} <span className="muted" style={{ fontSize: 11 }}>{r.identifier}</span></td>
                    {subjects.map((s) => {
                      const k = subjectKey(s);
                      if (ALWAYS_ALL.has(s.name) && s.kind === "group") return <td key={k} className="muted">✓</td>;
                      const v = cellState(idx, r, k, "view"), m = cellState(idx, r, k, "manage");
                      return (
                        <td key={k} style={{ whiteSpace: "nowrap" }}>
                          <label title={v.wide ? "accordé par un octroi large (toutes les tuiles)" : "voir"} style={{ fontWeight: 400 }}><input type="checkbox" checked={v.allowed} disabled={busy || v.wide} onChange={(e) => apply([grantFor(r, k, "view", e.target.checked)])} /> voir</label>
                          {showManage && !m.na && <label title="gérer (actions d'écriture de l'API)" style={{ fontWeight: 400, marginLeft: 6 }}><input type="checkbox" checked={m.allowed} disabled={busy} onChange={(e) => apply([grantFor(r, k, "manage", e.target.checked)])} /> gérer</label>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
