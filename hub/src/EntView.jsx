import React, { useState } from "react";
import CalendarView from "./CalendarView.jsx";
import KanbanView from "./KanbanView.jsx";
import ValidationView from "./ValidationView.jsx";
import GedView from "./GedView.jsx";
import RelationsView from "./RelationsView.jsx";

// Tuile "ENT" (Environnement Numérique de Travail), livraison #272 --
// demandée explicitement : "intègre un calendrier/agenda interne au
// hub et branche le sur la gestion de tickets et sur une gestion de
// tâche indépendante des tickets avec une vue kanban. la tuile ENT
// environnement numérique de travail". Conteneur à onglets réunissant
// Calendrier (#272, branché sur les tickets), Tâches (#271, Kanban
// indépendant des tickets), Validation (#273, "branche la création
// auto [de ticket depuis un événement], ajoute un écran de validation
// des tickets automatique") et GED (#333, backlog item 38 point 2 --
// "la tuile ENT devient une super tuile" : dépôt de fichiers interne
// déjà existant, GedView.jsx, réutilisé tel quel plutôt que reconstruit
// -- webmail explicitement "à voir" par la personne, pas ajouté ici ;
// vue "relations" transversale, backlog item 38, pas encore construite)
// -- même motif d'onglets que le reste du hub (ex. SchemaAnalyzerView).

export default function EntView({ onBack, ticketsApiBase, tasksApiBase, portalUrl, gedApiBase, login, relationsApiBase, ownCloudApiBase, ownCloudSearchApiBase }) {
  const [tab, setTab] = useState("calendrier");
  // Cible d'une navigation "voir les relations" depuis une autre vue
  // (livraison #339) -- {type, id} ou null. Portée à ce niveau
  // (pas dans RelationsView elle-même) car c'est ICI que vit le
  // changement d'onglet déclenché par le bouton d'une AUTRE vue.
  const [relationsTarget, setRelationsTarget] = useState(null);

  function viewRelations(entityType, entityId) {
    setRelationsTarget({ type: entityType, id: entityId });
    setTab("relations");
  }

  return (
    <div>
      <div className="hub-settings-topbar" style={{ padding: "0 16px" }}>
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🏫 ENT — Environnement numérique de travail</h1>
      </div>
      <div style={{ display: "flex", gap: 8, padding: "0 16px", marginBottom: 12 }}>
        <button className={tab === "calendrier" ? "" : "secondary"} onClick={() => setTab("calendrier")}>📅 Calendrier</button>
        <button className={tab === "taches" ? "" : "secondary"} onClick={() => setTab("taches")}>🗂️ Tâches</button>
        <button className={tab === "validation" ? "" : "secondary"} onClick={() => setTab("validation")}>✅ Validation</button>
        <button className={tab === "ged" ? "" : "secondary"} onClick={() => setTab("ged")}>📁 GED</button>
        <button className={tab === "relations" ? "" : "secondary"} onClick={() => setTab("relations")}>🔗 Relations</button>
      </div>
      {tab === "calendrier" ? (
        <CalendarView onBack={onBack} ticketsApiBase={ticketsApiBase} onViewRelations={viewRelations} embedded />
      ) : tab === "taches" ? (
        <KanbanView onBack={onBack} tasksApiBase={tasksApiBase} onViewRelations={viewRelations} embedded />
      ) : tab === "validation" ? (
        <ValidationView onBack={onBack} ticketsApiBase={ticketsApiBase} portalUrl={portalUrl} embedded />
      ) : tab === "ged" ? (
        <GedView
          onBack={onBack}
          gedApiBase={gedApiBase}
          login={login}
          ticketsPortalUrl={portalUrl}
          ownCloudApiBase={ownCloudApiBase}
          ownCloudSearchApiBase={ownCloudSearchApiBase}
          onViewRelations={viewRelations}
        />
      ) : (
        <RelationsView
          onBack={onBack}
          relationsApiBase={relationsApiBase}
          initialEntityType={relationsTarget?.type}
          initialEntityId={relationsTarget?.id}
          embedded
        />
      )}
    </div>
  );
}
