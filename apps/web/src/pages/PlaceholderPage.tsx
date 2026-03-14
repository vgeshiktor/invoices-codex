interface PlaceholderPageProps {
  title: string;
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <section className="app">
      <header className="app__header">
        <h2>{title}</h2>
        <p>This section is intentionally a Week 1 shell placeholder.</p>
      </header>
    </section>
  );
}
