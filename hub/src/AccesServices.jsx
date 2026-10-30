// #928 : onglet « Accès services » d'un poste -- temps d'accès aux sites de service de l'entreprise (GED, cloud,
// annuaire, tickets…) : temps BRUT (sans authentification) et, si un accès du coffre est configuré, temps de
// chargement en PASSANT l'authentification. Le secret ne quitte jamais le coffre : la liste ne porte que le NOM d'un
// accès. Éditeur de la liste repliable sous les résultats.
import { useCallback, useEffect, useState } from "react";
import { fetchServicesPoste, saveServicesPoste, runAccesServices, fetchAccesServices } from "./siAgentClient.js";
import BoutonDetail from "./FenetreTexte.jsx";
import { secondes, codeTon } from "./accesServicesLib.js";

const TON = { critical: "bad", warning: "warn", info: "neutral" };
const TYPES = [["aucun", "aucune"], ["form", "formulaire"], ["basic", "HTTP Basic"], ["token", "jeton"]];

function ligneVide() {
  return { nom: "", url: "", auth: { type: "aucun", acces: "", champ_user: "", champ_pass: "", url_login: "", marqueur_connecte: "" } };
}

function Resultats({ resultat, at }) {
  if (!resultat) return <p className="infra-muted">Aucun test lancé. « Lancer le test » mesure, pour chaque site, le temps d'accès brut puis (si authentification configurée) le temps en passant la connexion.</p>;
  const sites = resultat.sites || [];
  return (
    <>
      <div className="infra-muted" style={{ margin: "4px 0" }}>Dernier test : {at ? new Date(at).toLocaleString("fr-FR") : "—"}</div>
      <table className="infra-table">
        <thead><tr><th>Site</th><th>Accès brut</th><th>Code</th><th>Authentification</th><th>Connecté</th><th>Constat</th></tr></thead>
        <tbody>
          {sites.length === 0 && <tr><td colSpan={6} className="infra-muted">aucun site mesuré</td></tr>}
          {sites.map((s, i) => {
            const b = s.brut || {}, a = s.authentifie;
            const crit = (s.constats || []).filter((c) => c.severity === "critical");
            const txtConstat = (s.constats || []).map((c) => c.message).join("\n");
            return (
              <tr key={i}>
                <td>{s.nom}<div className="infra-muted" style={{ fontSize: 12 }}>{s.hote}</div></td>
                <td className={b.erreur ? "np-tone bad" : (b.total_ms >= 2000 ? "np-tone warn" : "")}>
                  {b.erreur ? "échec" : secondes(b.total_ms)}
                  {!b.erreur && b.ttfb_ms != null && <span className="infra-muted" style={{ fontSize: 12 }}> · 1er octet {secondes(b.ttfb_ms)}</span>}
                </td>
                <td className={`np-tone ${codeTon(b.status)}`}>{b.status ?? "—"}</td>
                <td>{a == null ? <span className="infra-muted">{s.auth_type === "aucun" ? "—" : "non mesurée"}</span>
                  : <span className={a.erreur ? "np-tone bad" : (a.total_ms >= 5000 ? "np-tone warn" : "")}>{a.erreur ? "échec" : secondes(a.total_ms)}</span>}
                  {a && a.auth_type !== "aucun" && <span className="infra-muted" style={{ fontSize: 12 }}> ({s.auth_type})</span>}</td>
                <td>{a == null ? "—" : a.connecte === true ? <span className="np-tone good">oui</span> : a.connecte === false ? <span className="np-tone bad">non</span> : "?"}</td>
                <td>{crit.length || (s.constats || []).length ? <BoutonDetail titre={`Constats : ${s.nom}`} urgence={crit.length ? "critique" : "alerte"} texte={txtConstat} /> : <span className="np-tone good">ok</span>}</td>
              </tr>);
          })}
        </tbody>
      </table>
    </>
  );
}

function Editeur({ base, actor, onFerme }) {
  const [liste, setListe] = useState(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { fetchServicesPoste(base).then((r) => setListe((r?.services || []).map((s) => ({ ...ligneVide(), ...s, auth: { ...ligneVide().auth, ...(s.auth || {}) } })))); }, [base]);
  if (!liste) return <p className="infra-muted">lecture…</p>;
  const maj = (i, f) => setListe(liste.map((s, k) => (k === i ? f(s) : s)));
  const majAuth = (i, champ, val) => maj(i, (s) => ({ ...s, auth: { ...s.auth, [champ]: val } }));
  const enregistrer = async () => {
    const propres = liste.filter((s) => s.nom.trim() && s.url.trim());
    const r = await saveServicesPoste(base, propres, actor);
    if (r?.error) { setMsg(r.error); return; }
    setMsg(`Enregistré (${(r.services || []).length} site(s)).`);
  };
  return (
    <div className="infra-card" style={{ marginTop: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <b>Sites de service</b>
        <span className="infra-muted" style={{ fontSize: 12 }}>La liste ne contient aucun mot de passe : seulement le <b>nom d'un accès du coffre</b> « Accès d'équipements ». Y créer un compte de supervision dédié.</span>
      </div>
      {msg && <p className={`np-tone ${/Enregistré/.test(msg) ? "good" : "bad"}`} style={{ margin: "4px 0" }}>{msg}</p>}
      <div style={{ maxHeight: 320, overflow: "auto" }}>
        <table className="infra-table">
          <thead><tr><th>Nom</th><th>URL</th><th>Auth.</th><th>Accès coffre</th><th>Détails formulaire</th><th /></tr></thead>
          <tbody>
            {liste.map((s, i) => (
              <tr key={i}>
                <td><input value={s.nom} onChange={(e) => maj(i, (x) => ({ ...x, nom: e.target.value }))} style={{ width: 90 }} placeholder="GED" /></td>
                <td><input value={s.url} onChange={(e) => maj(i, (x) => ({ ...x, url: e.target.value }))} style={{ width: 200 }} placeholder="https://ged.exemple/" /></td>
                <td><select value={s.auth.type} onChange={(e) => majAuth(i, "type", e.target.value)}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></td>
                <td>{s.auth.type !== "aucun" && <input value={s.auth.acces} onChange={(e) => majAuth(i, "acces", e.target.value)} style={{ width: 110 }} placeholder="ged-superv" />}</td>
                <td>{s.auth.type === "form" && (
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    <input value={s.auth.champ_user} onChange={(e) => majAuth(i, "champ_user", e.target.value)} style={{ width: 70 }} placeholder="champ user" title="nom du champ utilisateur du formulaire" />
                    <input value={s.auth.champ_pass} onChange={(e) => majAuth(i, "champ_pass", e.target.value)} style={{ width: 70 }} placeholder="champ pass" title="nom du champ mot de passe" />
                    <input value={s.auth.url_login} onChange={(e) => majAuth(i, "url_login", e.target.value)} style={{ width: 140 }} placeholder="url du login (option)" title="page du formulaire si différente de l'URL" />
                    <input value={s.auth.marqueur_connecte} onChange={(e) => majAuth(i, "marqueur_connecte", e.target.value)} style={{ width: 120 }} placeholder="texte « connecté » (option)" title="texte présent sur la page une fois connecté" />
                  </div>)}
                  {s.auth.type === "token" && <span className="infra-muted" style={{ fontSize: 12 }}>en-tête Authorization, « Bearer » + jeton du coffre</span>}</td>
                <td><button type="button" className="secondary" onClick={() => setListe(liste.filter((_, k) => k !== i))} title="retirer">✕</button></td>
              </tr>))}
          </tbody>
        </table>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
        <button type="button" className="secondary" onClick={() => setListe([...liste, ligneVide()])}>+ un site</button>
        <button type="button" className="primary" onClick={enregistrer}>Enregistrer</button>
        {onFerme && <button type="button" className="secondary" onClick={onFerme}>Fermer</button>}
      </div>
    </div>
  );
}

export default function AccesServices({ agent, base, actor }) {
  const [res, setRes] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [edite, setEdite] = useState(false);
  const charger = useCallback(() => fetchAccesServices(base, agent).then((r) => { if (r && !r.error) setRes(r); }), [base, agent]);
  useEffect(() => { setRes(null); charger(); }, [charger]);
  // un test tourne en tâche de fond sur le poste ~1 min : on relève quelques fois après le lancement
  const lancer = async () => {
    setBusy(true); setMsg("");
    const r = await runAccesServices(base, agent, { actor });
    setBusy(false);
    if (r?.error) { setMsg(r.error); return; }
    const ko = (r.coffre_indisponibles || []).length;
    setMsg(`Test envoyé : ${r.sites} site(s), ${r.authentifies} authentifié(s)${ko ? ` — ${ko} accès coffre indisponible(s)` : ""}. Résultat dans ~1 min.`);
    let n = 0;
    const t = setInterval(() => { n += 1; charger(); if (n >= 12) clearInterval(t); }, 6000);
  };
  return (
    <div>
      <p style={{ margin: "0 0 8px" }} className="infra-muted">
        Mesure depuis le poste le temps d'accès aux sites de service : d'abord <b>brut</b> (requête simple, sans se connecter),
        puis en <b>passant l'authentification</b> jusqu'à la page connectée, avec un compte de supervision dont le secret reste au coffre.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
        <button type="button" className="primary" disabled={busy} onClick={lancer}>▶ Lancer le test</button>
        <button type="button" className="secondary" onClick={() => setEdite((v) => !v)}>{edite ? "Masquer la liste" : "Configurer les sites"}</button>
        <button type="button" className="secondary" onClick={charger}>⟳</button>
      </div>
      {msg && <p className={`np-tone ${/envoyé/.test(msg) ? "neutral" : "bad"}`} style={{ margin: "4px 0" }}>{msg}</p>}
      {edite && <Editeur base={base} actor={actor} onFerme={() => setEdite(false)} />}
      <Resultats resultat={res?.resultat} at={res?.at} />
    </div>
  );
}
