# iOS Share Shortcut — KB Dashboard

This Shortcut lets you send any URL to your Knowledge Base inbox directly from the iOS share sheet.

## Network Requirement

Your iPhone must be able to reach the KB Dashboard host at port 7842. Two options:

- **Same WiFi**: Your phone and the machine running the dashboard are on the same local network.
- **Tailscale**: Install Tailscale on both your phone and your desktop. The dashboard will be reachable via its Tailscale IP or hostname even when you are away from home.

The dashboard itself does not need any special configuration for remote access — only the network path needs to exist.

## Configure the Base URL

Before building the Shortcut, decide which address you will use:

- Local WiFi example: `http://192.168.1.42:7842`
- Tailscale example: `http://100.64.0.5:7842`

Replace `<KB_HOST>` in the steps below with your chosen address.

## Build the Shortcut

1. Open **Shortcuts** on your iPhone.
2. Tap **+** to create a new Shortcut.
3. Tap the Shortcut name at the top and rename it to **Send to KB**.
4. Add the following actions in order:

---

### Action 1 — Receive Input from Share Sheet

- Action: **Receive** from Share Sheet
- Accept: **URLs** (also check **Webpages** if you want to share from Safari)
- If there is no input: **Stop and respond** (or ask for input)

---

### Action 2 — Get Variable

- Action: **Get variable**
- Variable: **Shortcut Input**

This gives you the URL the share sheet passed in.

---

### Action 3 — Get Contents of URL (POST request)

- Action: **Get Contents of URL**
- URL: `<KB_HOST>/api/share`
- Method: **POST**
- Headers:
  - Key: `Content-Type`  Value: `application/json`
- Request Body: **JSON**
  - Key: `url`  Value: **Shortcut Input** (select the variable from step 2)
  - Key: `note`  Value: (optional — leave blank or type a static annotation)

---

### Action 4 — Get Dictionary Value

- Action: **Get Dictionary Value**
- Dictionary: **Contents of URL** (output of step 3)
- Key: `status`

---

### Action 5 — If

- Action: **If**
- Condition: **Dictionary Value** equals `queued`

**If true (success):**

- Action: **Show Notification**
  - Title: `KB — Queued`
  - Body: `Article added to inbox.`

**Otherwise (duplicate or error):**

- Action: **Get Dictionary Value** from **Contents of URL**, Key: `existing_id`
- Action: **Show Notification**
  - Title: `KB — Already exists`
  - Body: **Dictionary Value** (the existing_id from above, or a static message)

---

### Action 6 — End If

---

## Enable in Share Sheet

1. In Shortcuts, tap the Shortcut's `...` menu → **Details**.
2. Enable **Show in Share Sheet**.
3. Set the types to **URLs** (and optionally **Webpages**).

## Usage

1. Open any link in Safari, Chrome, or any app.
2. Tap the **Share** button.
3. Scroll down in the share sheet and tap **Send to KB**.
4. A notification will confirm success or report a duplicate.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "URL not reachable" response | Check that the KB dashboard is running: `python3 dashboard.py` |
| No notification / times out | Check network path to `<KB_HOST>:7842` — try the URL in Safari first |
| "duplicate" notification | The URL is already in your KB — no action needed |
| Shortcut not in share sheet | Open Shortcuts → Details → enable "Show in Share Sheet" |
