// Chargement des historiques par équipement supervisé (livraison #424) --
// une origine = une API de tuile ; jamais d'exception vers le composant.
import { fetchSamples } from "./netprobeClient.js";
import { fetchUpsReadings } from "./upsClient.js";
import { fetchAgentMeasurements } from "./siAgentClient.js";
import { pointsFromNetprobeSamples, pointsFromUpsReadings, pointsFromAgentRisks } from "./supervisedHistory.js";

// Renvoie les points {at, state, text} d'un équipement fusionné : toutes
// ses origines sont interrogées, les points sont réunis et triés.
export async function fetchItemHistory(item, apiBases, { startIso, limit = 500 } = {}) {
  const out = [];
  for (const o of item.origins || []) {
    try {
      if (o.origin === "netprobe" && o.type === "probe" && apiBases.netprobe) {
        const d = await fetchSamples(apiBases.netprobe, o.originId, limit);
        out.push(...pointsFromNetprobeSamples(Array.isArray(d?.samples) ? d.samples : Array.isArray(d) ? d : []));
      } else if (o.origin === "ups" && apiBases.ups) {
        const rows = await fetchUpsReadings(apiBases.ups, o.originId, { start: startIso, limit });
        out.push(...pointsFromUpsReadings(Array.isArray(rows) ? rows : rows?.readings || []));
      } else if (o.origin === "si-agent" && apiBases.siAgent) {
        const rows = await fetchAgentMeasurements(apiBases.siAgent, o.originId, { task: "risks", limit, since: startIso });
        out.push(...pointsFromAgentRisks(rows));
      }
    } catch { /* origine injoignable : on garde ce que les autres ont donné */ }
  }
  return out.sort((a, b) => a.at - b.at);
}
