import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReportSummaryCards } from './ReportSummaryCards';

describe('ReportSummaryCards', () => {
  it('loads totals and VAT from the JSON artifact', async () => {
    const startDownload = vi.fn().mockResolvedValue({
      ok: true,
      blob: new Blob(
        [
          JSON.stringify([
            { currency: 'ILS', invoice_total: 118, invoice_vat: 18 },
            { currency: 'ILS', invoice_total: 236, invoice_vat: 36 },
          ]),
        ],
        { type: 'application/json' },
      ),
      fileName: 'report-123.json',
    });

    render(
      <ReportSummaryCards
        artifacts={[{ bytes: 1024, format: 'json', id: 'artifact-1', storagePath: 'artifacts/report.json' }]}
        reportId="report-123"
        startDownload={startDownload}
      />,
    );

    await waitFor(() => {
      expect(startDownload).toHaveBeenCalledWith('report-123', 'json');
      expect(screen.getByText('Invoices')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('ILS 354.00')).toBeInTheDocument();
      expect(screen.getByText('ILS 54.00')).toBeInTheDocument();
      expect(screen.getByText('ILS 300.00')).toBeInTheDocument();
    });
  });

  it('shows a waiting message when JSON artifact is unavailable', () => {
    render(<ReportSummaryCards artifacts={[]} reportId="report-123" />);

    expect(screen.getByText('JSON artifact not available yet, so totals and VAT cannot be calculated.')).toBeInTheDocument();
  });
});
