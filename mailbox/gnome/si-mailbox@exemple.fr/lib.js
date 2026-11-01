// si-mailbox (#843) : mise en forme du widget, sans dépendance GNOME (testée sous node).
export function resume(d, maintenant) {
    if (!d || typeof d.total !== 'number')
        return {texte: '—', etat: 'absent', lignes: ['si-mailbox : aucun relevé (agent arrêté ou aucun compte)']};
    const age = Math.max(0, maintenant - (d.maj || 0));
    const filtres = d.filtres || [], erreurs = d.erreurs || [];
    let texte = String(d.total);
    if (filtres.length)
        texte += ' · ' + filtres[0].n;
    let etat = d.total > 0 ? 'non_lus' : 'calme';
    if (filtres.some(f => f.n > 0))
        etat = 'filtre';
    if (age > 600)
        etat = 'ancien';
    if (erreurs.length && !(d.comptes || []).length) {
        etat = 'erreur';
        texte = '!';
    }
    const lignes = [`Non lus (${d.dossier || 'INBOX'}) : ${d.total}`]
        .concat(filtres.map(f => `${f.nom} : ${f.n}`))
        .concat(erreurs.map(e => '⚠ ' + e));
    lignes.push(age < 90 ? 'Relevé à l\'instant' : `Relevé il y a ${Math.round(age / 60)} min`);
    return {texte, etat, lignes};
}
