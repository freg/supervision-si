// Logique pure de « Contrôle PVE » (#653) : opérations d'exploitation / PRA sur les hyperviseurs remontés par les agents.

export const OPS = {
  migrate: { label: "Migrer vers un nœud", fields: ["target", "online", "with_local_disks"] },
  backup: { label: "Sauvegarder (vzdump)", fields: ["storage", "mode"] },
  move_disk: { label: "Déplacer un disque", fields: ["disk", "storage"] },
  clone: { label: "Cloner", fields: ["newid", "name", "target", "storage"] },
  replicate: { label: "Répliquer vers un nœud (pvesr)", fields: ["target", "schedule"] },
  unreplicate: { label: "Retirer la réplication", fields: ["job"] },
  start: { label: "Démarrer", fields: [] }, shutdown: { label: "Arrêter (ACPI)", fields: [] }, stop: { label: "Couper", fields: [] }, reboot: { label: "Redémarrer", fields: [] },
  snapshot: { label: "Instantané", fields: ["snapname"] }, rollback: { label: "Revenir à l'instantané", fields: ["snapname"] },
  // #658 : migration vers la virtualisation (étapes générées, pas proposées sur une VM existante : plan = true)
  create: { label: "Créer la VM / le conteneur", fields: [], plan: true }, import_disk: { label: "Importer l'image comme disque", fields: [], plan: true },
  set: { label: "Modifier des options", fields: [], plan: true }, destroy: { label: "DÉTRUIRE", fields: [], plan: true },
  image_host: { label: "Image à chaud du serveur", fields: [], plan: true }, host_shutdown: { label: "Arrêt du serveur physique", fields: [], plan: true },
  checkpoint: { label: "Transition (attente de l'opérateur)", fields: [], plan: true },
};
export const VM_OPS = Object.fromEntries(Object.entries(OPS).filter(([, o]) => !o.plan));

// #658 : formulaire de migration -> corps de /pra/migrations/plan (champs vides retirés, nombres convertis).
export const MIGRATION_DEFAULTS = { method: "image", os: "linux", source_agent_id: "", pve_agent_id: "", vmid: "", storage: "", bridge: "vmbr0", memory: 4096, cores: 2, image_target: "", template: "", ip: "dhcp", role_id: "", role_from: 0, role_to: 1, purge_on_rollback: false, auto_rollback: false, plan_name: "" };
export function migrationBody(f) {
  const out = {};
  for (const [k, v] of Object.entries({ ...MIGRATION_DEFAULTS, ...f })) {
    if (v === "" || v === null || v === undefined) continue;
    if (["vmid", "memory", "cores", "role_id", "role_from", "role_to", "rootfs_gb"].includes(k)) out[k] = Number(v); else out[k] = v;
  }
  if (out.method === "rebuild") delete out.image_target; else { delete out.template; delete out.ip; }
  return out;
}
// Ce qui manque avant de demander l'aperçu (message) ou null.
export function migrationMissing(f) {
  if (!f.source_agent_id) return "serveur source (agent) à choisir";
  if (!f.pve_agent_id) return "nœud Proxmox cible à choisir";
  if (!f.vmid || Number(f.vmid) < 100) return "vmid ≥ 100 libre sur le nœud";
  if (!f.storage) return "stockage Proxmox cible";
  if (f.method === "image" && !f.image_target) return "dossier / partage où le serveur écrit son image (Windows : \\serveur\partage\dossier ; Linux : /mnt/images)";
  if (f.method === "rebuild" && !f.template) return "modèle de conteneur (ex. local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst)";
  return null;
}
// Boutons possibles sur une exécution : reprendre / abandonner (en pause ou en cours), retour (terminée, plan avec étapes de retour).
export function runActions(run, plan) {
  if (!run || run.mode === "simulate") return [];
  const out = [];
  if (run.status === "paused") out.push("resume");
  if (run.status === "paused" || run.status === "running") out.push("abort");
  if (["done", "failed"].includes(run.status) && (plan?.rollback_steps || []).length && run.mode !== "rollback") out.push("rollback");
  return out;
}
// Consigne de la transition en attente (checkpoint « waiting »), ou null.
export function waitingStep(run) {
  return (run?.steps || []).find((s) => s.status === "waiting") || null;
}
export const FIELD_LABELS = { target: "nœud cible", online: "à chaud", with_local_disks: "avec disques locaux", storage: "stockage", mode: "mode (snapshot/suspend/stop)",
  disk: "disque (scsi0, rootfs…)", newid: "nouvel identifiant", name: "nom", schedule: "planification (*/15, 2:00)", job: "n° de job", snapname: "nom de l'instantané" };

// Hyperviseurs et VM aplatis depuis GET /proxmox : [{agent_id, node, vms: [{vmid, name, type, status, node}], storages: [name]}]
export function flattenProxmox(data) {
  return (data || []).map((n) => {
    const repl = n.replication || [];
    return { agent_id: n.agent_id, node: (n.node || {}).name || n.hostname || n.agent_id, hostname: n.hostname,
      vms: (n.vms || []).filter((v) => !v.template).map((v) => ({ vmid: v.vmid, name: v.name, type: v.type || "qemu", status: v.status,
        replication: repl.filter((r) => r.vmid === v.vmid), last_backup: v.last_backup_run || null })),
      storages: (n.storages || []).map((s) => s.storage || s.name).filter(Boolean), replication: repl };
  });
}

// Résumé de réplication d'une VM : "→ pve10 ✔ il y a 12 min" / "→ pve10 ✘ 3 échecs".
export function replSummary(jobs) {
  if (!jobs || jobs.length === 0) return "";
  return jobs.map((j) => `→ ${j.target} ${j.disabled ? "(désactivée)" : j.ok ? "✔" : "✘"}${j.fail_count ? ` ${j.fail_count} échec(s)` : ""}${j.last_sync_age_s !== null && j.last_sync_age_s !== undefined ? ` il y a ${ageText(j.last_sync_age_s)}` : ""}`).join(" ; ");
}

export function ageText(s) {
  if (s < 90) return `${s} s`; if (s < 5400) return `${Math.round(s / 60)} min`; if (s < 172800) return `${Math.round(s / 3600)} h`; return `${Math.round(s / 86400)} j`;
}

export function roleStepText(s, roles) {
  const p = s.params || {}; const r = (roles || []).find((x) => x.id === p.role_id); const c = r && r.candidates[p.to];
  return `bascule du rôle ${r ? "« " + r.name + " »" : "n°" + p.role_id} → ${c ? c.label : "candidat " + p.to}`;
}

// Autres nœuds (cibles de migration/réplication) que celui de l'agent.
export function otherNodes(hosts, agentId) {
  return hosts.filter((h) => h.agent_id !== agentId).map((h) => h.node);
}

// Une étape de plan depuis le formulaire d'opération.
export function makeStep(host, vm, action, params, label) {
  const p = {};
  for (const f of OPS[action]?.fields || []) if (params[f] !== undefined && params[f] !== "") p[f] = params[f];
  if (action === "clone" && p.newid) p.newid = Number(p.newid);
  if (action === "unreplicate" && p.job !== undefined) p.job = Number(p.job);
  return { agent_id: host.agent_id, vmid: vm.vmid, kind: vm.type === "lxc" ? "lxc" : "qemu", action, params: p, label: label || `${vm.name || vm.vmid} : ${OPS[action]?.label || action}` };
}

// Résumé d'une exécution : "3/4 étapes, échec à l'étape 2 : …".
export function runSummary(run) {
  const st = run?.steps || []; const done = st.filter((s) => s.status === "done" || s.ok === true).length;
  const bad = st.find((s) => ["failed", "timeout"].includes(s.status) || s.ok === false);
  return `${done}/${st.length} étape(s)` + (bad ? ` — échec à l'étape ${bad.index}${bad.result?.error ? " : " + bad.result.error : bad.error ? " : " + bad.error : ""}` : "");
}

export function stepText(s, roles) {
  const p = s.params || {}; const a = p.action || s.action;
  if (a === "role_switch") return roleStepText(s, roles);
  if (a === "checkpoint" || s.command === "checkpoint") return `⏸ transition : ${s.label || "attente de l'opérateur"}`;
  if (s.command === "image_host" || a === "image_host") return `${s.agent_id} · image à chaud → ${p.target || ""} (transférée au central)`;
  if (s.command === "power_action" || a === "host_shutdown" || (a === "shutdown" && !p.vmid && !s.vmid)) return `${s.agent_id} · arrêt du serveur physique`;
  const extras = Object.entries(p).filter(([k]) => !["vmid", "action", "kind"].includes(k)).map(([k, v]) => `${k}=${v}`).join(" ");
  return `${s.agent_id} · VM ${p.vmid ?? s.vmid} · ${OPS[p.action || s.action]?.label || p.action || s.action}${extras ? " (" + extras + ")" : ""}`;
}
