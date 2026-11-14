// How far an anomaly's score is from normal. The normalised score is 0.5 exactly at the model's threshold
// (detection-design.md), so the threshold mark sits in the middle of the track.
import type { CSSProperties } from 'react'

function clamp(score: number): number {
  return Math.max(0, Math.min(1, score))
}

function ratioText(raw: number | null | undefined, threshold: number | null | undefined): string | null {
  if (raw === null || raw === undefined || !threshold) return null
  const ratio = raw / threshold
  return ratio >= 10 ? `${Math.round(ratio)}×` : `${ratio.toFixed(1)}×`
}

/** Full gauge for the detail panel. */
export function ScoreGauge({ score, raw, threshold }: { score: number; raw?: number | null; threshold?: number | null }) {
  const ratio = ratioText(raw, threshold)
  return (
    <div className="gauge">
      <div className="gauge-track" role="img" aria-label={`Anomaly score ${score.toFixed(2)}; the threshold is 0.50`}>
        <span className="gauge-fill" style={{ '--w': `${clamp(score) * 100}%` } as CSSProperties} />
        <span className="gauge-mark" />
      </div>
      <div className="gauge-scale">
        <span>normal</span>
        <span>threshold</span>
        <span>far from normal</span>
      </div>
      <p className="gauge-text">
        <strong className="number">{score.toFixed(2)}</strong>
        {ratio && <span> · the model's error was {ratio} its threshold</span>}
      </p>
    </div>
  )
}

/** Small inline meter for table rows. */
export function ScoreMeter({ score }: { score: number }) {
  return (
    <span className="meter" title={`Score ${score.toFixed(2)} (threshold 0.50)`}>
      <span className="meter-track">
        <span className="meter-fill" style={{ '--w': `${clamp(score) * 100}%` } as CSSProperties} />
      </span>
      <span className="number">{score.toFixed(2)}</span>
    </span>
  )
}
