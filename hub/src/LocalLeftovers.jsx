// #765 : restes du rapatriement sur un nœud LOCAL (archives vzdump gardées, .part, images brutes montées en boucle) --
// l'agent les liste, l'API évalue les conditions (copie présente, démarrée, sauvegardée sur PBS), l'opérateur valide la
// suppression avec un motif (journal d'audit sur l'hôte : /var/log/si-agent/xfer-purge-audit.log). Forcer reste possible,
// motif obligatoire.
import { useEffect, useState } from "react";
import { sendCommand, fetchCommand, evaluateLeftovers, purgeLeftover } from "./siAgentClient.js";
import { fmtBytes } from "./infraLib.js";
import { leftoverTotals } from "./repaLib.js";
import JournalLinks from "./JournalLinks.jsx";   // #768

async function waitCommand(base, cid, onWait) {
  const t0 = Date.now();
  while (Date.now() - t0 < 4 * 60 * 1000) {
    await new Promise((ok) => setTimeout(ok, 2500));
    onWait?.(Math.round((Date.now() - t0) / 1000));
    const c = await fetchCommand(base, cid).catch(() => null);
    if (c && (c.status === "done" || c.status === "failed")) {
      const res = c.result?.result || c.result || {};
      if (c.status === "failed" || res.ok === false) throw new Error(res.error || c.result?.error || "refusé");
      return res;
    }
  }
  throw new Error("pas de réponse de l'agent en 4 min (hors ligne ?)");
}

const when = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—");

export default function LocalLeftovers({ base, hosts, defaultAgent, username, open }) {
  const [agent, setAgent] = useState(defaultAgent || ""), [items, setItems] = useState(null), [busy, setBusy] = useState(""), [err, setErr] = useState(null);
  const [msg, setMsg] = useState([]), [reason, setReason] = useState(""), [meta, setMeta] = useState(null);
  useEffect(() => { if (defaultAgent) setAgent(defaultAgent); }, [defaultAgent]);
  useEffect(() => { if (!agent && hosts?.[0]) setAgent(hosts[0].agent_id); }, [hosts, agent]);

  const analyse = async () => {
    setBusy("analyse"); setErr(null);
    try {
      const r = await sendCommand(base, agent, "xfer", { action: "leftovers" });
      if (r?.error) throw new Error(r.error);
      const res = await waitCommand(base, r?.command?.id || r?.id, (s) => setBusy(`analyse ${s} s`));
      const ev = await evaluateLeftovers(base, { agent_id: agent, items: res.items || [] });
      if (ev?.error) throw new Error(ev.error);
      setItems(ev.items); setMeta({ dirs: res.dirs, pbs: ev.pbs_seen, vms: ev.local_vms });
    } catch (e) { setErr(e.message); }
    setBusy("");
  };
  const purge = async (list, force) => {
    const size = list.reduce((s, x) => s + (x.size || 0), 0);
    if (!window.confirm(`${force ? "FORCER la suppression" : "Supprimer"} sur ${agent} :\n${list.map((x) => `· ${x.path} (${fmtBytes(x.size)})${x.loop ? " — démontage " + x.loop.dev : ""}`).join("\n")}\n\n${fmtBytes(size)} libérés. Irréversible.\nMotif : ${reason}`)) return;
    setErr(null);
    for (const it of list) {
      setBusy(`suppression de ${it.path.split("/").pop()}`);
      try {
        const r = await purgeLeftover(base, { agent_id: agent, item: it, reason, force, actor: username });
        if (r?.error) throw new Error(r.error);
        const res = await waitCommand(base, r.command.id);
        setMsg((m) => [...m, `✓ ${res.message}`]);
      } catch (e) { setMsg((m) => [...m, `✗ ${it.path} : ${e.message}`]); }
    }
    setBusy(""); analyse();
  };
  const t = items ? leftoverTotals(items) : null;
  const okReason = reason.trim().length >= 8;

  return (
    <details className="infra-card" open={open} style={{ marginTop: 8 }}>
      <summary><b>Restes sur le nœud local</b> <span className="infra-muted">— archives gardées après restauration, exports interrompus, images brutes montées : vérifier puis libérer la place</span></summary>
      <div className="infra-top" style={{ flexWrap: "wrap", marginTop: 8 }}>
        <label>Nœud <select value={agent} onChange={(e) => { setAgent(e.target.value); setItems(null); }}>{(hosts || []).map((h) => <option key={h.agent_id} value={h.agent_id}>{h.node || h.hostname} ({h.agent_id})</option>)}</select></label>
        <button className="secondary" disabled={!agent || !!busy} onClick={analyse}>Analyser</button>
        <label>Motif <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="ex. copies 9101/9108 validées et sauvegardées" style={{ width: 320 }} /></label>
        {t && t.ready > 0 && <button className="primary" disabled={!okReason || !!busy} onClick={() => purge(items.filter((x) => x.ok), false)}>Supprimer les {t.ready} élément(s) prêts ({fmtBytes(t.readySize)})</button>}
        {busy && <span className="infra-muted">⏳ {busy}</span>}
        {err && <span className="infra-status critical">{err}</span>}{err && <JournalLinks agentId={agent} q="xfer" />}
      </div>
      {meta && <p className="infra-muted" style={{ fontSize: 12 }}>Dossiers examinés : {(meta.dirs || []).join(", ")} + images en boucle (losetup). {meta.vms} CT / VM sur ce nœud (sonde proxmox).{!meta.pbs && " Aucune sonde PBS : la condition « sauvegarde PBS » ne peut pas être remplie (forcer avec un motif)."}</p>}
      {items && (items.length ? <>
        <p>{t.count} élément(s), {fmtBytes(t.size)} — {t.ready} prêt(s) à supprimer ({fmtBytes(t.readySize)}).</p>
        <div className="infra-table-wrap infra-scroll"><table className="infra-table">
          <thead><tr><th>Élément</th><th>Taille</th><th>Date</th><th>Rôle</th><th>Conditions</th><th /></tr></thead>
          <tbody>{items.map((x) => <tr key={x.path}>
            <td><b>{x.label}</b><div style={{ fontFamily: "monospace", fontSize: 12, whiteSpace: "nowrap" }}>{x.path}</div>{x.loop?.mount && <div className="infra-muted">monté sur {x.loop.mount}</div>}</td>
            <td style={{ whiteSpace: "nowrap" }}>{fmtBytes(x.size)}</td><td style={{ whiteSpace: "nowrap" }}>{when(x.mtime)}</td><td>{x.role}</td>
            <td><ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 12 }}>{x.checks.map((k) => <li key={k.label}>
              <span className={`infra-dot ${k.ok ? "good" : k.required ? "critical" : ""}`}>{k.ok ? "●" : k.required ? "■" : "○"}</span> {k.label} <span className="infra-muted">— {k.detail}</span></li>)}</ul></td>
            <td>{x.ok
              ? <button className="primary" disabled={!okReason || !!busy} title={okReason ? "" : "motif requis"} onClick={() => purge([x], false)}>Supprimer</button>
              : <button className="secondary" disabled={!okReason || !!busy || !!x.in_use} title={x.in_use || "conditions non remplies : motif obligatoire"} onClick={() => purge([x], true)}>Forcer…</button>}</td>
          </tr>)}</tbody></table></div></> : <p className="infra-muted">Aucun reste sur ce nœud.</p>)}
      {msg.length > 0 && <ul style={{ fontSize: 12 }}>{msg.map((m, i) => <li key={i}>{m}</li>)}</ul>}
    </details>
  );
}
