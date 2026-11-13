export function initUpdater() {
  const updaterUi = {
    overlay: document.getElementById("updater-overlay"),
    title: document.getElementById("updater-title"),
    desc: document.getElementById("updater-desc"),
    status: document.getElementById("updater-status"),
    btnCheck: document.getElementById("btn-check-update"),
  };

  async function triggerUpdateApply(targetVersion) {
    if (updaterUi.overlay) {
      updaterUi.overlay.classList.remove("is-hidden");
      updaterUi.title.textContent = "Actualizando PosterMaker...";
      updaterUi.desc.textContent = targetVersion
        ? `Descargando e integrando la versión v${targetVersion}...`
        : "Descargando e integrando los cambios...";
      updaterUi.status.textContent = "Por favor espera mientras se aplica la actualización...";
    }

    try {
      const applyRes = await fetch("/api/update/apply", { method: "POST" });
      const applyData = await applyRes.json();

      if (applyData.status === "updated" || applyData.ok !== false) {
        if (updaterUi.title) updaterUi.title.textContent = "¡Actualización completada!";
        if (updaterUi.desc) updaterUi.desc.textContent = "PosterMaker se ha actualizado correctamente. Reiniciando...";
        if (updaterUi.status) updaterUi.status.textContent = "Recargando interfaz...";

        setTimeout(() => {
          window.location.reload();
        }, 2000);
      } else {
        if (updaterUi.overlay) updaterUi.overlay.classList.add("is-hidden");
        alert(applyData.message || applyData.error || "No se pudo completar la actualización.");
      }
    } catch (err) {
      // En caso de que el reinicio del servidor corte la conexión
      if (updaterUi.status) updaterUi.status.textContent = "Servidor reiniciado. Recargando...";
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    }
  }

  async function handleStartupUpdateCheck() {
    try {
      const res = await fetch("/api/update/status");
      if (!res.ok) throw new Error("Status failed");
      const state = await res.json();

      if (state.status === "updating" && updaterUi.overlay) {
        updaterUi.overlay.classList.remove("is-hidden");
        updaterUi.title.textContent = "Actualizando PosterMaker...";
        updaterUi.desc.textContent = state.message || "Descargando e integrando cambios...";
        updaterUi.status.textContent = "Aplicando actualización...";

        let attempts = 0;
        const poll = setInterval(async () => {
          attempts++;
          try {
            const pollRes = await fetch("/api/update/status");
            const pollState = await pollRes.json();
            if (pollState.status === "updated") {
              clearInterval(poll);
              updaterUi.title.textContent = "¡Actualización completada!";
              updaterUi.desc.textContent = "PosterMaker está listo con la última versión.";
              updaterUi.status.textContent = "Iniciando...";
              setTimeout(() => window.location.reload(), 1000);
            } else if (pollState.status === "up_to_date" || pollState.status === "error" || attempts > 20) {
              clearInterval(poll);
              if (updaterUi.overlay) updaterUi.overlay.classList.add("is-hidden");
            }
          } catch (_) {
            clearInterval(poll);
            if (updaterUi.overlay) updaterUi.overlay.classList.add("is-hidden");
          }
        }, 700);
        return;
      } else if (state.status === "available" || state.has_update) {
        if (updaterUi.btnCheck) {
          updaterUi.btnCheck.textContent = `Actualizar a v${state.latest_version}`;
          updaterUi.btnCheck.style.fontWeight = "600";
          updaterUi.btnCheck.style.color = "#e4572e";
        }
      }
    } catch (e) {
      // Silencioso en modo local / sin conexión
    }
  }

  if (updaterUi.btnCheck) {
    updaterUi.btnCheck.addEventListener("click", async () => {
      updaterUi.btnCheck.disabled = true;
      updaterUi.btnCheck.textContent = "Buscando...";
      try {
        const res = await fetch("/api/update/check", { method: "POST" });
        const data = await res.json();
        if (data.status === "available" || data.has_update) {
          const confirmUpdate = confirm(
            `Nueva versión disponible: v${data.latest_version || data.current_version}.\n\n` +
            `¿Deseas descargar e instalar la actualización ahora?`
          );
          if (confirmUpdate) {
            await triggerUpdateApply(data.latest_version);
          }
        } else if (data.status === "updated") {
          alert("¡PosterMaker se ha actualizado correctamente! Recargando la página...");
          window.location.reload();
        } else if (data.status === "up_to_date") {
          alert(data.message || "PosterMaker ya está en la última versión.");
        } else {
          alert(data.message || "Comprobación completada.");
        }
      } catch (e) {
        alert("No se pudo conectar con el servidor para comprobar actualizaciones.");
      } finally {
        updaterUi.btnCheck.disabled = false;
        if (!updaterUi.btnCheck.textContent.includes("Actualizar a")) {
          updaterUi.btnCheck.textContent = "Buscar actualizaciones";
        }
      }
    });
  }

  handleStartupUpdateCheck();
}
