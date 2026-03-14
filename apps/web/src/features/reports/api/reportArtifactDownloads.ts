import { frontendEnv } from '../../../shared/config/env';
import { normalizeApiError, type ApiError } from '../../../shared/api/client';

export type ReportArtifactDownloadResult =
  | {
      ok: true;
      blob: Blob;
      fileName: string;
    }
  | {
      ok: false;
      error: ApiError;
    };

const extensionByFormat: Record<string, string> = {
  csv: 'csv',
  json: 'json',
  pdf: 'pdf',
  summary_csv: 'summary.csv',
};

const buildFileName = (reportId: string, format: string): string =>
  `${reportId}.${extensionByFormat[format] ?? format}`;

export const saveDownloadedBlob = (blob: Blob, fileName: string) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const downloadReportArtifact = async (
  reportId: string,
  format: string,
): Promise<ReportArtifactDownloadResult> => {
  try {
    const response = await fetch(
      `${frontendEnv.apiBaseUrl}/v1/reports/${encodeURIComponent(reportId)}/download?format=${encodeURIComponent(format)}`,
      {
        headers: frontendEnv.apiKey
          ? {
              'X-API-Key': frontendEnv.apiKey,
            }
          : undefined,
      },
    );

    if (!response.ok) {
      return {
        ok: false,
        error: await normalizeApiError(new Error(`Download failed with HTTP ${response.status}`), response),
      };
    }

    return {
      ok: true,
      blob: await response.blob(),
      fileName: buildFileName(reportId, format),
    };
  } catch (error) {
    return {
      ok: false,
      error: await normalizeApiError(error),
    };
  }
};
