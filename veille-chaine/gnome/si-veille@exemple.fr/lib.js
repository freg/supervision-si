// si-veille (#845) : mise en forme de l'icône de la barre du haut, sans dépendance GNOME (testée sous node).
const STATUT = {ok: '✓', ko: '✗', doute: '?', non_teste: '—'};
const hm = (t) => { const d = new Date(t * 1000); return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
const depuis = (s) => s < 90 ? 'à l\'instant' : s < 5400 ? `il y a ${Math.round(s / 60)} min` : `il y a ${Math.round(s / 3600)} h`;

export function resume(e, maintenant) {
    if (!e || !e.dernier_tour)
        return {etat: 'absent', texte: '', titre: 'si-veille : aucun passage (service arrêté ?)', derniere: null, maillons: [], alertes: []};
    const age = maintenant - e.dernier_tour, res = e.resultats || {};
    const ordre = (e.ordre && e.ordre.length) ? e.ordre : Object.keys(res);
    const maillons = ordre.filter(i => res[i]).map(i => `${STATUT[res[i].statut] || '?'} ${res[i].nom || i} — ${res[i].detail || ''}`.slice(0, 140));
    const alertes = (e.alertes || []).slice(-15).reverse().map(a => `${hm(a.ts)}  ${a.titre} : ${a.texte}`.slice(0, 160));
    const derniere = (e.alertes || []).length ? e.alertes[e.alertes.length - 1] : null;
    let etat = 'ok', texte = '', titre = `Chaîne du hub OK — vérifiée ${depuis(age)}`;
    if (e.incident) {
        etat = 'panne';
        texte = (e.incident.texte || 'panne').replace(/^Cause probable : /, '').split(' — ')[0].slice(0, 40);
        titre = `PANNE depuis ${Math.max(1, Math.round((maintenant - e.incident.debut) / 60))} min — ${e.incident.texte || ''}`;
    } else if (Object.values(res).some(r => r.statut === 'doute')) {
        etat = 'doute';
        titre = `Échec isolé, à confirmer au prochain passage (${depuis(age)})`;
    }
    if (age > 3 * (e.intervalle_s || 120) + 60) {
        etat = 'ancien';
        titre = `si-veille muet depuis ${Math.round(age / 60)} min (service arrêté ?)`;
    }
    return {etat, texte, titre, derniere: derniere ? `${hm(derniere.ts)}  ${derniere.titre} : ${derniere.texte}`.slice(0, 200) : null, maillons, alertes};
}
