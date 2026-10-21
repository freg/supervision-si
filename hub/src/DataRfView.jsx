// Tuile « Data RF » (livraison #806) : sondes radio des sites -- spectre 2,4 / 5 GHz (HackRF, rf-spectrum), écoute Wi-Fi
// passive (Alfa, wifi-monitor), croisement par canal (occupé au spectre sans trafic Wi-Fi = brouillage probable), bornes
// vues, lien client (wifi-probe), constats. Données : si-agent-api /datarf (collecte du mini-PC de chaque site + sondes
// enrôlées directement). Rafraîchie toutes les 30 s.
import { useEffect, useMemo, useState } from "react";
import { fetchDataRf, fetchDataRfConfig, sendDataRfConfig, fetchCommand } from "./siAgentClient.js";
import { BANDES, traces, croiser, bornes, age, fmtAge, LECTURE, ROLES, configInitiale, verifierConfig, suiviCommande } from "./datarfLib.js";

const num = (v, s = "") => (v == null ? "—" : `${Math.round(v * 10) / 10}${s}`);

function Spectre({ rf, bande }) {
  const w = 600, h = 140, bas = -90, haut = -30;
  const t = traces(rf?.spectre, bande, w, h, bas, haut);
  const bruit = (rf?.bandes || []).filter((b) => b.de >= bande.de - 20 && b.a <= bande.a + 20).map((b) => b.bruit_db).filter((b) => b != null);
  return (
    <figure className="infra-card datarf-spectre">
      <figcaption>Spectre {bande.nom} <span className="infra-muted">dB relatifs (non étalonnés){bruit.length ? ` · bruit ${bruit.map((b) => num(b)).join(" / ")} dB` : ""}</span></figcaption>
      {t.n === 0 ? <p className="infra-muted">pas de balayage sur cette bande</p> : (
        <svg viewBox={`0 0 ${w} ${h + 16}`} width="100%" role="img" aria-label={`spectre ${bande.nom}`}>
          {[-80, -60, -40].map((db) => <g key={db}><line x1="0" x2={w} y1={t.y(db)} y2={t.y(db)} stroke="var(--viz-grid)" strokeDasharray="3 3" /><text x="2" y={t.y(db) - 2} className="datarf-axe">{db}</text></g>)}
          {bande.canaux.map((c) => { const f = c <= 14 ? 2407 + 5 * c : 5000 + 5 * c; return <g key={c}><line x1={t.x(f)} x2={t.x(f)} y1="0" y2={h} stroke="var(--viz-grid)" /><text x={t.x(f)} y={h + 12} textAnchor="middle" className="datarf-axe">{c}</text></g>; })}
          <path d={t.max} fill="none" stroke="var(--viz-2)" strokeWidth="1" opacity="0.8" />
          <path d={t.moy} fill="none" stroke="var(--viz-1)" strokeWidth="1.5" />
        </svg>
      )}
      <ul className="infra-legend"><li><i style={{ background: "var(--viz-1)" }} />moyenne</li><li><i style={{ background: "var(--viz-2)" }} />pic</li></ul>
    </figure>
  );
}

function Pct({ v, seuil = 30, critique = 70 }) {
  if (v == null) return <span className="infra-muted">—</span>;
  const tone = v >= critique ? "critical" : v >= seuil ? "warning" : "";
  return <span className="infra-meter-wrap"><span className="infra-meter"><span className={`fill ${tone}`} style={{ width: `${Math.min(100, v)}%` }} /></span><em>{num(v, " %")}{tone === "critical" ? " ⛔" : tone ? " ⚠" : ""}</em></span>;
}

// #807 : configuration radio de la sonde -- rôles des interfaces, SSID testés (clé lue dans le coffre par le central),
// envoyée par l'agent du mini-PC du site (collecteur) ou directement à la sonde ; suivi de la commande jusqu'au résultat
function ConfigRadio({ base, s, actor }) {
  const [cfg, setCfg] = useState(null);
  const [etat, setEtat] = useState(null);
  const [suivi, setSuivi] = useState(null);
  const [msg, setMsg] = useState("");
  const cible = s.via_agent ? { via_agent: s.via_agent } : { agent_id: s.agent_id };
  const sonde = s.via_agent ? (s.agent_id || s.sonde) : s.sonde;
  useEffect(() => { setCfg(null); setEtat(null); setSuivi(null); fetchDataRfConfig(base, s.sonde).then((r) => setCfg(configInitiale(null, r?.config))).catch(() => setCfg(configInitiale(null, null))); }, [base, s.sonde]);
  const suivre = (id, quand) => {
    let n = 0;
    const tour = () => fetchCommand(base, id).then((c) => {
      const sv = suiviCommande(c);
      setSuivi(sv);
      if (sv.etat === "attente" && n++ < 60) setTimeout(tour, 3000); else if (sv.etat === "ok") quand(sv.charge);
    }).catch((e) => setSuivi({ etat: "ko", texte: e.message }));
    tour();
  };
  const lire = () => {
    setMsg(""); setSuivi({ etat: "attente", texte: "envoi…" });
    sendDataRfConfig(base, { sonde, ...cible, action: "etat" }).then((r) => {
      if (r?.error) return setSuivi({ etat: "ko", texte: r.error });
      suivre(r.id, (charge) => { setEtat(charge); setCfg((c) => configInitiale(charge, c)); });
    });
  };
  const envoyer = () => {
    const err = verifierConfig(cfg);
    if (err.length) return setMsg(err.join(" · "));
    setMsg(""); setSuivi({ etat: "attente", texte: "envoi…" });
    sendDataRfConfig(base, { sonde, ...cible, action: "appliquer", ...cfg, actor }).then((r) => {
      if (r?.error) return setSuivi({ etat: "ko", texte: r.error });
      suivre(r.id, (charge) => { if (charge?.etat) setEtat(charge.etat); setMsg(`${(charge?.connexions_ecrites || []).length} SSID en place, ${(charge?.connexions_retirees || []).length} retiré(s)`); });
    });
  };
  if (!cfg) return null;
  const maj = (f) => setCfg((c) => f(JSON.parse(JSON.stringify(c))));
  const clients = Object.entries(cfg.interfaces).filter(([, r]) => r === "client").map(([n]) => n);
  const infos = Object.fromEntries((etat?.interfaces || []).map((i) => [i.nom, i]));
  return (
    <figure className="infra-card datarf-config">
      <figcaption>Configuration radio de {s.sonde} {s.via ? <span className="infra-muted">· par le collecteur de {s.via}</span> : null}</figcaption>
      <div className="infra-top">
        <button className="secondary" onClick={lire}>Lire les interfaces de la sonde</button>
        <button onClick={envoyer} disabled={suivi?.etat === "attente"}>Envoyer à la sonde</button>
        {suivi && <span className={`infra-status ${suivi.etat === "ko" ? "critical" : ""}`}>{suivi.etat === "attente" ? "⏳" : suivi.etat === "ok" ? "✔" : "⛔"} {suivi.texte}</span>}
        {msg && <span className="infra-muted">{msg}</span>}
      </div>
      <table className="infra-table">
        <thead><tr><th>Interface</th><th>Pilote</th><th>État</th><th>Rôle</th></tr></thead>
        <tbody>{Object.keys(cfg.interfaces).length === 0 ? <tr><td colSpan={4} className="infra-muted">Interfaces inconnues : « Lire les interfaces de la sonde ».</td></tr>
          : Object.entries(cfg.interfaces).map(([n, r]) => (
            <tr key={n}><td>{n}</td><td>{infos[n]?.pilote || "—"}</td><td>{infos[n] ? `${infos[n].type || "?"}${infos[n].connexion ? ` · ${infos[n].connexion}` : ""}` : "—"}</td>
              <td><select value={r} onChange={(e) => maj((c) => { c.interfaces[n] = e.target.value; return c; })}>{ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></td></tr>))}</tbody>
      </table>
      <table className="infra-table">
        <thead><tr><th>Actif</th><th>SSID testé</th><th>Accès du coffre (clé)</th><th>Interface</th><th></th></tr></thead>
        <tbody>{cfg.ssids.map((x, i) => (
          <tr key={i}>
            <td><input type="checkbox" checked={x.actif} onChange={(e) => maj((c) => { c.ssids[i].actif = e.target.checked; return c; })} aria-label={`activer ${x.ssid}`} /></td>
            <td><input value={x.ssid} onChange={(e) => maj((c) => { c.ssids[i].ssid = e.target.value; return c; })} placeholder="SSID" /></td>
            <td><input value={x.acces} onChange={(e) => maj((c) => { c.ssids[i].acces = e.target.value; return c; })} placeholder="nom de l'accès (vide = réseau ouvert)" /></td>
            <td><select value={x.iface} onChange={(e) => maj((c) => { c.ssids[i].iface = e.target.value; return c; })}><option value="">automatique</option>{clients.map((n) => <option key={n} value={n}>{n}</option>)}</select></td>
            <td><button className="secondary" onClick={() => maj((c) => { c.ssids.splice(i, 1); return c; })} aria-label={`retirer ${x.ssid}`}>✕</button></td>
          </tr>))}
          <tr><td colSpan={5}><button className="secondary" onClick={() => maj((c) => { c.ssids.push({ ssid: "", acces: "", actif: true, iface: "" }); return c; })}>+ SSID</button>
            <span className="infra-muted"> Les clés restent dans le coffre (tuile Accès d'équipements) : le central les lit au moment de l'envoi, la sonde les range en fichiers lisibles par root seul.</span></td></tr>
        </tbody>
      </table>
    </figure>
  );
}

export default function DataRfView({ onBack, siAgentApiBase, username }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [choix, setChoix] = useState("");
  const [at, setAt] = useState(null);
  useEffect(() => {
    let stop = false;
    const load = () => fetchDataRf(siAgentApiBase).then((d) => { if (!stop) { if (d?.error) setErr(d.error); else { setData(d); setErr(null); setAt(new Date()); } } }).catch((e) => !stop && setErr(e.message));
    load();
    const id = setInterval(load, 30000);
    return () => { stop = true; clearInterval(id); };
  }, [siAgentApiBase]);
  const sondes = data?.sondes || [];
  const s = sondes.find((x) => x.sonde === choix) || sondes[0];
  const canaux = useMemo(() => croiser(s?.rf_spectrum, s?.wifi_monitor), [s]);
  const bs = useMemo(() => bornes(s?.wifi_monitor), [s]);
  const constats = (data?.constats || []).filter((c) => !s || String(c.message || "").startsWith(s.sonde));
  const lien = s?.wifi_probe?.link || {};
  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Data RF</h2>
        {sondes.length > 0 && <select value={s?.sonde || ""} onChange={(e) => setChoix(e.target.value)} aria-label="sonde">{sondes.map((x) => <option key={x.sonde} value={x.sonde}>{x.sonde}{x.via ? ` (via ${x.via})` : ""}</option>)}</select>}
        <span className="infra-muted">{at ? `mis à jour ${at.toLocaleTimeString("fr-FR")}` : "lecture…"}</span>
      </div>
      {err && <p className="infra-error">{err}</p>}
      {data && !sondes.length && <p className="infra-muted">Aucune sonde : installer le collecteur sur le mini-PC du site (si-agent/local-central/installer-collecteur.sh), y enrôler les sondes, puis activer la sonde <code>collecte-sondes</code> sur l'agent du mini-PC (fiche de l'agent › Sondes).</p>}
      {s && (
        <div className="infra-scroll infra-page">
          <div className="infra-kpis">
            <div className="infra-kpi-group"><h3>{s.sonde}</h3>
              <div className="infra-kpi"><span>dernier contact</span><b>{fmtAge(s.age_s ?? age(s.recu))}</b><small>{s.ip || ""}{s.via ? ` · via ${s.via}` : ""}</small></div>
              <div className="infra-kpi"><span>écoute Wi-Fi</span><b>{s.wifi_monitor ? `${(s.wifi_monitor.canaux || []).length} canaux` : "—"}</b><small>{s.wifi_monitor ? `${bs.length} bornes · ${s.wifi_monitor.clients ?? 0} clients · ${fmtAge(age(s.wifi_monitor_at))}` : "wifi-monitor inactive"}</small></div>
              <div className="infra-kpi"><span>spectre</span><b>{s.rf_spectrum?.present === false ? "HackRF absent" : s.rf_spectrum ? `${(s.rf_spectrum.canaux || []).length} canaux` : "—"}</b><small>{s.rf_spectrum ? fmtAge(age(s.rf_spectrum_at)) : "rf-spectrum inactive"}</small></div>
              <div className="infra-kpi"><span>lien client</span><b>{lien.connected ? `${lien.signal_dbm ?? lien.signal ?? "?"} dBm` : s.wifi_probe ? "non associé" : "—"}</b><small>{lien.ssid || ""}{lien.freq ? ` · ${lien.freq} MHz` : ""}</small></div>
              <div className="infra-kpi"><span>constats</span><b>{constats.length}</b></div>
            </div>
          </div>
          <div className="infra-grid">
            {BANDES.map((b) => <Spectre key={b.nom} rf={s.rf_spectrum} bande={b} />)}
          </div>
          <ConfigRadio base={siAgentApiBase} s={s} actor={username} />
          <div className="infra-table-wrap">
            <table className="infra-table">
              <thead><tr><th>Canal</th><th>MHz</th><th>Occupation au spectre</th><th>Occupation Wi-Fi</th><th>Trames/s</th><th>Retransmissions</th><th>Désauth.</th><th>Signal max</th><th>Lecture</th></tr></thead>
              <tbody>{canaux.length === 0 ? <tr><td colSpan={9} className="infra-muted">Pas encore de mesure par canal.</td></tr> : canaux.map((c) => (
                <tr key={c.canal}><td>{c.canal}</td><td>{c.freq}</td><td><Pct v={c.spectre_pct} /></td><td><Pct v={c.wifi_pct} />{c.wifi_estime && c.wifi_pct != null ? <small className="infra-muted"> estim.</small> : null}</td>
                  <td>{num(c.trames_s)}</td><td>{c.retry_pct == null ? "—" : <Pct v={c.retry_pct} seuil={25} critique={50} />}</td><td>{c.deauth ?? "—"}</td><td>{c.signal_max == null ? "—" : `${c.signal_max} dBm`}</td>
                  <td>{c.lecture ? <span className={`infra-status ${c.lecture === "non-wifi" ? "warning" : ""}`}>{c.lecture === "non-wifi" ? "⚠ " : ""}{LECTURE[c.lecture]}</span> : ""}</td></tr>))}</tbody>
            </table>
          </div>
          <div className="infra-table-wrap">
            <table className="infra-table">
              <thead><tr><th>Borne (BSSID)</th><th>SSID</th><th>Canal</th><th>Signal max / moy.</th><th>Balises</th><th>Clients vus</th><th>Stations (borne)</th><th>Utilisation (borne)</th><th>Désauth.</th></tr></thead>
              <tbody>{bs.length === 0 ? <tr><td colSpan={9} className="infra-muted">Aucune borne relevée (écoute inactive ou carte absente).</td></tr> : bs.map((b) => (
                <tr key={b.bssid}><td className="infra-mono">{b.bssid}</td><td>{b.ssid === "" ? <span className="infra-muted">(masqué)</span> : b.ssid ?? "—"}</td><td>{b.canal ?? "—"}</td>
                  <td>{b.signal_max == null ? "—" : `${b.signal_max} / ${num(b.signal_moy)} dBm`}</td><td>{b.balises}</td><td>{b.clients}</td><td>{b.stations_borne ?? "—"}</td><td>{b.util_borne_pct == null ? "—" : <Pct v={b.util_borne_pct} />}</td><td>{b.deauth || ""}</td></tr>))}</tbody>
            </table>
          </div>
          <div className="infra-table-wrap">
            <table className="infra-table">
              <thead><tr><th>Gravité</th><th>Constat</th></tr></thead>
              <tbody>{constats.length === 0 ? <tr><td colSpan={2} className="infra-muted">Aucun constat.</td></tr>
                : constats.map((c, i) => <tr key={`${c.code}${i}`}><td><span className={`infra-status ${c.severity === "critical" ? "critical" : "warning"}`}>{c.severity === "critical" ? "⛔ critique" : "⚠ attention"}</span></td><td>{c.message}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
