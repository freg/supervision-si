// Registre des équipements d'un site (#960) : report au bureau des notes de terrain — nom, rôle, IP, MAC, position sur le
// plan, local, prise, étiquettes libres (« clé:valeur » pour les catégories à venir). Rapprochement Nebula (où est branché,
// fabricant, IP/MAC vues) et doublons signalés. API : nebula-api /sites/<site>/reperage/equipements*. Logique : reperageLib.js.
import { useCallback, useEffect, useMemo, useState } from "react";
import Plan from "./PlanSite.jsx";
import BoutonDetail from "./FenetreTexte.jsx";
import ParcSite from "./ParcSite.jsx";   // #971
import { SITE_KEY, filtrerEquipements, couleurRole, initiales, suggestionNebula, EQUIPEMENT_VIDE, versFormulaire } from "./reperageLib.js";

const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* stockage indisponible */ } },
};
async function getJson(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}
const corps = (m, body) => ({ method: m, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const ch = { width: "100%", boxSizing: "border-box" };

export default function EquipementsSiteView({ onBack, nebulaApiBase, actor }) {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState(() => store.get(SITE_KEY, ""));
  const [data, setData] = useState(null);           // {equipements, roles, tags, locaux, erreurs}
  const [inv, setInv] = useState(null);             // inventaire Nebula (suggestions de saisie)
  const [form, setForm] = useState(EQUIPEMENT_VIDE);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const [sansPos, setSansPos] = useState(false);
  const [importOuvert, setImportOuvert] = useState(false);
  const [importTexte, setImportTexte] = useState("");
  const [parcOuvert, setParcOuvert] = useState(false);   // #971
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}`;

  useEffect(() => {
    getJson(`${nebulaApiBase}/reperage/sites`).then((d) => { const s = d.sites || []; setSites(s); if (!siteId && s[0]) setSiteId(s[0].site_id); }).catch((e) => setMsg({ ok: false, text: "Nebula : " + e.message }));
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [nebulaApiBase]);
  useEffect(() => { if (siteId) store.set(SITE_KEY, siteId); }, [siteId]);

  const charger = useCallback(async () => {
    if (!siteId) return;
    try { setData(await getJson(`${base}/reperage/equipements`)); } catch (e) { setMsg({ ok: false, text: e.message }); }
    getJson(`${base}/reperage/inventaire?period=1d`).then(setInv).catch(() => setInv(null));
  }, [base, siteId]);
  useEffect(() => { setData(null); setForm(EQUIPEMENT_VIDE); charger(); }, [charger]);

  const eqs = data?.equipements || [];
  const roles = data?.roles || [];
  const liste = useMemo(() => filtrerEquipements(eqs, { q, tag, sansPosition: sansPos }), [eqs, q, tag, sansPos]);
  const sugg = useMemo(() => (form.id ? null : suggestionNebula(inv, { mac: form.mac, ip: form.ip })), [inv, form.mac, form.ip, form.id]);
  const courant = form.id ? eqs.find((e) => e.id === form.id) : null;

  const enregistrer = async (suivant) => {
    setBusy("enregistrer"); setMsg(null);
    try {
      const e = await getJson(`${base}/reperage/equipements`, corps("PUT", { ...form, par: actor }));
      setMsg({ ok: true, text: `✓ ${e.nom || e.ip || e.mac} enregistré${e.nebula ? ` — Nebula : ${e.nebula.ou || "vu"}` : ""}${e.alertes?.length ? ` — ⚠ ${e.alertes.join(" ; ")}` : ""}` });
      await charger();
      setForm(suivant ? { ...EQUIPEMENT_VIDE, local: form.local, role: form.role, tags: form.tags } : versFormulaire(e));
    } catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(null); }
  };
  const supprimer = async () => {
    if (!form.id || !window.confirm(`Supprimer « ${form.nom || form.ip || form.mac} » du registre ?`)) return;
    setBusy("supprimer");
    try { await getJson(`${base}/reperage/equipements/${form.id}`, { method: "DELETE" }); setForm(EQUIPEMENT_VIDE); await charger(); setMsg({ ok: true, text: "✓ supprimé" }); }
    catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(null); }
  };
  const importer = async () => {
    setBusy("import"); setMsg(null);
    try {
      const r = await getJson(`${base}/reperage/equipements/import`, corps("POST", { texte: importTexte }));
      setMsg({ ok: !r.erreurs?.length, text: `✓ ${r.ajoutes} ajouté(s), ${r.mis_a_jour} mis à jour${r.erreurs?.length ? ` — ${r.erreurs.length} ligne(s) refusée(s) : ${r.erreurs.join(" ; ")}` : ""}` });
      setImportTexte(""); setImportOuvert(false); await charger();
    } catch (err) { setMsg({ ok: false, text: err.message }); }
    finally { setBusy(null); }
  };
  const champ = (k) => ({ value: form[k] ?? "", onChange: (e) => setForm({ ...form, [k]: e.target.value }), onKeyDown: (e) => { if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") enregistrer(!form.id); } });
  const marqueurs = liste.filter((e) => e.x != null).map((e) => ({
    key: e.id, x: e.x, y: e.y, texte: initiales(e), taille: 26, couleur: couleurRole(e.role, roles),
    titre: `${e.nom || ""} · ${e.role || ""} · ${e.ip || ""} ${e.mac || ""}`, onClick: () => setForm(versFormulaire(e)),
  }));
  if (form.x != null && !form.id) marqueurs.push({ key: "_nouveau", x: form.x, y: form.y, texte: "+", taille: 26, couleur: "var(--text)", titre: "nouvelle fiche" });
  if (form.id && courant && (form.x !== courant.x || form.y !== courant.y) && form.x != null) {
    const m = marqueurs.find((x) => x.key === form.id); if (m) { m.x = form.x; m.y = form.y; } else marqueurs.push({ key: form.id, x: form.x, y: form.y, texte: "↦", taille: 26, couleur: "var(--text)" });
  }

  return (
    <section className="view equipements-site">
      <header className="view-header" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>
        <h1 style={{ margin: 0 }}>🗂 Équipements du site</h1>
        <select value={siteId} onChange={(e) => setSiteId(e.target.value)} aria-label="site">
          {!siteId && <option value="">— site —</option>}
          {sites.map((s) => <option key={s.site_id} value={s.site_id}>{s.name}</option>)}
        </select>
        <input placeholder="rechercher (nom, IP, MAC, rôle, local…)" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 220 }} />
        <select value={tag} onChange={(e) => setTag(e.target.value)} aria-label="étiquette"><option value="">toutes étiquettes</option>{(data?.tags || []).map((t) => <option key={t} value={t}>{t}</option>)}</select>
        <label><input type="checkbox" checked={sansPos} onChange={(e) => setSansPos(e.target.checked)} /> sans position</label>
        <button type="button" className="secondary" onClick={() => setImportOuvert(!importOuvert)}>📥 Importer</button>
        <button type="button" className={parcOuvert ? "" : "secondary"} onClick={() => setParcOuvert(!parcOuvert)}>📊 Parc, baux, déplacements</button>
        {siteId && <a className="button secondary" href={`${base}/reperage/equipements.csv`} download>⬇ CSV</a>}
      </header>
      {msg && <p className={msg.ok ? "ok" : "error"}>{msg.text}</p>}
      {data?.erreurs?.length > 0 && <p className="muted">Nebula partiel : {data.erreurs.join(" ; ")} (la saisie reste possible)</p>}
      {importOuvert && (
        <div className="panel">
          <p>Coller un tableau (tableur, CSV `;` `,` ou tabulations) avec une ligne d'en-tête : <code>nom ; role ; ip ; mac ; local ; prise ; tags ; note</code>, et pour un inventaire de parc : <code>catégorie ; type ; désignation ; modèle ; n° de série ; lab ; stockage ; compte ; profil ; parcours ; mise en service</code>. Une ligne dont la MAC, l'IP ou le n° de série existe déjà complète la fiche ; sans MAC ni IP, c'est le nom qui fait le lien.</p>
          <textarea rows={6} style={ch} value={importTexte} onChange={(e) => setImportTexte(e.target.value)} />
          <p><input type="file" accept=".csv,.txt,.tsv" onChange={(e) => { const f = e.target.files?.[0]; if (f) f.text().then(setImportTexte); }} />{" "}
            <button type="button" onClick={importer} disabled={!importTexte.trim() || !!busy}>{busy === "import" ? "⏳ import…" : "Importer"}</button></p>
        </div>
      )}

      {parcOuvert && siteId && <ParcSite base={base} actor={actor} selection={form.id} onChange={charger}
        onOuvrir={(id) => { const e = eqs.find((x) => x.id === id); if (e) setForm(versFormulaire(e)); }} onInscrire={(f) => setForm(f)} />}

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ flex: "3 1 480px", minWidth: 0 }}>
          <Plan base={base} version={0} marqueurs={marqueurs} selection={form.id || "_nouveau"} onPoser={(f) => setForm({ ...form, x: f.x, y: f.y })} />
          <p className="muted" style={{ marginTop: 4 }}>Cliquer le plan place la fiche en cours ; cliquer un marqueur ouvre sa fiche. {eqs.filter((e) => e.x != null).length}/{eqs.length} positionné(s).</p>
        </div>

        <div className="panel" style={{ flex: "1 1 300px", minWidth: 280 }}>
          <h3 style={{ marginTop: 0 }}>{form.id ? `Fiche : ${form.nom || form.ip || form.mac}` : "Nouvel équipement"}</h3>
          <label>Nom<input style={ch} {...champ("nom")} autoFocus placeholder="ex. Écran accueil" /></label>
          <label>Rôle<input style={ch} list="eq-roles" {...champ("role")} placeholder="affichage, caméra, serveur…" /></label>
          <datalist id="eq-roles">{roles.map((r) => <option key={r} value={r} />)}</datalist>
          <label>IP<input style={ch} {...champ("ip")} placeholder="172.16.20.10" inputMode="decimal" /></label>
          <label>MAC<input style={ch} {...champ("mac")} placeholder="aa:bb:cc:dd:ee:ff" /></label>
          {sugg && (sugg.ip !== form.ip || sugg.mac !== form.mac || (!form.nom && sugg.nom)) && (
            <p className="muted">Nebula : {sugg.mac} · {sugg.ip || "sans IP"}{sugg.nom ? ` · ${sugg.nom}` : ""}{sugg.fabricant ? ` · ${sugg.fabricant}` : ""}{" "}
              <button type="button" className="secondary" onClick={() => setForm({ ...form, mac: form.mac && form.mac.replace(/[^0-9a-f]/gi, "").length === 12 ? form.mac : sugg.mac, ip: form.ip || sugg.ip || "", nom: form.nom || sugg.nom || "" })}>compléter</button></p>
          )}
          <label>Local<input style={ch} list="eq-locaux" {...champ("local")} placeholder="pièce, étage" /></label>
          <datalist id="eq-locaux">{(data?.locaux || []).map((r) => <option key={r} value={r} />)}</datalist>
          <label>Prise<input style={ch} {...champ("prise")} placeholder="B-12" /></label>
          <label>Étiquettes<input style={ch} list="eq-tags" {...champ("tags")} placeholder="critique, vlan:20, propriétaire:sempat" /></label>
          <datalist id="eq-tags">{(data?.tags || []).map((r) => <option key={r} value={r} />)}</datalist>
          <label>Note<textarea style={ch} rows={2} value={form.note || ""} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
          <p className="muted" style={{ margin: "4px 0" }}>Position : {form.x != null ? `posée (${Math.round(form.x * 100)} %, ${Math.round(form.y * 100)} %)` : "cliquer sur le plan"}
            {form.x != null && <> <button type="button" className="secondary" onClick={() => setForm({ ...form, x: null, y: null })}>retirer du plan</button></>}</p>
          {courant?.nebula && <p className="muted" style={{ margin: "4px 0" }}>Nebula ({courant.nebula.par === "mac" ? "par MAC" : "par IP"}) : {courant.nebula.ou || "vu"}{courant.nebula.fabricant ? ` · ${courant.nebula.fabricant}` : ""}{courant.nebula.vlan ? ` · VLAN ${courant.nebula.vlan}` : ""}</p>}
          {courant?.alertes?.length > 0 && <p className="error" style={{ margin: "4px 0" }}>⚠ {courant.alertes.join(" ; ")}</p>}
          <p style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {!form.id && <button type="button" onClick={() => enregistrer(true)} disabled={!!busy} title="Entrée : garde local, rôle et étiquettes pour la fiche suivante">{busy === "enregistrer" ? "⏳ enregistrement…" : "Enregistrer et suivant"}</button>}
            <button type="button" className={form.id ? "" : "secondary"} onClick={() => enregistrer(false)} disabled={!!busy}>{busy === "enregistrer" && form.id ? "⏳ enregistrement…" : "Enregistrer"}</button>
            <button type="button" className="secondary" onClick={() => setForm(EQUIPEMENT_VIDE)} disabled={!!busy}>Nouveau</button>
            {form.id && <button type="button" className="secondary" onClick={supprimer} disabled={!!busy}>{busy === "supprimer" ? "⏳" : "Supprimer"}</button>}
          </p>
        </div>
      </div>

      <table className="table" style={{ marginTop: 12 }}>
        <thead><tr><th>Nom</th><th>Rôle</th><th>IP</th><th>MAC</th><th>Local / prise</th><th>Étiquettes</th><th>Nebula</th><th>Plan</th></tr></thead>
        <tbody>
          {liste.map((e) => (
            <tr key={e.id} onClick={() => setForm(versFormulaire(e))} style={{ cursor: "pointer", outline: form.id === e.id ? "2px solid var(--accent)" : "none" }}>
              <td><strong>{e.nom || "—"}</strong></td>
              <td><span style={{ color: couleurRole(e.role, roles) }}>●</span> {e.role || ""}</td>
              <td>{e.ip || ""}</td><td><code>{e.mac || ""}</code>{e.macs?.length > 1 && <BoutonDetail texte={e.macs.join("\n")} titre={`MAC de ${e.nom || e.ip}`} urgence="info" libelle={`+${e.macs.length - 1}`} />}</td>
              <td>{e.local || ""}{e.prise ? ` · ${e.prise}` : ""}</td>
              <td>{(e.tags || []).join(", ")}</td>
              <td>{e.nebula ? <small>{e.nebula.ou || "vu"}</small> : <small className="muted">non vu</small>}{" "}
                {e.alertes?.length > 0 && <BoutonDetail texte={e.alertes.join("\n")} titre={`Écarts : ${e.nom || e.ip || e.mac}`} urgence="alerte" libelle="⚠" />}</td>
              <td>{e.x != null ? "📍" : ""}</td>
            </tr>
          ))}
          {!liste.length && <tr><td colSpan={8} className="muted">{eqs.length ? "aucun équipement avec ces filtres" : "registre vide : saisir la première fiche à droite"}</td></tr>}
        </tbody>
      </table>
    </section>
  );
}
