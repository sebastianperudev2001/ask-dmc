import type { CourseRecommendation } from '@/types/chat'

type CourseRecommendationCardProps = {
  recommendations: CourseRecommendation[]
}

const CourseRecommendationCard = ({ recommendations }: CourseRecommendationCardProps) => {
  if (!recommendations.length) return null

  // Dedupe by courseId — RF-I16 (reemplaza SourceChips).
  const unique = Array.from(new Map(recommendations.map((r) => [r.courseId, r])).values())

  return (
    <div
      data-testid="course-recommendation-list"
      style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}
    >
      {unique.map((course) => (
        <div
          key={course.courseId}
          data-testid="course-recommendation-card"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '10px 14px',
            borderRadius: 10,
            border: '1px solid color-mix(in oklab, var(--color-tool) 25%, transparent)',
            background: 'var(--color-tool-bg)',
          }}
        >
          <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--color-text)' }}>
            {course.name}
          </span>
          <span
            style={{
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
              color: 'var(--color-tool)',
              flexShrink: 0,
            }}
          >
            match {Math.round(course.similarityScore * 100)}%
          </span>
        </div>
      ))}
    </div>
  )
}

export default CourseRecommendationCard
