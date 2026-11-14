// Models: which model is deciding what counts as an anomaly, how it was trained, how well it did on the
// evaluation runs (fault run with ground truth, fault-free run), what operators said about its anomalies, and every
// registered version.
import { Link } from 'react-router-dom'
import { Cpu } from 'lucide-react'
import '../components/anomalies/anomalies.css'
import '../components/models/models.css'
import { useModels, type Verdicts } from '../hooks/useModels'
import { formatDateTime, formatNumber, formatPercent, formatShortDateTime } from '../lib/format'
import { describeParameter, readMetrics, scenarioName, type FaultRun, type NormalRun } from '../lib/modelMetrics'
import { rangeOption, useTimeRange } from '../lib/timeRange'
import type { Model } from '../types/api'

function fixed(value: number | null, digits: number): string {
  return value === null ? '—' : value.toFixed(digits)
}

function ActiveModel({ model }: { model: Model }) {
  const files = (model.training_data ?? '').split(',').map((f) => f.trim()).filter(Boolean)
  const parameters = Object.entries(model.parameters).filter(([key]) => key !== 'algorithm')
  return (
    <section className="panel model-hero">
      <div className="model-title">
        <span className="model-icon" aria-hidden="true"><Cpu size={22} /></span>
        <div>
          <p className="eyebrow">Active model</p>
          <h2>{model.name} <span className="model-version">v{model.version}</span></h2>
          <p className="muted">{model.algorithm.toUpperCase()} · trained {formatDateTime(model.trained_at)}</p>
        </div>
      </div>

      <dl className="model-facts">
        <div>
          <dt>Threshold</dt>
          <dd className="number">{fixed(model.threshold, 2)}</dd>
        </div>
        <div>
          <dt>Training windows</dt>
          <dd className="number">{formatNumber(model.training_samples)}</dd>
        </div>
        <div>
          <dt>Training runs</dt>
          <dd className="number">{files.length || '—'}</dd>
        </div>
      </dl>

      <div className="model-explain">
        <h3>How it decides</h3>
        <p>
          Every minute, each service's logs become one window of numbers: how often each message type appeared,
          new message types, error and warning rates, and latency. The model learned what normal windows look like
          from {formatNumber(model.training_samples)} windows of fault-free traffic. A window it cannot reconstruct
          well is unusual; when the reconstruction error passes the threshold (the
          {' '}{String(model.parameters.percentile ?? 99.9)}th percentile of the training errors) the window is flagged,
          and rules grade its severity with reasons.
        </p>
      </div>

      {parameters.length > 0 && (
        <ul className="param-chips" aria-label="Model settings">
          {parameters.map(([key, value]) => {
            const [name, text] = describeParameter(key, value)
            return <li key={key}><span>{name}</span> {text}</li>
          })}
        </ul>
      )}
      {files.length > 0 && <p className="hint">Trained on {files.join(', ')}.</p>}
    </section>
  )
}

function Evaluation({ fault, normal }: { fault: FaultRun | null; normal: NormalRun | null }) {
  if (!fault && !normal) {
    return (
      <section className="panel model-section">
        <h2>Evaluation</h2>
        <p className="muted">This model was registered without evaluation runs.</p>
      </section>
    )
  }
  return (
    <section className="panel model-eval">
      <h2>How well it did</h2>
      <p className="lead">
        Measured before activation on a recorded run with every fault scenario and its ground truth
        {fault?.file ? ` (${fault.file})` : ''}, and on a separate hour without faults
        {normal?.file ? ` (${normal.file})` : ''}.
      </p>

      <dl className="readout eval-readout">
        {fault && (
          <>
            <div>
              <dt>Incidents detected</dt>
              <dd className="number">{fault.incidentsDetected ?? '—'}<small>of {fault.incidents ?? '—'}</small></dd>
            </div>
            <div>
              <dt>Recall (faulty minutes flagged)</dt>
              <dd className="number">{formatPercent(fault.recall)}</dd>
            </div>
            <div>
              <dt>Precision · F1</dt>
              <dd className="number">{formatPercent(fault.precision)}<small>F1 {fixed(fault.f1, 3)}</small></dd>
            </div>
          </>
        )}
        {normal && (
          <div>
            <dt>False alarms without faults</dt>
            <dd className="number">{formatPercent(normal.falseAlarmRate, 2)}
              <small>{normal.falseAlarms ?? '—'} of {formatNumber(normal.windows)} windows</small></dd>
          </div>
        )}
      </dl>

      {fault && fault.quietWindows !== null && (
        <p className="hint">
          Quiet minutes (no fault close by) in the fault run: {fault.quietFalseAlarms ?? 0} of {fault.quietWindows} flagged.
          {normal && Object.keys(normal.severities).length > 0 && (
            <> False alarms in the fault-free hour were graded {Object.entries(normal.severities)
              .map(([s, n]) => `${s.toLowerCase()} (${n})`).join(', ')}.</>
          )}
        </p>
      )}

      {fault && fault.perRecord.length > 0 && (
        <>
          <h3 className="sub-head">Per injected fault</h3>
          <table className="incident-table">
            <thead>
              <tr><th>Fault</th><th>Service</th><th>Minutes flagged</th><th>Flagged after</th></tr>
            </thead>
            <tbody>
              {fault.perRecord.map((r, i) => (
                <tr key={`${r.scenario}-${r.service}-${i}`}>
                  <td>{scenarioName(r.scenario)}</td>
                  <td className="nowrap">{r.service}</td>
                  <td>
                    <span className="coverage" role="img" aria-label={`${r.flagged} of ${r.windows} minutes flagged`}>
                      {Array.from({ length: r.windows }, (_, k) => (
                        <span key={k} className={k < r.flagged ? 'hit' : 'miss'} />
                      ))}
                    </span>
                    <span className="number muted"> {r.flagged}/{r.windows}</span>
                  </td>
                  <td className="number">{r.timeToFlagS === null ? 'not flagged' : `${Math.round(r.timeToFlagS)} s`}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">
            "Flagged after" is measured from the fault's start to the end of the first flagged minute, on a replay.
            Live, the service adds a 5 s grace period, so a fault is reported about half a minute after it starts.
          </p>
        </>
      )}
    </section>
  )
}

function Feedback({ verdicts }: { verdicts: Verdicts }) {
  const { range } = useTimeRange()
  const reviewed = verdicts.confirmed + verdicts.falseAlarms
  return (
    <section className="panel model-feedback">
      <h2>What operators said</h2>
      <p className="lead">Verdicts on anomalies in the last {rangeOption(range).phrase}, from the Anomalies page.</p>
      <dl className="readout eval-readout">
        <div>
          <dt>Real problems</dt>
          <dd className="number">{verdicts.confirmed}</dd>
        </div>
        <div>
          <dt>False alarms</dt>
          <dd className="number">{verdicts.falseAlarms}</dd>
        </div>
        <div>
          <dt>Not reviewed</dt>
          <dd className="number">{verdicts.notReviewed}</dd>
        </div>
      </dl>
      <p className="hint">
        {reviewed === 0
          ? <>No verdicts yet. Mark anomalies on the <Link to="/anomalies?feedback=NONE" className="text-link">Anomalies page</Link> to measure the model on live traffic.</>
          : <>{formatPercent(verdicts.confirmed / reviewed)} of reviewed anomalies were real problems.{' '}
              <Link to="/anomalies?feedback=NONE" className="text-link">Review the rest</Link></>}
      </p>
    </section>
  )
}

function Versions({ models }: { models: Model[] }) {
  return (
    <section className="panel model-section">
      <h2>All versions</h2>
      <table className="versions-table">
        <thead>
          <tr><th>Model</th><th>Algorithm</th><th>Trained</th><th>Threshold</th><th>Training windows</th><th>F1 (fault run)</th><th /></tr>
        </thead>
        <tbody>
          {models.map((m) => (
            <tr key={m.id} className={m.is_active ? 'active-row' : ''}>
              <td className="nowrap">{m.name} <span className="model-version">v{m.version}</span></td>
              <td>{m.algorithm.toUpperCase()}</td>
              <td className="number nowrap">{formatShortDateTime(m.trained_at)}</td>
              <td className="number">{fixed(m.threshold, 2)}</td>
              <td className="number">{formatNumber(m.training_samples)}</td>
              <td className="number">{fixed(readMetrics(m.metrics).faultRun?.f1 ?? null, 3)}</td>
              <td>{m.is_active && <span className="active-pill">Active</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint">Only one model is active at a time. Registering a new version with
        {' '}<code>backend.detection.train --register</code> activates it; restart the detection service to load it.</p>
    </section>
  )
}

export function Models() {
  const { models, verdicts, error } = useModels()
  const active = models?.find((m) => m.is_active) ?? null
  const metrics = active ? readMetrics(active.metrics) : null

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Models</h1>
          <p className="lead">The model that decides what is unusual, how it was trained and how well it works.</p>
        </div>
      </div>

      {error && <p className="error-note">Could not load the models: {error}</p>}
      {models === null && !error && <p className="muted">Loading models…</p>}
      {models !== null && models.length === 0 && (
        <p className="muted">No model is registered yet. Train one with <code>python -m backend.detection.train … --register</code>.</p>
      )}
      {models !== null && models.length > 0 && !active && (
        <p className="error-note">No model is active, so the detection service cannot start. Register or activate a model.</p>
      )}

      {active && metrics && (
        <>
          <ActiveModel model={active} />
          <div className="model-pair">
            <Evaluation fault={metrics.faultRun} normal={metrics.normalRun} />
            {verdicts && <Feedback verdicts={verdicts} />}
          </div>
        </>
      )}
      {models !== null && models.length > 0 && <Versions models={models} />}
    </section>
  )
}