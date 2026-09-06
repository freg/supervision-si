export default function SynthesisPanel({ selectedSource, sourcePayload, selectedFeature }) {
  if (!selectedSource) {
    return (
      <p className="synthesis-empty">
        Sélectionnez une source à gauche, puis un élément sur la carte pour
        en voir le détail ici.
      </p>
    );
  }

  const isOk = sourcePayload?.status === "ok";

  return (
    <>
      <div className="synthesis-title">Source</div>
      <div className="synthesis-value">{selectedSource}</div>

      {!isOk && (
        <p className="synthesis-empty">
          Aucune donnée disponible pour cette source pour le moment.
        </p>
      )}

      {isOk && !selectedFeature && (
        <p className="synthesis-empty">
          Cliquez un élément sur la carte pour afficher son détail.
        </p>
      )}

      {isOk && selectedFeature && (
        <>
          <div className="synthesis-title">Élément sélectionné</div>
          {Object.entries(selectedFeature.properties || {}).map(([key, value]) => (
            <div className="synthesis-field-row" key={key}>
              <span className="synthesis-field-label">{key}</span>
              <span>{String(value)}</span>
            </div>
          ))}
        </>
      )}
    </>
  );
}
