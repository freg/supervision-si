// Onglet « Contrôles » du serveur de messagerie (livraison #770) : tests fabriqués envoyés à une boîte de test
// (courriel ordinaire, spam GTUBE, virus EICAR, pièce jointe interdite, message libre) avec le verdict attendu du
// filtre, indicateurs du journal avec seuils ; résultats du dernier passage de la sonde mail-server et historique.
// Le catalogue s'édite ici et s'écrit sur l'agent (action mailctl checks_set, motif obligatoire, journalisé).
// Logique pure : mailChecksLib.js.
import { useEffect, useState } from "react";
import { TEMPLATES, newTest, newIndicator, validate, toPayload, testState, STATE_LABEL, STATE_TONE, summary } from "./mailChecksLib.js";

function Tone({ tone, children }) { return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>; }
const IND_TONE = { ok: "good", warning: "warn", critical: "bad" };
const when = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");

export default function MailChecks({ probe, run, reason }) {
  const block = probe?.data?.checks || null;
  const [cat, setCat] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [add, setAdd] = useState({ template: "custom", label: "" });
  const [addInd, setAddInd] = useState({ label: "", regex: "" });
  useEffect(() => { if (block?.catalog) setCat(JSON.parse(JSON.stringify(block.catalog))); }, [probe?.at]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!block) return <p className="muted">La sonde mail-server de ce serveur ne remonte pas encore de contrôles : la mettre à jour (version 3, livraison #770) depuis la fiche de l'agent.</p>;
  const s = summary(block);
  const res = Object.fromEntries((block.tests || []).map((t) => [t.id, t]));
  const errs = cat ? validate(cat) : [];
  const motif = () => { if ((reason || "").trim().length < 4) { setMsg({ error: "Indiquer d'abord le motif, en haut de la page (journalisé sur le serveur)." }); return false; } return true; };
  const save = async () => {
    if (errs.length || !motif()) return;
    setBusy(true); setMsg(null);
    try { const r = await run({ action: "checks_set", checks: toPayload(cat), reason }); setMsg({ ok: `Catalogue écrit sur le serveur (${r.tests} test(s), ${r.indicators} indicateur(s)) : pris en compte au prochain passage de la sonde.` }); }
    catch (e) { setMsg({ error: e.message }); } finally { setBusy(false); }
  };
  const runNow = async () => {
    if (!motif()) return;
    setBusy(true); setMsg(null);
    try { const r = await run({ action: "canary_run", reason }); setMsg({ ok: r.message }); } catch (e) { setMsg({ error: e.message }); } finally { setBusy(false); }
  };
  const setT = (i, k, v) => setCat({ ...cat, tests: cat.tests.map((t, j) => (j === i ? { ...t, [k]: v } : t)) });
  const setI = (i, k, v) => setCat({ ...cat, indicators: cat.indicators.map((t, j) => (j === i ? { ...t, [k]: v } : t)) });
  const setC = (k, v) => setCat({ ...cat, canary: { ...cat.canary, [k]: v } });

  return (
    <div>
      <p>
        {s.configured ? <>Tests : <Tone tone={s.failed ? "bad" : "good"}>{s.ok} réussi(s) / {s.tests}</Tone>{s.failed > 0 && <> · <Tone tone="bad">{s.failed} en échec</Tone></>}{s.pending > 0 && <> · {s.pending} en cours</>}</>
          : <Tone tone="warn">aucune boîte de test : les messages fabriqués ne sont pas envoyés</Tone>}
        {" "}· indicateurs en alerte : {s.indicatorsAlert}
        {" "}· dernière série {when(block.canary?.last_run)}{block.canary?.next_run ? ` · prochaine vers ${when(block.canary.next_run)}` : ""}
        {" "}<button className="secondary" disabled={busy || !s.configured} onClick={runNow}>Lancer les tests maintenant</button>
      </p>
      {(block.errors || []).length > 0 && <p className="np-tone bad">Catalogue sur le serveur : {block.errors.join(" ; ")}</p>}
      {msg?.error && <p className="np-tone bad">{msg.error}</p>}
      {msg?.ok && <p className="np-tone good">{msg.ok}</p>}

      {cat && <>
        <h4>Boîte de test</h4>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <label>Destinataire <input value={cat.canary.to || ""} placeholder="test-hub@domaine" onChange={(e) => setC("to", e.target.value)} /></label>
          <label>Expéditeur <input value={cat.canary.from || ""} placeholder="(par défaut : le destinataire)" onChange={(e) => setC("from", e.target.value)} /></label>
          <label>Toutes les <input type="number" min="1" max="168" style={{ width: 60 }} value={cat.canary.every_hours} onChange={(e) => setC("every_hours", e.target.value)} /> h</label>
          <label>Verdict attendu sous <input type="number" min="5" max="240" style={{ width: 60 }} value={cat.canary.timeout_minutes} onChange={(e) => setC("timeout_minutes", e.target.value)} /> min</label>
        </div>
        <p className="muted" style={{ fontSize: 12 }}>Une boîte dédiée (ex. créée dans Modoboa) : elle reçoit les messages acceptés ; les messages arrêtés vont en quarantaine. Fonctionne avec un filtre local ou une VM de filtrage distante (verdict lu dans la réponse du filtre à Postfix).</p>

        <h4>Tests fabriqués</h4>
        <table>
          <thead><tr><th>Actif</th><th>Test</th><th>Modèle</th><th>Verdict attendu</th><th>Dernier résultat</th><th>Historique</th><th /></tr></thead>
          <tbody>{cat.tests.map((t, i) => {
            const r = res[t.id]; const st = testState(r ? { ...r, enabled: t.enabled } : { enabled: t.enabled });
            return (
              <tr key={t.id + i}>
                <td><input type="checkbox" checked={t.enabled} onChange={(e) => setT(i, "enabled", e.target.checked)} /></td>
                <td><input value={t.label} onChange={(e) => setT(i, "label", e.target.value)} style={{ width: 230 }} /><div className="muted" style={{ fontSize: 11 }}>{t.id}</div>
                  {t.template === "custom" && <><input placeholder="objet" value={t.subject || ""} onChange={(e) => setT(i, "subject", e.target.value)} style={{ width: 230 }} />
                    <textarea placeholder="texte du message" rows={2} value={t.body || ""} onChange={(e) => setT(i, "body", e.target.value)} style={{ width: 230 }} /></>}</td>
                <td title={TEMPLATES[t.template]?.help}>{TEMPLATES[t.template]?.label || t.template}</td>
                <td><input value={(t.expect || []).join(", ")} onChange={(e) => setT(i, "expect", e.target.value.split(/\s*,\s*/).filter(Boolean))} style={{ width: 200 }} /></td>
                <td><Tone tone={STATE_TONE[st]}>{STATE_LABEL[st]}</Tone>{r?.last && <div className="muted" style={{ fontSize: 11 }}>{when(r.last.at)} · {r.last.verdict || "—"}{r.last.detail ? ` · ${r.last.detail}` : ""}</div>}</td>
                <td style={{ whiteSpace: "nowrap" }}>{(r?.history || []).map((h, k) => <span key={k} title={`${when(h.at)} ${h.verdict || ""}`} className={`np-tone ${h.ok ? "good" : "bad"}`} style={{ padding: "0 3px", marginRight: 1 }}>{h.ok ? "✓" : "✗"}</span>)}</td>
                <td><button className="secondary" onClick={() => setCat({ ...cat, tests: cat.tests.filter((_, j) => j !== i) })}>Retirer</button></td>
              </tr>);
          })}</tbody>
        </table>
        <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "6px 0 14px" }}>
          <select value={add.template} onChange={(e) => setAdd({ ...add, template: e.target.value })}>{Object.entries(TEMPLATES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select>
          <input placeholder="libellé du nouveau test" value={add.label} onChange={(e) => setAdd({ ...add, label: e.target.value })} />
          <button className="secondary" onClick={() => { setCat({ ...cat, tests: [...cat.tests, newTest(add.template, add.label || undefined)] }); setAdd({ ...add, label: "" }); }}>+ Ajouter un test</button>
        </div>

        <h4>Indicateurs du journal</h4>
        <table>
          <thead><tr><th>Actif</th><th>Indicateur</th><th>Expression cherchée</th><th>Fenêtre (min)</th><th>Alerte au-delà de</th><th>Critique au-delà de</th><th>Valeur</th><th /></tr></thead>
          <tbody>{cat.indicators.map((x, i) => {
            const v = (block.indicators || []).find((y) => y.id === x.id);
            return (
              <tr key={x.id + i}>
                <td><input type="checkbox" checked={x.enabled} onChange={(e) => setI(i, "enabled", e.target.checked)} /></td>
                <td><input value={x.label} onChange={(e) => setI(i, "label", e.target.value)} style={{ width: 220 }} /><div className="muted" style={{ fontSize: 11 }}>{x.id}</div></td>
                <td><input value={x.regex} onChange={(e) => setI(i, "regex", e.target.value)} style={{ width: 220, fontFamily: "monospace" }} /></td>
                <td><input type="number" min="1" style={{ width: 70 }} value={x.window_minutes} onChange={(e) => setI(i, "window_minutes", e.target.value)} /></td>
                <td><input type="number" min="0" style={{ width: 70 }} value={x.warn_above ?? ""} onChange={(e) => setI(i, "warn_above", e.target.value)} /></td>
                <td><input type="number" min="0" style={{ width: 70 }} value={x.crit_above ?? ""} onChange={(e) => setI(i, "crit_above", e.target.value)} /></td>
                <td>{v ? <Tone tone={IND_TONE[v.state]}>{v.value}</Tone> : <span className="muted">—</span>}</td>
                <td><button className="secondary" onClick={() => setCat({ ...cat, indicators: cat.indicators.filter((_, j) => j !== i) })}>Retirer</button></td>
              </tr>);
          })}</tbody>
        </table>
        <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "6px 0 14px" }}>
          <input placeholder="libellé" value={addInd.label} onChange={(e) => setAddInd({ ...addInd, label: e.target.value })} />
          <input placeholder="expression du journal, ex. TLS library problem" style={{ fontFamily: "monospace", width: 260 }} value={addInd.regex} onChange={(e) => setAddInd({ ...addInd, regex: e.target.value })} />
          <button className="secondary" onClick={() => { setCat({ ...cat, indicators: [...cat.indicators, newIndicator(addInd.label, addInd.regex)] }); setAddInd({ label: "", regex: "" }); }}>+ Ajouter un indicateur</button>
        </div>

        {errs.length > 0 && <ul className="np-tone bad">{errs.map((e) => <li key={e}>{e}</li>)}</ul>}
        <button disabled={busy || errs.length > 0} onClick={save}>{busy ? "Envoi…" : "Enregistrer sur le serveur"}</button>
        <button className="secondary" style={{ marginLeft: 8 }} onClick={() => setCat(JSON.parse(JSON.stringify(block.catalog)))}>Annuler les modifications</button>
      </>}
    </div>
  );
}
