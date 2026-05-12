import type { HistoryGroup, Suggestion } from '@/types/chat'

export const HISTORY: HistoryGroup[] = [
  {
    group: 'Hoy',
    items: [
      { id: 'h-1', title: 'Ruta para analista junior', preview: 'Recomendaste Python + SQL + Power BI…', active: true },
    ],
  },
  {
    group: 'Ayer',
    items: [
      { id: 'h-2', title: 'Diferencias entre diplomas', preview: 'Comparativa Business Analyst vs Data Science' },
      { id: 'h-3', title: 'Quiero migrar a roles de datos', preview: 'Vengo del área comercial, ¿por dónde empiezo?' },
    ],
  },
  {
    group: 'Semana pasada',
    items: [
      { id: 'h-4', title: 'Prerrequisitos de Machine Learning', preview: 'Necesito bases de Python primero' },
      { id: 'h-5', title: 'Modalidad híbrida vs en vivo', preview: 'Diferencias y carga horaria' },
      { id: 'h-6', title: 'Certificaciones DMC', preview: 'Vigencia y reconocimiento corporativo' },
      { id: 'h-7', title: 'Becas y financiamiento', preview: 'Opciones de pago en cuotas' },
    ],
  },
]

export const SUGGESTIONS: Suggestion[] = [
  { title: 'Soy analista junior y quiero crecer en datos', sub: 'Recomiéndame una ruta de aprendizaje' },
  { title: 'Quiero aprender Machine Learning desde cero', sub: '¿Qué requisitos previos necesito?' },
  { title: 'Compara el Diploma Business Analyst con Data Science', sub: 'Ayúdame a decidir según mi perfil' },
  { title: 'Necesito dominar Power BI para mi trabajo actual', sub: 'Curso corto y aplicado, por favor' },
]
