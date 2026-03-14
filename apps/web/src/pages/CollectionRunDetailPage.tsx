import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import type { ApiError } from '../shared/api/client';
import {
  getCollectionJob,
  type GetCollectionJobResult,
} from '../features/collections/api/getCollectionJob';
import type { CollectionJob } from '../features/collections/api/createCollectionJob';

type CollectionRunDetailPageProps = {
  collectionJobId?: string;
  loadCollectionJob?: (collectionJobId: string) => Promise<GetCollectionJobResult>;
  pollIntervalMs?: number;
};

const providerLabel: Record<string, string> = {
  gmail: 'Gmail',
  outlook: 'Outlook',
};

const statusLabel: Record<CollectionJob['status'], string> = {
  failed: 'Failed',
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Succeeded',
};

const formatTimestamp = (value?: string | null): string => {
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

const parseErrorMessages = (value?: string | null): string[] => {
  if (!value) {
    return [];
  }

  try {
    const parsed = JSON.parse(value) as unknown;
    if (Array.isArray(parsed)) {
      return parsed.flatMap((item) => {
        if (typeof item === 'string' && item.trim().length > 0) {
          return [item];
        }

        if (item && typeof item === 'object') {
          const record = item as Record<string, unknown>;
          const provider = typeof record.provider === 'string' ? record.provider : null;
          const message =
            typeof record.error === 'string'
              ? record.error
              : typeof record.message === 'string'
                ? record.message
                : null;
          if (message) {
            return [provider ? `${provider}: ${message}` : message];
          }
        }

        return [];
      });
    }

    if (parsed && typeof parsed === 'object') {
      const record = parsed as Record<string, unknown>;
      const detail =
        typeof record.error === 'string'
          ? record.error
          : typeof record.message === 'string'
            ? record.message
            : null;
      if (detail) {
        return [detail];
      }
    }
  } catch {
    return [value];
  }

  return [value];
};

const isTerminalStatus = (status: CollectionJob['status']): boolean =>
  status === 'succeeded' || status === 'failed';

export function CollectionRunDetailPage({
  collectionJobId,
  loadCollectionJob = getCollectionJob,
  pollIntervalMs = 3000,
}: CollectionRunDetailPageProps) {
  const params = useParams<{ collectionJobId: string }>();
  const resolvedCollectionJobId = collectionJobId ?? params.collectionJobId ?? '';
  const hasCollectionJobId = resolvedCollectionJobId.length > 0;
  const [job, setJob] = useState<CollectionJob | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(hasCollectionJobId);

  useEffect(() => {
    if (!hasCollectionJobId) {
      return;
    }

    let isCancelled = false;
    let timeoutId: number | undefined;

    const load = async () => {
      const result = await loadCollectionJob(resolvedCollectionJobId);
      if (isCancelled) {
        return;
      }

      if (!result.ok) {
        setLoadError(result.error);
        setIsLoading(false);
        return;
      }

      setJob(result.job);
      setLoadError(null);
      setIsLoading(false);

      if (!isTerminalStatus(result.job.status)) {
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
  }, [hasCollectionJobId, loadCollectionJob, pollIntervalMs, resolvedCollectionJobId]);

  const errorMessages = parseErrorMessages(job?.error_message);

  return (
    <section className="app">
      <header className="app__header">
        <h2>Collection run detail</h2>
        <p>Track provider progress, file counts, parse job output, and failures until the run completes.</p>
      </header>

      <section className="app__meta">
        <div>
          <strong>Run ID:</strong> {resolvedCollectionJobId || 'Unknown'}
        </div>
        <div>
          <Link className="app__button" to="/collections">
            Start another run
          </Link>
        </div>
      </section>

      {isLoading && (
        <section aria-live="polite" className="app__panel">
          <p>Loading collection run...</p>
        </section>
      )}

      {!hasCollectionJobId && (
        <section className="app__panel app__panel--error" role="alert">
          <h3>Could not load collection run</h3>
          <p>Collection run ID is required.</p>
        </section>
      )}

      {hasCollectionJobId && !isLoading && loadError && (
        <section className="app__panel app__panel--error" role="alert">
          <h3>Could not load collection run</h3>
          <p>{loadError.message}</p>
        </section>
      )}

      {hasCollectionJobId && !isLoading && !loadError && job && (
        <>
          <section className="collection-run-summary">
            <article className="app__panel">
              <header className="collection-run-summary__header">
                <div>
                  <h3>Status</h3>
                  <p className="report-card__meta">Updated {formatTimestamp(job.updated_at)}</p>
                </div>
                <span className={`status-badge status-badge--${job.status}`}>
                  {statusLabel[job.status]}
                </span>
              </header>
              <dl className="collection-run-summary__stats">
                <div>
                  <dt>Providers</dt>
                  <dd>
                    {job.providers.length > 0
                      ? job.providers.map((provider) => providerLabel[provider] ?? provider).join(', ')
                      : 'Not available'}
                  </dd>
                </div>
                <div>
                  <dt>Month scope</dt>
                  <dd>{job.month_scope}</dd>
                </div>
                <div>
                  <dt>Files discovered</dt>
                  <dd>{job.files_discovered ?? 0}</dd>
                </div>
                <div>
                  <dt>Files downloaded</dt>
                  <dd>{job.files_downloaded ?? 0}</dd>
                </div>
              </dl>
            </article>

            <article className="app__panel">
              <h3>Timeline</h3>
              <dl className="collection-run-summary__timeline">
                <div>
                  <dt>Created</dt>
                  <dd>{formatTimestamp(job.created_at)}</dd>
                </div>
                <div>
                  <dt>Started</dt>
                  <dd>{formatTimestamp(job.started_at)}</dd>
                </div>
                <div>
                  <dt>Finished</dt>
                  <dd>{formatTimestamp(job.finished_at)}</dd>
                </div>
              </dl>
            </article>
          </section>

          <section className="app__panel">
            <h3>Parse jobs</h3>
            {job.parse_job_ids && job.parse_job_ids.length > 0 ? (
              <ul className="collection-run-summary__list">
                {job.parse_job_ids.map((parseJobId) => (
                  <li key={parseJobId}>
                    <code>{parseJobId}</code>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No parse jobs attached yet.</p>
            )}
          </section>

          {errorMessages.length > 0 && (
            <section className="app__panel app__panel--error" role="alert">
              <h3>Provider errors</h3>
              <ul className="collection-run-summary__list">
                {errorMessages.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </section>
  );
}
