const sections = [
  {
    title: "Acceptance",
    body: "By using ScopeVista, you agree to these Terms and all applicable laws governing insurance and claims data handling.",
  },
  {
    title: "Service Description",
    body: "ScopeVista provides analysis of two Xactimate estimate PDFs and produces comparative reporting outputs for business use.",
  },
  {
    title: "User Responsibilities",
    body: "You are responsible for lawful document use, account security, and verifying outputs before claim or financial decisions.",
  },
  {
    title: "Limitations",
    body: "ScopeVista supports professional workflows but does not replace licensed adjuster judgment, coverage interpretation, or legal advice.",
  },
  {
    title: "Termination",
    body: "We may suspend or terminate access for misuse, policy violations, or security concerns.",
  },
];

export default function TermsPage() {
  return (
    <section className="mx-auto max-w-3xl space-y-8">
      <header className="space-y-3">
        <h1 className="text-4xl font-semibold text-slate-900">Terms of Service</h1>
        <p className="text-sm text-slate-600">
          These terms govern use of ScopeVista for carrier and contractor estimate comparison workflows.
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
