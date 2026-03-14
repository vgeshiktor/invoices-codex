export const REPORT_FORMATS = ['json', 'csv', 'summary_csv', 'pdf'] as const;

export type ReportFormat = (typeof REPORT_FORMATS)[number];

export type ReportStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface ReportArtifact {
  id: string;
  format: string;
  bytes: number | null;
  storagePath: string;
}

export interface ReportItem {
  id: string;
  status: ReportStatus;
  requestedFormats: ReportFormat[];
  parseJobIds: string[];
  filters: Record<string, unknown>;
  errorMessage: string | null;
  createdAt: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  artifacts: ReportArtifact[];
}

export interface CreateReportInput {
  formats: ReportFormat[];
  parseJobIds?: string[];
  filters?: Record<string, unknown>;
}
