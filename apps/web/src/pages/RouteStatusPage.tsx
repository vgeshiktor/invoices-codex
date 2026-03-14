interface RouteStatusPageProps {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function RouteStatusPage({
  title,
  message,
  actionLabel,
  onAction,
}: RouteStatusPageProps) {
  return (
    <main className="route-status">
      <h1>{title}</h1>
      <p>{message}</p>
      {actionLabel && onAction ? (
        <button className="shell__button" onClick={onAction} type="button">
          {actionLabel}
        </button>
      ) : null}
    </main>
  );
}
