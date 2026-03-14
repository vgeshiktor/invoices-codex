import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ReportCreationScreen } from './ReportCreationScreen';
import type { ReportCreationAdapter } from '../api/reportCreationAdapter';
import type { ReportItem } from '../model/report';

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
  overrides?: Partial<{
    createReport: ReportCreationAdapter['createReport'];
    listReports: ReportCreationAdapter['listReports'];
  }>,
): ReportCreationAdapter => ({
  createReport:
    overrides?.createReport ??
    (async () => ({
      ok: true,
      data: createReport(),
    })),
  listReports:
    overrides?.listReports ??
    (async () => ({
      ok: true,
      data: [],
    })),
});

describe('ReportCreationScreen', () => {
  it('submits report request with selected formats and parsed filters', async () => {
    const created = createReport({ requestedFormats: ['json', 'csv', 'summary_csv', 'pdf'] });
    const createReportMock = vi
      .fn<ReportCreationAdapter['createReport']>()
      .mockResolvedValue({ ok: true, data: created });
    const listReportsMock = vi
      .fn<ReportCreationAdapter['listReports']>()
      .mockResolvedValueOnce({ ok: true, data: [] })
      .mockResolvedValueOnce({ ok: true, data: [created] });

    const adapter = buildAdapter({
      createReport: createReportMock,
      listReports: listReportsMock,
    });

    render(<ReportCreationScreen adapter={adapter} />);

    await screen.findByText('No reports created yet.');

    await userEvent.click(screen.getByLabelText('Summary CSV (.csv)'));
    await userEvent.click(screen.getByLabelText('PDF (.pdf)'));
    await userEvent.type(screen.getByLabelText('Parse job IDs (optional)'), 'parse-1, parse-2, parse-2');
    fireEvent.change(screen.getByLabelText('Filters JSON (optional)'), {
      target: { value: '{"vendor":"acme","min_total":100}' },
    });

    await userEvent.click(screen.getByRole('button', { name: 'Create report' }));

    await waitFor(() => {
      expect(createReportMock).toHaveBeenCalledWith({
        filters: { min_total: 100, vendor: 'acme' },
        formats: ['json', 'csv', 'summary_csv', 'pdf'],
        parseJobIds: ['parse-1', 'parse-2'],
      });
      expect(screen.getByText('Report queued')).toBeInTheDocument();
      expect(screen.getAllByText('report-123')).toHaveLength(2);
    });

    expect(listReportsMock).toHaveBeenCalledTimes(2);
  });

  it('shows API error details when report creation fails', async () => {
    const createReportMock = vi
      .fn<ReportCreationAdapter['createReport']>()
      .mockResolvedValue({
        ok: false,
        error: {
          message: 'report validation failed',
          requestId: 'req-fe-401',
          status: 400,
        },
      });

    const adapter = buildAdapter({ createReport: createReportMock });

    render(<ReportCreationScreen adapter={adapter} />);

    await screen.findByText('No reports created yet.');
    await userEvent.click(screen.getByRole('button', { name: 'Create report' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('report validation failed');
      expect(screen.getByRole('alert')).toHaveTextContent('request-id: req-fe-401');
    });
  });
});
