// Comptes et groupes (livraison #557) -- logique pure, testée sous Node
// (hub/tests/accountsLib.test.mjs).

/** Filtre + tri des comptes : recherche sur identifiant, nom, e-mail, groupe. */
export function filterUsers(users, query, group = "") {
  const q = (query || "").trim().toLowerCase();
  return (users || []).filter((u) => {
    if (group && !(u.groups || []).includes(group)) return false;
    if (!q) return true;
    const hay = [u.username, u.first_name, u.last_name, u.email, ...(u.groups || [])].filter(Boolean).join(" ").toLowerCase();
    return hay.includes(q);
  }).sort((a, b) => (a.username || "").localeCompare(b.username || "", "fr"));
}

/** Validation du formulaire de création ; renvoie la liste des erreurs (vide = ok). */
export function validateNewUser(form, ldapWritable) {
  const errors = [];
  const username = (form.username || "").trim();
  if (!username) errors.push("identifiant requis");
  else if (!/^[a-z0-9._-]{2,64}$/i.test(username)) errors.push("identifiant : lettres, chiffres, . _ - (2 à 64)");
  if (form.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) errors.push("e-mail invalide");
  if (form.password && form.password.length < 8) errors.push("mot de passe : 8 caractères minimum");
  if (!form.password && !form.email) errors.push("sans mot de passe temporaire, un e-mail est nécessaire pour l'invitation");
  if (ldapWritable === false && !form.allowKeycloakOnly) errors.push("l'annuaire LDAP est en lecture seule : le compte sera créé dans Keycloak seulement (cocher pour confirmer)");
  return errors;
}

/** Nombre de membres par groupe à partir de la liste des comptes. */
export function membersByGroup(users) {
  const out = {};
  for (const u of users || []) for (const g of u.groups || []) out[g] = (out[g] || 0) + 1;
  return out;
}

/** Diff d'appartenance pour l'affichage (ajoutés / retirés). */
export function groupDiff(before, after) {
  const b = new Set(before || []), a = new Set(after || []);
  return { added: [...a].filter((x) => !b.has(x)).sort(), removed: [...b].filter((x) => !a.has(x)).sort() };
}
