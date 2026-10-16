'use client';

import type { ApiError } from '@/lib/api';

/**
 * Diagnoses a failure to reach the detection engine.
 *
 * The two cases need opposite fixes, so they get opposite messages:
 *
 * - the engine answered with an error: it is deployed, and something in the
 *   engine or the request is wrong
 * - nothing that speaks JSON answered: the engine is not deployed at this
 *   address, and no amount of retrying will help
 *
 * The old version told the reader to run uvicorn locally, which is unhelpful
 * on a deployed site and actively misleading when the real problem is that the
 * backend service never shipped.
 */
export default function EngineError({ failure }: { failure: ApiError }) {
  const responded = failure.kind === 'http';

  return (
    <div className="rounded-md border border-signal-extreme/40 bg-signal-extreme/10 px-4 py-4 text-sm text-signal-extreme">
      <p className="font-semibold">
        {responded
          ? `The detection engine responded with an error (HTTP ${failure.status}).`
          : 'The detection engine could not be reached.'}
      </p>

      <p className="mt-1 break-words text-signal-extreme/80">{failure.message}</p>

      {responded ? (
        <p className="mt-3 text-xs leading-relaxed text-slate-400">
          The engine is deployed and answering, so this is a request or engine error rather
          than a deployment problem. The message above is the engine&apos;s own response.
        </p>
      ) : (
        <div className="mt-3 space-y-2 text-xs leading-relaxed text-slate-400">
          <p>
            Something answered at{' '}
            <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">{failure.url}</code>{' '}
            but it was not the Python engine&apos;s JSON. On this deployment that almost always
            means the backend service is not running, so the platform&apos;s own 404 page came back
            instead.
          </p>
          <p className="font-semibold text-slate-300">To check, in this order:</p>
          <ol className="ml-4 list-decimal space-y-1">
            <li>
              Open{' '}
              <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">{failure.url}</code>{' '}
              in a new tab. If that is a 404 as well, the engine is not deployed.
            </li>
            <li>
              In the Vercel project, open <strong>Settings</strong> then{' '}
              <strong>Build and Deployment</strong>. The <strong>Framework Preset</strong> has
              to be <strong>Services</strong>, and the <strong>Root Directory</strong> has to
              be the repository root. A project still set to the Next.js preset builds only
              the frontend and silently ignores the Python service.
            </li>
            <li>
              Confirm the repository&apos;s root <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">vercel.json</code>{' '}
              lists both services and rewrites <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">/api</code>{' '}
              to the backend one.
            </li>
            <li>
              Check the deployment&apos;s build log for a Python service build step. If there is
              only a Next.js build, the backend was never part of the deployment.
            </li>
          </ol>
          <p>
            Running locally instead? Start the engine and point the dashboard at it:
            <code className="ml-1 rounded bg-ink-950 px-1.5 py-0.5 font-mono">
              uvicorn main:app --reload --port 8000
            </code>{' '}
            from <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">backend/</code>, with{' '}
            <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">
              NEXT_PUBLIC_API_BASE=http://localhost:8000
            </code>{' '}
            in <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono">frontend/.env.local</code>.
          </p>
        </div>
      )}
    </div>
  );
}
