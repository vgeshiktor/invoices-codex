import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { CollectionWizardPage } from './CollectionWizardPage';
import type {
  CreateCollectionJobRequest,
  CreateCollectionJobResult,
} from '../features/collections/api/createCollectionJob';

const toCurrentMonthScope = (): string => {
  const now = new Date();
  return `${now.getFullYear()}-${`${now.getMonth() + 1}`.padStart(2, '0')}`;
};

describe('CollectionWizardPage', () => {
  it('submits default current-month payload and shows started run details', async () => {
    const submitCollectionJob = vi
      .fn<(payload: CreateCollectionJobRequest) => Promise<CreateCollectionJobResult>>()
      .mockResolvedValue({
        job: {
          id: 'col-happy-1',
          month_scope: toCurrentMonthScope(),
          providers: ['gmail'],
          status: 'queued',
        },
        ok: true,
        requestId: 'req-col-happy',
        status: 201,
      });

    render(
      <MemoryRouter>
        <CollectionWizardPage submitCollectionJob={submitCollectionJob} />
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Start collection run' }));

    await waitFor(() => {
      expect(submitCollectionJob).toHaveBeenCalledWith({
        month_scope: toCurrentMonthScope(),
        providers: ['gmail'],
      });
      expect(screen.getByText('Run started')).toBeInTheDocument();
      expect(screen.getByText(/col-happy-1/)).toBeInTheDocument();
      expect(screen.getByText(/queued/)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Open run detail' })).toHaveAttribute(
        'href',
        '/collections/col-happy-1',
      );
    });
  });

  it('shows error state when submit request fails', async () => {
    const submitCollectionJob = vi
      .fn<(payload: CreateCollectionJobRequest) => Promise<CreateCollectionJobResult>>()
      .mockResolvedValue({
        error: {
          message: 'collection queue unavailable',
        },
        ok: false,
      });

    render(
      <MemoryRouter>
        <CollectionWizardPage submitCollectionJob={submitCollectionJob} />
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Start collection run' }));

    await waitFor(() => {
      expect(submitCollectionJob).toHaveBeenCalledTimes(1);
      expect(screen.getByRole('alert')).toHaveTextContent('collection queue unavailable');
    });
  });
});
