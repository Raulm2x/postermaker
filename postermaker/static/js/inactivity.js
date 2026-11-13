export function initInactivity() {
  // Heartbeat periódico para mantener el servidor despierto mientras la app esté abierta
  setInterval(() => {
    fetch("/api/heartbeat", { method: "POST" }).catch(() => {});
  }, 45000);

  // Notificar al servidor cuando la pestaña se cierra o se navega a otro sitio
  window.addEventListener("beforeunload", () => {
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/tab-closed");
    }
  });

  // Botón de apagado manual
  const shutdownBtn = document.getElementById("btn-shutdown");
  if (shutdownBtn) {
    shutdownBtn.addEventListener("click", async () => {
      const confirmShutdown = window.confirm(
        "¿Deseas salir de PosterMaker y cerrar la aplicación?"
      );
      if (!confirmShutdown) return;

      shutdownBtn.disabled = true;
      shutdownBtn.textContent = "Cerrando...";

      try {
        await fetch("/api/shutdown", { method: "POST" });
      } catch (e) {
        // Proceso terminado
      }

      document.body.innerHTML = `
        <div style="min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: system-ui, -apple-system, sans-serif; text-align: center; padding: 24px; background: #fffdf8; color: #17211f;">
          <div style="max-width: 440px; background: #ffffff; border: 1px solid rgba(23,33,31,0.12); border-radius: 14px; padding: 36px 28px; box-shadow: 0 10px 30px rgba(0,0,0,0.06);">
            <h1 style="font-size: 1.3rem; font-weight: 600; margin-bottom: 12px; color: #17211f;">PosterMaker se ha cerrado</h1>
            <p style="font-size: 0.95rem; color: #526360; line-height: 1.5; margin: 0;">
              Ya puedes cerrar esta pestaña. Para volver a usar la aplicación, iníciala desde tu lanzador de programas.
            </p>
          </div>
        </div>
      `;
    });
  }
}
