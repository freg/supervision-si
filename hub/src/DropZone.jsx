// Zone de dépôt de fichier (livraison #604) -- règle d'ergonomie : partout où
// le hub importe un fichier, on peut le GLISSER-DÉPOSER ou cliquer pour le
// choisir ; le nom du fichier retenu s'affiche, et la zone dit ce qu'elle
// accepte. Un seul fichier (le premier déposé).
import { useRef, useState } from "react";

export default function DropZone({ accept = "", file, onFile, label = "Glisser un fichier ici, ou cliquer pour le choisir", hint = "", compact = false, disabled = false }) {
  const [over, setOver] = useState(false);
  const input = useRef(null);
  const pick = (files) => { const f = files && files[0]; if (f && !disabled) onFile(f); };
  return (
    <div
      className={`hub-dropzone${over ? " over" : ""}${compact ? " compact" : ""}${disabled ? " disabled" : ""}`}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files); }}
      onClick={() => !disabled && input.current && input.current.click()}
      role="button" tabIndex={0}
      onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !disabled) { e.preventDefault(); input.current && input.current.click(); } }}
      title={hint || accept}
    >
      <input ref={input} type="file" accept={accept} style={{ display: "none" }} onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
      <span className="hub-dropzone-icon">{file ? "📄" : "⤓"}</span>
      <span className="hub-dropzone-text">
        {file ? <><b>{file.name}</b> <span className="muted">({Math.max(1, Math.round(file.size / 1024))} Ko)</span> — <span className="muted">déposer ou cliquer pour changer</span></> : <>{label}{hint ? <span className="muted"> · {hint}</span> : null}</>}
      </span>
    </div>
  );
}
