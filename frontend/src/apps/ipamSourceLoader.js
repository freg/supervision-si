import { fetchIpamRoots, fetchIpamTree } from "./ipamApi.js";
import { ingestSource } from "../api.js";
import { buildIpamForestPayload } from "./ipamForestLib.js";

// Nom STABLE (pas d'horodatage) : contrairement à "Figer cette vue"
// (des photos ponctuelles distinctes, une par capture), "Charger
// comme source" représente LA vision complète et courante d'IPAM —
// recharger met à jour la même source en place plutôt que d'empiler
// des doublons. Le garde-fou différentiel de /ingest (voir
// api/app.py) fait qu'un rechargement à contenu inchangé ne réécrit
// même rien côté serveur.
export const IPAM_SOURCE_NAME = "ipam";

/**
 * Récupère TOUTES les racines indépendantes d'IPAM et l'arbre complet
 * de chacune (pas une seule à la fois comme dans l'onglet IPAM
 * lui-même), combine, puis enregistre via le même chemin d'injection
 * que "Figer cette vue" et le bouton "Injecter" manuel — aucun
 * service intermédiaire, toujours un appel direct à ipam-api suivi
 * d'un unique POST /ingest.
 */
export async function loadIpamAsSource() {
  const { roots, error: rootsError } = await fetchIpamRoots();
  if (rootsError) {
    return { ok: false, error: rootsError };
  }
  if (roots.length === 0) {
    return { ok: false, error: "aucune racine indépendante trouvée côté IPAM" };
  }

  const entries = await Promise.all(
    roots.map(async (root) => [root.id, await fetchIpamTree(root.id)])
  );
  const treesByRootId = Object.fromEntries(entries);

  const payload = buildIpamForestPayload(roots, treesByRootId);
  const result = await ingestSource(IPAM_SOURCE_NAME, payload);
  if (!result.ok) {
    return { ok: false, error: result.error };
  }
  return { ok: true, name: IPAM_SOURCE_NAME, rootCount: roots.length };
}
