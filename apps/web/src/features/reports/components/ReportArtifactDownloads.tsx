import { useState } from 'react';
import type { ReportArtifact, ReportFormat } from '../model/report';
import {
  downloadReportArtifact,
  saveDownloadedBlob,
} from '../api/reportArtifactDownloads';

type ReportArtifactDownloadsProps = {
  artifacts: ReportArtifact[];
  reportId: string;
  requestedFormats: ReportFormat[];
  startDownload?: typeof downloadReportArtifact;
  saveBlob?: typeof saveDownloadedBlob;
};

const formatLabel: Record<string, string> = {
  csv: 'CSV',
  json: 'JSON',
  pdf: 'PDF',
  summary_csv: 'Summary CSV',
};

export function ReportArtifactDownloads({
  artifacts,
  reportId,
  requestedFormats,
  startDownload = downloadReportArtifact,
  saveBlob = saveDownloadedBlob,
}: ReportArtifactDownloadsProps) {
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);
  const artifactsByFormat = new Map(artifacts.map((artifact) => [artifact.format, artifact]));
  const formatsToRender = requestedFormats.length > 0 ? requestedFormats : [...artifactsByFormat.keys()];

  const handleDownload = async (format: string) => {
    setDownloadError(null);
    setDownloadingFormat(format);

    const result = await startDownload(reportId, format);
    setDownloadingFormat(null);

    if (!result.ok) {
      setDownloadError(result.error.message);
      return;
    }

    saveBlob(result.blob, result.fileName);
  };

  return (
    <>
      {downloadError && (
        <section className="app__panel app__panel--error" role="alert">
          <h3>Could not download artifact</h3>
          <p>{downloadError}</p>
        </section>
      )}

      <ul className="report-detail__artifact-list">
        {formatsToRender.map((format) => {
          const artifact = artifactsByFormat.get(format);
          const isAvailable = artifact !== undefined;

          return (
            <li className="report-detail__artifact" key={format}>
              <div>
                <strong>{formatLabel[format] ?? format}</strong>
                <p className="report-card__meta">
                  {isAvailable
                    ? artifact.bytes === null
                      ? 'Ready to download'
                      : `${artifact.bytes.toLocaleString()} bytes`
                    : 'Not available yet'}
                </p>
              </div>
              <button
                className="app__button"
                disabled={!isAvailable || downloadingFormat === format}
                onClick={() => void handleDownload(format)}
                type="button"
              >
                {downloadingFormat === format ? 'Downloading...' : 'Download'}
              </button>
            </li>
          );
        })}
      </ul>
    </>
  );
}
