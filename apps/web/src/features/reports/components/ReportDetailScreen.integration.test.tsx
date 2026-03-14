import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { ReportCreationAdapter } from '../api/reportCreationAdapter';
import type { ReportItem } from '../model/report';
import { ReportDetailScreen } from './ReportDetailScreen';

const createReport = (overrides?: Partial<ReportItem>): ReportItem => ({
  artifacts: [],
  createdAt: '2026-03-14T12:00:00.000Z',
  errorMessage: null,
  filters: {},
  finishedAt: null,
  id: 'report-123',
  parseJobIds: ['parse-1'],
  requestedFormats: ['json', 'csv'],
  startedAt: null,
  status: 'queued',
  ...overrides,
});

const buildAdapter = (
  overrides?: Partial<ReportCreationAdapter>,
): ReportCreationAdapter => ({
  createReport: overrides?.createReport ?? (async () => ({ ok: true, data: createReport() })),
  getReport: overrides?.getReport ?? (async () => ({ ok: true, data: createReport() })),
  listReports: overrides?.listReports ?? (async () => ({ ok: true, data: [createReport()] })),
  retryReport: overrides?.retryReport ?? (async () => ({ ok: true, data: createReport({ status: 'queued' }) })),
});

describe('ReportDetailScreen', () => {
  it('loads report detail and renders status metadata', async () => {
    const getReport = vi
      .fn<ReportCreationAdapter['getReport']>()
      .mockResolvedValue(
        {
          ok: true,
          data: createReport({
            artifacts: [{ bytes: 2048, format: 'json', id: 'artifact-1', storagePath: 'artifacts/report.json' }],
            finishedAt: '2026-03-14T12:05:00.000Z',
            status: 'succeeded',
          }),
        },
      );

    render(
      <MemoryRouter initialEntries={['/reports/report-123']}>
        <Routes>
          <Route element={<ReportDetailScreen adapter={buildAdapter({ getReport })} pollIntervalMs={60_000} />} path="/reports/:reportId" />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(getReport).toHaveBeenCalledWith('report-123');
    });

    expect(screen.getByText('Report detail')).toBeInTheDocument();
    expect(screen.getByText('Succeeded')).toBeInTheDocument();
    expect(screen.getByText('JSON')).toBeInTheDocument();
    expect(screen.getByText('2,048 bytes')).toBeInTheDocument();
  });

  it('retries a failed report', async () => {
    const getReport = vi.fn<ReportCreationAdapter['getReport']>().mockResolvedValue({
      ok: true,
      data: createReport({
        errorMessage: 'report generation failed',
        status: 'failed',
      }),
    });
    const retryReport = vi.fn<ReportCreationAdapter['retryReport']>().mockResolvedValue({
      ok: true,
      data: createReport({
        status: 'queued',
      }),
    });

    render(
      <MemoryRouter initialEntries={['/reports/report-123']}>
        <Routes>
          <Route
            element={<ReportDetailScreen adapter={buildAdapter({ getReport, retryReport })} pollIntervalMs={60_000} />}
            path="/reports/:reportId"
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: 'Retry report' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry report' }));

    await waitFor(() => {
      expect(retryReport).toHaveBeenCalledWith('report-123');
      expect(screen.getByText('Queued')).toBeInTheDocument();
    });
  });
});
