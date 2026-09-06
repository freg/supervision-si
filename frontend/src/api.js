// Point d'entrée unique pour parler à l'API. Centraliser ici évite de
// disperser des fetch() dans les composants et facilite le changement
// d'URL de base entre dev/prod.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

/**
 * Récupère la donnée d'une source. Reflète fidèlement le contrat de l'API :
 * - { status: "ok", source, updated_at, data } si disponible
 * - { status: "unavailable", source } si rien n'a encore été poussé (503)
 * En cas d'erreur réseau, on renvoie un état "unavailable" cohérent plutôt
 * que de laisser une exception remonter jusqu'au composant.
 */
export async function fetchSourceData(source) {
  try {
    const response = await fetch(`${API_BASE_URL}/data/${source}`);
    const body = await response.json();
    return body;
  } catch (err) {
    return { status: "unavailable", source };
  }
}

/**
 * Scanne les sources connues de l'API : celles poussées par /ingest et
 * celles simplement déposées dans le dossier data. Chaque entrée porte
 * un statut ("ok" | "new" | "modified") et un flag `registered`.
 */
export async function fetchSources() {
  try {
    const response = await fetch(`${API_BASE_URL}/sources`);
    const body = await response.json();
    return body.sources || [];
  } catch (err) {
    return [];
  }
}

/**
 * Pousse un payload JSON vers une source via le chemin de confiance
 * /ingest — utilisé par le bouton "Injecter" de la colonne des sources.
 */
export async function ingestSource(source, payload) {
  try {
    const response = await fetch(`${API_BASE_URL}/ingest/${source}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      return { ok: false, error: body.error || `Erreur HTTP ${response.status}` };
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, error: "Impossible de joindre l'API" };
  }
}

/**
 * Suppression douce d'une source (les données restent sur disque,
 * récupérables via restoreSource).
 */
export async function deleteSource(source) {
  try {
    const response = await fetch(`${API_BASE_URL}/sources/${source}`, { method: "DELETE" });
    return response.ok;
  } catch (err) {
    return false;
  }
}

export async function fetchDeletedSources() {
  try {
    const response = await fetch(`${API_BASE_URL}/sources/deleted`);
    if (!response.ok) return [];
    const body = await response.json();
    return body.sources || [];
  } catch (err) {
    return [];
  }
}

export async function restoreSource(source) {
  try {
    const response = await fetch(`${API_BASE_URL}/sources/${source}/restore`, { method: "POST" });
    return response.ok;
  } catch (err) {
    return false;
  }
}

/**
 * Confirme l'ajout d'une source "new" ou la prise en compte d'une
 * modification externe détectée sur une source déjà enregistrée.
 */
export async function registerSource(source) {
  try {
    const response = await fetch(`${API_BASE_URL}/sources/${source}/register`, {
      method: "POST",
    });
    return response.ok;
  } catch (err) {
    return false;
  }
}

/**
 * "Verse" une sélection (Fusion, RadialTree, carte...) comme nouvelle
 * source dans la bannette d'interaction — jamais auto-enregistrée
 * (contrairement à /ingest), reste "proposée" jusqu'à promotion
 * explicite via registerSource(). Renvoie {ok, source} ou
 * {ok:false, error}.
 */
export async function createSourceFromSelection(name, data) {
  try {
    const response = await fetch(`${API_BASE_URL}/sources/from-selection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, data }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      return { ok: false, error: body.error || `Erreur HTTP ${response.status}` };
    }
    return { ok: true, source: body.source };
  } catch (err) {
    return { ok: false, error: "Impossible de joindre l'API" };
  }
}

/**
 * Résumé agrégé pour une période : une cellule par mois (level="year")
 * ou par jour (level="month"), avec has_match (présence simple).
 * `keywordExpr` est une expression brute, ex: "incident OR panne AND regions".
 */
export async function fetchCalendarSummary(level, period, keywordExpr) {
  const params = new URLSearchParams({ level, period });
  if (keywordExpr) params.set("keywords", keywordExpr);

  try {
    const response = await fetch(`${API_BASE_URL}/calendar/summary?${params.toString()}`);
    const body = await response.json();
    return body.buckets || [];
  } catch (err) {
    return [];
  }
}

/**
 * Variante "compteur" du résumé calendaire — agrège une valeur
 * numérique par cellule (mode compteur ou occurrences selon `label`).
 */
export async function fetchPixelSummary(level, period, label, keywordExpr) {
  const params = new URLSearchParams({ level, period, label });
  if (keywordExpr) params.set("keywords", keywordExpr);

  try {
    const response = await fetch(`${API_BASE_URL}/calendar/pixel-summary?${params.toString()}`);
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    return null;
  }
}

/**
 * Détail précis des correspondances pour un jour donné.
 */
export async function fetchCalendarDay(date, keywordExpr) {
  const params = new URLSearchParams({ date });
  if (keywordExpr) params.set("keywords", keywordExpr);

  try {
    const response = await fetch(`${API_BASE_URL}/calendar/day?${params.toString()}`);
    const body = await response.json();
    return body.matches || [];
  } catch (err) {
    return [];
  }
}

/**
 * Résout une sélection de dates (potentiellement sur plusieurs mois/années)
 * en sources concernées — alimente la corbeille de sélection.
 */
export async function fetchMatchingSources(dates, keywordExpr) {
  const params = new URLSearchParams({ dates: dates.join(",") });
  if (keywordExpr) params.set("keywords", keywordExpr);

  try {
    const response = await fetch(`${API_BASE_URL}/calendar/sources?${params.toString()}`);
    const body = await response.json();
    return body.sources || [];
  } catch (err) {
    return [];
  }
}
