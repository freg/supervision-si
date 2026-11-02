// Repérage physique sur site (livraison #949) : page pensée pour le téléphone (application installée du hub), dans
// l'ordre d'importance de l'intervention :
//  1. prise terminale → équipement branché (nom, IP, MAC) → port de commutateur (Nebula sw-clients) ;
//  2. brassage : port par port, prises déclarées et corrigées sur place, anomalies, export CSV ;
//  3. position de l'équipement sur le plan du site (plan de l'onglet Nebula › Plan), photo (long cordon, Wi-Fi) ;
//  4. couverture Wi-Fi relative : le signal du téléphone VU PAR LA BORNE (Nebula ap-clients), relevé là où on se trouve
//     sur le plan, + RSSI lu sur le téléphone en option. Logique pure : reperageLib.js. API : nebula-api /reperage/*.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ONGLETS, MAC_KEY, SITE_KEY, CLASSE_COULEUR, classeSignal, bande, libelleClient, ouEstBranche, tableBrassage, anomaliesBrassage, versFraction, texteReleve, syntheseCouverture, tailleReduite } from "./reperageLib.js";
import { hubLink } from "./hubLinks.js";

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
const putJson = (url, body) => getJson(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const postJson = (url, body) => getJson(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

/** Réduit la photo dans le navigateur (plus grand côté 1600 px, JPEG 0,8) avant l'envoi : une photo de téléphone fait 4 à 8 Mo. */
async function reduirePhoto(file) {
  if (!file.type.startsWith("image/") || typeof createImageBitmap !== "function") return file;
  try {
    const bmp = await createImageBitmap(file);
    const { w, h } = tailleReduite(bmp.width, bmp.height, 1600);
    if (w === bmp.width && file.size < 1.5e6) return file;
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    c.getContext("2d").drawImage(bmp, 0, 0, w, h);
    const blob = await new Promise((res) => c.toBlob(res, "image/jpeg", 0.8));
    return blob ? new File([blob], "photo.jpg", { type: "image/jpeg" }) : file;
  } catch { return file; }
}

function Plan({ base, version, marqueurs, onPoser, hauteur = 360 }) {
  const img = useRef(null);
  const [ok, setOk] = useState(null);
  return (
    <div style={{ position: "relative", border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden", background: "var(--panel)" }}>
      <img ref={img} alt="plan du site" src={`${base}/plan?v=${version}`} onLoad={() => setOk(true)} onError={() => setOk(false)}
        style={{ display: ok === false ? "none" : "block", width: "100%", maxHeight: hauteur, objectFit: "contain", cursor: onPoser ? "crosshair" : "default", touchAction: "manipulation" }}
        onClick={(e) => { if (!onPoser) return; const f = versFraction(e.clientX, e.clientY, img.current.getBoundingClientRect()); if (f) onPoser(f); }} />
      {ok === false && <p className="muted" style={{ padding: 12, margin: 0 }}>Aucun plan pour ce site — le déposer dans <a href={hubLink("nebula", { tab: "plan" })}>Nebula › Plan du site</a> (photo du plan d'évacuation suffit).</p>}
      {ok && (marqueurs || []).map((m) => (
        <div key={m.key} title={m.titre} onClick={(e) => { e.stopPropagation(); m.onClick && m.onClick(); }}
          style={{ position: "absolute", left: `${m.x * 100}%`, top: `${m.y * 100}%`, transform: "translate(-50%, -50%)", width: m.taille || 18, height: m.taille || 18, borderRadius: "50%",
            background: m.couleur || "var(--accent)", border: "2px solid var(--bg)", boxShadow: "0 0 0 1px var(--border)", fontSize: 10, lineHeight: `${(m.taille || 18) - 4}px`, textAlign: "center", color: "var(--bg)", fontWeight: 700, cursor: m.onClick ? "pointer" : "default" }}>
          {m.texte || ""}
        </div>
      ))}
    </div>
  );
}

export default function ReperageView({ onBack, nebulaApiBase, actor }) {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState(() => store.get(SITE_KEY, ""));
  const [onglet, setOnglet] = useState("prise");
  const [inv, setInv] = useState(null);
  const [prises, setPrises] = useState([]);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [sel, setSel] = useState(null);           // client sélectionné (onglet 1)
  const [form, setForm] = useState(null);         // prise en édition (onglets 1/2/3)
  const [msg, setMsg] = useState(null);
  const [mac, setMac] = useState(() => store.get(MAC_KEY, ""));
  const [mobile, setMobile] = useState(null);
  const [releves, setReleves] = useState([]);
  const [rssiTel, setRssiTel] = useState("");
  const [noteRel, setNoteRel] = useState("");
  const [planV, setPlanV] = useState(0);
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}`;

  useEffect(() => {
    getJson(`${nebulaApiBase}/health-board?hours=1`).then((d) => { const s = d.sites || []; setSites(s); if (!siteId && s[0]) setSiteId(s[0].site_id); }).catch((e) => setErr(e.message));
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [nebulaApiBase]);
  useEffect(() => { if (siteId) store.set(SITE_KEY, siteId); }, [siteId]);

  const charger = useCallback(async (refresh) => {
    if (!siteId) return;
    setBusy(true); setErr(null);
    try {
      const [i, p, r] = await Promise.all([getJson(`${base}/reperage/inventaire?period=1d${refresh ? "&refresh=1" : ""}`), getJson(`${base}/reperage/prises`), getJson(`${base}/reperage/releves`)]);
      setInv(i); setPrises(p.prises || []); setReleves(r.releves || []);
      if (i.erreurs?.length) setErr("Nebula partiel : " + i.erreurs.join(" ; "));
    } catch (e) { setErr(e.message); }
    finally { setBusy(false); }
  }, [base, siteId]);
  useEffect(() => { charger(false); }, [charger]);

  // recherche (onglet 1) avec un petit délai de frappe
  useEffect(() => {
    if (!siteId || q.trim().length < 2) { setRes(null); return; }
    const t = setTimeout(() => getJson(`${base}/reperage/recherche?q=${encodeURIComponent(q.trim())}`).then((d) => setRes(d.resultats || [])).catch((e) => setErr(e.message)), 350);
    return () => clearTimeout(t);
  }, [q, base, siteId]);

  // mobile (onglet 4) : ce que la borne voit du téléphone, toutes les 20 s
  useEffect(() => {
    if (onglet !== "wifi" || !siteId || !mac) return;
    let stop = false;
    const tic = () => getJson(`${base}/reperage/mobile?mac=${encodeURIComponent(mac)}&refresh=1`).then((d) => { if (!stop) setMobile(d); }).catch((e) => { if (!stop) setMobile({ error: e.message }); });
    tic(); const t = setInterval(tic, 20000);
    return () => { stop = true; clearInterval(t); };
  }, [onglet, siteId, mac, base]);

  const table = useMemo(() => tableBrassage(inv, prises), [inv, prises]);
  const anomalies = useMemo(() => anomaliesBrassage(table), [table]);
  const synthese = useMemo(() => syntheseCouverture(releves), [releves]);
  const prisePour = (c) => prises.find((p) => p.mac === c.mac) || prises.find((p) => p.commutateur === c.commutateur && String(p.port) === String(c.port));

  const ouvrirPrise = (p, c) => setForm({ prise: "", local: "", panneau: "", note: "", long_cordon: false, wifi: false, defaut: false, photos: [], ...(p || {}),
    ...(c ? { commutateur: c.commutateur || p?.commutateur || "", port: c.port ?? p?.port ?? "", mac: c.mac, equipement: p?.equipement || libelleClient(c) } : {}) });

  const enregistrerPrise = async () => {
    if (!form?.prise?.trim()) { setMsg({ ok: false, text: "libellé de prise requis (ex. B-12)" }); return; }
    setBusy(true); setMsg(null);
    try {
      const p = await putJson(`${base}/reperage/prises`, { ...form, par: actor || "" });
      setPrises((cur) => [...cur.filter((x) => x.prise !== p.prise), p].sort((a, b) => a.prise.localeCompare(b.prise, "fr")));
      setMsg({ ok: true, text: `prise ${p.prise} enregistrée` }); setForm(p);
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  };
  const supprimerPrise = async (p) => {
    if (!confirm(`Supprimer la prise ${p.prise} ?`)) return;
    await getJson(`${base}/reperage/prises/${encodeURIComponent(p.prise)}`, { method: "DELETE" }).catch((e) => setMsg({ ok: false, text: e.message }));
    setPrises((cur) => cur.filter((x) => x.prise !== p.prise)); if (form?.prise === p.prise) setForm(null);
  };
  const photo = async (file) => {
    if (!file || !form) return;
    setBusy(true); setMsg({ ok: true, text: "⏳ réduction et envoi de la photo…" });
    try {
      const f = await reduirePhoto(file);
      const fd = new FormData(); fd.append("file", f, f.name || "photo.jpg");
      const r = await getJson(`${base}/reperage/photos`, { method: "POST", body: fd });
      setForm((cur) => ({ ...cur, photos: [...(cur.photos || []), r.id] }));
      setMsg({ ok: true, text: `photo ajoutée (${Math.round(r.taille / 1024)} ko) — penser à enregistrer la prise` });
    } catch (e) { setMsg({ ok: false, text: "photo : " + e.message }); }
    finally { setBusy(false); }
  };
  const relever = async (f) => {
    if (!mac) { setMsg({ ok: false, text: "renseigner d'abord la MAC Wi-Fi du téléphone" }); return; }
    setBusy(true);
    try {
      const r = await postJson(`${base}/reperage/releves`, { x: f.x, y: f.y, mac, note: noteRel, rssi_mobile: rssiTel === "" ? null : Number(rssiTel) });
      setReleves((cur) => [...cur, r]); setMsg({ ok: true, text: `relevé : ${texteReleve(r)}` });
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  };
  const supprimerReleve = async (r) => { await getJson(`${base}/reperage/releves/${r.id}`, { method: "DELETE" }).catch(() => {}); setReleves((cur) => cur.filter((x) => x.id !== r.id)); };

  const carteClient = (c, cle) => {
    const p = prisePour(c);
    return (
      <div key={cle || c.mac} className="hub-card" style={{ margin: "6px 0", padding: 10, cursor: "pointer", borderColor: sel?.mac === c.mac ? "var(--accent)" : undefined }} onClick={() => setSel(c)}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <strong>{libelleClient(c)}</strong>
          <span className="muted" style={{ fontSize: 12 }}>{c.type === "wifi" ? "📶" : c.type === "filaire" ? "🔌" : "?"} {c.ip || ""}</span>
        </div>
        <div style={{ fontSize: 13 }}>{ouEstBranche(c)}</div>
        <div className="muted" style={{ fontSize: 12 }}>{c.mac}{c.fabricant ? ` · ${c.fabricant}` : ""}{c.vlan && c.type === "wifi" ? ` · VLAN ${c.vlan}` : ""}{p ? ` · prise ${p.prise}${p.local ? ` (${p.local})` : ""}` : c.type === "filaire" ? " · prise non relevée" : ""}</div>
      </div>
    );
  };

  const formulairePrise = () => form && (
    <div className="hub-card" style={{ marginTop: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}><strong>Prise {form.prise || "(nouvelle)"}</strong><button type="button" className="secondary" onClick={() => setForm(null)}>✕</button></div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
        <label>Prise (étiquette)<input value={form.prise} onChange={(e) => setForm({ ...form, prise: e.target.value })} placeholder="B-12" /></label>
        <label>Local / pièce<input value={form.local || ""} onChange={(e) => setForm({ ...form, local: e.target.value })} placeholder="Amphi" /></label>
        <label>Commutateur<input list="rep-sw" value={form.commutateur || ""} onChange={(e) => setForm({ ...form, commutateur: e.target.value })} /></label>
        <label>Port<input type="number" inputMode="numeric" value={form.port ?? ""} onChange={(e) => setForm({ ...form, port: e.target.value })} /></label>
        <label>Panneau / position<input value={form.panneau || ""} onChange={(e) => setForm({ ...form, panneau: e.target.value })} placeholder="baie 1, panneau A, 12" /></label>
        <label>Équipement attendu<input value={form.equipement || ""} onChange={(e) => setForm({ ...form, equipement: e.target.value })} /></label>
        <label style={{ gridColumn: "1 / -1" }}>MAC de l'équipement<input value={form.mac || ""} onChange={(e) => setForm({ ...form, mac: e.target.value })} placeholder="aa:bb:cc:dd:ee:ff" /></label>
      </div>
      <datalist id="rep-sw">{(inv?.commutateurs || []).map((s) => <option key={s.id} value={s.nom} />)}</datalist>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", margin: "8px 0" }}>
        <label><input type="checkbox" checked={!!form.long_cordon} onChange={(e) => setForm({ ...form, long_cordon: e.target.checked })} /> long cordon</label>
        <label><input type="checkbox" checked={!!form.wifi} onChange={(e) => setForm({ ...form, wifi: e.target.checked })} /> en Wi-Fi</label>
        <label><input type="checkbox" checked={!!form.defaut} onChange={(e) => setForm({ ...form, defaut: e.target.checked })} /> défaut constaté</label>
      </div>
      <label>Note<textarea rows={2} value={form.note || ""} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="état de la prise, du cordon, à corriger…" /></label>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 6 }}>
        <label className="secondary" style={{ cursor: "pointer" }}>📷 Photo<input type="file" accept="image/*" capture="environment" style={{ display: "none" }} onChange={(e) => { photo(e.target.files?.[0]); e.target.value = ""; }} /></label>
        {(form.photos || []).map((id) => <a key={id} href={`${base}/reperage/photos/${id}`} target="_blank" rel="noreferrer"><img alt="" src={`${base}/reperage/photos/${id}`} style={{ height: 56, borderRadius: 6, border: "1px solid var(--border)" }} /></a>)}
        <span style={{ flex: 1 }} />
        {form.maj && <button type="button" className="secondary" onClick={() => supprimerPrise(form)}>Supprimer</button>}
        <button type="button" disabled={busy} onClick={enregistrerPrise}>{busy ? "⏳ en cours…" : "Enregistrer"}</button>
      </div>
      {form.x != null && <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>position sur le plan : {Math.round(form.x * 100)} % · {Math.round(form.y * 100)} % (onglet 3 pour la changer)</p>}
    </div>
  );

  return (
    <div className="urg-root" style={{ display: "flex", flexDirection: "column", maxWidth: 900, margin: "0 auto", padding: "0 4px" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2 style={{ margin: 0, fontSize: 18 }}>📍 Repérage sur site</h2>
        <select value={siteId} onChange={(e) => setSiteId(e.target.value)} style={{ flex: 1, minWidth: 120 }}>{sites.map((s) => <option key={s.site_id} value={s.site_id}>{s.name || s.site_id}</option>)}</select>
        <button type="button" className="secondary" disabled={busy} onClick={() => charger(true)}>{busy ? "⏳" : "↻"}</button>
      </div>
      {err && <p style={{ color: "var(--warning)", margin: "6px 0", fontSize: 13 }}>{err}</p>}
      {msg && <p style={{ color: msg.ok ? "var(--ok)" : "var(--danger)", margin: "6px 0", fontSize: 13 }}>{msg.text}</p>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 4, margin: "6px 0" }}>
        {ONGLETS.map((o) => <button key={o.id} type="button" className={onglet === o.id ? "" : "secondary"} onClick={() => setOnglet(o.id)} style={{ padding: "8px 4px", fontSize: 12, lineHeight: 1.2 }}>{o.icon}<br />{o.label}</button>)}
      </div>

      {onglet === "prise" && (
        <div>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="MAC, IP, nom, fabricant, « p12 », prise, local…" style={{ width: "100%", fontSize: 16, padding: 10 }} autoFocus />
          <p className="muted" style={{ margin: "4px 0", fontSize: 12 }}>{inv ? `${inv.clients.length} équipements vus par Nebula (24 h) · ${prises.length} prises relevées` : "lecture Nebula…"}</p>
          {res && res.length === 0 && <p className="muted">rien ne correspond — l'équipement n'est peut-être plus vu par Nebula (période 24 h) : brancher, attendre une minute, ↻.</p>}
          {res && res.map((r, i) => r.genre === "client" ? carteClient(r.objet, "r" + i) : (
            <div key={"p" + i} className="hub-card" style={{ margin: "6px 0", padding: 10, cursor: "pointer" }} onClick={() => ouvrirPrise(r.objet)}>
              <strong>🔌 prise {r.objet.prise}</strong> <span className="muted">{r.objet.local || ""}</span>
              <div style={{ fontSize: 13 }}>{r.objet.commutateur ? `${r.objet.commutateur} port ${r.objet.port ?? "?"}` : "port non relevé"}{r.objet.equipement ? ` · ${r.objet.equipement}` : ""}</div>
            </div>
          ))}
          {!res && inv && q.trim().length < 2 && (inv.clients || []).filter((c) => c.type === "filaire").slice(0, 30).map((c) => carteClient(c))}
          {sel && (
            <div className="hub-card" style={{ marginTop: 8, borderColor: "var(--accent)" }}>
              <strong>{libelleClient(sel)}</strong> — {ouEstBranche(sel)}
              <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                <button type="button" onClick={() => ouvrirPrise(prisePour(sel), sel)}>{prisePour(sel) ? `Corriger la prise ${prisePour(sel).prise}` : "Relever la prise de cet équipement"}</button>
                <button type="button" className="secondary" onClick={() => { setOnglet("position"); ouvrirPrise(prisePour(sel), sel); }}>📍 Positionner</button>
                <button type="button" className="secondary" onClick={() => setSel(null)}>✕</button>
              </div>
            </div>
          )}
          {formulairePrise()}
        </div>
      )}

      {onglet === "brassage" && (
        <div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <button type="button" onClick={() => ouvrirPrise(null)}>+ Prise</button>
            <a className="secondary" href={`${base}/reperage/prises.csv`} target="_blank" rel="noreferrer">⬇ CSV des prises</a>
            <span className="muted" style={{ fontSize: 12 }}>port par port : ce que Nebula voit (24 h) et les prises déclarées ; toucher un port pour déclarer / corriger</span>
          </div>
          {anomalies.length > 0 && <div className="hub-card" style={{ borderColor: "var(--warning)", margin: "8px 0" }}><strong>⚠ {anomalies.length} anomalie(s) de brassage</strong>{anomalies.map((a, i) => <div key={i} style={{ fontSize: 13 }}>• {a.texte}</div>)}</div>}
          {formulairePrise()}
          {table.commutateurs.map((sw) => (
            <details key={sw.id} open style={{ margin: "8px 0" }}>
              <summary><strong>{sw.nom}</strong> <span className="muted">· {sw.ports.length} port(s) actifs</span></summary>
              <table style={{ width: "100%", fontSize: 13 }}><tbody>
                {sw.ports.map((p) => (
                  <tr key={p.port} style={{ cursor: "pointer" }} onClick={() => ouvrirPrise(p.prises[0] || null, p.clients[0] ? { ...p.clients[0], commutateur: sw.nom, port: p.port } : { commutateur: sw.nom, port: p.port, mac: null })}>
                    <td style={{ width: 44, fontWeight: 700 }}>{p.port}</td>
                    <td>{p.clients.map((c) => <div key={c.mac}>{libelleClient(c)} <span className="muted">{c.ip || c.mac}{c.vlan ? ` · VLAN ${c.vlan}` : ""}</span></div>)}</td>
                    <td style={{ textAlign: "right" }}>{p.prises.length ? p.prises.map((x) => <div key={x.prise} style={{ color: x.defaut ? "var(--danger)" : undefined }}>🔌 {x.prise}{x.local ? ` · ${x.local}` : ""}</div>) : <span className="muted">prise ?</span>}</td>
                  </tr>
                ))}
              </tbody></table>
            </details>
          ))}
          {table.orphelines.length > 0 && <details style={{ margin: "8px 0" }}><summary>prises déclarées sans équipement vu ({table.orphelines.length})</summary>{table.orphelines.map((p) => <div key={p.prise} style={{ fontSize: 13, cursor: "pointer" }} onClick={() => ouvrirPrise(p)}>🔌 {p.prise} · {p.commutateur} port {p.port}{p.local ? ` · ${p.local}` : ""}</div>)}</details>}
          {!table.commutateurs.length && <p className="muted">aucun client de commutateur vu par Nebula (24 h) — vérifier la connexion Nebula dans <a href={hubLink("nebula")}>Nebula</a>.</p>}
        </div>
      )}

      {onglet === "position" && (
        <div>
          <p className="muted" style={{ margin: "4px 0", fontSize: 13 }}>{form ? <>Toucher le plan pour poser la prise <strong>{form.prise || "(nouvelle)"}</strong>, puis Enregistrer.</> : "Choisir une prise (onglets 1 ou 2, ou + Prise) puis toucher le plan. Les prises posées : 🔌 ; défaut : rouge."}</p>
          <Plan base={base} version={planV}
            marqueurs={prises.filter((p) => p.x != null).map((p) => ({ key: p.prise, x: p.x, y: p.y, texte: "", titre: `${p.prise}${p.local ? " · " + p.local : ""}`, couleur: p.defaut ? "var(--danger)" : form?.prise === p.prise ? "var(--accent)" : "var(--ok)", taille: 16, onClick: () => ouvrirPrise(p) }))}
            onPoser={form ? (f) => setForm({ ...form, x: f.x, y: f.y }) : null} />
          <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
            <button type="button" className="secondary" onClick={() => ouvrirPrise(null)}>+ Prise</button>
            <button type="button" className="secondary" onClick={() => setPlanV((v) => v + 1)}>↻ plan</button>
          </div>
          {formulairePrise()}
          <details style={{ marginTop: 8 }}><summary className="muted">prises posées ({prises.filter((p) => p.x != null).length}) / non posées ({prises.filter((p) => p.x == null).length})</summary>
            {prises.map((p) => <div key={p.prise} style={{ fontSize: 13, cursor: "pointer" }} onClick={() => ouvrirPrise(p)}>{p.x != null ? "📍" : "·"} {p.prise}{p.local ? ` · ${p.local}` : ""}{p.long_cordon ? " · long cordon" : ""}{p.wifi ? " · Wi-Fi" : ""}{p.photos?.length ? ` · ${p.photos.length} photo(s)` : ""}</div>)}
          </details>
        </div>
      )}

      {onglet === "wifi" && (
        <div>
          <div className="hub-card" style={{ padding: 10 }}>
            <label>MAC Wi-Fi du téléphone <span className="muted" style={{ fontSize: 12 }}>(Réglages › À propos ; désactiver la MAC aléatoire pour le SSID du site)</span>
              <input value={mac} onChange={(e) => { setMac(e.target.value); store.set(MAC_KEY, e.target.value); }} placeholder="aa:bb:cc:dd:ee:ff" style={{ fontSize: 16 }} /></label>
            {mobile?.error && <p style={{ color: "var(--danger)", margin: "6px 0" }}>{mobile.error}</p>}
            {mobile && !mobile.error && (mobile.vu ? (
              <p style={{ margin: "6px 0" }}>Vu par <strong>{mobile.mobile.borne || "?"}</strong> · <span style={{ color: CLASSE_COULEUR[mobile.classe] }}>{mobile.mobile.signal != null ? `${mobile.mobile.signal} dBm (${mobile.classe})` : "signal non transmis"}</span>{mobile.mobile.bande ? ` · ${bande(mobile.mobile.bande)}` : ""}{mobile.mobile.canal ? ` · canal ${mobile.mobile.canal}` : ""}{mobile.mobile.ssid ? ` · ${mobile.mobile.ssid}` : ""} <span className="muted" style={{ fontSize: 12 }}>(Nebula, retard ≈ 1 min)</span></p>
            ) : <p className="muted" style={{ margin: "6px 0" }}>téléphone non vu par les bornes (2 h) : vérifier la MAC et la connexion au SSID du site.</p>)}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 8 }}>
              <label>RSSI lu sur le téléphone<input type="number" inputMode="numeric" value={rssiTel} onChange={(e) => setRssiTel(e.target.value)} placeholder="-62" /></label>
              <label>Note<input value={noteRel} onChange={(e) => setNoteRel(e.target.value)} placeholder="amphi, rang 5…" /></label>
            </div>
          </div>
          <p className="muted" style={{ margin: "6px 0", fontSize: 13 }}>Toucher le plan à l'endroit où vous êtes : le point prend la couleur du signal (vert ≥ −60, bleu ≥ −70, orange ≥ −80, rouge).</p>
          <Plan base={base} version={planV} onPoser={relever}
            marqueurs={releves.map((r) => ({ key: r.id, x: r.x, y: r.y, taille: 20, texte: String((r.rssi_mobile ?? r.signal ?? "")).replace("-", ""), couleur: CLASSE_COULEUR[classeSignal(r.rssi_mobile ?? r.signal)], titre: texteReleve(r), onClick: () => { if (confirm(`Supprimer ce relevé ? ${texteReleve(r)}`)) supprimerReleve(r); } }))} />
          <div className="hub-card" style={{ marginTop: 8, padding: 10, fontSize: 13 }}>
            <strong>{synthese.total} relevé(s)</strong>{synthese.faibles ? <span style={{ color: "var(--warning)" }}> · {synthese.faibles} faible(s) / mauvais</span> : null}
            {synthese.bornes.map((b) => <div key={b.borne}>{b.borne} : {b.n} relevé(s), médiane {b.median != null ? `${b.median} dBm` : "—"}</div>)}
            {inv?.bornes?.length ? <details><summary className="muted">bornes vues par Nebula ({inv.bornes.length})</summary>{inv.bornes.map((b) => <div key={b.id}>{b.nom} : {b.clients} client(s), signal moyen {b.signal_moyen != null ? `${b.signal_moyen} dBm` : "—"}</div>)}</details> : null}
          </div>
        </div>
      )}
    </div>
  );
}
