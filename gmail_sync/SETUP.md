# Gmail API setup

One-time setup. After this, `python3 -m gmail_sync.verify` will authenticate and list your labels.

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

New deps: `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`.

## 2. Create a Google Cloud project

1. Open <https://console.cloud.google.com/>.
2. Top bar → project dropdown → **New Project**. Name it anything (e.g. `cash-flow`). Create.
3. Make sure the new project is selected in the top bar.

## 3. Enable the Gmail API

1. Left menu → **APIs & Services → Library**.
2. Search for **Gmail API** → click it → **Enable**.

## 4. Configure the OAuth consent screen

1. Left menu → **APIs & Services → OAuth consent screen**.
2. User type: **External** → Create.
3. Fill only the required fields:
   - App name: `cash-flow`
   - User support email: your email
   - Developer contact: your email
4. Save and continue through the **Scopes** step (leave empty, we request scopes in code).
5. On the **Test users** step, click **Add users** and add your own Gmail address. Save.
6. You do **not** need to publish the app — leave it in *Testing* mode. The only test user is you.

## 5. Create OAuth client credentials

1. Left menu → **APIs & Services → Credentials**.
2. **+ Create Credentials → OAuth client ID**.
3. Application type: **Desktop app**. Name: `cash-flow-cli`. Create.
4. Click **Download JSON** on the popup (or from the credentials list afterward).
5. Save the file as `credentials.json` in the repo root:

```
/mnt/data2/Code/cash_flow/credentials.json
```

`credentials.json` and `token.json` are both gitignored.

## 6. Verify

```bash
cd /mnt/data2/Code/cash_flow
python3 -m gmail_sync.verify
```

The first run:
- Opens your browser.
- Google warns *"Google hasn't verified this app"* — click **Advanced → Go to cash-flow (unsafe)**. This is expected because the app is in *Testing* mode with only you as a test user.
- Grant read-only Gmail access.
- The script prints your user labels.
- `token.json` is created alongside `credentials.json`. Subsequent runs don't need the browser.

If `token.json` stops working (rare — usually token expiry past refresh window), delete it and re-run.

## Scope

Read-only: `https://www.googleapis.com/auth/gmail.readonly`. We never modify, send, or delete.
