# LeadFlow AI – WhatsApp inbox fix

## What was updated
- The dashboard now checks the manual-send API response before showing a success message.
- Webhook logs now show event counts and whether an incoming text message was parsed, without printing the customer's full message payload.
- The project archive excludes `.env`, `.git`, virtual environments, and Python cache files.
- `.env.example` documents the required environment variable names. Never commit a real `.env` file.

## Required Render environment variables
Set these in Render > your service > Environment:
- `DATABASE_URL`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_VERIFY_TOKEN`

The value of `WHATSAPP_VERIFY_TOKEN` must exactly match the Verify Token entered in Meta's webhook setup.

## Required Meta webhook configuration
In Meta Developer Dashboard > your App > WhatsApp > Configuration:
1. Callback URL: `https://YOUR-RENDER-DOMAIN/webhook`
2. Verify Token: exactly the same value as `WHATSAPP_VERIFY_TOKEN` in Render.
3. Subscribe the WhatsApp webhook field named `messages`.
4. Confirm the correct WhatsApp Business Account is connected to this app.

## How to test real incoming messages
1. Deploy this version to Render.
2. Open Render Logs.
3. Send a new text message from a WhatsApp account to the connected business number.
4. Look for `[WhatsApp Webhook] Event received` and `incoming_messages=1`.
5. Then look for `[WhatsApp Webhook] Incoming text event ...`.
6. If the event arrives, look for `[WhatsApp DEBUG] Sending reply to:` and the Meta API result.
7. In the admin inbox, select that contact and confirm its AI mode says `AI Mode Active`.

## Important interpretation
- No `[WhatsApp Webhook] Event received` after sending a real WhatsApp message: Meta is not delivering the event to this endpoint, or the callback/subscription/account setup is incorrect.
- Event received but `incoming_messages=0`: Meta sent a status-only event, not an incoming customer message.
- Incoming event appears but no AI send log: inspect the traceback and that contact's `ai_mode`; `human` mode intentionally pauses automatic replies.
- Meta API acceptance is not proof of delivery. Check later `sent`, `delivered`, `read`, or `failed` status callbacks.
- WhatsApp Cloud API business-initiated messaging is subject to Meta's current messaging-window and template rules.

## Run locally
Activate your virtual environment, install requirements, configure `.env` using `.env.example`, then run:
`python -m uvicorn main:app --reload`

Do not share `.env` or access tokens in screenshots or ZIP files. If a real token was included in a shared archive, revoke/rotate it in Meta and update Render.
