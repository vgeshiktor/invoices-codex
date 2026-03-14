import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { ApiError } from '../../../shared/api/client';
import {
  reportCreationAdapter,
  type ReportCreationAdapter,
} from '../api/reportCreationAdapter';
import type { ReportArtifact, ReportItem, ReportStatus } from '../model/report';
import { isTerminalReportStatus } from '../model/report';

type ReportDetailScreenProps = {
  adapter?: ReportCreationAdapter;
  pollIntervalMs?: number;
  reportId?: string;
};

const statusLabel: Record<ReportStatus, string> = {
  failed: 'Failed',
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Succeeded',
};

const formatTimestamp = (value: string | null): string => {
  if (!value) {
    return 'Not available yet';
  }

  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(parsed));
};

const formatArtifactBytes = (artifact: ReportArtifact): string =>
  artifact.bytes === null ? 'Size unavailable' : `${artifact.bytes.toLocaleString()} bytes`;

export function ReportDetailScreen({
  adapter = reportCreationAdapter,
  pollIntervalMs = 4000,
  reportId,
}: ReportDetailScreenProps) {
  const params = useParams<{ reportId: string }>();
  const resolvedReportId = reportId ?? params.reportId ?? '';
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(resolvedReportId.length > 0);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [report, setReport] = useState<ReportItem | null>(null);

  useEffect(() => {
    if (resolvedReportId.length === 0) {
      return;
    }

    let isCancelled = false;
    let timeoutId: number | undefined;

    const load = async () => {
      const result = await adapter.getReport(resolvedReportId);
      if (isCancelled) {
        return;
      }

      if (!result.ok) {
        setLoadError(result.error);
        setIsLoading(false);
        return;
      }

      setReport(result.data);
      setLoadError(null);
      setIsLoading(false);

      if (!isTerminalReportStatus(result.data.status)) {
        timeoutId = window.setTimeout(() => {
          void load();
        }, pollIntervalMs);
      }
    };

    void load();

    return () => {
      isCancelled = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [adapter, pollIntervalMs, resolvedReportId]);

  const retry = async () => {
    if (!report) {
      return;
    }

    setIsRetrying(true);
    const result = await adapter.retryReport(report.id);
    setIsRetrying(false);

    if (!result.ok) {
      setLoadError(result.error);
      return;
    }

    setReport(result.data);
    setLoadError(null);
  };

  return (
    <section className="app">
      <header className="app__header">
        <h2>Report detail</h2>
        <p>Track live report status transitions, inspect artifacts, and retry failed work.</p>
      </header>

      <section className="app__meta">
        <div>
          <strong>Report ID:</strong> {resolvedReportId || 'Unknown'}
        </div>
        <div className="app__actions">
          <Link className="app__button" to="/reports">
            Back to reports
          </Link>
        </div>
      </section>

      {resolvedReportId.length === 0 && (
        <section className="app__panel app__panel--error" role="alert">
          <h3>Could not load report detail</h3>
          <p>Report ID is required.</p>
        </section>
      )}

      {isLoading && (
        <section aria-live="polite" className="app__panel">
          <p>Loading report detail...</p>
        </section>
      )}

      {!isLoading && loadError && (
        <section className="app__panel app__panel--error" role="alert">
          <h3>Could not load report detail</h3>
          <p>{loadError.message}</p>
        </section>
      )}

      {!isLoading && !loadError && report && (
        <>
          <section className="report-detail-grid">
            <article className="app__panel">
              <header className="report-detail__header">
                <div>
                  <h3>Status</h3>
                  <p className="report-card__meta">Refreshes automatically while work is still running.</p>
                </div>
                <span className={`status-badge status-badge--${report.status}`}>
                  {statusLabel[report.status]}
                </span>
              </header>
              <dl className="report-detail__stats">
                <div>
                  <dt>Requested formats</dt>
                  <dd>{report.requestedFormats.length > 0 ? report.requestedFormats.join(', ') : 'none'}</dd>
                </div>
                <div>
                  <dt>Artifacts ready</dt>
                  <dd>{report.artifacts.length}</dd>
                </div>
                <div>
                  <dt>Created</dt>
                  <dd>{formatTimestamp(report.createdAt)}</dd>
                </div>
                <div>
                  <dt>Started</dt>
                  <dd>{formatTimestamp(report.startedAt)}</dd>
                </div>
                <div>
                  <dt>Finished</dt>
                  <dd>{formatTimestamp(report.finishedAt)}</dd>
                </div>
              </dl>
            </article>

            <article className="app__panel">
              <h3>Request scope</h3>
              <p className="report-card__meta">
                Parse jobs: {report.parseJobIds.length > 0 ? report.parseJobIds.join(', ') : 'all available'}
              </p>
              <pre>{JSON.stringify(report.filters, null, 2)}</pre>
            </article>
          </section>

          <section className="app__panel">
            <div className="report-detail__subheader">
              <h3>Artifacts</h3>
              <button className="app__button" onClick={() => window.location.reload()} type="button">
                Refresh page
              </button>
            </div>
            {report.artifacts.length === 0 ? (
              <p>No artifacts available yet.</p>
            ) : (
              <ul className="report-detail__artifact-list">
                {report.artifacts.map((artifact) => (
                  <li className="report-detail__artifact" key={artifact.id}>
                    <strong>{artifact.format}</strong>
                    <span>{formatArtifactBytes(artifact)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {report.errorMessage && (
            <section className="app__panel app__panel--error" role="alert">
              <h3>Report error</h3>
              <p>{report.errorMessage}</p>
            </section>
          )}

          {report.status === 'failed' && (
            <section className="app__actions">
              <button className="app__button" disabled={isRetrying} onClick={() => void retry()} type="button">
                {isRetrying ? 'Retrying report...' : 'Retry report'}
              </button>
            </section>
          )}
        </>
      )}
    </section>
  );
}
