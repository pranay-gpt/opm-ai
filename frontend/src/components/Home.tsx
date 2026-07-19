import { useCurrentJob, useJobHistory, useLastResults, useLastBuildResponse } from '../stores/useAppStore';

export default function Home() {
  const currentJob = useCurrentJob();
  const jobHistory = useJobHistory();
  const lastResults = useLastResults();
  const lastBuildResponse = useLastBuildResponse();

  const stats = [
    { label: 'Decks Built', value: jobHistory.length, icon: <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg> },
    { label: 'Simulations Run', value: jobHistory.filter((j) => j.status === 'completed').length, icon: <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg> },
    { label: 'Last Run', value: lastResults ? 'Complete' : '-', icon: <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg> },
    { label: 'Active Job', value: currentJob?.status ?? 'None', icon: <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg> },
  ];

  const recentJobs = jobHistory.slice(0, 5);

  return (
    <div className="h-full overflow-y-auto space-y-6">
      {/* Hero Section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-textPrimary">End-to-End Geo Workflow</h1>
            <p className="text-textSecondary mt-1">
              Build, validate, simulate, and analyze OPM Flow decks with AI assistance
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-primary/10 border border-primary/20">
            <span className="w-2 h-2 rounded-full bg-success" />
            <span className="text-sm font-medium text-primary">Operational</span>
          </div>
        </div>

        {/* 3D Illustration Placeholder */}
        <div className="aspect-video rounded-lg bg-surface border border-border flex items-center justify-center relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-warning/5" />
          <div className="relative z-10 text-center p-8">
            <div className="w-32 h-32 mx-auto mb-4 rounded-xl bg-base border border-border flex items-center justify-center relative">
              <svg className="w-16 h-16 text-primary/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-textPrimary mb-2">3D Geomodel Visualization</h2>
            <p className="text-textSecondary max-w-md mx-auto">
              Interactive reservoir grid with property mapping, well trajectories, and simulation results
            </p>
          </div>
        </div>
      </section>

      {/* Stats Grid */}
      <section>
        <h2 className="text-lg font-semibold text-textPrimary mb-4">Workflow Status</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((stat) => (
            <div key={stat.label} className="card p-4">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{stat.icon}</span>
                <div>
                  <div className="text-2xl font-bold text-textPrimary">{stat.value}</div>
                  <div className="text-xs text-textSecondary">{stat.label}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Capability Cards */}
      <section>
        <h2 className="text-lg font-semibold text-textPrimary mb-4">Capabilities</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            {
              title: 'Static Model Intake',
              desc: 'Import and validate geomodel grids, properties, and fault data from industry formats.',
              link: '/deck-builder',
            },
            {
              title: 'Geomodel Validation',
              desc: 'Check grid topology, property consistency, and physical plausibility before simulation.',
              link: '/linter',
            },
            {
              title: 'Deck Generation',
              desc: 'AI-assisted OPM Flow deck creation from natural language descriptions.',
              link: '/deck-builder',
            },
            {
              title: 'Simulation Setup',
              desc: 'Configure wells, controls, schedules, and run OPM Flow simulations with job monitoring.',
              link: '/simulator',
            },
            {
              title: 'Result Interpretation',
              desc: 'KPIs, production plots, pressure profiles, and ResInsight integration for analysis.',
              link: '/results',
            },
          ].map((cap) => (
            <div key={cap.title} className="card p-5 card-hover">
              <h3 className="font-semibold text-textPrimary mb-2">{cap.title}</h3>
              <p className="text-sm text-textSecondary mb-4">{cap.desc}</p>
              <a
                href={cap.link}
                className="text-sm font-medium text-primary hover:text-primaryHover flex items-center gap-1"
              >
                Learn More →
              </a>
            </div>
          ))}
        </div>
      </section>

      {/* Recent Jobs */}
      {recentJobs.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-textPrimary">Recent Jobs</h2>
            <a href="/simulator" className="text-sm font-medium text-primary hover:text-primaryHover">
              View All →
            </a>
          </div>
          <div className="card overflow-hidden">
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Job ID</th>
                    <th>Status</th>
                    <th>Deck</th>
                    <th>Duration</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {recentJobs.map((job) => (
                    <tr key={job.job_id}>
                      <td className="font-mono text-xs">{job.job_id.slice(0, 8)}...</td>
                      <td>
                        <span
                          className={`badge ${
                            job.status === 'completed'
                              ? 'badge-success'
                              : job.status === 'failed'
                              ? 'badge-error'
                              : job.status === 'running'
                              ? 'badge-warning'
                              : 'badge-outline'
                          }`}
                        >
                          {job.status}
                        </span>
                      </td>
                      <td className="text-textSecondary">
                        {job.result?.output_dir ? job.result.output_dir.split('/').pop() : '-'}
                      </td>
                      <td className="text-textSecondary">-</td>
                      <td>
                        <a
                          href={`/results?id=${job.job_id}`}
                          className="text-sm text-primary hover:text-primaryHover"
                        >
                          View
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* Quick Actions */}
      <section>
        <h2 className="text-lg font-semibold text-textPrimary mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a
            href="/deck-builder"
            className="card p-5 card-hover flex flex-col items-center text-center gap-3"
          >
            <span className="text-3xl"><svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg></span>
            <span className="font-semibold text-textPrimary">Build a Deck</span>
            <span className="text-sm text-textSecondary">Describe your model in plain English</span>
          </a>
          <a
            href="/deck-editor"
            className="card p-5 card-hover flex flex-col items-center text-center gap-3"
          >
            <span className="text-3xl"><svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 4H9a2 2 0 00-2 2v12a2 2 0 002 2h2a2 2 0 002-2V6a2 2 0 00-2-2z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 10h10M7 14h10M7 18h10" /></svg></span>
            <span className="font-semibold text-textPrimary">Edit a Deck</span>
            <span className="text-sm text-textSecondary">Syntax-highlighted Monaco editor</span>
          </a>
          <a
            href="/simulator"
            className="card p-5 card-hover flex flex-col items-center text-center gap-3"
          >
            <span className="text-3xl"><svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg></span>
            <span className="font-semibold text-textPrimary">Run Simulation</span>
            <span className="text-sm text-textSecondary">Submit jobs and monitor progress</span>
          </a>
        </div>
      </section>
    </div>
  );
}