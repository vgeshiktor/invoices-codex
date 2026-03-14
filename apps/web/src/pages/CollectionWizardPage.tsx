import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  createCollectionJob,
  type CollectionJob,
  type CollectionProvider,
  type CreateCollectionJobRequest,
  type CreateCollectionJobResult,
} from '../features/collections/api/createCollectionJob';

type CollectionWizardPageProps = {
  submitCollectionJob?: (payload: CreateCollectionJobRequest) => Promise<CreateCollectionJobResult>;
};

const COLLECTION_PROVIDERS: CollectionProvider[] = ['gmail', 'outlook'];

const providerLabel: Record<CollectionProvider, string> = {
  gmail: 'Gmail',
  outlook: 'Outlook',
};

const toCurrentMonthScope = (date: Date): string => {
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  return `${date.getFullYear()}-${month}`;
};

const isValidMonthScope = (value: string): boolean => /^\d{4}-(0[1-9]|1[0-2])$/.test(value);

const upsertProvider = (
  providers: CollectionProvider[],
  provider: CollectionProvider,
  isChecked: boolean,
): CollectionProvider[] => {
  if (isChecked) {
    return providers.includes(provider) ? providers : [...providers, provider];
  }

  return providers.filter((item) => item !== provider);
};

export function CollectionWizardPage({ submitCollectionJob = createCollectionJob }: CollectionWizardPageProps) {
  const [monthScope, setMonthScope] = useState<string>(toCurrentMonthScope(new Date()));
  const [providers, setProviders] = useState<CollectionProvider[]>(['gmail']);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [createdJob, setCreatedJob] = useState<CollectionJob | null>(null);
  const [requestId, setRequestId] = useState<string | undefined>(undefined);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setCreatedJob(null);
    setRequestId(undefined);

    if (!isValidMonthScope(monthScope)) {
      setErrorMessage('Month scope must use YYYY-MM format.');
      return;
    }

    if (providers.length === 0) {
      setErrorMessage('Select at least one provider.');
      return;
    }

    setIsSubmitting(true);

    const response = await submitCollectionJob({
      month_scope: monthScope,
      providers,
    });

    if (!response.ok) {
      setErrorMessage(response.error.message);
      setIsSubmitting(false);
      return;
    }

    setCreatedJob(response.job);
    setRequestId(response.requestId);
    setIsSubmitting(false);
  };

  return (
    <section className="app">
      <header className="app__header">
        <h2>Collect current month</h2>
        <p>Start a collection run in one step with provider selection and month defaults.</p>
      </header>

      <form className="collection-wizard" onSubmit={handleSubmit}>
        <fieldset className="collection-wizard__fieldset">
          <legend>Providers</legend>
          <div className="collection-wizard__providers">
            {COLLECTION_PROVIDERS.map((provider) => (
              <label className="collection-wizard__provider-option" key={provider}>
                <input
                  checked={providers.includes(provider)}
                  name={`provider-${provider}`}
                  onChange={(event) => {
                    setProviders((currentProviders) =>
                      upsertProvider(currentProviders, provider, event.target.checked),
                    );
                  }}
                  type="checkbox"
                />
                <span>{providerLabel[provider]}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <label className="collection-wizard__month">
          <span>Month scope</span>
          <input
            className="collection-wizard__month-input"
            name="month_scope"
            onChange={(event) => setMonthScope(event.target.value)}
            type="month"
            value={monthScope}
          />
        </label>

        <button className="app__button" disabled={isSubmitting} type="submit">
          {isSubmitting ? 'Starting run...' : 'Start collection run'}
        </button>
      </form>

      {errorMessage && (
        <section className="app__panel app__panel--error" role="alert">
          <h3>Could not start collection run</h3>
          <p>{errorMessage}</p>
        </section>
      )}

      {createdJob && (
        <section className="app__panel">
          <h3>Run started</h3>
          <p>
            Collection run <code>{createdJob.id}</code> is now <strong>{createdJob.status}</strong>.
          </p>
          <p>
            Providers: {createdJob.providers.map((provider) => providerLabel[provider]).join(', ')}
          </p>
          <p>Month scope: {createdJob.month_scope}</p>
          {requestId ? <p>request-id: {requestId}</p> : null}
          <p>
            <Link className="app__button" to={`/collections/${createdJob.id}`}>
              Open run detail
            </Link>
          </p>
        </section>
      )}
    </section>
  );
}
