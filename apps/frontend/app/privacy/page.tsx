const sections = [
  {
    title: "Data Collection",
    body: "We collect account details, usage metadata, and uploaded estimate documents required to process bid comparisons.",
  },
  {
    title: "Data Usage",
    body: "Data is used to generate carrier-vs-contractor comparison outputs, maintain account access, and improve service reliability.",
  },
  {
    title: "Data Storage",
    body: "Uploaded Xactimate PDFs are processed for report generation and are not retained as long-term customer document archives.",
  },
  {
    title: "Your Rights",
    body: "You may request access, correction, or deletion of account data by contacting our team.",
  },
  {
    title: "Contact",
    body: "For privacy questions, contact hello@scopevista.app.",
  },
];

export default function PrivacyPage() {
  return (
    <section className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-3">
        <h1 className="text-4xl font-semibold text-slate-900">Privacy Policy</h1>
        <p className="text-sm text-slate-600">
          ScopeVista processes Xactimate estimate data to generate comparison reports. Data is encrypted in transit
          and at rest through managed infrastructure.
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
