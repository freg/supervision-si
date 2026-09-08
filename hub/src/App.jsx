import React, { Fragment, useEffect, useRef, useState } from "react";
import { useAuth } from "react-oidc-context";
import { buildFrontsList, formatUserRoles, isAdmin, isTechnicien, ROLE_LABELS } from "./lib.js";
import { createAccountThemeStore } from "./preferences.js";
import ReminderWidget from "./ReminderWidget.jsx";
import TabShell from "./TabShell.jsx";
import {
  fetchAppSettings, saveAppSettings, mergeTicketsAppSettings,
  fetchTechReminderPrefs, saveTechReminderPrefs, DEFAULT_TECH_REMINDER_PREFS,
  fetchChangelog, fetchBacklog,
  fetchDocsList, fetchDoc,
  fetchGovernanceDocuments, governanceDocumentDownloadUrl,
  fetchExternalLinks, createExternalLink, updateExternalLink, deleteExternalLink,
  provisionKeycloakClient, deprovisionKeycloakClient,
  fetchHubLayout, saveHubLayout,
  fetchInfraStatus,
} from "./settingsClient.js";
import { applyHubLayout } from "./hubLayoutLib.js";
import LogsManagerView from "./LogsManagerView.jsx";
import SchemaAnalyzerView from "./SchemaAnalyzerView.jsx";
import RetroView from "./RetroView.jsx";
import BackupRestoreView from "./BackupRestoreView.jsx";
import ArchitectureView from "./ArchitectureView.jsx";
import MemoryView from "./MemoryView.jsx";
import ClassifierView from "./ClassifierView.jsx";
import VigilanceView from "./VigilanceView.jsx";
import EntView from "./EntView.jsx";
import RightsView from "./RightsView.jsx";
import NetprobeView from "./NetprobeView.jsx";
import UpsView from "./UpsView.jsx";
import SiAgentView from "./SiAgentView.jsx";
import SiAgentEventsBanner from "./SiAgentEventsBanner.jsx";
import SupervisionSiView from "./SupervisionSiView.jsx";
import GedView from "./GedView.jsx";
import SshTunnelsView from "./SshTunnelsView.jsx";
import SnmpView from "./SnmpView.jsx";
import NetmapOrchestratorView from "./NetmapOrchestratorView.jsx";
import NebulaView from "./NebulaView.jsx";
import ImapView from "./ImapView.jsx";
import GlpiInventoryView from "./GlpiInventoryView.jsx";
import NetworkAgentView from "./NetworkAgentView.jsx";
import NetworkCycleView from "./NetworkCycleView.jsx";
import CyberView from "./CyberView.jsx";
import PersonalizeHomeView from "./PersonalizeHomeView.jsx";
import FileManagerView from "./FileManagerView.jsx";
import { logPresenceTransitions } from "./hubLogClient.js";
import { parseMarkdown } from "./markdown.js";
import versionInfo from "./VERSION.json";

const FRONTEND_URL = import.meta.env.VITE_SUPERVISION_FRONTEND_URL || "";
const PORTAL_URL = import.meta.env.VITE_TICKETS_PORTAL_URL || "";
const DBA_URL = import.meta.env.VITE_DBA_PORTAL_URL || "";
const LDAP_ADMIN_URL = import.meta.env.VITE_LDAP_ADMIN_PORTAL_URL || "";
const VAULT_URL = import.meta.env.VITE_VAULT_PORTAL_URL || "";
// Portail d'administration du coffre-fort (rôles) -- JAMAIS routé par
// la passerelle publique (voir vault-standalone/README.md/docker-
// compose.yml, service vault-admin-portal), adresse LAN directe
// contrairement à VAULT_URL ci-dessus. Ouvre dans un nouvel onglet
// comme les autres liens externes de ce hub, aucune intégration
// particulière nécessaire.
const VAULT_ADMIN_URL = import.meta.env.VITE_VAULT_ADMIN_PORTAL_URL || "";
const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL || "";
const KEYCLOAK_REALM = import.meta.env.VITE_KEYCLOAK_REALM || "supervision-si";
const PREFS_API_BASE_URL = import.meta.env.VITE_PREFS_API_BASE_URL || "";
const TICKETS_API_BASE_URL = import.meta.env.VITE_TICKETS_API_BASE_URL || "";
// Analyse de schémas (livraison #156) -- DBA_API_BASE_URL en LECTURE
// SEULE ici (juste lister les connexions existantes pour le
// sélecteur, voir SchemaAnalyzerView.jsx), jamais un CRUD complet
// dans le hub -- ça reste le rôle de l'onglet DBA (portail séparé).
const DBA_API_BASE_URL = import.meta.env.VITE_DBA_API_BASE_URL || "";
const SCHEMA_ANALYZER_API_BASE_URL = import.meta.env.VITE_SCHEMA_ANALYZER_API_BASE_URL || "";
const RETRO_API_BASE_URL = import.meta.env.VITE_RETRO_API_BASE_URL || "";
const BACKUP_RESTORE_API_BASE_URL = import.meta.env.VITE_BACKUP_RESTORE_API_BASE_URL || "";
const ARCHITECTURE_API_BASE_URL = import.meta.env.VITE_ARCHITECTURE_API_BASE_URL || "";
const MEMORY_API_BASE_URL = import.meta.env.VITE_MEMORY_API_BASE_URL || "";
const CLASSIFIER_API_BASE_URL = import.meta.env.VITE_CLASSIFIER_API_BASE_URL || "";
const VIGILANCE_API_BASE_URL = import.meta.env.VITE_VIGILANCE_API_BASE_URL || "";
const TASKS_API_BASE_URL = import.meta.env.VITE_TASKS_API_BASE_URL || "";
const RIGHTS_API_BASE_URL = import.meta.env.VITE_RIGHTS_API_BASE_URL || "";
const NETPROBE_API_BASE_URL = import.meta.env.VITE_NETPROBE_API_BASE_URL || "";
// Tuile UPS (livraison #415) -- ups-monitor-api.
const UPS_API_BASE_URL = import.meta.env.VITE_UPS_API_BASE_URL || "";
// Tuile Agents hôtes (livraison #421, backlog 63) -- si-agent-api.
const SI_AGENT_API_BASE_URL = import.meta.env.VITE_SI_AGENT_API_BASE_URL || "";
// Géolocalisations (pixel-grid) -- positions connues pour la nouvelle tuile
// Supervision SI (livraison #423, backlog 64).
const PIXEL_GRID_API_BASE_URL = import.meta.env.VITE_PIXEL_GRID_API_BASE_URL || "";
const RELATIONS_API_BASE_URL = import.meta.env.VITE_RELATIONS_API_BASE_URL || "";
// Onglet GED (livraison #167) -- même API que TicketDocuments.jsx
// (tickets-portal, #160), consommée ici pour la navigation/gestion
// générale des documents, pas limitée à un ticket en particulier.
const GED_API_BASE_URL = import.meta.env.VITE_GED_API_BASE_URL || "";
// Sous-onglets "OwnCloud"/"Recherche" de la tuile GED (livraison
// #354) -- dépôt EXTERNE lecture seule, distinct de GED_API_BASE_URL
// ci-dessus (dépôt interne, Mayan).
const OWNCLOUD_API_BASE_URL = import.meta.env.VITE_OWNCLOUD_API_BASE_URL || "";
const OWNCLOUD_SEARCH_API_BASE_URL = import.meta.env.VITE_OWNCLOUD_SEARCH_API_BASE_URL || "";
// Gestionnaire de fichiers (livraison #396, backlog item 26) -- agrège
// GED, montages SSHFS, et espace protégé du hub.
const FILE_MANAGER_API_BASE_URL = import.meta.env.VITE_FILE_MANAGER_API_BASE_URL || "";
// Onglet ssh-tunnels (livraison #175) -- backend #159.
const SSH_TUNNELS_API_BASE_URL = import.meta.env.VITE_SSH_TUNNELS_API_BASE_URL || "";
const SNMP_API_BASE_URL = import.meta.env.VITE_SNMP_API_BASE_URL || "";
const NETMAP_ORCHESTRATOR_API_BASE_URL = import.meta.env.VITE_NETMAP_ORCHESTRATOR_API_BASE_URL || "";
const NEBULA_API_BASE_URL = import.meta.env.VITE_NEBULA_API_BASE_URL || "";
const IMAP_CLIENT_API_BASE_URL = import.meta.env.VITE_IMAP_CLIENT_API_BASE_URL || "";
const GLPI_API_BASE_URL = import.meta.env.VITE_GLPI_API_BASE_URL || "";
const NETWORK_AGENT_API_BASE_URL = import.meta.env.VITE_NETWORK_AGENT_API_BASE_URL || "";
// Console SCOPÉE au realm supervision-si, pas la console master --
// voir hub/README.md : avoir le rôle applicatif "admin" dans ce realm
// ne donne pas automatiquement de droits Keycloak plateforme.
const KEYCLOAK_CONSOLE_URL = KEYCLOAK_URL ? `${KEYCLOAK_URL}/admin/${KEYCLOAK_REALM}/console/` : "";
// Émetteur (issuer) OIDC public -- même formule qu'authConfig.js
// (authority) -- affiché à l'admin après provisionnement d'un client
// Keycloak pour un lien externe (backlog "interface d'intégration
// Keycloak", livraison #124) : c'est CETTE valeur que l'appli externe
// doit configurer comme émetteur, jamais une adresse interne au
// réseau Docker.
const KEYCLOAK_ISSUER = KEYCLOAK_URL ? `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}` : "";

// Une seule instance du store pour toute la durée de vie de l'appli
// (pas recréée à chaque rendu) -- voir shared/preferences.js. Thème
// lié au compte Keycloak (hub = un des deux seuls fronts qui
// connaissent une identité aujourd'hui, avec le portail tickets).
const themeStore = createAccountThemeStore({ apiBase: PREFS_API_BASE_URL });

// Visibilité de la note de pied de page (écran d'accueil) --
// personnalisation de l'accueil, étape 1 (livraison #132), demandée
// explicitement ("masquable"). Même principe/même appareil que les
// clés déjà utilisées côté TabShell.jsx (timeline, onglets ouverts) --
// pas un réglage de compte à synchroniser entre appareils. Visible
// par défaut (comportement inchangé tant que la personne n'a jamais
// touché au bouton).
const FOOTER_NOTE_VISIBLE_STORAGE_KEY = "supervision-si:hub:footer-note-visible";

function loadStoredFooterNoteVisible() {
  try {
    const raw = localStorage.getItem(FOOTER_NOTE_VISIBLE_STORAGE_KEY);
    if (raw === null) return true;
    return JSON.parse(raw) === true;
  } catch {
    return true;
  }
}

// Page de paramètres -- demandée explicitement : section "Général"
// (paramétrage global par application, admin uniquement) et section
// "Mes préférences" (personnel, tout le monde). Fondation prévue pour
// accueillir d'autres applications/préférences plus tard -- premier
// cas d'usage concret : le rappel d'activité technicien.
function SettingsView({ groups, login, apiBase, onBack }) {
  const isAdminUser = isAdmin(groups);
  const isTech = isTechnicien(groups);

  const [appSettings, setAppSettings] = useState(mergeTicketsAppSettings(null));
  // Chargé pour les admins (édition) ET les techniciens (référence
  // affichée comme repère dans leurs préférences personnelles) --
  // bug réel trouvé en relisant : limité aux seuls admins au premier
  // jet, un technicien non-admin aurait alors vu un repère figé sur
  // la valeur par défaut du code (30 min), jamais la vraie valeur
  // configurée par l'admin.
  const [appSettingsLoading, setAppSettingsLoading] = useState(isAdminUser || isTech);
  const [appSettingsSaving, setAppSettingsSaving] = useState(false);
  const [appSettingsSaved, setAppSettingsSaved] = useState(false);

  const [personalPrefs, setPersonalPrefs] = useState(DEFAULT_TECH_REMINDER_PREFS);
  const [personalPrefsLoading, setPersonalPrefsLoading] = useState(isTech);
  const [personalSaving, setPersonalSaving] = useState(false);
  const [personalSaved, setPersonalSaved] = useState(false);

  useEffect(() => {
    if (!isAdminUser && !isTech) return;
    fetchAppSettings(apiBase, "tickets").then((data) => {
      setAppSettings(mergeTicketsAppSettings(data));
      setAppSettingsLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdminUser, isTech]);

  useEffect(() => {
    if (!isTech) return;
    fetchTechReminderPrefs(apiBase, login).then((data) => {
      setPersonalPrefs({ ...DEFAULT_TECH_REMINDER_PREFS, ...data });
      setPersonalPrefsLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isTech, login]);

  const handleSaveAppSettings = async () => {
    setAppSettingsSaving(true);
    await saveAppSettings(apiBase, "tickets", appSettings, login);
    setAppSettingsSaving(false);
    setAppSettingsSaved(true);
    setTimeout(() => setAppSettingsSaved(false), 2000);
  };

  const handleSavePersonalPrefs = async () => {
    setPersonalSaving(true);
    await saveTechReminderPrefs(apiBase, login, personalPrefs);
    setPersonalSaving(false);
    setPersonalSaved(true);
    setTimeout(() => setPersonalSaved(false), 2000);
  };

  return (
    <div className="hub-settings">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>⚙️ Paramètres</h1>
      </div>

      <div className="hub-settings-grid">
      {isAdminUser && (
        <div className="hub-card hub-settings-section">
          <h2>🌐 Général</h2>
          <h3>Rappel d'activité (tickets)</h3>
          <p className="muted">
            Valeurs par défaut pour tous les techniciens -- chacun peut ensuite les
            personnaliser dans sa propre section "Mes préférences".
          </p>
          {appSettingsLoading ? (
            <p className="muted">Chargement…</p>
          ) : (
            <>
              <div className="hub-settings-row">
                <label>Message (activité en cours)</label>
                <input
                  value={appSettings.message_state}
                  onChange={(e) => setAppSettings({ ...appSettings, message_state: e.target.value })}
                />
              </div>
              <div className="hub-settings-row">
                <label>Message (demande d'activité)</label>
                <input
                  value={appSettings.message_ask}
                  onChange={(e) => setAppSettings({ ...appSettings, message_ask: e.target.value })}
                />
              </div>
              <div className="hub-settings-row">
                <label>Fréquence du rappel (minutes)</label>
                <input
                  type="number"
                  min="1"
                  value={appSettings.frequency_minutes}
                  onChange={(e) => setAppSettings({ ...appSettings, frequency_minutes: Number(e.target.value) || 1 })}
                />
              </div>
              <div className="hub-settings-row">
                <label>Durée d'affichage avant fermeture auto (secondes)</label>
                <input
                  type="number"
                  min="5"
                  value={appSettings.popup_duration_seconds}
                  onChange={(e) => setAppSettings({ ...appSettings, popup_duration_seconds: Number(e.target.value) || 5 })}
                />
              </div>

              <h3>Import des demandeurs</h3>
              <p className="muted">
                Groupe Keycloak LOCAL complémentaire à "demandeurs" (LDAP) -- ses membres
                sont importés en plus lors d'un import, jamais à la place. Laisser vide pour
                n'importer que "demandeurs" comme avant.
              </p>
              <div className="hub-settings-row">
                <label>Nom du groupe local (vide = aucun)</label>
                <input
                  value={appSettings.local_requester_group}
                  onChange={(e) => setAppSettings({ ...appSettings, local_requester_group: e.target.value })}
                  placeholder="ex. demandeurs-locaux"
                />
              </div>

              <button className="primary" onClick={handleSaveAppSettings} disabled={appSettingsSaving}>
                {appSettingsSaving ? "…" : appSettingsSaved ? "✓ Enregistré" : "Enregistrer"}
              </button>
            </>
          )}
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <h2>👤 Mes préférences</h2>
        {!isTech && (
          <p className="muted">Aucune préférence personnalisable pour votre profil pour l'instant.</p>
        )}
        {isTech && personalPrefsLoading && <p className="muted">Chargement…</p>}
        {isTech && !personalPrefsLoading && (
          <>
            <h3>Rappel d'activité</h3>
            <div className="hub-settings-row">
              <label>
                <input
                  type="checkbox"
                  checked={personalPrefs.enabled}
                  onChange={(e) => setPersonalPrefs({ ...personalPrefs, enabled: e.target.checked })}
                />{" "}
                Activer le rappel d'activité
              </label>
            </div>
            <div className="hub-settings-row">
              <label>Fréquence personnalisée (minutes, vide = valeur par défaut)</label>
              <input
                type="number"
                min="1"
                placeholder={String(appSettings.frequency_minutes)}
                value={personalPrefs.frequency_minutes_override ?? ""}
                onChange={(e) => setPersonalPrefs({
                  ...personalPrefs,
                  frequency_minutes_override: e.target.value ? Number(e.target.value) : null,
                })}
              />
            </div>
            <div className="hub-settings-row">
              <label>Durée d'affichage personnalisée (secondes, vide = valeur par défaut)</label>
              <input
                type="number"
                min="5"
                placeholder={String(appSettings.popup_duration_seconds)}
                value={personalPrefs.popup_duration_seconds_override ?? ""}
                onChange={(e) => setPersonalPrefs({
                  ...personalPrefs,
                  popup_duration_seconds_override: e.target.value ? Number(e.target.value) : null,
                })}
              />
            </div>
            <button className="primary" onClick={handleSavePersonalPrefs} disabled={personalSaving}>
              {personalSaving ? "…" : personalSaved ? "✓ Enregistré" : "Enregistrer"}
            </button>
          </>
        )}
      </div>
      </div>
    </div>
  );
}

// Rendu d'un document markdown déjà parsé en blocs (voir markdown.js)
// -- h1 markdown décalé en h2 visuel (h1 réservé au titre de la page
// elle-même), etc., jamais deux h1 sur la même page.
function InlineSegment({ segment, keyPrefix }) {
  if (segment.type === "bold") return <strong key={keyPrefix}>{segment.content}</strong>;
  if (segment.type === "code") return <code key={keyPrefix}>{segment.content}</code>;
  return segment.content;
}

function MarkdownDocument({ blocks }) {
  return (
    <div className="hub-markdown">
      {blocks.map((block, i) => {
        if (block.type === "heading") {
          const Tag = `h${Math.min(block.level + 1, 6)}`;
          return <Tag key={i}>{block.inline.map((s, j) => <InlineSegment key={j} segment={s} keyPrefix={j} />)}</Tag>;
        }
        if (block.type === "list") {
          return (
            <ul key={i}>
              {block.items.map((item, j) => (
                <li key={j}>{item.map((s, k) => <InlineSegment key={k} segment={s} keyPrefix={k} />)}</li>
              ))}
            </ul>
          );
        }
        return <p key={i}>{block.inline.map((s, j) => <InlineSegment key={j} segment={s} keyPrefix={j} />)}</p>;
      })}
    </div>
  );
}

// Vue "historique des évolutions" + "backlog" -- demandé
// explicitement, sert CHANGELOG.md/BACKLOG.md tels qu'ils sont
// réellement (jamais une copie figée), avec un rendu markdown de
// base (titres/gras/code/listes -- voir markdown.js).
function HistoryView({ apiBase, onBack }) {
  const [subTab, setSubTab] = useState("changelog");
  const [changelogBlocks, setChangelogBlocks] = useState(null);
  const [backlogBlocks, setBacklogBlocks] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const load = subTab === "changelog" ? fetchChangelog : fetchBacklog;
    const setBlocks = subTab === "changelog" ? setChangelogBlocks : setBacklogBlocks;
    load(apiBase).then((res) => {
      setLoading(false);
      if (res.ok) setBlocks(parseMarkdown(res.content));
      else setError(res.error);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subTab]);

  const blocks = subTab === "changelog" ? changelogBlocks : backlogBlocks;

  return (
    <div className="hub-settings">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>📜 Historique du projet</h1>
      </div>

      <div className="tabs" style={{ marginBottom: 16 }}>
        <button className={subTab === "changelog" ? "active" : ""} onClick={() => setSubTab("changelog")}>
          Historique des évolutions
        </button>
        <button className={subTab === "backlog" ? "active" : ""} onClick={() => setSubTab("backlog")}>
          Backlog
        </button>
      </div>

      <div className="hub-settings-grid">
      <div className="hub-card hub-settings-section">
        {loading && <p className="muted">Chargement…</p>}
        {error && <p className="hub-error">{error}</p>}
        {!loading && !error && blocks && <MarkdownDocument blocks={blocks} />}
      </div>
      </div>
    </div>
  );
}

// Aide du hub -- livraison #143, demandé explicitement ("une aide qui
// s'enrichit des readme et des exemples"). "S'enrichit" au sens
// littéral : la liste vient de prefs-api (/docs), qui découvre EN
// DIRECT les README.md du dépôt à chaque appel -- un nouveau document
// ajouté n'importe où apparaît ici sans le moindre code à modifier.
// Les exemples (commandes, extraits JSON...) sont déjà abondamment
// présents DANS les README existants -- les afficher couvre les deux
// demandes à la fois, pas de base d'exemples séparée à maintenir.
function docLabel(path) {
  if (path === "README.md") return "Racine du projet";
  return path.replace(/\/README\.md$/, "");
}

function AideView({ apiBase, onBack }) {
  const [docs, setDocs] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [blocks, setBlocks] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [governanceDocs, setGovernanceDocs] = useState([]);

  // Liste chargée une fois à l'ouverture -- pas de sondage
  // périodique, une nouvelle documentation apparaît au rythme des
  // livraisons, jamais en temps réel pendant qu'on lit.
  useEffect(() => {
    fetchDocsList(apiBase).then((list) => {
      setDocs(list);
      setSelectedDoc((current) => current || (list.includes("README.md") ? "README.md" : list[0]));
    });
    // Documents de gouvernance VERSIONNÉS (livraison #195) -- liste
    // séparée, chargée en parallèle, jamais mélangée à la liste des
    // README.md ci-dessus (fichiers binaires à télécharger, pas du
    // markdown à afficher en ligne).
    fetchGovernanceDocuments(apiBase).then(setGovernanceDocs);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedDoc) return;
    setLoading(true);
    setError(null);
    fetchDoc(apiBase, selectedDoc).then((res) => {
      setLoading(false);
      if (res.ok) setBlocks(parseMarkdown(res.content));
      else setError(res.error);
    });
  }, [selectedDoc, apiBase]);

  const filterLower = filter.trim().toLowerCase();
  const filteredDocs = filterLower ? docs.filter((d) => docLabel(d).toLowerCase().includes(filterLower)) : docs;

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>❓ Aide</h1>
      </div>

      {governanceDocs.length > 0 && (
        <div className="hub-card" style={{ marginBottom: 16, padding: 12 }}>
          <h3 style={{ marginTop: 0 }}>📄 Documents officiels</h3>
          <ul style={{ marginBottom: 0 }}>
            {governanceDocs.map((d) => (
              <li key={d.id} style={{ marginBottom: 6 }}>
                <a href={governanceDocumentDownloadUrl(apiBase, d.id)} target="_blank" rel="noreferrer">{d.name}</a>
                <span className="muted"> — version {d.version} · mis à jour le {(d.updated_at || "").slice(0, 10)}</span>
                {d.description && <p className="muted" style={{ margin: "2px 0 0" }}>{d.description}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="aide-layout">
        <div className="aide-sidebar">
          <input
            className="aide-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filtrer…"
          />
          {docs.length === 0 && <p className="muted">Aucune documentation découverte.</p>}
          {docs.length > 0 && filteredDocs.length === 0 && <p className="muted">Aucun résultat.</p>}
          <ul className="aide-doc-list">
            {filteredDocs.map((d) => (
              <li key={d}>
                <button className={d === selectedDoc ? "active" : ""} onClick={() => setSelectedDoc(d)}>
                  {docLabel(d)}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="hub-card hub-settings-section aide-content">
          {loading && <p className="muted">Chargement…</p>}
          {error && <p className="hub-error">{error}</p>}
          {!loading && !error && blocks && <MarkdownDocument blocks={blocks} />}
        </div>
      </div>
    </div>
  );
}

// Rôles applicatifs proposés dans le formulaire -- dérivés de
// ROLE_LABELS (lib.js) plutôt qu'une liste dupliquée, jamais laissée
// diverger de ce que le reste du hub connaît déjà.
const EXTERNAL_LINK_ROLES = Object.keys(ROLE_LABELS);

// Administration des liens externes -- backlog, livraison #121. Scope
// volontairement simple (décidé avec la personne) : une liste d'URI
// ajoutées par les administrateurs, avec une visibilité par rôle --
// PAS de pont d'authentification/SSO (voir BACKLOG.md #3 pour la
// piste envisagée plus tard). Chaque lien reste un lien externe
// CLASSIQUE (nouvel onglet), sauf "Intégrer en onglet" coché
// explicitement -- l'appli visée doit alors accepter d'être embarquée
// en iframe (X-Frame-Options/CSP), vérifié par l'admin lui-même,
// jamais par ce formulaire.
function ExternalLinksAdminView({ apiBase, login, links, onLinksChanged, onBack }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null); // null = nouveau lien
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formEmbeddable, setFormEmbeddable] = useState(false);
  const [formRoles, setFormRoles] = useState([]);
  const [saving, setSaving] = useState(false);

  // Intégration Keycloak par lien (backlog, livraison #124) --
  // panneau dépliable, un seul ouvert à la fois (même motif que
  // ObservationsScreen.jsx), réinitialisé à chaque dépli/repli.
  const [keycloakExpandedId, setKeycloakExpandedId] = useState(null);
  const [keycloakRedirectUri, setKeycloakRedirectUri] = useState("");
  const [keycloakClientIdOverride, setKeycloakClientIdOverride] = useState("");
  const [keycloakBusy, setKeycloakBusy] = useState(false);
  const [keycloakError, setKeycloakError] = useState(null);
  // Conflit adoptable (livraison #125) -- un client Keycloak existe
  // déjà sous cet identifiant (ex. trb140-sms-relay, provisionné à la
  // main en #123) : { redirectUris } le temps que l'admin choisisse
  // d'adopter, ou change d'identifiant.
  const [keycloakConflict, setKeycloakConflict] = useState(null);

  // `links` vient du parent (App.jsx, déjà chargé pour buildFrontsList)
  // -- pas de fetch séparé ici, juste un indicateur de premier
  // chargement (le parent envoie [] avant la 1ère réponse, jamais
  // distinguable de "vraiment aucun lien" sans ce indicateur local).
  useEffect(() => {
    setLoading(false);
  }, [links]);

  function resetForm() {
    setEditingId(null);
    setFormName("");
    setFormUrl("");
    setFormDescription("");
    setFormEmbeddable(false);
    setFormRoles([]);
    setError(null);
  }

  function startEdit(link) {
    setEditingId(link.id);
    setFormName(link.name);
    setFormUrl(link.url);
    setFormDescription(link.description || "");
    setFormEmbeddable(!!link.embeddable);
    setFormRoles(Array.isArray(link.allowed_roles) ? link.allowed_roles : []);
    setError(null);
    setShowForm(true);
  }

  function toggleFormRole(role) {
    setFormRoles((prev) => (prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]));
  }

  const handleSave = async () => {
    if (!formName.trim() || !formUrl.trim()) return;
    setSaving(true);
    setError(null);
    const payload = {
      name: formName.trim(),
      url: formUrl.trim(),
      description: formDescription.trim() || null,
      embeddable: formEmbeddable,
      allowed_roles: formRoles,
      actor: login,
    };
    const res = editingId
      ? await updateExternalLink(apiBase, editingId, payload)
      : await createExternalLink(apiBase, payload);
    setSaving(false);
    if (res.ok) {
      resetForm();
      setShowForm(false);
      onLinksChanged();
    } else {
      setError(res.error);
    }
  };

  const handleDelete = async (link) => {
    if (!window.confirm(`Supprimer le lien "${link.name}" ?`)) return;
    await deleteExternalLink(apiBase, link.id);
    onLinksChanged();
  };

  // Réduit un texte libre à un aperçu d'identifiant Keycloak --
  // PUREMENT indicatif (placeholder de l'input), le slugify qui fait
  // foi reste côté serveur (prefs-api/app.py, slugify()) -- jamais
  // les deux implémentations à synchroniser pour rester correctes,
  // celle-ci n'a qu'à donner une idée juste à l'admin.
  function slugifyPreview(text) {
    const slug = (text || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return slug || "app";
  }

  function toggleKeycloakPanel(link) {
    setKeycloakError(null);
    setKeycloakConflict(null);
    if (keycloakExpandedId === link.id) {
      setKeycloakExpandedId(null);
      return;
    }
    setKeycloakExpandedId(link.id);
    // Pré-remplit avec l'URI déjà utilisée si un client existe déjà
    // (redémarrer une intégration retirée), sinon un point de départ
    // raisonnable dérivé de l'URL du lien -- l'admin ajuste si besoin
    // (voir trb140-sms-relay, qui demandait précisément /auth/callback,
    // jamais un chemin générique deviné à sa place).
    setKeycloakRedirectUri(link.keycloak_redirect_uri || `${link.url.replace(/\/$/, "")}/auth/callback`);
    setKeycloakClientIdOverride("");
  }

  const handleProvisionKeycloak = async (link) => {
    if (!keycloakRedirectUri.trim()) return;
    setKeycloakBusy(true);
    setKeycloakError(null);
    setKeycloakConflict(null);
    const res = await provisionKeycloakClient(apiBase, link.id, keycloakRedirectUri.trim(), keycloakClientIdOverride.trim());
    setKeycloakBusy(false);
    if (res.ok) {
      onLinksChanged();
    } else if (res.existingClient) {
      // Collision adoptable (livraison #125) -- pas forcément une
      // erreur bloquante, l'admin peut vouloir rattacher ce lien au
      // client déjà existant (ex. identifiant fixé côté appli
      // externe, cas trb140-sms-relay) plutôt que renommer.
      setKeycloakConflict({ redirectUris: res.existingRedirectUris });
    } else {
      setKeycloakError(res.error);
    }
  };

  const handleAdoptKeycloak = async (link) => {
    setKeycloakBusy(true);
    setKeycloakError(null);
    const res = await provisionKeycloakClient(apiBase, link.id, keycloakRedirectUri.trim(), keycloakClientIdOverride.trim(), true);
    setKeycloakBusy(false);
    if (res.ok) {
      setKeycloakConflict(null);
      onLinksChanged();
    } else {
      setKeycloakError(res.error);
    }
  };

  const handleDeprovisionKeycloak = async (link) => {
    if (!window.confirm(`Retirer l'intégration Keycloak de "${link.name}" ? Le lien restera, mais sans SSO.`)) return;
    setKeycloakBusy(true);
    setKeycloakError(null);
    const res = await deprovisionKeycloakClient(apiBase, link.id);
    setKeycloakBusy(false);
    if (res.ok) {
      setKeycloakExpandedId(null);
      onLinksChanged();
    } else {
      setKeycloakError(res.error);
    }
  };

  return (
    <div className="hub-settings">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🔗 Liens externes</h1>
      </div>

      <div className="hub-settings-grid">
        <div className="hub-card hub-settings-section">
          <div className="hub-settings-section-header-row">
            <h2>Applications externes</h2>
            <button
              className="secondary"
              onClick={() => { if (showForm) resetForm(); setShowForm((v) => !v); }}
            >
              {showForm ? "✕ Annuler" : "+ Ajouter"}
            </button>
          </div>
          <p className="muted">
            Liens simples (nouvel onglet du navigateur) présentés dans le hub selon les rôles
            cochés ci-dessous -- aucune connexion automatique n'est faite, chaque application
            garde son propre écran de connexion.
          </p>

          {showForm && (
            <div className="hub-external-links-form">
              <div className="hub-settings-row">
                <label>Nom</label>
                <input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="ex. GLPI" />
              </div>
              <div className="hub-settings-row">
                <label>URL</label>
                <input value={formUrl} onChange={(e) => setFormUrl(e.target.value)} placeholder="https://…" />
              </div>
              <div className="hub-settings-row">
                <label>Description (optionnel)</label>
                <input value={formDescription} onChange={(e) => setFormDescription(e.target.value)} />
              </div>
              <div className="hub-settings-row">
                <label>
                  <input
                    type="checkbox"
                    checked={formEmbeddable}
                    onChange={(e) => setFormEmbeddable(e.target.checked)}
                  />
                  {" "}Intégrer en onglet (l'appli doit accepter d'être affichée en iframe)
                </label>
              </div>
              <div className="hub-settings-row">
                <label>Visible par (aucune case cochée = tout le monde)</label>
                <div className="hub-external-links-roles">
                  {EXTERNAL_LINK_ROLES.map((role) => (
                    <label key={role} className="hub-external-links-role-checkbox">
                      <input
                        type="checkbox"
                        checked={formRoles.includes(role)}
                        onChange={() => toggleFormRole(role)}
                      />
                      {ROLE_LABELS[role]}
                    </label>
                  ))}
                </div>
              </div>
              {error && <p className="hub-error">{error}</p>}
              <button
                className="primary"
                onClick={handleSave}
                disabled={saving || !formName.trim() || !formUrl.trim()}
              >
                {saving ? "…" : editingId ? "✓ Enregistrer" : "➕ Créer"}
              </button>
            </div>
          )}

          {loading && <p className="muted">Chargement…</p>}
          {!loading && links.length === 0 && <p className="muted">Aucun lien externe pour l'instant.</p>}
          {!loading && links.length > 0 && (
            <table className="hub-external-links-table">
              <thead>
                <tr>
                  <th>Nom</th><th>URL</th><th>Visible par</th><th>Intégré</th><th>Keycloak</th><th></th>
                </tr>
              </thead>
              <tbody>
                {links.map((link) => (
                  <Fragment key={link.id}>
                  <tr>
                    <td>{link.name}</td>
                    <td className="muted">{link.url}</td>
                    <td className="muted">
                      {Array.isArray(link.allowed_roles) && link.allowed_roles.length > 0
                        ? link.allowed_roles.map((r) => ROLE_LABELS[r] || r).join(", ")
                        : "Tout le monde"}
                    </td>
                    <td>{link.embeddable ? "Oui" : "Non"}</td>
                    <td>
                      {link.keycloak_client_id
                        ? <span title={`client_id : ${link.keycloak_client_id}`}>✅ SSO</span>
                        : <span className="muted">—</span>}
                    </td>
                    <td className="hub-external-links-actions">
                      <button className="secondary" onClick={() => startEdit(link)} title="Modifier">✏️</button>
                      <button className="secondary" onClick={() => toggleKeycloakPanel(link)} title="Intégration Keycloak">🔑</button>
                      <button className="secondary" onClick={() => handleDelete(link)} title="Supprimer">🗑️</button>
                    </td>
                  </tr>
                  {keycloakExpandedId === link.id && (
                    <tr className="hub-external-links-kc-detail-row">
                      <td colSpan={6}>
                        {!link.keycloak_client_id ? (
                          <div className="hub-external-links-kc-panel">
                            <p className="muted">
                              Crée un client OIDC public (Authorization Code + PKCE) pour cette
                              application -- elle doit savoir parler OIDC nativement. Les rôles
                              applicatifs propres à cette appli (pas ceux du hub) restent un
                              ajout manuel côté Keycloak pour l'instant, voir keycloak/README.md.
                            </p>
                            <div className="hub-settings-row">
                              <label>URI de redirection (exacte, demandée par l'application)</label>
                              <input
                                value={keycloakRedirectUri}
                                onChange={(e) => setKeycloakRedirectUri(e.target.value)}
                                placeholder="https://…/auth/callback"
                              />
                            </div>
                            <div className="hub-settings-row">
                              <label>Identifiant du client (optionnel -- dérivé du nom sinon)</label>
                              <input
                                value={keycloakClientIdOverride}
                                onChange={(e) => { setKeycloakClientIdOverride(e.target.value); setKeycloakConflict(null); }}
                                placeholder={slugifyPreview(link.name)}
                              />
                            </div>
                            {keycloakConflict && (
                              <div className="hub-external-links-kc-conflict">
                                <p>
                                  Un client Keycloak <code>{keycloakClientIdOverride.trim() || slugifyPreview(link.name)}</code> existe
                                  déjà{keycloakConflict.redirectUris.length > 0 && (
                                    <> — URI de redirection actuelle : <code>{keycloakConflict.redirectUris.join(", ")}</code></>
                                  )}. Identifiant déjà fixé côté application externe (ex. une appli déjà
                                  provisionnée à la main) ? Rattachez ce lien au client existant plutôt que
                                  d'en créer un nouveau -- la configuration réelle sera reprise telle quelle.
                                </p>
                                <button
                                  className="secondary"
                                  onClick={() => handleAdoptKeycloak(link)}
                                  disabled={keycloakBusy}
                                >
                                  {keycloakBusy ? "…" : "Adopter ce client existant"}
                                </button>
                              </div>
                            )}
                            {keycloakError && <p className="hub-error">{keycloakError}</p>}
                            <button
                              className="primary"
                              onClick={() => handleProvisionKeycloak(link)}
                              disabled={keycloakBusy || !keycloakRedirectUri.trim() || !!keycloakConflict}
                            >
                              {keycloakBusy ? "…" : "🔑 Activer SSO Keycloak"}
                            </button>
                          </div>
                        ) : (
                          <div className="hub-external-links-kc-panel">
                            <p><strong>Client Keycloak actif</strong> -- valeurs à transmettre à la configuration OIDC de l'application externe :</p>
                            <p className="hub-external-links-kc-field">
                              <span className="muted">Émetteur (issuer)</span>
                              <code>{KEYCLOAK_ISSUER || "—"}</code>
                            </p>
                            <p className="hub-external-links-kc-field">
                              <span className="muted">Identifiant du client</span>
                              <code>{link.keycloak_client_id}</code>
                            </p>
                            <p className="hub-external-links-kc-field">
                              <span className="muted">URI de redirection</span>
                              <code>{link.keycloak_redirect_uri}</code>
                            </p>
                            {keycloakError && <p className="hub-error">{keycloakError}</p>}
                            <button
                              className="secondary"
                              onClick={() => handleDeprovisionKeycloak(link)}
                              disabled={keycloakBusy}
                            >
                              {keycloakBusy ? "…" : "Retirer l'intégration Keycloak"}
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const auth = useAuth();
  const [showDebug, setShowDebug] = useState(false);
  // Menu de navigation regroupé (livraison #236, réorganisation de
  // l'en-tête demandée explicitement -- "trop d'outils maintenant")
  // -- UN SEUL état pour les QUATRE menus déroulants (Général/Réseau/
  // Data/Paramètres), jamais plusieurs ouverts en même temps (ouvrir
  // l'un ferme automatiquement les autres, simple comparaison de
  // chaîne plutôt que quatre booléens indépendants à resynchroniser
  // à la main). `null` = tout fermé. Remplace `showSettingsMenu`
  // (livraison #173) -- même mécanique, juste généralisée aux trois
  // nouveaux menus plutôt que dupliquée quatre fois.
  const [openNavMenu, setOpenNavMenu] = useState(null);
  // Personnalisation de l'accueil, étape 1 (livraison #132).
  const [showFooterNote, setShowFooterNote] = useState(() => loadStoredFooterNoteVisible());
  useEffect(() => {
    try {
      localStorage.setItem(FOOTER_NOTE_VISIBLE_STORAGE_KEY, JSON.stringify(showFooterNote));
    } catch {
      // Stockage indisponible -- la bascule marche quand même pour
      // cette session, seule la mémorisation pour la PROCHAINE visite
      // est perdue silencieusement, jamais bloquant ici.
    }
  }, [showFooterNote]);
  const [theme, setThemeState] = useState(themeStore.get() || "light");
  const [viewMode, setViewMode] = useState(() => {
    // Lien profond depuis un autre front (ex. "⚙️ Paramètres" du
    // portail tickets, voir tickets/portal/src/App.jsx) -- ouvre
    // directement la page de paramètres plutôt que d'ajouter un clic
    // supplémentaire une fois arrivé sur le hub.
    const params = new URLSearchParams(window.location.search);
    const requestedView = params.get("view");
    return ["settings", "history", "tabs", "external-links"].includes(requestedView) ? requestedView : "grid";
  }); // "grid" | "settings"

  const username = auth.user?.profile?.preferred_username;
  useEffect(() => {
    if (!username) return;
    themeStore.load(username);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username]);
  useEffect(() => themeStore.onChange(setThemeState), []);

  const toggleTheme = () => {
    themeStore.set(theme === "dark" ? "light" : "dark", username);
  };
  // Vérification SILENCIEUSE de session au montage — bug réel
  // rencontré : sans ça, chaque front (hub, portail tickets) ne
  // regarde QUE son propre stockage local pour savoir s'il est
  // connecté, jamais s'il existe déjà une session Keycloak valide
  // ailleurs dans le même realm. Résultat observé : authentifié sur
  // le portail (page reprise du cache), mais "Se connecter" redemandé
  // en revenant sur le hub, alors que la session Keycloak elle-même
  // était toujours valide. signinSilent() (iframe cachée, prompt=none)
  // règle ça -- et comme Keycloak vit maintenant sur la MÊME origine
  // que ce front (entrée unique par chemin), cette iframe est de même
  // origine : aucun souci de cookies tiers, contrairement à la
  // plupart des architectures Keycloak+React qu'on trouve en ligne.
  const [silentCheckDone, setSilentCheckDone] = useState(false);

  // Liens externes gérés par les administrateurs -- backlog, livraison
  // #121. Chargés ICI (avant les retours anticipés ci-dessous, voir
  // les règles des hooks React) -- donnée publique/non sensible
  // (nom/URL/rôles autorisés, jamais un secret), aucune raison
  // d'attendre l'authentification complète pour la charger.
  const [externalLinks, setExternalLinks] = useState([]);
  const loadExternalLinks = () => {
    fetchExternalLinks(PREFS_API_BASE_URL).then(setExternalLinks);
  };
  useEffect(() => {
    loadExternalLinks();
  }, []);

  // Horloge permanente navigateur/serveur -- demandée explicitement
  // ("tout semble désynchronisé sous docker"), livraison #137.
  // browserNow tique chaque seconde (affichage fluide) ; serverTimeInfo
  // n'est resondé QUE périodiquement (30s, pas chaque seconde -- inutile
  // de solliciter prefs-api à cette fréquence pour un simple repère
  // visuel) et "avance" ENTRE deux sondages en extrapolant depuis
  // fetchedAtBrowser, pour un affichage qui tique lui aussi chaque
  // seconde plutôt qu'un saut visible toutes les 30s.
  const [browserNow, setBrowserNow] = useState(() => Date.now());
  const [serverTimeInfo, setServerTimeInfo] = useState(null);
  useEffect(() => {
    const tick = setInterval(() => setBrowserNow(Date.now()), 1000);
    return () => clearInterval(tick);
  }, []);
  useEffect(() => {
    let cancelled = false;
    async function fetchServerTime() {
      try {
        const res = await fetch(`${PREFS_API_BASE_URL}/health`);
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && typeof data.server_time === "number") {
          setServerTimeInfo({ serverTime: data.server_time, fetchedAtBrowser: Date.now() });
        }
      } catch {
        // Échec réseau -- pas d'heure serveur affichée pour cette
        // fois, jamais une exception qui casserait le reste du hub
        // pour un simple repère visuel.
      }
    }
    fetchServerTime();
    const poll = setInterval(fetchServerTime, 30000);
    return () => { cancelled = true; clearInterval(poll); };
  }, []);

  // Indicateurs de présence Keycloak/gateway/vault-standalone --
  // demandé explicitement, livraison #138. undefined tant que le
  // premier sondage n'a pas encore répondu -- affichage neutre en
  // attendant, jamais "en panne" par défaut avant même d'avoir sondé.
  const [infraStatus, setInfraStatus] = useState(undefined);
  // Journalisation des transitions -- livraison #141, voir
  // hubLogClient.js. useRef (pas un second useState) : doit être lu
  // de façon SYNCHRONE dans poll() pour comparer au sondage
  // précédent -- un état React se lirait "en retard" (rendu suivant),
  // un ref est immédiatement à jour.
  const infraStatusRef = useRef(undefined);
  useEffect(() => {
    let cancelled = false;
    async function poll() {
      const data = await fetchInfraStatus(PREFS_API_BASE_URL);
      if (!cancelled && data) {
        const current = { keycloak: data.keycloak, vault_standalone: data.vault_standalone };
        logPresenceTransitions(PREFS_API_BASE_URL, infraStatusRef.current, current, {
          keycloak: "Keycloak/gateway",
          vault_standalone: "Coffre-fort isolé (vault-standalone)",
        });
        infraStatusRef.current = current;
        setInfraStatus(data);
      }
    }
    poll();
    const interval = setInterval(poll, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  // Personnalisation de l'accueil, étape 2 (livraison #133) -- chargé
  // ICI aussi (avant les retours anticipés, mêmes règles des hooks
  // que ci-dessus) mais dépend du login, pas encore connu tant que
  // l'authentification n'a pas résolu -- lu directement depuis `auth`
  // (jamais la variable `profile` dérivée plus bas dans ce composant,
  // déclarée APRÈS les retours anticipés, donc pas fiable ici).
  const [hubLayout, setHubLayout] = useState(undefined);
  const loginForLayout = auth.user?.profile?.preferred_username;
  const loadHubLayout = () => {
    if (!loginForLayout) return;
    fetchHubLayout(PREFS_API_BASE_URL, loginForLayout).then(setHubLayout);
  };
  useEffect(() => {
    loadHubLayout();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loginForLayout]);

  useEffect(() => {
    if (auth.isLoading || auth.isAuthenticated || auth.activeNavigator || silentCheckDone) return;
    auth.signinSilent()
      .catch(() => {
        // Pas de session Keycloak valide ailleurs -- normal, le
        // formulaire "Se connecter" s'affichera juste après.
      })
      .finally(() => setSilentCheckDone(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isLoading, auth.isAuthenticated, auth.activeNavigator, silentCheckDone]);

  if (auth.isLoading || (!auth.isAuthenticated && !silentCheckDone && !auth.error)) {
    return (
      <div className="hub-shell hub-center">
        <p className="muted">Connexion en cours…</p>
      </div>
    );
  }

  if (auth.error) {
    return (
      <div className="hub-shell hub-center">
        <div className="hub-card hub-error-card">
          <h2>⚠️ Erreur de connexion</h2>
          <p>{auth.error.message}</p>
          <button className="primary" onClick={() => auth.signinRedirect()}>
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="hub-shell hub-center">
        <div className="hub-card">
          <h1>Hub SI</h1>
          <p className="muted">
            Portail d'accès — connexion via l'annuaire de l'entreprise (Keycloak / LDAP).
          </p>
          <button className="primary" onClick={() => auth.signinRedirect()}>
            🔐 Se connecter
          </button>
        </div>
      </div>
    );
  }

  const profile = auth.user?.profile || {};
  const displayName = profile.name || profile.preferred_username || "—";
  const rawRoles = auth.user?.profile?.realm_access?.roles;
  const groups = Array.isArray(profile.groups) ? profile.groups : [];
  const roles = formatUserRoles(groups);
  const fronts = buildFrontsList({
    frontendUrl: FRONTEND_URL,
    portalUrl: PORTAL_URL,
    keycloakConsoleUrl: KEYCLOAK_CONSOLE_URL,
    dbaUrl: DBA_URL,
    vaultUrl: VAULT_URL,
    vaultAdminUrl: VAULT_ADMIN_URL,
    ldapAdminUrl: LDAP_ADMIN_URL,
    groups,
    externalLinks,
  });
  // Nouvelle tuile « Supervision SI » (livraison #423, backlog 64) : la
  // tuile « maquette initiale » (front externe, lib.js) devient une VUE
  // INTERNE du hub -- même identifiant et même rôle (`supervision`) pour
  // ne pas casser la personnalisation de l'accueil ni les droits ; l'ancien
  // front reste accessible dans la vue (« ancienne maquette ») et dans le
  // mode onglets (embeddable) tant que ses outils ne sont pas redistribués.
  for (const f of fronts) {
    if (f.id === "supervision") {
      f.description = "Supervisés, propositions, liens -- carte et table en cadres, tuiles d'origine à un clic";
      f.onClick = () => setViewMode("supervision-si");
    }
  }
  // GED promue en tuile de front (livraison #172, demandé
  // explicitement -- "on commence par le plus facile : juste une
  // tuile qui pointe vers l'écran actuel"). PAS via buildFrontsList
  // (lib.js) -- ce mécanisme suppose une URL de portail EXTERNE,
  // alors que GedView.jsx vit À L'INTÉRIEUR du hub (un viewMode
  // interne). Ajoutée ICI, directement, avec `onClick` au lieu de
  // `url` -- voir renderFrontTile ci-dessous pour le rendu adapté.
  // Un vrai front "façon portail" (plein écran, URL dédiée) reste à
  // construire plus tard, explicitement mis de côté par la personne
  // pour cette première étape ("on y reviendra"). Concaténée APRÈS
  // buildFrontsList pour bénéficier de la MÊME personnalisation
  // (réordonnancement/regroupement, applyHubLayout ci-dessous) que
  // les autres fronts, jamais une tuile à part figée.
  if (GED_API_BASE_URL) {
    fronts.push({
      id: "ged",
      name: "GED (documents)",
      description: "Documents joints, versions et liaisons — accès direct depuis l'accueil",
      onClick: () => setViewMode("ged"),
    });
  }
  // Exploration réseau promue en tuile de front (livraison #265,
  // demandé explicitement -- "peux tu transformer l'explorateur
  // réseau en tuile ?") -- MÊME mécanisme que GED ci-dessus
  // (`onClick` interne, jamais une URL externe -- NetworkAgentView.jsx
  // vit lui aussi À L'INTÉRIEUR du hub).
  if (NETWORK_AGENT_API_BASE_URL) {
    fronts.push({
      id: "network-agent",
      name: "Exploration réseau",
      description: "Appareils découverts, échanges, sous-réseaux — accès direct depuis l'accueil",
      onClick: () => setViewMode("network-agent"),
    });
  }
  // Tuile "ENT" (livraison #272, demandée explicitement -- "la tuile
  // ENT environnement numérique de travail") -- même mécanisme que
  // GED/Exploration réseau ci-dessus (`onClick` interne).
  if (TICKETS_API_BASE_URL || TASKS_API_BASE_URL) {
    fronts.push({
      id: "ent",
      name: "ENT",
      description: "Environnement numérique de travail — calendrier et tâches, accès direct depuis l'accueil",
      onClick: () => setViewMode("ent"),
    });
  }
  // Tuile "Droits" (livraison #283, demandée explicitement -- "la
  // gestion des droits devient une tuile") -- RÉSERVÉE au groupe
  // admin_hub, jamais affichée sans (le contrôle réel se fait de
  // toute façon côté rights-api à chaque action, ceci n'est qu'un
  // confort d'affichage -- masquer une tuile n'est jamais LA
  // sécurité, seulement une commodité).
  if (RIGHTS_API_BASE_URL && groups.includes("admin_hub")) {
    fronts.push({
      id: "rights",
      name: "Droits",
      description: "Gestion des permissions et inventaire des fichiers du hub — réservé à admin_hub",
      onClick: () => setViewMode("rights"),
    });
  }
  // Tuile "Gestionnaire de fichiers" (livraison #396, backlog item 26) --
  // agrège GED, montages SSHFS, espace protégé. Accessible à tous les
  // groupes authentifiés (la protection fine se fait côté file-manager-api).
  if (FILE_MANAGER_API_BASE_URL) {
    fronts.push({
      id: "file-manager",
      name: "Gestionnaire de fichiers",
      description: "Documents, montages SSHFS, espace protégé — exploration arborescente",
      onClick: () => setViewMode("file-manager"),
    });
  }
  // Tuile "Sondes réseau" (netprobe, livraisons #295/#297/#301) --
  // collecteur d'IP, système de contrôle, suivi smokeping. Module
  // séparé de network-agent (voir netprobe/README.md) -- aucune
  // restriction de groupe particulière ici, contrairement à Droits
  // (pas une gestion d'accès système, juste de la supervision réseau).
  if (NETPROBE_API_BASE_URL) {
    fronts.push({
      id: "netprobe",
      name: "Sondes réseau",
      description: "Cibles surveillées, configuration des sondes, suivi de latence (smokeping)",
      onClick: () => setViewMode("netprobe"),
    });
  }
  // Tuile "UPS" (livraison #415, demandée en urgence) -- liste des
  // onduleurs, relevé automatique de leur page d'état, fiche et timeline.
  // Conditionnée à sa variable d'API comme Sondes réseau (la vue appelle
  // l'API dès le montage).
  if (UPS_API_BASE_URL) {
    fronts.push({
      id: "ups",
      name: "Onduleurs (UPS)",
      description: "État des onduleurs relevé automatiquement, fiche et historique",
      onClick: () => setViewMode("ups"),
    });
  }
  // Tuile "Agents hôtes" (livraison #421, backlog 63) -- flotte des
  // agents si-agent : surveillance de l'hôte, risques internes, sondes.
  if (SI_AGENT_API_BASE_URL) {
    fronts.push({
      id: "si-agent",
      name: "Agents hôtes",
      description: "Agents Linux : CPU, mémoire, disques, services, ports, risques internes, sondes déployées",
      onClick: () => setViewMode("si-agent"),
    });
  }
  // Personnalisation de l'accueil, étape 2 (livraison #133) --
  // hubLayout encore undefined tant qu'il n'a jamais été chargé (ou
  // jamais personnalisé) : applyHubLayout gère déjà ce cas par
  // défaut, comportement identique à avant ce chantier tant que
  // l'écran de personnalisation (étape 3, pas encore livrée) n'existe
  // pas pour en créer un.
  const { ungrouped: ungroupedFronts, groups: frontGroups } = applyHubLayout(fronts, hubLayout);

  // Horloge permanente -- calcul dérivé de browserNow/serverTimeInfo
  // ci-dessus, à chaque rendu (pas besoin d'un state séparé, c'est une
  // simple projection). Seuil de désynchronisation (livraison #255,
  // demandé explicitement -- "quand les valeurs sont proches pas
  // besoin d'afficher les 2, mettons une dérive acceptable de
  // 15mn") : 900s -- en-deçà, une seule horloge affichée (navigateur
  // ET serveur sont considérés "la même heure" pour un usage
  // pratique), la seconde horloge et l'écart ne s'affichent QUE si
  // ce seuil est dépassé, un vrai signal plutôt qu'un bruit visuel
  // sur deux valeurs quasi identiques.
  const browserClockLabel = new Date(browserNow).toLocaleTimeString("fr-FR");
  let serverClockLabel = null;
  let driftSeconds = null;
  if (serverTimeInfo) {
    const elapsedSinceFetch = (browserNow - serverTimeInfo.fetchedAtBrowser) / 1000;
    const estimatedServerNow = serverTimeInfo.serverTime + elapsedSinceFetch;
    driftSeconds = browserNow / 1000 - estimatedServerNow;
    serverClockLabel = new Date(estimatedServerNow * 1000).toLocaleTimeString("fr-FR");
  }
  const isClockDesync = driftSeconds !== null && Math.abs(driftSeconds) >= 900;

  // Factorisé -- réutilisé pour les tuiles sans cadre ET celles à
  // l'intérieur de chaque cadre, jamais deux copies du même balisage
  // à faire dériver l'une de l'autre par erreur plus tard.
  // `f.onClick` (livraison #172) : front INTERNE au hub (ex. GED) --
  // rendu comme un bouton plutôt qu'un lien, jamais les deux en même
  // temps sur la même tuile (un front a soit une URL externe, soit
  // une action interne, pas les deux).
  function renderFrontTile(f) {
    if (f.onClick) {
      return (
        <button key={f.id} type="button" className="hub-card hub-front-card hub-front-tile-button" onClick={f.onClick}>
          <h2>{f.name}</h2>
          <p className="muted">{f.description}</p>
        </button>
      );
    }
    return (
      <a key={f.id} className="hub-card hub-front-card" href={f.url}>
        <h2>{f.name}</h2>
        <p className="muted">{f.description}</p>
      </a>
    );
  }

  return (
    <div className="hub-shell">
      <ReminderWidget
        login={profile.preferred_username}
        groups={groups}
        prefsApiBase={PREFS_API_BASE_URL}
        ticketsApiBase={TICKETS_API_BASE_URL}
        ticketsPortalUrl={PORTAL_URL}
      />
      <header className="hub-header">
        <h1>Hub SI</h1>
        <nav className="hub-nav">
          <button
            type="button"
            className={viewMode === "aide" ? "active" : ""}
            onClick={() => setViewMode((v) => (v === "aide" ? "grid" : "aide"))}
          >
            Aide
          </button>
          <button
            type="button"
            className={viewMode === "tabs" ? "active" : ""}
            onClick={() => setViewMode((v) => (v === "tabs" ? "grid" : "tabs"))}
          >
            Onglets
          </button>

          {/* Réorganisation de l'en-tête (livraison #236) demandée
              explicitement -- "trop d'outils maintenant" : deux
              boutons permanents (Aide, Onglets) ci-dessus, tout le
              reste regroupé par catégorie sous ces trois menus. Un
              choix sous un menu FERME ce menu (setOpenNavMenu(null))
              et navigue -- jamais les deux actions séparées. */}
          <div className="hub-nav-dropdown">
            <button
              type="button"
              className={
                openNavMenu === "general" || ["logs", "cyber", "vigilance", "history", "imap", "backup-restore", "memory"].includes(viewMode)
                  ? "active"
                  : ""
              }
              onClick={() => setOpenNavMenu((v) => (v === "general" ? null : "general"))}
            >
              Général ▾
            </button>
            {openNavMenu === "general" && (
              <div className="hub-nav-dropdown-panel">
                <button type="button" onClick={() => { setViewMode((v) => (v === "logs" ? "grid" : "logs")); setOpenNavMenu(null); }}>
                  Logs
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "cyber" ? "grid" : "cyber")); setOpenNavMenu(null); }}>
                  Cyber
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "vigilance" ? "grid" : "vigilance")); setOpenNavMenu(null); }}>
                  Vigilance
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "history" ? "grid" : "history")); setOpenNavMenu(null); }}>
                  Historique
                </button>
                {/* Client IMAP -- pas mentionné explicitement dans les
                    trois catégories demandées (Général/Réseau/Data),
                    placé ici par défaut (ni réseau bas niveau, ni
                    analyse de données) -- à corriger si une autre
                    catégorie convient mieux. */}
                <button type="button" onClick={() => { setViewMode((v) => (v === "imap" ? "grid" : "imap")); setOpenNavMenu(null); }}>
                  Client IMAP
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "backup-restore" ? "grid" : "backup-restore")); setOpenNavMenu(null); }}>
                  Sauvegardes
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "memory" ? "grid" : "memory")); setOpenNavMenu(null); }}>
                  Mémoire
                </button>
              </div>
            )}
          </div>

          <div className="hub-nav-dropdown">
            <button
              type="button"
              className={
                openNavMenu === "reseau" || ["ssh-tunnels", "snmp", "nebula", "glpi-inventory", "architecture", "netmap-orchestrator", "network-cycle", "network-agent", "netprobe", "ups"].includes(viewMode)
                  ? "active"
                  : ""
              }
              onClick={() => setOpenNavMenu((v) => (v === "reseau" ? null : "reseau"))}
            >
              Réseau ▾
            </button>
            {openNavMenu === "reseau" && (
              <div className="hub-nav-dropdown-panel">
                <button type="button" onClick={() => { setViewMode((v) => (v === "network-cycle" ? "grid" : "network-cycle")); setOpenNavMenu(null); }}>
                  Cycle agile réseau
                </button>
                {/* Exploration réseau (#265) et Sondes réseau (#295) n'existaient
                    QUE comme tuiles d'accueil, alors que tout le reste de
                    l'écosystème réseau vit dans ce menu -- deux chemins d'accès
                    vers le MÊME viewMode, jamais une vue dupliquée. Contrairement
                    aux sept autres entrées de ce menu, celles-ci sont
                    CONDITIONNÉES à leur variable d'API : NetworkAgentView et
                    NetprobeView appellent leur API dès le montage sans garde-fou
                    sur une base absente (vérifié) -- une entrée non conditionnée
                    mènerait à un écran d'erreur réseau, pas à un "non configuré".
                    Même garde que les tuiles correspondantes plus haut. */}
                {NETWORK_AGENT_API_BASE_URL && (
                  <button type="button" onClick={() => { setViewMode((v) => (v === "network-agent" ? "grid" : "network-agent")); setOpenNavMenu(null); }}>
                    Exploration réseau
                  </button>
                )}
                {NETPROBE_API_BASE_URL && (
                  <button type="button" onClick={() => { setViewMode((v) => (v === "netprobe" ? "grid" : "netprobe")); setOpenNavMenu(null); }}>
                    Sondes réseau
                  </button>
                )}
                {UPS_API_BASE_URL && (
                  <button type="button" onClick={() => { setViewMode((v) => (v === "ups" ? "grid" : "ups")); setOpenNavMenu(null); }}>
                    Onduleurs (UPS)
                  </button>
                )}
                {SI_AGENT_API_BASE_URL && (
                  <button type="button" onClick={() => { setViewMode((v) => (v === "si-agent" ? "grid" : "si-agent")); setOpenNavMenu(null); }}>
                    Agents hôtes
                  </button>
                )}
                <button type="button" onClick={() => { setViewMode((v) => (v === "ssh-tunnels" ? "grid" : "ssh-tunnels")); setOpenNavMenu(null); }}>
                  Tunnels SSH
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "snmp" ? "grid" : "snmp")); setOpenNavMenu(null); }}>
                  SNMP
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "netmap-orchestrator" ? "grid" : "netmap-orchestrator")); setOpenNavMenu(null); }}>
                  Orchestrateur réseau
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "nebula" ? "grid" : "nebula")); setOpenNavMenu(null); }}>
                  Nebula
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "glpi-inventory" ? "grid" : "glpi-inventory")); setOpenNavMenu(null); }}>
                  GLPI Inventory
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "architecture" ? "grid" : "architecture")); setOpenNavMenu(null); }}>
                  Architecture réseau
                </button>
              </div>
            )}
          </div>

          <div className="hub-nav-dropdown">
            <button
              type="button"
              className={openNavMenu === "data" || ["schema-analyzer", "retro", "classifier"].includes(viewMode) ? "active" : ""}
              onClick={() => setOpenNavMenu((v) => (v === "data" ? null : "data"))}
            >
              Data ▾
            </button>
            {openNavMenu === "data" && (
              <div className="hub-nav-dropdown-panel">
                <button type="button" onClick={() => { setViewMode((v) => (v === "schema-analyzer" ? "grid" : "schema-analyzer")); setOpenNavMenu(null); }}>
                  Analyse de schémas
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "retro" ? "grid" : "retro")); setOpenNavMenu(null); }}>
                  Rétro-ingénierie
                </button>
                <button type="button" onClick={() => { setViewMode((v) => (v === "classifier" ? "grid" : "classifier")); setOpenNavMenu(null); }}>
                  Classification
                </button>
              </div>
            )}
          </div>

          {/* Regroupement "Paramètres" (livraison #173) -- hiérarchie
              d'inclusion demandée explicitement : liens externes,
              personnalisation de l'accueil et diagnostic technique
              vivent SOUS ce menu, jamais des icônes séparées au même
              rang que le reste. Le déclencheur lui-même ne navigue
              JAMAIS directement -- ouvre seulement le sous-menu, un
              choix explicite en dessous navigue. */}
          <div className="hub-nav-dropdown">
            <button
              type="button"
              className={
                openNavMenu === "settings" || ["settings", "personalize", "external-links"].includes(viewMode)
                  ? "active"
                  : ""
              }
              onClick={() => setOpenNavMenu((v) => (v === "settings" ? null : "settings"))}
            >
              Paramètres ▾
            </button>
            {openNavMenu === "settings" && (
              <div className="hub-nav-dropdown-panel">
                <button
                  type="button"
                  onClick={() => {
                    setViewMode((v) => (v === "settings" ? "grid" : "settings"));
                    setOpenNavMenu(null);
                  }}
                >
                  Paramètres généraux
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setViewMode((v) => (v === "personalize" ? "grid" : "personalize"));
                    setOpenNavMenu(null);
                  }}
                >
                  Personnaliser l'accueil
                </button>
                {isAdmin(groups) && (
                  <button
                    type="button"
                    onClick={() => {
                      setViewMode((v) => (v === "external-links" ? "grid" : "external-links"));
                      setOpenNavMenu(null);
                    }}
                  >
                    Liens externes
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setShowDebug((v) => !v);
                    setOpenNavMenu(null);
                  }}
                >
                  Diagnostic (jeton Keycloak)
                </button>
              </div>
            )}
          </div>
        </nav>
        <div className="hub-user">
          <span>👤 {displayName}</span>
          {roles.length > 0 && <span className="muted">({roles.join(", ")})</span>}
          <button onClick={toggleTheme} title={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}>
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
          <button onClick={() => auth.signoutRedirect()}>Se déconnecter</button>
        </div>
      </header>

      {viewMode === "settings" ? (
        <SettingsView
          groups={groups}
          login={profile.preferred_username}
          apiBase={PREFS_API_BASE_URL}
          onBack={() => setViewMode("grid")}
        />
      ) : viewMode === "history" ? (
        <HistoryView apiBase={PREFS_API_BASE_URL} onBack={() => setViewMode("grid")} />
      ) : viewMode === "aide" ? (
        <AideView apiBase={PREFS_API_BASE_URL} onBack={() => setViewMode("grid")} />
      ) : viewMode === "tabs" ? (
        <TabShell fronts={fronts} onBack={() => setViewMode("grid")} login={profile.preferred_username} prefsApiBase={PREFS_API_BASE_URL} />
      ) : viewMode === "logs" ? (
        <LogsManagerView onBack={() => setViewMode("grid")} prefsApiBase={PREFS_API_BASE_URL} />
      ) : viewMode === "schema-analyzer" ? (
        <SchemaAnalyzerView
          onBack={() => setViewMode("grid")}
          dbaApiBase={DBA_API_BASE_URL}
          schemaApiBase={SCHEMA_ANALYZER_API_BASE_URL}
          login={profile.preferred_username}
        />
      ) : viewMode === "retro" ? (
        <RetroView
          onBack={() => setViewMode("grid")}
          retroApiBase={RETRO_API_BASE_URL}
          dbaApiBase={DBA_API_BASE_URL}
          schemaApiBase={SCHEMA_ANALYZER_API_BASE_URL}
        />
      ) : viewMode === "backup-restore" ? (
        <BackupRestoreView onBack={() => setViewMode("grid")} backupRestoreApiBase={BACKUP_RESTORE_API_BASE_URL} />
      ) : viewMode === "architecture" ? (
        <ArchitectureView onBack={() => setViewMode("grid")} architectureApiBase={ARCHITECTURE_API_BASE_URL} />
      ) : viewMode === "memory" ? (
        <MemoryView onBack={() => setViewMode("grid")} memoryApiBase={MEMORY_API_BASE_URL} />
      ) : viewMode === "classifier" ? (
        <ClassifierView onBack={() => setViewMode("grid")} classifierApiBase={CLASSIFIER_API_BASE_URL} />
      ) : viewMode === "vigilance" ? (
        <VigilanceView onBack={() => setViewMode("grid")} vigilanceApiBase={VIGILANCE_API_BASE_URL} />
      ) : viewMode === "ged" ? (
        <GedView
          onBack={() => setViewMode("grid")}
          gedApiBase={GED_API_BASE_URL}
          login={profile.preferred_username}
          ticketsPortalUrl={PORTAL_URL}
          ownCloudApiBase={OWNCLOUD_API_BASE_URL}
          ownCloudSearchApiBase={OWNCLOUD_SEARCH_API_BASE_URL}
        />
      ) : viewMode === "ssh-tunnels" ? (
        <SshTunnelsView
          onBack={() => setViewMode("grid")}
          sshTunnelsApiBase={SSH_TUNNELS_API_BASE_URL}
          login={profile.preferred_username}
        />
      ) : viewMode === "snmp" ? (
        <SnmpView
          onBack={() => setViewMode("grid")}
          snmpApiBase={SNMP_API_BASE_URL}
          glpiApiBase={GLPI_API_BASE_URL}
          login={profile.preferred_username}
        />
      ) : viewMode === "netmap-orchestrator" ? (
        <NetmapOrchestratorView
          onBack={() => setViewMode("grid")}
          netmapOrchestratorApiBase={NETMAP_ORCHESTRATOR_API_BASE_URL}
        />
      ) : viewMode === "nebula" ? (
        <NebulaView
          onBack={() => setViewMode("grid")}
          nebulaApiBase={NEBULA_API_BASE_URL}
          glpiApiBase={GLPI_API_BASE_URL}
        />
      ) : viewMode === "imap" ? (
        <ImapView
          onBack={() => setViewMode("grid")}
          imapApiBase={IMAP_CLIENT_API_BASE_URL}
        />
      ) : viewMode === "glpi-inventory" ? (
        <GlpiInventoryView
          onBack={() => setViewMode("grid")}
          glpiApiBase={GLPI_API_BASE_URL}
          networkAgentApiBase={NETWORK_AGENT_API_BASE_URL}
        />
      ) : viewMode === "network-agent" ? (
        <NetworkAgentView
          onBack={() => setViewMode("grid")}
          networkAgentApiBase={NETWORK_AGENT_API_BASE_URL}
          classifierApiBase={CLASSIFIER_API_BASE_URL}
        />
      ) : viewMode === "network-cycle" ? (
        <NetworkCycleView
          onBack={() => setViewMode("grid")}
          netmapOrchestratorApiBase={NETMAP_ORCHESTRATOR_API_BASE_URL}
          networkAgentApiBase={NETWORK_AGENT_API_BASE_URL}
          netprobeApiBase={NETPROBE_API_BASE_URL}
          snmpApiBase={SNMP_API_BASE_URL}
          sshTunnelsApiBase={SSH_TUNNELS_API_BASE_URL}
          vigilanceApiBase={VIGILANCE_API_BASE_URL}
          backupRestoreApiBase={BACKUP_RESTORE_API_BASE_URL}
          onNavigate={(target) => setViewMode(target)}
        />
      ) : viewMode === "ent" ? (
        <EntView
          onBack={() => setViewMode("grid")}
          ticketsApiBase={TICKETS_API_BASE_URL}
          tasksApiBase={TASKS_API_BASE_URL}
          portalUrl={PORTAL_URL}
          gedApiBase={GED_API_BASE_URL}
          login={profile.preferred_username}
          relationsApiBase={RELATIONS_API_BASE_URL}
          ownCloudApiBase={OWNCLOUD_API_BASE_URL}
          ownCloudSearchApiBase={OWNCLOUD_SEARCH_API_BASE_URL}
        />
      ) : viewMode === "rights" ? (
        <RightsView
          onBack={() => setViewMode("grid")}
          rightsApiBase={RIGHTS_API_BASE_URL}
          groups={groups}
        />
      ) : viewMode === "file-manager" ? (
        <FileManagerView
          onBack={() => setViewMode("grid")}
          fileManagerApiBase={FILE_MANAGER_API_BASE_URL}
          login={profile.preferred_username}
          groups={groups}
        />
      ) : viewMode === "netprobe" ? (
        <NetprobeView
          onBack={() => setViewMode("grid")}
          netprobeApiBase={NETPROBE_API_BASE_URL}
        />
      ) : viewMode === "ups" ? (
        <UpsView
          onBack={() => setViewMode("grid")}
          upsApiBase={UPS_API_BASE_URL}
        />
      ) : viewMode === "supervision-si" ? (
        <SupervisionSiView
          onBack={() => setViewMode("grid")}
          onNavigate={(target) => setViewMode(target)}
          legacyFrontendUrl={FRONTEND_URL}
          netprobeApiBase={NETPROBE_API_BASE_URL}
          upsApiBase={UPS_API_BASE_URL}
          siAgentApiBase={SI_AGENT_API_BASE_URL}
          snmpApiBase={SNMP_API_BASE_URL}
          sshTunnelsApiBase={SSH_TUNNELS_API_BASE_URL}
          networkAgentApiBase={NETWORK_AGENT_API_BASE_URL}
          netmapOrchestratorApiBase={NETMAP_ORCHESTRATOR_API_BASE_URL}
          vigilanceApiBase={VIGILANCE_API_BASE_URL}
          pixelGridApiBase={PIXEL_GRID_API_BASE_URL}
        />
      ) : viewMode === "si-agent" ? (
        <SiAgentView
          onBack={() => setViewMode("grid")}
          siAgentApiBase={SI_AGENT_API_BASE_URL}
        />
      ) : viewMode === "cyber" ? (
        <CyberView
          onBack={() => setViewMode("grid")}
          prefsApiBase={PREFS_API_BASE_URL}
          login={profile.preferred_username}
        />
      ) : viewMode === "personalize" ? (
        <PersonalizeHomeView
          fronts={fronts}
          hubLayout={hubLayout}
          onHubLayoutChanged={setHubLayout}
          apiBase={PREFS_API_BASE_URL}
          login={profile.preferred_username}
          onBack={() => setViewMode("grid")}
        />
      ) : viewMode === "external-links" ? (
        <ExternalLinksAdminView
          apiBase={PREFS_API_BASE_URL}
          login={profile.preferred_username}
          links={externalLinks}
          onLinksChanged={loadExternalLinks}
          onBack={() => setViewMode("grid")}
        />
      ) : (
      <>
      <div className="hub-grid-view">
        <div className="hub-grid-scroll">
          {showDebug && (
            <div className="hub-debug">
              <p>
                <strong>realm_access.roles</strong> (NON utilisé par cette appli —
                bug Keycloak connu, KEYCLOAK-3469 : les rôles hérités d'un groupe
                ne remontent pas toujours ici de façon fiable. Affiché seulement
                à titre de comparaison) :{" "}
                {Array.isArray(rawRoles) && rawRoles.length > 0 ? rawRoles.join(", ") : "(absent ou vide)"}
              </p>
              <p>
                <strong>groups</strong> (source RÉELLEMENT utilisée pour tout —
                cartes du hub, sélecteur de vues du portail tickets) :{" "}
                {groups.length > 0 ? groups.join(", ") : "(absent du jeton — realm pas encore réimporté avec le mapper \"groups\", ou déconnexion/reconnexion pas encore refaite depuis)"}
              </p>
              <p>
                <strong>Jeton émis</strong> :{" "}
                {profile.iat ? new Date(profile.iat * 1000).toLocaleString("fr-FR") : "—"}
                {" — "}
                <strong>expire</strong> :{" "}
                {profile.exp ? new Date(profile.exp * 1000).toLocaleString("fr-FR") : "—"}
              </p>
              <p><strong>sub</strong> (identifiant Keycloak) : {profile.sub || "—"}</p>
              <details>
                <summary>Profil OIDC complet (JSON)</summary>
                <pre>{JSON.stringify(profile, null, 2)}</pre>
              </details>
            </div>
          )}

          <main className="hub-main">
            {SI_AGENT_API_BASE_URL && (
              <SiAgentEventsBanner siAgentApiBase={SI_AGENT_API_BASE_URL} onOpen={() => setViewMode("si-agent")} />
            )}
            {fronts.length === 0 && (
              <p className="muted">
                Aucune application configurée — vérifiez VITE_SUPERVISION_FRONTEND_URL /
                VITE_TICKETS_PORTAL_URL côté déploiement.
              </p>
            )}
            <div className="hub-grid">
              {ungroupedFronts.map(renderFrontTile)}
            </div>
            {frontGroups.map((g) => (
              <div key={g.id} className="hub-frame">
                <h3 className="hub-frame-title">{g.title}</h3>
                <div className="hub-grid">
                  {g.tiles.map(renderFrontTile)}
                </div>
              </div>
            ))}
          </main>
        </div>

        <footer className="hub-footer">
          <button
            className="hub-footer-toggle"
            onClick={() => setShowFooterNote((v) => !v)}
            title={showFooterNote ? "Masquer les informations" : "Afficher les informations"}
          >
            {showFooterNote ? "▾ Informations" : "▸ Informations"}
          </button>
          {showFooterNote && (
            <p className="hub-footer-text">
              Cette page vérifie votre identité. Le portail tickets a lui aussi sa
              propre connexion Keycloak (retour silencieux si vous êtes déjà
              connecté ici, même realm) — Supervision SI, elle, reste entièrement
              ouverte, sans aucune vérification. Et côté API : ni l'une ni
              l'autre ne vérifie encore de jeton, quel que soit le front.
              {fronts.some((f) => f.id === "keycloak-admin") && (
                <>
                  {" "}La carte "Administration Keycloak" est un lien, pas une garantie
                  d'accès : elle apparaît parce que vous avez le rôle applicatif "admin"
                  ou "technicien" dans ce realm, mais la console Keycloak elle-même
                  exige des droits de gestion de realm accordés séparément.
                </>
              )}
            </p>
          )}
        </footer>
      </div>
      </>
      )}
      <div className="status-badges">
        <div
          className="clock-badge"
          title={
            serverClockLabel
              ? isClockDesync
                ? `Navigateur : ${browserClockLabel} · prefs-api : ${serverClockLabel} · écart ${driftSeconds > 0 ? "+" : ""}${driftSeconds.toFixed(0)}s`
                : `Navigateur : ${browserClockLabel} · prefs-api : ${serverClockLabel} (écart < 15 min, horloges considérées synchronisées)`
              : `Navigateur : ${browserClockLabel} · heure serveur indisponible`
          }
        >
          🕐 {browserClockLabel}
          {serverClockLabel && isClockDesync && (
            <>
              {" · "}{serverClockLabel}
              <span className="clock-badge-desync"> ⚠ {driftSeconds > 0 ? "+" : ""}{driftSeconds.toFixed(0)}s</span>
            </>
          )}
        </div>
        <div
          className="presence-badge"
          title={
            infraStatus
              ? `Keycloak/gateway (Keycloak + tls-proxy, stack séparé) : ${infraStatus.keycloak ? "joignable" : "injoignable"} · Coffre-fort isolé (vault-standalone) : ${infraStatus.vault_standalone ? "joignable" : "injoignable"}`
              : "Indicateurs de présence — vérification en cours…"
          }
        >
          {infraStatus === undefined ? (
            <>⚪ ⚪</>
          ) : (
            <>
              <span className={infraStatus.keycloak ? "presence-up" : "presence-down"}>●</span>
              {" "}
              <span className={infraStatus.vault_standalone ? "presence-up" : "presence-down"}>●</span>
            </>
          )}
        </div>
        <div className="version-badge" title={`hash contenu : ${versionInfo.content_hash} · hash git : ${versionInfo.git_hash} · dernière vérification : ${versionInfo.last_checked_at}`}>
          #{versionInfo.delivery_number || "?"}
        </div>
      </div>
    </div>
  );
}
