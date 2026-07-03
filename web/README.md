# Web Frontend

React 19 + TypeScript + Vite source for the Cash Flow dashboard. See [docs/web.md](../docs/web.md) for the full guide.

```bash
npm install
npm run dev        # Vite dev server; proxies /api to localhost:8090
npm run build      # emits to dist/
npm run lint
```

To ship a build, copy the contents of `dist/` into the repo's `static/` directory — the FastAPI server serves the SPA from there, so the Python app stays self-contained.

Structure:

```
src/
├── api/           # typed API client
├── components/    # charts, layout shell, primitives, transaction widgets
├── hooks/         # auth, theme, transaction search
├── pages/         # Dashboard, Transactions, Review, Invoices, Subscriptions, Settings, Login
├── styles/        # global.css + design tokens (light/dark)
└── utils/         # formatters
```
