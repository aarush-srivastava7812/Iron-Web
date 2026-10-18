# Voyara free demo deployment

The public Vite website runs on Vercel. A Render free web service runs the travel
API and a loopback-only FalkorDB process in one container. The separate dashboard
is excluded from both bundles; its files and relay configuration are unchanged.

## Render

Create a Docker web service from the repository root and deployment branch,
using the root `Dockerfile`. `Dockerfile.dockerignore` excludes private files,
runtime data and dashboard code while leaving the relay's root `.dockerignore`
unchanged. Use one service instance and one web worker.

Set `SECRET_KEY` privately to at least 32 random characters. Environment variables
or Render's `/etc/secrets/voyara.env` secret file are supported. The launcher seeds
the synthetic catalog and binds to `0.0.0.0:$PORT`. Secure cookies are enabled
and local developer sign-in is disabled. Set `CORS_ORIGINS` to the Vercel website
origin. `/health` is the HTTP health-check endpoint.

Set `NVIDIA_API_KEY` privately to enable the hosted travel agents. The existing
auto mode explicitly labels offline behavior when no credential is available.
Set `GOOGLE_CLIENT_ID` and authorize the website's HTTPS origin in Google to
enable Google sign-in. Email/password accounts are also supported.

The free demo stores SQLite, Qdrant, graph AOF files and journals under `/data`
on the ephemeral container filesystem. Data is lost on restarts, redeploys and
idle spin-down. Existing workstation data is not uploaded or migrated. A paid
service with a disk mounted at `/data` is required to retain these files.

The combined service is for a small demo. CPU and memory are limited; monitor
planning requests and upgrade capacity if the service runs out of memory.

## Vercel

Deploy only `stitch_ai_travel_booking_platform/frontend`, with Node 22, install
command `npm ci`, build command `npm run build`, and output `dist`. Its
`vercel.json` proxies `/api` to Render to preserve same-origin session and CSRF
cookies, adds the Google popup response header, and supports direct route links.
Update that proxy target and redeploy if the Render service domain changes.

Never put provider keys or session secrets in Git or Vite environment variables.

## Live deployment

- Website: https://voyara-travel-taupe.vercel.app
- API health: https://voyara-api-kyb2.onrender.com/health
- Render service: `srv-dbaann2jnfac73f0qchg`, Singapore, free plan.
- Vercel project: `voyara-travel`, scope `aarushsrivastava7812-6631`.
- Source branch: `codex/deploy-voyara`; the main branch and dashboard are managed separately.

Automatic Render deployments are disabled. To release a reviewed commit:

```powershell
render deploys create srv-dbaann2jnfac73f0qchg --commit <commit-sha> --output json
```

From the public frontend directory, deploy website changes with:

```powershell
vercel deploy --project voyara-travel --scope aarushsrivastava7812-6631 --prod --yes --no-wait
```

The initial container smoke test passed under a 512 MiB memory limit, using
about 410 MiB after one offline planning request. It checked catalog loading,
registration, authenticated identity, trip requirements and a successful real
graph/vector-backed offline plan. This is not a concurrency capacity guarantee.
