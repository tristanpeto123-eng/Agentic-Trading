# CEO Console — Sprint 1

React 19 + TypeScript + Vite. Three responsive tabs (Home / Students / Trading), server-authenticated CEO login, student enrolment, direction changes and versioned profile history. **All performance/trading placeholders explicitly say disabled or unavailable, never imply profit.**

## Run locally

Start and initialise the backend as explained in the root README, then:

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 . Vite proxies `/v1` and `/health` to `http://127.0.0.1:8000`; the signed HttpOnly CEO session cookie remains same-origin in the browser. Nothing in the frontend stores passwords, cookies, or tokens in localStorage.

`npm run build` runs TypeScript strict checking and produces `dist/`. A production release must configure an HTTPS same-origin API, server-side secrets, approved origins, database migrations, backups, audit retention, and distributed login throttling. **Do not expose the development server publicly.**
