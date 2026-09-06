import { useEffect, useState } from "react";

/**
 * Renvoie `value`, mais mis à jour seulement `delayMs` après la
 * dernière modification — évite de déclencher un appel réseau à
 * chaque pixel de glissement d'un curseur (ex. TimelineRangeSlider).
 * Générique, aucune dépendance métier.
 */
export default function useDebouncedValue(value, delayMs = 300) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
