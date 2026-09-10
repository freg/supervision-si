(function () {
  "use strict";
  const B = typeof browser !== "undefined" ? browser : chrome;
  const $ = (id) => document.getElementById(id);
  B.storage.local.get(["relayUrl", "bases", "recordValues"]).then((s) => {
    $("relayUrl").value = s.relayUrl || "http://127.0.0.1:6320";
    $("bases").value = (s.bases || []).join("\n");
    $("recordValues").checked = !!s.recordValues;
  });
  $("save").onclick = async () => {
    const bases = $("bases").value.split(/\r?\n/).map((x) => x.trim().replace(/\/+$/, "")).filter(Boolean);
    await B.storage.local.set({ relayUrl: $("relayUrl").value.trim() || "http://127.0.0.1:6320", bases: bases, recordValues: $("recordValues").checked });
    $("msg").textContent = "enregistré";
  };
})();
