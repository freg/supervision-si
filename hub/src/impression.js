// #935 : impression CIBLÉE d'une zone. Ajoute une classe au <body> le temps de l'impression ; la feuille de style
// @media print (hub.css) masque tout sauf la zone associée à cette classe, puis la classe est retirée. Évite que
// l'« Imprimer » d'une vue imprime tout le hub (régression de #933 corrigée). Sans classe, l'impression reste normale.
export function imprimer(classe) {
  if (typeof document === "undefined") return;
  try {
    document.body.classList.add(classe);
    const nettoyer = () => {
      document.body.classList.remove(classe);
      window.removeEventListener("afterprint", nettoyer);
    };
    window.addEventListener("afterprint", nettoyer);
    setTimeout(nettoyer, 10000);   // filet de sécurité si « afterprint » ne se déclenche pas
    window.print();
  } catch { /* impression indisponible */ }
}
