# Android Share Intent — KB Dashboard

This guide sets up an Android share target using the free **HTTP Shortcuts** app (available on F-Droid and Google Play). When you share a URL from any app, HTTP Shortcuts sends it to your Knowledge Base inbox.

## Network Requirement

Your Android device must be able to reach the KB Dashboard host at port 7842:

- **Same WiFi**: Your phone and the desktop running the dashboard are on the same local network.
- **Tailscale**: Install Tailscale on both devices. The dashboard will be reachable via the Tailscale IP or hostname from anywhere.

The dashboard does not need any special configuration — only the network path matters.

## Install HTTP Shortcuts

- **F-Droid**: Search "HTTP Shortcuts" (id: `ch.reto_schindler.http_shortcuts`)
- **Google Play**: Search "HTTP Shortcuts"

## Configure the Base URL

Decide which address to use before building the shortcut:

- Local WiFi example: `http://192.168.1.42:7842`
- Tailscale example: `http://100.64.0.5:7842`

Replace `<KB_HOST>` in the steps below with your chosen address.

## Create the Share Target

### Step 1 — Create a new shortcut

1. Open HTTP Shortcuts.
2. Tap **+** → **Regular Shortcut**.
3. Set the **Name** to `Send to KB`.

### Step 2 — Configure the request

- **Method**: POST
- **URL**: `<KB_HOST>/api/share`
- **Request Body**: JSON body

In the Request Body section, enter:

```json
{
  "url": "{url}",
  "note": ""
}
```

The `{url}` placeholder is filled in at runtime from the share intent.

### Step 3 — Add headers

Under **Headers**, add:

| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |

### Step 4 — Variable for the shared URL

1. Go to **Variables** in the shortcut.
2. Add a variable named `url`.
3. Type: **Intent URL** (reads the URL from the Android share intent automatically).

### Step 5 — Response handling

1. Go to **Response Handling**.
2. Set **Display type** to **Toast** (a small popup) or **Dialog**.
3. Enable **Show response**.

This will show the API response (e.g. `{"status":"queued","inbox_id":"INX-..."}`) after each share.

### Step 6 — Enable as share target

1. In the shortcut, tap the **…** menu → **Quick Settings Tile / Share Target**.
2. Enable **Show as Share Target**.
3. Accept the system prompt to add HTTP Shortcuts as a share target.

## Usage

1. Open any page in Chrome, Firefox, or any app.
2. Tap **Share**.
3. Select **Send to KB** from the share sheet.
4. A toast notification confirms the result:
   - `{"status":"queued","inbox_id":"INX-..."}` — success
   - `{"status":"duplicate","existing_id":"..."}` — already in your KB

## Advanced: Custom response display

If you prefer a cleaner notification, in Response Handling set:

- **Display type**: Custom Toast
- **Content**: `Status: {response.status}` (uses JSONPath extraction)

Or use the **Shortcut Script** tab to parse the JSON response and show a tailored message.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Request times out | Check the KB dashboard is running: `python3 dashboard.py` |
| "URL not reachable" in response | Verify network path to `<KB_HOST>:7842` — open it in Chrome first |
| Share target not visible | Open HTTP Shortcuts → Settings → enable "Show as share target" |
| `{url}` not substituted | Ensure variable type is set to **Intent URL**, not Static |
