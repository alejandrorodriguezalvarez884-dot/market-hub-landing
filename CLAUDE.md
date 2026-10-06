# Instrucciones para agentes

Lee primero [docs/HANDOFF.md](docs/HANDOFF.md): estado, pendientes y siguientes pasos.

Reglas que no se negocian:
- **Nada de trading.** No se escribe código que envíe órdenes ni que se conecte a un broker, y no
  se usa ningún conector de broker (IBKR u otro), ni siquiera para importar posiciones o precios.
- **Describir, no recomendar.** El dashboard muestra valores, ganancias frente al coste del propio
  usuario y rentabilidades pasadas. Nada de "compra", "vende", alertas de oportunidad ni
  predicciones.
- **Los datos del usuario son suyos.** Solo se guarda lo que la web dice en `/privacy/`. El
  contenido de las carteras nunca va a los logs. Cada usuario solo lee y escribe su documento
  (la clave es el `sub` de Google que sale de la sesión, nunca un parámetro de la petición).
  Borrar la cuenta borra el documento entero. De una cartera solo salen del servidor los tickers
  (al proveedor de precios), los tickers con sus pesos y rentabilidades (al modelo que escribe
  las frases de My Hub, `insights.facts`) y lo que su dueño decide compartir en Community: nunca
  la identidad, el número de acciones, los costes ni los importes. Cualquier dato nuevo que se
  guarde se añade antes a la página de privacidad y a la de cuenta.
- **El login se verifica en el servidor.** Nunca se confía en un email o un id que mande el
  navegador; solo en el ID token verificado y en la cookie firmada. Las escrituras pasan el
  control de `Origin`.
- **Claves solo en `.env` o en el entorno.** Nunca en el repo, en logs ni en commits.
- **Nada programado y nada en GitHub Actions.** Todo se lanza a mano desde el `Makefile`.

Convenciones:
- Hablar con el usuario en español. Código, comentarios y textos de la web en inglés.
- Python 3.12 con `uv`. Tests con `make test`; web con `make check`.
- Mismo stack y estilo visual que `fundamentals-lab` y `decision-signal-lab`, para unificarlos.
- Al terminar una tarea relevante, actualizar "Dónde estamos" en `docs/HANDOFF.md`.
