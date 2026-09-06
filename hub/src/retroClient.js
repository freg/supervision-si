// Client API vers retro-api (livraison #243, backlog item 30 --
// "Rétro-ingénierie"). Même motif que les autres clients hub --
// renvoie toujours le corps JSON, même en cas d'erreur.

export async function scanPhpArchive(retroApiBase, file) {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await fetch(`${retroApiBase}/scan`, { method: "POST", body: formData });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (data === null) {
      return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    }
    return data;
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}
