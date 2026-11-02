// Repérage physique sur site (livraison #949, simplifié #950) : page TÉLÉPHONE -- un menu de 4 gros boutons, un écran
// à la fois, quelques mots, défilement vertical seulement. Ordre d'importance de l'intervention :
//  1. prise → équipement branché (nom, IP, MAC) → port de commutateur (Nebula sw-clients) ;
//  2. brassage : port par port, prises déclarées / corrigées sur place ;
//  3. position sur le plan du site (plan de Nebula › Plan) + photo ;
//  4. couverture Wi-Fi : signal du téléphone vu par la borne (Nebula ap-clients), relevé là où l'on se trouve.
// Logique pure : reperageLib.js. API : nebula-api /sites/<site>/reperage/*. Rendu plein écran sur mobile (App : VUES_MOBILE).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ONGLETS, MAC_KEY, SITE_KEY, CLASSE_COULEUR, classeSignal, bande, libelleClient, ouEstBranche, tableBrassage, anomaliesBrassage, versFraction, texteReleve, syntheseCouverture, tailleReduite, lignesRadar, ageBalayage } from "./reperageLib.js";
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

/** Réduit la photo dans le navigateur (plus grand côté 1600 px, JPEG 0,8) : une photo de téléphone fait 4 à 8 Mo. */
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

function Plan({ base, version, marqueurs, onPoser }) {
  const img = useRef(null);
  const [ok, setOk] = useState(null);
  return (
    <div style={{ position: "relative", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden", background: "var(--panel)" }}>
      <img ref={img} alt="plan du site" src={`${base}/plan?v=${version}`} onLoad={() => setOk(true)} onError={() => setOk(false)}
        style={{ display: ok === false ? "none" : "block", width: "100%", cursor: onPoser ? "crosshair" : "default", touchAction: "manipulation" }}
        onClick={(e) => { if (!onPoser) return; const f = versFraction(e.clientX, e.clientY, img.current.getBoundingClientRect()); if (f) onPoser(f); }} />
      {ok === false && <p className="muted" style={{ padding: 12, margin: 0 }}>Pas de plan pour ce site. Le déposer dans <a href={hubLink("nebula", { tab: "plan" })}>Nebula › Plan</a> (photo du plan d'évacuation).</p>}
      {ok && (marqueurs || []).map((m) => (
        <div key={m.key} title={m.titre} onClick={(e) => { e.stopPropagation(); m.onClick && m.onClick(); }}
          style={{ position: "absolute", left: `${m.x * 100}%`, top: `${m.y * 100}%`, transform: "translate(-50%, -50%)", width: m.taille || 22, height: m.taille || 22, borderRadius: "50%",
            background: m.couleur || "var(--accent)", border: "2px solid var(--bg)", boxShadow: "0 0 0 1px var(--border)", fontSize: 11, lineHeight: `${(m.taille || 22) - 4}px`, textAlign: "center", color: "var(--bg)", fontWeight: 700 }}>
          {m.texte || ""}
        </div>
      ))}
    </div>
  );
}

const Barre = ({ titre, onRetour, droite }) => (
  <div className="mob-barre"><button type="button" className="secondary" onClick={onRetour}>◀</button><h2>{titre}</h2>{droite}</div>
);

export default function ReperageView({ onBack, nebulaApiBase, actor }) {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState(() => store.get(SITE_KEY, ""));
  const [ecran, setEcran] = useState("menu");       // menu | prise | brassage | position | wifi
  const [inv, setInv] = useState(null);
  const [prises, setPrises] = useState([]);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [form, setForm] = useState(null);           // prise en édition
  const [msg, setMsg] = useState(null);
  const [mac, setMac] = useState(() => store.get(MAC_KEY, ""));
  const [mobile, setMobile] = useState(null);
  const [releves, setReleves] = useState([]);
  const [rssiTel, setRssiTel] = useState("");
  const [noteRel, setNoteRel] = useState("");
  const [swOuvert, setSwOuvert] = useState(null);
  const [appareils, setAppareils] = useState([]);     // appareils connus (téléphones de test) : base du module, pas le dépôt
  const [nomApp, setNomApp] = useState("");
  const [radar, setRadar] = useState(null);           // dernier balayage reçu du téléphone (Termux) / de la sonde
  const [radarSource, setRadarSource] = useState(() => store.get("hub.reperage.radar.source", ""));
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}`;

  useEffect(() => {
    getJson(`${nebulaApiBase}/reperage/sites`).then((d) => { const s = d.sites || []; setSites(s); if (!siteId && s[0]) setSiteId(s[0].site_id); }).catch((e) => setErr("Nebula : " + e.message));
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [nebulaApiBase]);
  useEffect(() => { if (siteId) store.set(SITE_KEY, siteId); }, [siteId]);
  const chargerAppareils = useCallback(() => getJson(`${nebulaApiBase}/reperage/appareils`).then((d) => setAppareils(d.appareils || [])).catch(() => {}), [nebulaApiBase]);
  useEffect(() => { chargerAppareils(); }, [chargerAppareils]);
  const enregistrerAppareil = async () => {
    setBusy(true); setMsg(null);
    try { const a = await putJson(`${nebulaApiBase}/reperage/appareils`, { mac, nom: nomApp, genre: "telephone" }); setMsg({ ok: true, text: `✓ ${a.nom} (${a.mac}) enregistré comme appareil connu.` }); setNomApp(""); chargerAppareils(); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  };

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

  useEffect(() => {
    if (!siteId || q.trim().length < 2) { setRes(null); return; }
    const t = setTimeout(() => getJson(`${base}/reperage/recherche?q=${encodeURIComponent(q.trim())}`).then((d) => setRes(d.resultats || [])).catch((e) => setErr(e.message)), 350);
    return () => clearTimeout(t);
  }, [q, base, siteId]);

  useEffect(() => {
    if (ecran !== "wifi" || !siteId || !mac) return;
    let stop = false;
    const tic = () => getJson(`${base}/reperage/mobile?mac=${encodeURIComponent(mac)}&refresh=1`).then((d) => { if (!stop) setMobile(d); }).catch((e) => { if (!stop) setMobile({ error: e.message }); });
    tic(); const t = setInterval(tic, 20000);
    return () => { stop = true; clearInterval(t); };
  }, [ecran, siteId, mac, base]);

  useEffect(() => {
    if (ecran !== "radar" || !siteId) return;
    let stop = false;
    const tic = () => getJson(`${base}/reperage/radar`).then((d) => { if (!stop) setRadar(d); }).catch((e) => { if (!stop) setRadar({ error: e.message }); });
    tic(); const t = setInterval(tic, 5000);
    return () => { stop = true; clearInterval(t); };
  }, [ecran, siteId, base]);
  const marquerPosition = async (f) => {
    const src = radarSource || Object.keys(radar?.derniers || {})[0] || "?";
    try { await postJson(`${base}/reperage/radar/position`, { source: src, x: f.x, y: f.y }); setMsg({ ok: true, text: `✓ Position marquée (${src}).` }); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
  };
  const table = useMemo(() => tableBrassage(inv, prises), [inv, prises]);
  const anomalies = useMemo(() => anomaliesBrassage(table), [table]);
  const synthese = useMemo(() => syntheseCouverture(releves), [releves]);
  const prisePour = (c) => prises.find((p) => p.mac === c.mac) || prises.find((p) => p.commutateur === c.commutateur && String(p.port) === String(c.port));
  const ouvrirPrise = (p, c) => { setMsg(null); setForm({ prise: "", local: "", panneau: "", note: "", long_cordon: false, wifi: false, defaut: false, photos: [], ...(p || {}),
    ...(c ? { commutateur: c.commutateur || p?.commutateur || "", port: c.port ?? p?.port ?? "", mac: c.mac || p?.mac || "", equipement: p?.equipement || libelleClient(c) } : {}) }); };

  const enregistrerPrise = async () => {
    if (!form?.prise?.trim()) { setMsg({ ok: false, text: "Donner l'étiquette de la prise (ex. B-12)." }); return; }
    setBusy(true); setMsg(null);
    try {
      const p = await putJson(`${base}/reperage/prises`, { ...form, par: actor || "" });
      setPrises((cur) => [...cur.filter((x) => x.prise !== p.prise), p].sort((a, b) => a.prise.localeCompare(b.prise, "fr")));
      setMsg({ ok: true, text: `✓ Prise ${p.prise} enregistrée.` }); setForm(null);
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  };
  const supprimerPrise = async (p) => {
    if (!confirm(`Supprimer la prise ${p.prise} ?`)) return;
    await getJson(`${base}/reperage/prises/${encodeURIComponent(p.prise)}`, { method: "DELETE" }).catch((e) => setMsg({ ok: false, text: e.message }));
    setPrises((cur) => cur.filter((x) => x.prise !== p.prise)); setForm(null);
  };
  const photo = async (file) => {
    if (!file || !form) return;
    setBusy(true); setMsg({ ok: true, text: "⏳ Envoi de la photo…" });
    try {
      const f = await reduirePhoto(file);
      const fd = new FormData(); fd.append("file", f, f.name || "photo.jpg");
      const r = await getJson(`${base}/reperage/photos`, { method: "POST", body: fd });
      setForm((cur) => ({ ...cur, photos: [...(cur.photos || []), r.id] }));
      setMsg({ ok: true, text: "✓ Photo ajoutée. Enregistrer la prise pour la garder." });
    } catch (e) { setMsg({ ok: false, text: "Photo : " + e.message }); }
    finally { setBusy(false); }
  };
  const relever = async (f) => {
    if (!mac) { setMsg({ ok: false, text: "Renseigner d'abord la MAC Wi-Fi du téléphone." }); return; }
    setBusy(true);
    try {
      const r = await postJson(`${base}/reperage/releves`, { x: f.x, y: f.y, mac, note: noteRel, rssi_mobile: rssiTel === "" ? null : Number(rssiTel) });
      setReleves((cur) => [...cur, r]); setMsg({ ok: true, text: `✓ Relevé : ${texteReleve(r)}` });
    } catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  };
  const supprimerReleve = async (r) => { await getJson(`${base}/reperage/releves/${r.id}`, { method: "DELETE" }).catch(() => {}); setReleves((cur) => cur.filter((x) => x.id !== r.id)); };

  const messages = (
    <>
      {err && <p style={{ color: "var(--warning)", margin: "6px 0" }}>{err}</p>}
      {msg && <p style={{ color: msg.ok ? "var(--ok)" : "var(--danger)", margin: "6px 0", fontWeight: 600 }}>{msg.text}</p>}
    </>
  );

  const carteClient = (c, cle) => {
    const p = prisePour(c);
    return (
      <div key={cle || c.mac} className="mob-carte">
        <div className="t">{c.type === "wifi" ? "📶" : "🔌"} {libelleClient(c)}</div>
        <div>{ouEstBranche(c)}</div>
        <div className="d">{c.ip ? `IP ${c.ip} · ` : ""}{c.mac}{c.fabricant ? ` · ${c.fabricant}` : ""}{c.connu ? ` · ★ ${c.connu}` : ""}</div>
        <div className="d">{p ? `Prise ${p.prise}${p.local ? ` · ${p.local}` : ""}` : c.type === "filaire" ? "Prise non relevée" : ""}</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
          <button type="button" onClick={() => ouvrirPrise(p, c)}>{p ? "Corriger la prise" : "Relever la prise"}</button>
          <button type="button" className="secondary" onClick={() => { ouvrirPrise(p, c); setEcran("position"); }}>📍 Poser sur le plan</button>
        </div>
      </div>
    );
  };

  const fichePrise = () => form && (
    <div className="mob-carte on">
      <div className="t">Prise {form.prise || "(nouvelle)"}</div>
      <label>Étiquette de la prise<input value={form.prise} onChange={(e) => setForm({ ...form, prise: e.target.value })} placeholder="B-12" /></label>
      <label>Local / pièce<input value={form.local || ""} onChange={(e) => setForm({ ...form, local: e.target.value })} placeholder="Amphi" /></label>
      <label>Commutateur<input list="rep-sw" value={form.commutateur || ""} onChange={(e) => setForm({ ...form, commutateur: e.target.value })} /></label>
      <datalist id="rep-sw">{(inv?.commutateurs || []).map((s) => <option key={s.id} value={s.nom} />)}</datalist>
      <label>Port<input type="number" inputMode="numeric" value={form.port ?? ""} onChange={(e) => setForm({ ...form, port: e.target.value })} /></label>
      <label>Panneau / position en baie<input value={form.panneau || ""} onChange={(e) => setForm({ ...form, panneau: e.target.value })} placeholder="baie 1, panneau A, 12" /></label>
      <label>Équipement attendu<input value={form.equipement || ""} onChange={(e) => setForm({ ...form, equipement: e.target.value })} /></label>
      <label>MAC de l'équipement<input value={form.mac || ""} onChange={(e) => setForm({ ...form, mac: e.target.value })} placeholder="aa:bb:cc:dd:ee:ff" /></label>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, margin: "8px 0" }}>
        {[["long_cordon", "Long cordon"], ["wifi", "En Wi-Fi"], ["defaut", "Défaut"]].map(([k, l]) => (
          <button key={k} type="button" className={form[k] ? "" : "secondary"} onClick={() => setForm({ ...form, [k]: !form[k] })} style={{ minHeight: 48, fontSize: 15 }}>{form[k] ? "☑ " : "☐ "}{l}</button>))}
      </div>
      <label>Note<textarea rows={2} value={form.note || ""} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="état, à corriger…" /></label>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", margin: "8px 0" }}>
        {(form.photos || []).map((id) => <a key={id} href={`${base}/reperage/photos/${id}`} target="_blank" rel="noreferrer"><img alt="" src={`${base}/reperage/photos/${id}`} style={{ height: 64, borderRadius: 8, border: "1px solid var(--border)" }} /></a>)}
      </div>
      {form.x != null && <p className="d" style={{ margin: "4px 0" }}>Posée sur le plan ({Math.round(form.x * 100)} %, {Math.round(form.y * 100)} %).</p>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <label className="mob-btn secondary" style={{ display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", border: "1px solid var(--border)" }}>📷 Photo<input type="file" accept="image/*" capture="environment" style={{ display: "none" }} onChange={(e) => { photo(e.target.files?.[0]); e.target.value = ""; }} /></label>
        <button type="button" disabled={busy} onClick={enregistrerPrise}>{busy ? "⏳ En cours…" : "✓ Enregistrer"}</button>
        <button type="button" className="secondary" onClick={() => setForm(null)}>Annuler</button>
        {form.maj ? <button type="button" className="secondary" onClick={() => supprimerPrise(form)} style={{ color: "var(--danger)" }}>Supprimer</button> : <span />}
      </div>
    </div>
  );

  // ---------------------------------------------------------------- écrans
  if (ecran === "menu") {
    return (
      <div>
        <div className="mob-barre"><button type="button" className="secondary" onClick={onBack}>◀ Hub</button><h2>📍 Repérage</h2></div>
        {sites.length > 1 && <label>Site<select value={siteId} onChange={(e) => setSiteId(e.target.value)}>{sites.map((s) => <option key={s.site_id} value={s.site_id}>{s.name || s.site_id}</option>)}</select></label>}
        {inv?.test && <p className="d">Site de test : commutateur SW-TEST, borne BORNE-TEST (SSID GROUPE_I), plan = rectangle du bureau ; le signal du téléphone est simulé et varie. Les prises et relevés sont réels (table du module).</p>}
        {messages}
        <div className="mob-menu">
          {ONGLETS.map((o) => (
            <button key={o.id} type="button" className="secondary" onClick={() => { setMsg(null); setEcran(o.id); }}>
              <span className="ic">{o.icon}</span>
              <span>{o.label.replace(/^\d · /, "")}<small>{{ prise: "Trouver où est branché un équipement", brassage: "Port par port, déclarer les prises", position: "Poser la prise sur le plan, photo", wifi: "Relever le signal là où je suis" }[o.id]}</small></span>
            </button>
          ))}
          <button type="button" className="secondary" disabled={busy} onClick={() => charger(true)}><span className="ic">↻</span><span>Rafraîchir Nebula<small>{inv ? `${inv.clients.length} équipements vus · ${prises.length} prises relevées` : busy ? "lecture…" : "pas encore lu"}</small></span></button>
        </div>
      </div>
    );
  }

  const retour = () => { setForm(null); setMsg(null); setEcran("menu"); };

  if (ecran === "prise") {
    const liste = res ?? (inv ? (inv.clients || []).filter((c) => c.type === "filaire").slice(0, 20) : []);
    return (
      <div>
        <Barre titre="🔌 Prise / équipement" onRetour={retour} />
        {!form && <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nom, IP, MAC, « p12 », prise…" autoFocus />}
        {messages}
        {fichePrise()}
        {!form && res && res.length === 0 && <p className="d">Rien trouvé. Brancher l'équipement, attendre une minute, puis ↻ au menu.</p>}
        {!form && liste.map((r, i) => (r.genre ? (r.genre === "client" ? carteClient(r.objet, "r" + i) : (
          <div key={"p" + i} className="mob-carte" onClick={() => ouvrirPrise(r.objet)}>
            <div className="t">🔌 Prise {r.objet.prise}</div><div>{r.objet.local || ""}</div>
            <div className="d">{r.objet.commutateur ? `${r.objet.commutateur} port ${r.objet.port ?? "?"}` : "port non relevé"}{r.objet.equipement ? ` · ${r.objet.equipement}` : ""}</div>
          </div>)) : carteClient(r)))}
      </div>
    );
  }

  if (ecran === "brassage") {
    return (
      <div>
        <Barre titre="🧵 Brassage" onRetour={retour} droite={<a className="secondary mob-btn" style={{ display: "inline-flex", alignItems: "center" }} href={`${base}/reperage/prises.csv`} target="_blank" rel="noreferrer">⬇ CSV</a>} />
        {messages}
        {fichePrise()}
        {!form && <button type="button" onClick={() => ouvrirPrise(null)} style={{ width: "100%" }}>+ Déclarer une prise</button>}
        {!form && anomalies.length > 0 && <div className="mob-carte" style={{ borderColor: "var(--warning)" }}><div className="t">⚠ {anomalies.length} anomalie(s)</div>{anomalies.map((a, i) => <div key={i}>• {a.texte}</div>)}</div>}
        {!form && table.commutateurs.map((sw) => (
          <div key={sw.id} className="mob-carte">
            <button type="button" className="secondary" style={{ width: "100%", textAlign: "left" }} onClick={() => setSwOuvert(swOuvert === sw.id ? null : sw.id)}>{swOuvert === sw.id ? "▾" : "▸"} {sw.nom} <small style={{ color: "var(--muted)" }}>· {sw.ports.length} ports actifs</small></button>
            {swOuvert === sw.id && sw.ports.map((p) => (
              <div key={p.port} className="mob-carte" style={{ margin: "6px 0" }} onClick={() => ouvrirPrise(p.prises[0] || null, p.clients[0] ? { ...p.clients[0], commutateur: sw.nom, port: p.port } : { commutateur: sw.nom, port: p.port, mac: null })}>
                <div className="t">Port {p.port}{p.prises.length ? ` — 🔌 ${p.prises.map((x) => x.prise).join(", ")}` : ""}</div>
                {p.clients.map((c) => <div key={c.mac}>{libelleClient(c)} <span className="d">{c.ip || c.mac}{c.vlan ? ` · VLAN ${c.vlan}` : ""}</span></div>)}
                <div className="d">{p.prises.length ? p.prises.map((x) => x.local).filter(Boolean).join(", ") || "toucher pour corriger" : "prise non déclarée — toucher pour déclarer"}</div>
              </div>
            ))}
          </div>
        ))}
        {!form && table.orphelines.length > 0 && <div className="mob-carte"><div className="t">Prises sans équipement vu ({table.orphelines.length})</div>{table.orphelines.map((p) => <div key={p.prise} onClick={() => ouvrirPrise(p)}>🔌 {p.prise} · {p.commutateur} port {p.port}</div>)}</div>}
        {!form && !table.commutateurs.length && <p className="d">Aucun client de commutateur vu par Nebula (24 h).</p>}
      </div>
    );
  }

  if (ecran === "position") {
    return (
      <div>
        <Barre titre="📍 Position" onRetour={retour} />
        {messages}
        <p className="d" style={{ margin: "4px 0" }}>{form ? <>Toucher le plan là où est la prise <b>{form.prise || "(nouvelle)"}</b>, puis ✓ Enregistrer.</> : "Choisir une prise ci-dessous (ou en déclarer une), puis toucher le plan. Rouge = défaut."}</p>
        <Plan base={base} version={0}
          marqueurs={prises.filter((p) => p.x != null).map((p) => ({ key: p.prise, x: p.x, y: p.y, titre: p.prise, couleur: p.defaut ? "var(--danger)" : form?.prise === p.prise ? "var(--accent)" : "var(--ok)", taille: 18, onClick: () => ouvrirPrise(p) }))}
          onPoser={form ? (f) => setForm({ ...form, x: f.x, y: f.y }) : null} />
        {fichePrise()}
        {!form && <button type="button" onClick={() => ouvrirPrise(null)} style={{ width: "100%", marginTop: 8 }}>+ Déclarer une prise</button>}
        {!form && prises.map((p) => <div key={p.prise} className="mob-carte" onClick={() => ouvrirPrise(p)}><div className="t">{p.x != null ? "📍" : "·"} {p.prise}</div><div className="d">{[p.local, p.long_cordon ? "long cordon" : null, p.wifi ? "Wi-Fi" : null, p.photos?.length ? `${p.photos.length} photo(s)` : null].filter(Boolean).join(" · ") || "non posée"}</div></div>)}
      </div>
    );
  }

  if (ecran === "radar") {
    const sources = Object.keys(radar?.derniers || {});
    const src = radarSource && radar?.derniers?.[radarSource] ? radarSource : sources[0];
    const dernier = src ? radar.derniers[src] : null;
    const lignes = lignesRadar(dernier?.bornes);
    return (
      <div>
        <Barre titre="📡 Radar Wi-Fi" onRetour={() => setEcran("wifi")} droite={<a className="secondary mob-btn" style={{ display: "inline-flex", alignItems: "center" }} href={`${base}/reperage/radar.csv`} target="_blank" rel="noreferrer">⬇ CSV</a>} />
        {messages}
        {radar?.error && <p style={{ color: "var(--danger)" }}>{radar.error}</p>}
        <div className="mob-carte">
          <div className="t">{radar ? `${radar.scans || 0} balayage(s) · ${radar.bssids || 0} bornes distinctes · ${radar.positions || 0} position(s)` : "…"}</div>
          {sources.length > 1 && <label>Source<select value={src || ""} onChange={(e) => { setRadarSource(e.target.value); store.set("hub.reperage.radar.source", e.target.value); }}>{sources.map((x) => <option key={x} value={x}>{x}</option>)}</select></label>}
          <div className="d">{dernier ? `Dernier balayage de ${src} ${ageBalayage(dernier.at, radar.maintenant)} — ${lignes.length} borne(s) visibles` : "Aucun balayage reçu : lancer le script radar-mobile.sh dans Termux (voir aide ci-dessous)."}</div>
        </div>
        {lignes.map((l) => (
          <div key={l.cle} className="mob-carte" style={{ padding: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}><span className="t" style={{ fontSize: 17 }}>{l.nom}</span><span style={{ color: CLASSE_COULEUR[l.classe], fontWeight: 700 }}>{l.rssi} dBm · ≈ {l.distance}</span></div>
            <div style={{ height: 10, background: "var(--border)", borderRadius: 5, margin: "6px 0" }}><div style={{ width: `${Math.round(l.niveau * 100)}%`, height: "100%", background: CLASSE_COULEUR[l.classe], borderRadius: 5 }} /></div>
            <div className="d">{l.bssid}{l.bande ? ` · ${l.bande}` : ""}{l.canal ? ` · canal ${l.canal}` : ""}</div>
          </div>
        ))}
        <p className="d" style={{ margin: "8px 0" }}>Toucher le plan là où vous êtes : la position est horodatée et rapprochée des balayages au post-traitement.</p>
        <Plan base={base} version={0} onPoser={marquerPosition} marqueurs={(radar?.positions_recentes || []).map((p, i) => ({ key: "pos" + p.at, x: p.x, y: p.y, taille: i === 0 ? 22 : 14, texte: i === 0 ? "●" : "", couleur: i === 0 ? "var(--accent)" : "var(--muted)", titre: `${p.source} · ${ageBalayage(p.at, radar.maintenant)}` }))} />
        <details className="mob-carte"><summary>Aide : envoyer les balayages depuis le téléphone</summary>
          <div className="d">1. Installer <b>Termux</b> et <b>Termux:API</b> (F-Droid) ; dans Termux : <code>pkg install termux-api jq curl</code>.<br />2. Android › Options pour les développeurs › désactiver « Limitation de la recherche Wi-Fi ».<br />3. Copier <code>nebula/tools/radar-mobile.sh</code> sur le téléphone puis : <code>HUB={nebulaApiBase.startsWith("http") ? nebulaApiBase : window.location.origin + nebulaApiBase} SOURCE="Téléphone" ./radar-mobile.sh 5 {siteId}</code> (réglages mémorisés : ensuite <code>./radar-mobile.sh</code> suffit ; le site peut être donné par son nom)<br />Alternative : la sonde Pi (Alfa) portée, qui balaie plus vite et sur toutes les bandes.</div>
        </details>
      </div>
    );
  }

  // wifi
  return (
    <div>
      <Barre titre="📶 Couverture Wi-Fi" onRetour={retour} droite={<button type="button" className="secondary" onClick={() => setEcran("radar")}>📡 Radar</button>} />
      {messages}
      <div className="mob-carte">
        {appareils.length > 0 && <label>Appareil connu<select value={appareils.some((a) => a.mac === mac) ? mac : ""} onChange={(e) => { if (e.target.value) { setMac(e.target.value); store.set(MAC_KEY, e.target.value); } }}>
          <option value="">— choisir —</option>{appareils.map((a) => <option key={a.mac} value={a.mac}>{a.nom} · {a.mac}</option>)}</select></label>}
        <label>MAC Wi-Fi du téléphone<input value={mac} onChange={(e) => { setMac(e.target.value); store.set(MAC_KEY, e.target.value); }} placeholder="aa:bb:cc:dd:ee:ff" /></label>
        <div className="d">Réglages › À propos. Désactiver la MAC aléatoire pour le Wi-Fi du site.</div>
        {mac && !appareils.some((a) => a.mac === mac.trim().toLowerCase()) && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, marginTop: 6 }}>
            <input value={nomApp} onChange={(e) => setNomApp(e.target.value)} placeholder="nom (ex. Téléphone Freg)" />
            <button type="button" className="secondary" disabled={busy || !nomApp.trim()} onClick={enregistrerAppareil}>{busy ? "⏳" : "＋ Mémoriser"}</button>
          </div>
        )}
        {mobile?.error && <p style={{ color: "var(--danger)" }}>{mobile.error}</p>}
        {mobile && !mobile.error && (mobile.vu ? (
          <p style={{ margin: "8px 0", fontSize: 19 }}>Borne <b>{mobile.mobile.borne || "?"}</b><br /><span style={{ color: CLASSE_COULEUR[mobile.classe], fontWeight: 700 }}>{mobile.mobile.signal != null ? `${mobile.mobile.signal} dBm — ${mobile.classe}` : "signal non transmis"}</span>{mobile.mobile.bande ? ` · ${bande(mobile.mobile.bande)}` : ""}{mobile.mobile.canal ? ` · canal ${mobile.mobile.canal}` : ""}</p>
        ) : <p className="d" style={{ margin: "8px 0" }}>Téléphone non vu par les bornes : vérifier la MAC et le Wi-Fi du site (retard Nebula ≈ 1 min).</p>)}
        <label>RSSI lu sur le téléphone (facultatif)<input type="number" inputMode="numeric" value={rssiTel} onChange={(e) => setRssiTel(e.target.value)} placeholder="-62" /></label>
        <label>Note<input value={noteRel} onChange={(e) => setNoteRel(e.target.value)} placeholder="amphi, rang 5…" /></label>
      </div>
      <p className="d" style={{ margin: "6px 0" }}>Toucher le plan là où vous êtes. Vert ≥ −60 · bleu ≥ −70 · orange ≥ −80 · rouge. Toucher un point pour le supprimer.</p>
      <Plan base={base} version={0} onPoser={relever}
        marqueurs={releves.map((r) => ({ key: r.id, x: r.x, y: r.y, taille: 24, texte: String((r.rssi_mobile ?? r.signal ?? "")).replace("-", ""), couleur: CLASSE_COULEUR[classeSignal(r.rssi_mobile ?? r.signal)], titre: texteReleve(r), onClick: () => { if (confirm(`Supprimer ce relevé ?\n${texteReleve(r)}`)) supprimerReleve(r); } }))} />
      <div className="mob-carte">
        <div className="t">{synthese.total} relevé(s){synthese.faibles ? ` · ${synthese.faibles} faible(s)` : ""}</div>
        {synthese.bornes.map((b) => <div key={b.borne}>{b.borne} : {b.n} relevé(s), médiane {b.median != null ? `${b.median} dBm` : "—"}</div>)}
        {inv?.bornes?.length ? <div className="d" style={{ marginTop: 6 }}>Bornes vues par Nebula : {inv.bornes.map((b) => `${b.nom} (${b.clients})`).join(", ")}</div> : null}
      </div>
    </div>
  );
}
