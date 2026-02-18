const sections = [
  {
    title: "Data Encryption",
    body: "All network traffic uses TLS. Stored service data is encrypted using managed platform controls.",
  },
  {
    title: "Document Handling",
    body: "Uploaded estimate documents are processed transiently for comparison generation and are not intended for permanent archival storage.",
  },
  {
    title: "Infrastructure",
    body: "ScopeVista is hosted on Render with managed services, environment-scoped secrets, and operational monitoring controls.",
  },
  {
    title: "Compliance Posture",
    body: "We follow least-privilege access patterns and continuous review of operational safeguards for insurance workflow data.",
  },
];

export default function SecurityPage() {
  return (
    <section className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-3">
        <h1 className="text-4xl font-semibold text-slate-900">Security</h1>
        <p className="text-sm text-slate-600">
          Security controls are designed to protect estimate data through transport, processing, and application
          access boundaries.
        </p>
      </header>

      <div className="space-y-6">
        {sections.map((section) => (
          <article key={section.title} className="rounded-2xl border border-slate-200 bg-white p-6">
            <h2 className="text-xl font-semibold text-slate-900">{section.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-700">{section.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
