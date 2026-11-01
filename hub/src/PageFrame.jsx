// Gabarit de page généralisé (livraison #562) -- note design : « cadre de
// menu de gauche et droit fixe, les options déroulent pas le titre, idem
// header et footer fixes ; tbody et page centrale déroulants ; division
// verticale ou horizontale ». L'en-tête et le pied du hub sont ceux de
// App.jsx (fixes) ; ce gabarit ajoute une barre de titre, des cadres
// latéraux (ou en bandes) et une zone centrale, seuls les corps défilent.
// Styles : .hub-page* dans hub.css.
export function SideFrame({ title, children, className = "" }) {
  return (
    <aside className={`hub-page-side ${className}`}>
      {title && <div className="hub-page-side-title">{title}</div>}
      <div className="hub-page-side-body">{children}</div>
    </aside>
  );
}

/**
 * @param {object} p
 * @param {"vertical"|"horizontal"} [p.split] vertical = colonnes (défaut), horizontal = bandes
 * @param {React.ReactNode} [p.left]  cadre gauche (ou bande haute) : {title, body} ou nœud
 * @param {React.ReactNode} [p.right] cadre droit (ou bande basse)
 * @param {React.ReactNode} [p.foot]  pied de page de la vue (fixe)
 */
export default function PageFrame({ title, actions, onBack, split = "vertical", left, right, foot, children, className = "" }) {
  const side = (s, cls) => (s == null ? null : s.body !== undefined || s.title !== undefined ? <SideFrame title={s.title} className={cls}>{s.body}</SideFrame> : <SideFrame className={cls}>{s}</SideFrame>);
  return (
    <div className={`hub-page ${className}`}>
      {(title || onBack || actions) && (
        <div className="hub-page-head">
          {onBack && <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>}
          {title && <h1>{title}</h1>}
          <span style={{ flex: 1 }} />
          {actions}
        </div>
      )}
      <div className={`hub-page-body ${split}`}>
        {side(left, "left")}
        <section className="hub-page-center">{children}</section>
        {side(right, "right")}
      </div>
      {foot && <div className="hub-page-foot">{foot}</div>}
    </div>
  );
}
