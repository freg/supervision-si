// #995 : mesure d'un job de la tour -- durée et charge de l'hôte par étape, comparaison avec les lancements à la main.
import { tonCharge, tonIo, duree, nombre, etapeLaPlusLongue, texteComparaison } from "./towerMesuresLib.js";

const COULEUR = { ok: "var(--ok)", warn: "var(--warning)", bad: "var(--danger)" };
const Val = ({ ton, children }) => <span style={{ color: COULEUR[ton] || "inherit", fontWeight: ton === "bad" ? 700 : 400 }}>{children}</span>;

export default function TowerMesures({ mesures: m }) {
  if (!m) return null;
  const lourde = etapeLaPlusLongue(m);
  return (
    <div style={{ marginTop: 8, fontSize: 12 }}>
      <strong>⏱ Mesure</strong> : {duree(m.duree_s)} au total · charge max <Val ton={tonCharge(m.load_max, m.coeurs)}>{nombre(m.load_max)}</Val> ({m.coeurs} cœurs vus)
      {" "}· attente disque max <Val ton={tonIo(m.iowait_max)}>{nombre(m.iowait_max)} %</Val> · mémoire disponible min {nombre(m.mem_min_mo, 0)} Mo
      {lourde && <> · étape la plus longue : <em>{lourde.label}</em> ({duree(lourde.duree_s)})</>}
      <table className="table" style={{ marginTop: 4 }}>
        <thead><tr><th>Étape</th><th>Durée</th><th>Charge max</th><th>Attente disque max</th><th>Mémoire dispo. min</th></tr></thead>
        <tbody>
          {m.etapes.map((e, i) => (
            <tr key={i}>
              <td>{e.en_cours ? "⏳ " : e.rc ? "✗ " : ""}{e.label}</td>
              <td>{duree(e.duree_s)}</td>
              <td><Val ton={tonCharge(e.load_max, m.coeurs)}>{nombre(e.load_max)}</Val></td>
              <td><Val ton={tonIo(e.iowait_max)}>{e.iowait_max == null ? "—" : `${nombre(e.iowait_max)} %`}</Val></td>
              <td>{e.mem_min_mo == null ? "—" : `${nombre(e.mem_min_mo, 0)} Mo`}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted" style={{ margin: "4px 0 0" }}>Constructions réussies — {texteComparaison(m.comparaison)}</p>
    </div>
  );
}
