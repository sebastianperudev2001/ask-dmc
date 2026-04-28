# Personas — DMC Sales Agent

---

## P1 — Visitante (Estudiante Prospecto)

**Nombre representativo**: Lucía Torres  
**Rol**: Visitante del sitio dmc.pe que explora programas de capacitación

### Características
- Profesional entre 24 y 38 años, trabajando en áreas de negocio, tecnología o analítica
- Motivaciones variadas: cambio de carrera, mejora salarial, requerimiento laboral, o curiosidad académica
- Puede no saber exactamente qué programa necesita
- Acostumbrado a chat en apps móviles; expectativa de respuesta inmediata y personalizada
- Puede haber visitado el sitio antes (datos en localStorage) o ser primera vez

### Objetivos
- Entender qué programa le conviene según su perfil y objetivos
- Recibir información confiable sin presión de venta agresiva
- Poder revisar el brochure del programa de su interés
- Si decide comprar, hacerlo de forma ágil (link de pago directo)
- Si no está listo, dejar sus datos y que el equipo lo contacte

### Frustraciones
- Formularios largos y esperar una llamada que nunca llega
- Chatbots genéricos que no entienden su contexto
- Información inconsistente o inventada sobre precios o fechas
- Tener que repetir su información si ya la proporcionó antes

### Contexto de uso
- Dispositivo: mobile o desktop, cualquier hora del día
- Idioma: español (Perú)
- Canal de entrada: dmc.pe → popup de chat flotante o página `/demo`

---

## P2 — Equipo Comercial (Sales Admin)

**Nombre representativo**: Carlos Mendoza  
**Rol**: Miembro del equipo de ventas de DMC Institute que gestiona leads en el backoffice

### Características
- Experiencia comercial; no necesariamente técnico
- Accede al backoffice desde desktop, principalmente en horario laboral
- Maneja múltiples leads simultáneamente
- Recibe notificaciones por email cuando un lead solicita contacto humano

### Objetivos
- Ver rápidamente qué leads son prioritarios (score hot/warm/cold)
- Entender el contexto de cada lead sin leer la conversación completa
- Identificar de inmediato los leads que pidieron ser contactados por un humano
- Acceder al historial de conversación cuando necesite contexto profundo
- Filtrar leads por score, motivación y rango de fechas

### Frustraciones
- Leads sin información útil que obligan a empezar la conversación desde cero
- No saber qué programa recomendó el agente ni por qué
- Perder tiempo en leads fríos antes de atender los calientes

### Contexto de uso
- Dispositivo: desktop con navegador
- Acceso: autenticado con Cognito (admin@dmc.pe)
- Idioma: español

---

## P3 — Agente IA (Persona del Sistema)

**Nombre**: Asistente DMC  
**Rol**: Agente conversacional IA que representa a DMC Institute en el chat widget

### Características
- Se presenta explícitamente como asistente IA de DMC Institute
- Opera dentro de un scope estrictamente limitado: recomendación de programas y cierre de ventas
- Solo usa información fundamentada en los brochures cargados en la knowledge base
- Ejecuta el flujo conversacional estado a estado (una pregunta a la vez)
- Nunca menciona competidores ni realiza comparaciones externas

### Objetivos del sistema
- Calificar conversacionalmente al visitante sin fricción de formulario
- Recomendar 1–3 programas con pitch personalizado según motivación detectada
- Cerrar la venta generando un link de pago Mercado Pago
- Escalar a humano de forma elegante cuando el visitante lo solicita
- Persistir el lead completo en DynamoDB al finalizar

### Restricciones de comportamiento
- No inventa precios, fechas ni condiciones especiales
- No menciona otras empresas o institutos educativos
- No ejecuta tareas fuera del scope de ventas (ej. ejercicios de código, soporte técnico)
- No hace múltiples preguntas en un mismo turno
- Responde únicamente con información de los brochures oficiales
