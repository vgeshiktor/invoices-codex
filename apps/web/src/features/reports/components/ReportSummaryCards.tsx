import { useEffect, useState } from 'react';
import type { ReportArtifact } from '../model/report';
import { downloadReportArtifact } from '../api/reportArtifactDownloads';

type ReportSummaryCardsProps = {
  artifacts: ReportArtifact[];
  reportId: string;
  startDownload?: typeof downloadReportArtifact;
};

type InvoiceRow = {
  currency?: string | null;
  invoice_total?: number | null;
  invoice_vat?: number | null;
};

type SummaryState =
  | {
      status: 'idle' | 'loading';
    }
  | {
      status: 'error';
      message: string;
    }
  | {
      currencyLabel: string;
      invoiceCount: number;
      netBeforeVat: number;
      status: 'ready';
      totalGross: number;
      totalVat: number;
    };

const formatMoney = (value: number, currencyLabel: string): string =>
  `${currencyLabel} ${value.toLocaleString(undefined, {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  })}`;

const parseInvoiceRows = async (blob: Blob): Promise<InvoiceRow[]> => {
  const parsed = JSON.parse(await blob.text()) as unknown;
  if (!Array.isArray(parsed)) {
    return [];
  }

  return parsed.flatMap((item) => {
    if (!item || typeof item !== 'object') {
      return [];
    }

    const record = item as Record<string, unknown>;
    return [
      {
        currency: typeof record.currency === 'string' ? record.currency : null,
        invoice_total: typeof record.invoice_total === 'number' ? record.invoice_total : null,
        invoice_vat: typeof record.invoice_vat === 'number' ? record.invoice_vat : null,
      },
    ];
  });
};

export function ReportSummaryCards({
  artifacts,
  reportId,
  startDownload = downloadReportArtifact,
}: ReportSummaryCardsProps) {
  const jsonArtifact = artifacts.find((artifact) => artifact.format === 'json');
  const [summaryState, setSummaryState] = useState<SummaryState>({
    status: jsonArtifact ? 'loading' : 'idle',
  });

  useEffect(() => {
    if (!jsonArtifact) {
      return;
    }

    let isCancelled = false;

    const load = async () => {
      const result = await startDownload(reportId, 'json');
      if (isCancelled) {
        return;
      }

      if (!result.ok) {
        setSummaryState({
          status: 'error',
          message: result.error.message,
        });
        return;
      }

      const rows = await parseInvoiceRows(result.blob);
      const totals = rows.reduce(
        (acc, row) => {
          acc.invoiceCount += 1;
          acc.totalGross += row.invoice_total ?? 0;
          acc.totalVat += row.invoice_vat ?? 0;
          if (!acc.currencyLabel && row.currency) {
            acc.currencyLabel = row.currency;
          }
          return acc;
        },
        {
          currencyLabel: '',
          invoiceCount: 0,
          totalGross: 0,
          totalVat: 0,
        },
      );

      setSummaryState({
        currencyLabel: totals.currencyLabel || 'Total',
        invoiceCount: totals.invoiceCount,
        netBeforeVat: totals.totalGross - totals.totalVat,
        status: 'ready',
        totalGross: totals.totalGross,
        totalVat: totals.totalVat,
      });
    };

    void load();

    return () => {
      isCancelled = true;
    };
  }, [jsonArtifact, reportId, startDownload]);

  if (!jsonArtifact || summaryState.status === 'idle') {
    return (
      <section className="app__panel">
        <h3>Totals summary</h3>
        <p>JSON artifact not available yet, so totals and VAT cannot be calculated.</p>
      </section>
    );
  }

  if (summaryState.status === 'loading') {
    return (
      <section aria-live="polite" className="app__panel">
        <h3>Totals summary</h3>
        <p>Loading totals from report artifact...</p>
      </section>
    );
  }

  if (summaryState.status === 'error') {
    return (
      <section className="app__panel app__panel--error" role="alert">
        <h3>Could not load totals summary</h3>
        <p>{summaryState.message}</p>
      </section>
    );
  }

  if (summaryState.status !== 'ready') {
    return null;
  }

  return (
    <section className="app__panel">
      <h3>Totals summary</h3>
      <div className="report-summary-grid">
        <article className="report-summary-card">
          <span>Invoices</span>
          <strong>{summaryState.invoiceCount}</strong>
        </article>
        <article className="report-summary-card">
          <span>Total gross</span>
          <strong>{formatMoney(summaryState.totalGross, summaryState.currencyLabel)}</strong>
        </article>
        <article className="report-summary-card">
          <span>Total VAT</span>
          <strong>{formatMoney(summaryState.totalVat, summaryState.currencyLabel)}</strong>
        </article>
        <article className="report-summary-card">
          <span>Net before VAT</span>
          <strong>{formatMoney(summaryState.netBeforeVat, summaryState.currencyLabel)}</strong>
        </article>
      </div>
    </section>
  );
}
