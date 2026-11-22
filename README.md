# Onion DSS farmer messaging

This repository starts the two-way communication layer described in the project brief. It contains a Django REST backend, a React Native / Expo farmer app, Twilio-compatible inbound and outbound SMS, and a staff-only extension inbox. The SMS advisory responder only uses approved, published advisory records; open-ended reports go to an officer for review.

## Requirements

- Python 3.11 or newer
- Node.js 22.13 or newer and an Expo SDK 58 test client for the mobile prototype
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

## Farmer field map and NDVI

Build the React and TypeScript map before opening it. Django serves the generated JavaScript and CSS as static assets. For deployment, run the build before Django's `collectstatic`.

```powershell
cd web
npm.cmd ci
npm.cmd run build
cd ..
```

Sign in with a staff account and open `/fields/map/`. The map opens on Ilocos Norte. Search by farmer or field name or code and select a field to zoom in. In Django admin, set each registered field's **Boundary** to a GeoJSON Point, Polygon, or MultiPolygon geometry. Points use longitude first, for example `{"type":"Point","coordinates":[120.59,18.20]}`. Fields without a saved location are listed with their location status.

For the NDVI overlay, use the Earth Engine image asset produced by the project's NDVI workflow. Enable Earth Engine for a Google Cloud project and grant the Django runtime access to the image asset. For local development, authenticate with the Earth Engine CLI in the same environment used to run Django:

```powershell
earthengine authenticate
$env:EARTH_ENGINE_PROJECT = 'your-google-cloud-project'
$env:EARTH_ENGINE_NDVI_ASSET = 'projects/your-google-cloud-project/assets/your_ndvi_image'
$env:EARTH_ENGINE_NDVI_BAND = 'NDVI'
py manage.py runserver
```

Set the band name to match the asset. The image should contain NDVI values scaled to −1 through 1. Leaflet uses Stadia Maps Alidade Smooth for the basemap and Google Earth Engine for the raster. Stadia Maps supports local development at `localhost` or `127.0.0.1` without a key, subject to rate limits. Register the deployed website's domain with Stadia Maps before using this basemap there. When Earth Engine is unconfigured or unavailable, the field map remains usable.

## Run the farmer app

```powershell
cd mobile
npm install
npx expo start
```

For a UI review, open the project in [Expo Go for Android with SDK 58 support](https://expo.dev/go) and tap **Preview sample content** on the sign-in screen. The preview includes sample fields in Ilocos Norte, advisories, and conversations. You can attach a photo and add a sample message without a Django server or farmer account. Preview changes reset when you exit.

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
