import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ReportArtifactDownloads } from './ReportArtifactDownloads';

describe('ReportArtifactDownloads', () => {
  it('renders download buttons for requested formats and disables missing artifacts', async () => {
    render(
      <ReportArtifactDownloads
        artifacts={[{ bytes: 2048, format: 'json', id: 'artifact-1', storagePath: 'artifacts/report.json' }]}
        reportId="report-123"
        requestedFormats={['json', 'csv']}
      />,
    );

    const buttons = screen.getAllByRole('button', { name: 'Download' });

    expect(buttons[0]).toBeEnabled();
    expect(screen.getByText('JSON')).toBeInTheDocument();
    expect(screen.getByText('CSV')).toBeInTheDocument();
    expect(buttons[1]).toBeDisabled();
  });

  it('downloads an available artifact', async () => {
    const startDownload = vi.fn().mockResolvedValue({
      ok: true,
      blob: new Blob(['{"ok":true}'], { type: 'application/json' }),
      fileName: 'report-123.json',
    });
    const saveBlob = vi.fn();

    render(
      <ReportArtifactDownloads
        artifacts={[{ bytes: 2048, format: 'json', id: 'artifact-1', storagePath: 'artifacts/report.json' }]}
        reportId="report-123"
        requestedFormats={['json']}
        saveBlob={saveBlob}
        startDownload={startDownload}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Download' }));

    await waitFor(() => {
      expect(startDownload).toHaveBeenCalledWith('report-123', 'json');
      expect(saveBlob).toHaveBeenCalled();
    });
  });
});
