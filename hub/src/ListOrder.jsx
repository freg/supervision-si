// Sélecteur d'ordre d'une liste (#742) : « A → Z · Récent · Gravité », mémorisé par liste.
//   const [order, setOrder] = useListOrder("si-agent.fleet", "alpha");
//   <OrderSwitch value={order} onChange={setOrder} />   …   orderItems(items, order, {name, date, severity})
import { useState } from "react";
import { ORDER_MODES, loadOrder, saveOrder } from "./listOrder.js";

export function useListOrder(listId, fallback = "alpha") {
  const [mode, setMode] = useState(() => loadOrder(listId, fallback));
  const set = (m) => { setMode(m); saveOrder(listId, m); };
  return [mode, set];
}

export function OrderSwitch({ value, onChange, modes = ORDER_MODES }) {
  return (
    <span className="hub-order-switch" role="group" aria-label="Ordre de la liste">
      {modes.map((m) => (
        <button key={m.id} type="button" title={m.title} aria-pressed={value === m.id}
          className={value === m.id ? "active" : "secondary"} onClick={() => onChange(m.id)}>{m.label}</button>
      ))}
    </span>
  );
}
