# NFR Requirements — Clarificación: Dirección del Webhook

Tu respuesta a Question 1 ("podemos llamar al webhook de sandbox de mercado pago normal") deja una ambigüedad técnica real que quiero confirmar antes de diseñar la infraestructura, porque afecta directamente qué se puede probar en local sin cambios adicionales.

**La distinción importa**:
- **Llamadas salientes** (nuestro backend → Mercado Pago): por ejemplo crear una preferencia de pago, o consultar `GET /v1/payments/{id}`. Esto **sí funciona sin ningún cambio** desde `localhost` — es una llamada HTTP normal hacia afuera, como cualquier request a una API externa.
- **El webhook en sí** (Mercado Pago → nuestro backend): cuando el pago se confirma en el sandbox de Mercado Pago, son **sus servidores** los que hacen un POST hacia la `notification_url` que configuramos. Esa notificación viene de internet — **no puede alcanzar `localhost:8000`** aunque estemos usando credenciales de sandbox/test, salvo que expongamos el puerto local con un túnel (ngrok, Cloudflare Tunnel, etc.).

Es decir: sandbox/test **no** cambia esta restricción de red — solo cambia que el dinero es ficticio, no que la notificación se vuelva "más fácil de recibir" en local.

## Question 1
Dado lo anterior, ¿cómo prefieres manejar la recepción real del webhook durante las pruebas de este incremento?

A) Usar un túnel temporal (ej. `ngrok`) apuntando a `localhost:8000` solo durante las sesiones de prueba manual — así el webhook real de Mercado Pago sandbox sí llega, sin cambiar el alcance de despliegue decidido
B) Desplegar únicamente el endpoint del webhook a Azure Container Apps (URL pública estable) mientras el resto del flujo se prueba en local
C) No depender de que Mercado Pago realmente alcance el webhook en este incremento — simular la llamada manualmente (`curl`/script) contra `localhost` con un payload realista, verificando la lógica de firma/actualización de estado sin necesitar exposición pública
D) Other (please describe after [Answer]: tag below)

[Answer]:  C
