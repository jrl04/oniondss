# Onion DSS farmer messaging

This repository starts the two-way communication layer described in the project brief. It contains a Django REST backend, a React Native / Expo farmer app, Twilio-compatible inbound and outbound SMS, and a staff-only extension inbox. The SMS advisory responder only uses approved, published advisory records; open-ended reports go to an officer for review.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer and Expo Go for the mobile prototype
- SQLite for local development; PostgreSQL for a deployed pilot
- A public HTTPS endpoint and a reply-capable SMS number for the SMS pilot

## Run the backend

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
py manage.py migrate
py manage.py createsuperuser
py manage.py runserver
```

The API is at `http://127.0.0.1:8000/api/`, Django admin at `/admin/`, and the officer inbox at `/officer/`. Create a farmer login in Users, create a matching Farmer record and set its `user` relation, add that farmer's fields, and set `phone_verified` after verifying ownership. Set `sms_opt_in` only after recording consent. Add approved Advisory records with a publication date for automatic IRRIGATION replies. The admin site is the initial account and field management surface.

## Run the farmer app

```powershell
cd mobile
npm install
npx expo start
```

The development API URL in `mobile/App.js` targets the Android emulator (`10.0.2.2`). For a physical device, replace it with the development computer's LAN address; for a build, use the deployed HTTPS API URL. The app includes My Fields, Advisories, and Messages views, field selection, photo attachment, and conversation status/history. Users authenticate at `/api/auth/token/` with their Django username and password.

## SMS provider configuration

Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER` from environment secrets. Configure the provider's inbound message webhook to `https://<host>/api/webhooks/sms/inbound/` using POST, and delivery status callback to `/api/webhooks/sms/status/`. Twilio inbound requests receive a TwiML response so an advisory or acknowledgment is returned in the same exchange. Officer replies are sent through the REST client and delivery status is recorded when callbacks arrive.

The webhook uses Twilio signature validation when `DJANGO_DEBUG=0` (unless explicitly disabled). Serve it behind HTTPS and ensure Django sees the original public URL for signature checks. SMS commands are `IRRIGATION <field code>`, `HELP`, `START`, and `STOP`; any other message opens an officer review conversation. A field code is only accepted when it belongs to the farmer associated with the exact sender number.

Officer SMS replies run through Celery when `CELERY_BROKER_URL` is set; start a worker with `py -m celery -A config worker -l info` and provide a reachable Redis broker. Without a broker, the prototype sends directly and stores the provider state.

Before buying/provisioning SMS, the project must confirm with the provider that a Philippine reply-capable number or short code is available, inbound messages reach the webhook, outbound replies reach the pilot networks, and farmer charges are understood. Test on the mobile networks used by pilot participants. Twilio branded alphanumeric sender IDs are not two-way numbers.

## API outline

- `POST /api/auth/token/` — obtain a farmer/staff token
- `GET /api/fields/`, `GET /api/advisories/`, `GET /api/conversations/` — authenticated, scoped to the signed-in farmer (staff see all)
- `POST /api/messages/` — create an app conversation; multipart form supports `body`, optional registered `field` id, and optional `photo`
- `POST /api/conversations/<id>/reply/` — staff-only officer reply; SMS conversations reply by SMS when consent is on
- `POST /api/webhooks/sms/inbound/`, `/api/webhooks/sms/status/` — provider webhooks

Field boundary GeoJSON is retained on the Field record so it can be joined to the project's existing PostGIS / GeoServer layers. Earth Engine and cloud raster production remain upstream; this messaging service reads only approved advisory records and does not replace the existing geospatial pipeline.

## Pilot acceptance flow

1. Link a test farmer account and phone to field `F03`, mark the phone verified, and record SMS consent.
2. Publish an approved, dated irrigation advisory and text `IRRIGATION F03`; the phone should receive its title, date, and text.
3. Send an open-ended field issue from the app with a photo; the officer inbox should show its field, image, thread, and awaiting status.
4. Reply in the officer inbox; the app should show the reply and answered status. Repeat the SMS issue-and-reply exchange and verify delivery callback states.

The project has no existing account, field, advisory, provider credentials, or production host configuration, so those pilot records and external settings must be supplied by the deployment team.
