import { useEffect, useState } from "react";

// Connexion DIRECTE à ipam-api — aucun import, aucune copie de
// données, aucun passage par le service `api` principal.
const IPAM_API_BASE_URL = import.meta.env.VITE_IPAM_API_BASE_URL || "http://localhost:6106";

/**
 * Stats + santé d'ipam-api. pollMs=0 désactive le sondage périodique
 * (un seul appel au montage) — utile pour un badge léger qui n'a pas
 * besoin de rester à jour en continu (liste des sources), par
 * opposition au panneau d'aperçu qui, lui, se rafraîchit.
 */
export default function useIpamStats(pollMs = 60000) {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const [healthRes, statsRes] = await Promise.all([
          fetch(`${IPAM_API_BASE_URL}/health`).then((r) => r.json()),
          fetch(`${IPAM_API_BASE_URL}/stats`).then((r) => r.json()),
        ]);
        if (cancelled) return;
        setHealth(healthRes);
        if (statsRes.error) {
          setError(statsRes.error);
          setStats(null);
        } else {
          setStats(statsRes);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(String(err));
          setStats(null);
        }
      }
    }

    poll();
    if (!pollMs) return undefined;
    const interval = setInterval(poll, pollMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pollMs]);

  return { stats, health, error };
}
