import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import type { ApiError } from '../../../shared/api/client';
import { frontendEnv } from '../../../shared/config/env';
import { safeJsonStringify } from '../../../shared/utils/serialization';
import {
  reportCreationAdapter,
  type ReportCreationAdapter,
} from '../api/reportCreationAdapter';
import {
  REPORT_FORMATS,
  type CreateReportInput,
  type ReportFormat,
  type ReportItem,
} from '../model/report';

const formatLabel: Record<ReportFormat, string> = {
  csv: 'CSV (.csv)',
  json: 'JSON (.json)',
  pdf: 'PDF (.pdf)',
  summary_csv: 'Summary CSV (.csv)',
};

const statusLabel: Record<ReportItem['status'], string> = {
  failed: 'Failed',
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Succeeded',
};

const parseJobIdsFromInput = (value: string): string[] => {
  const seen = new Set<string>();
  const result: string[] = [];

  for (const rawId of value.split(/[\n,\s]+/)) {
    const id = rawId.trim();
    if (id.length === 0 || seen.has(id)) {
      continue;
    }
    seen.add(id);
    result.push(id);
  }

  return result;
};

const parseFiltersFromInput = (
  value: string,
): { ok: true; value: Record<string, unknown> | undefined } | { ok: false; message: string } => {
  if (value.trim().length === 0) {
    return { ok: true, value: undefined };
  }

  try {
    const parsed = JSON.parse(value) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { ok: false, message: 'Filters must be a JSON object (for example {"vendor":"acme"}).' };
    }

    return {
      ok: true,
      value: parsed as Record<string, unknown>,
    };
  } catch {
    return { ok: false, message: 'Filters must be valid JSON.' };
  }
};

interface ReportCreationScreenProps {
  adapter?: ReportCreationAdapter;
}

type ReportsLoadState = 'loading' | 'ready' | 'error';

export function ReportCreationScreen({
  adapter = reportCreationAdapter,
}: ReportCreationScreenProps) {
  const [loadState, setLoadState] = useState<ReportsLoadState>('loading');
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [reports, setReports] = useState<ReportItem[]>([]);

  const [selectedFormats, setSelectedFormats] = useState<Set<ReportFormat>>(
    () => new Set<ReportFormat>(['json', 'csv']),
  );
  const [parseJobIdsInput, setParseJobIdsInput] = useState('');
  const [filtersInput, setFiltersInput] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [createdReport, setCreatedReport] = useState<ReportItem | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const includeErrorStack = frontendEnv.appEnv !== 'production';

  const loadReports = useCallback(async () => {
    setLoadError(null);
    setLoadState('loading');

    const result = await adapter.listReports();
    if (!result.ok) {
      setLoadError(result.error);
      setLoadState('error');
      return;
    }

    setReports(result.data);
    setLoadState('ready');
  }, [adapter]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  const sortedReports = useMemo(
    () =>
      [...reports].sort((left, right) => {
        const leftTime = left.createdAt ? Date.parse(left.createdAt) : 0;
        const rightTime = right.createdAt ? Date.parse(right.createdAt) : 0;
        return rightTime - leftTime;
      }),
    [reports],
  );

  const orderedSelectedFormats = useMemo(
    () => REPORT_FORMATS.filter((format) => selectedFormats.has(format)),
    [selectedFormats],
  );

  const toggleFormat = (format: ReportFormat) => {
    setSelectedFormats((currentFormats) => {
      const nextFormats = new Set(currentFormats);
      if (nextFormats.has(format)) {
        nextFormats.delete(format);
      } else {
        nextFormats.add(format);
      }
      return nextFormats;
    });
  };

  const submitReport = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setSubmitError(null);

    if (orderedSelectedFormats.length === 0) {
      setFormError('Select at least one output format.');
      return;
    }

    const parsedFilters = parseFiltersFromInput(filtersInput);
    if (!parsedFilters.ok) {
      setFormError(parsedFilters.message);
      return;
    }

    const parseJobIds = parseJobIdsFromInput(parseJobIdsInput);
    const payload: CreateReportInput = {
      filters: parsedFilters.value,
      formats: orderedSelectedFormats,
      parseJobIds: parseJobIds.length > 0 ? parseJobIds : undefined,
    };

    setIsSubmitting(true);
    try {
      const result = await adapter.createReport(payload);
      if (!result.ok) {
        setSubmitError(result.error);
        return;
      }

      setCreatedReport(result.data);
      await loadReports();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="app">
      <header className="app__header">
        <h2>Create report</h2>
        <p>Request report generation with selected output formats and optional filters.</p>
      </header>

      <section className="app__meta">
        <div>
          <strong>Supported formats:</strong> {REPORT_FORMATS.join(', ')}
        </div>
        <div>
          <strong>Runtime:</strong> {frontendEnv.appEnv}
        </div>
      </section>

      <form className="report-builder" onSubmit={(event) => void submitReport(event)}>
        <fieldset className="report-builder__fieldset">
          <legend>Output formats</legend>
          <div className="report-builder__format-grid">
            {REPORT_FORMATS.map((format) => (
              <label className="report-builder__checkbox" key={format}>
                <input
                  checked={selectedFormats.has(format)}
                  disabled={isSubmitting}
                  onChange={() => {
                    toggleFormat(format);
                  }}
                  type="checkbox"
                />
                {formatLabel[format]}
              </label>
            ))}
          </div>
        </fieldset>

        <label className="report-builder__field">
          <span>Parse job IDs (optional)</span>
          <textarea
            disabled={isSubmitting}
            onChange={(event) => {
              setParseJobIdsInput(event.target.value);
            }}
            placeholder="parse-job-1, parse-job-2"
            rows={2}
            value={parseJobIdsInput}
          />
        </label>

        <label className="report-builder__field">
          <span>Filters JSON (optional)</span>
          <textarea
            disabled={isSubmitting}
            onChange={(event) => {
              setFiltersInput(event.target.value);
            }}
            placeholder='{"vendor": "acme", "min_total": 100}'
            rows={4}
            value={filtersInput}
          />
        </label>

        <div className="report-builder__actions">
          <button className="app__button" disabled={isSubmitting} type="submit">
            {isSubmitting ? 'Submitting report...' : 'Create report'}
          </button>
        </div>
      </form>

      {formError && (
        <section className="app__panel app__panel--error" role="alert">
          <h3>Validation error</h3>
          <p>{formError}</p>
        </section>
      )}

      {submitError && (
        <section className="app__panel app__panel--error" role="alert">
          <h3>Could not create report</h3>
          <p>{submitError.message}</p>
          <p>
            {submitError.status ? `HTTP ${submitError.status}` : 'No HTTP response'}
            {submitError.requestId ? ` | request-id: ${submitError.requestId}` : ''}
          </p>
          {includeErrorStack &&
            submitError.cause !== null &&
            submitError.cause !== undefined && (
            <pre>{safeJsonStringify(submitError.cause)}</pre>
            )}
        </section>
      )}

      {createdReport && (
        <section className="app__panel">
          <h3>Report queued</h3>
          <p>
            Report <strong>{createdReport.id}</strong> is currently{' '}
            <strong>{statusLabel[createdReport.status]}</strong>.
          </p>
        </section>
      )}

      <section className="report-list">
        <header className="report-list__header">
          <h3>Recent reports</h3>
          <button className="app__button" onClick={() => void loadReports()} type="button">
            Refresh
          </button>
        </header>

        {loadState === 'loading' && (
          <section aria-live="polite" className="app__panel">
            <p>Loading reports...</p>
          </section>
        )}

        {loadState === 'error' && loadError && (
          <section className="app__panel app__panel--error" role="alert">
            <h3>Could not load reports</h3>
            <p>{loadError.message}</p>
            <button className="app__button" onClick={() => void loadReports()} type="button">
              Retry
            </button>
          </section>
        )}

        {loadState === 'ready' && sortedReports.length === 0 && (
          <section className="app__panel">
            <p>No reports created yet.</p>
          </section>
        )}

        {loadState === 'ready' && sortedReports.length > 0 && (
          <div className="report-list__grid">
            {sortedReports.map((report) => (
              <article className="report-card" key={report.id}>
                <header className="report-card__header">
                  <h4>{report.id}</h4>
                  <span className={`status-badge status-badge--${report.status}`}>
                    {statusLabel[report.status]}
                  </span>
                </header>
                <p className="report-card__meta">
                  Formats: {report.requestedFormats.length > 0 ? report.requestedFormats.join(', ') : 'none'}
                </p>
                <p className="report-card__meta">Artifacts: {report.artifacts.length}</p>
                {report.errorMessage && <p className="provider-card__error">{report.errorMessage}</p>}
              </article>
            ))}
          </div>
        )}
      </section>
    </section>
  );
}
