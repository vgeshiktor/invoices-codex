import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { CollectionRunDetailPage } from './CollectionRunDetailPage';
import type { GetCollectionJobResult } from '../features/collections/api/getCollectionJob';

describe('CollectionRunDetailPage', () => {
  it('loads a collection run and renders live progress details', async () => {
    const loadCollectionJob = vi
      .fn<(collectionJobId: string) => Promise<GetCollectionJobResult>>()
      .mockResolvedValue({
        job: {
          created_at: '2026-03-14T10:00:00.000Z',
          files_discovered: 12,
          files_downloaded: 8,
          finished_at: null,
          id: 'col-123',
          month_scope: '2026-03',
          parse_job_ids: ['parse-1', 'parse-2'],
          providers: ['gmail', 'outlook'],
          started_at: '2026-03-14T10:02:00.000Z',
          status: 'running',
          updated_at: '2026-03-14T10:03:00.000Z',
        },
        ok: true,
      });

    render(
      <MemoryRouter initialEntries={['/collections/col-123']}>
        <Routes>
          <Route
            element={<CollectionRunDetailPage loadCollectionJob={loadCollectionJob} pollIntervalMs={60_000} />}
            path="/collections/:collectionJobId"
          />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(loadCollectionJob).toHaveBeenCalledWith('col-123');
    });

    expect(screen.getByText('Collection run detail')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByText('parse-1')).toBeInTheDocument();
    expect(screen.getByText('parse-2')).toBeInTheDocument();
  });

  it('decodes serialized provider failures', async () => {
    const loadCollectionJob = vi
      .fn<(collectionJobId: string) => Promise<GetCollectionJobResult>>()
      .mockResolvedValue({
        job: {
          created_at: '2026-03-14T10:00:00.000Z',
          error_message: '[{"provider":"gmail","error":"OAuth expired"}]',
          id: 'col-124',
          month_scope: '2026-03',
          providers: ['gmail'],
          status: 'failed',
          updated_at: '2026-03-14T10:05:00.000Z',
        },
        ok: true,
      });

    render(
      <MemoryRouter initialEntries={['/collections/col-124']}>
        <Routes>
          <Route
            element={<CollectionRunDetailPage loadCollectionJob={loadCollectionJob} pollIntervalMs={60_000} />}
            path="/collections/:collectionJobId"
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('gmail: OAuth expired');
  });
});
