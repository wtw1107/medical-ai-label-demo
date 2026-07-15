# Deployment Guide

## 1. Deployment Architecture

This project is prepared for a single-server demo deployment with four services:

- `frontend`: builds the Vite React app and serves static assets through Nginx
- `backend`: FastAPI application on port `8000`
- `model_service`: FastAPI model service on port `9000`
- `label-studio`: Label Studio on port `8080`

Recommended external exposure:

- Expose only `80` through the reverse proxy
- Keep `8000`, `8080`, and `9000` internal to the Docker network

Recommended reverse proxy paths:

- `/` -> frontend static app
- `/api/` -> backend
- `/media/` -> backend media files
- `/label-studio/` -> Label Studio

## 2. Directory Layout

Recommended application directory:

```text
/opt/medical-ai-label-demo
```

Recommended persistent data directories:

```text
/data/medical-ai-label-demo/data
/data/medical-ai-label-demo/label-studio
```

Notes:

- `DATA_ROOT` should point to `/data` inside the backend container
- The backend container writes uploaded datasets, exports, and SQLite data to the mounted volume
- Do not keep production uploads or databases inside the code checkout directory

## 3. Environment Variables

Copy the production template:

```bash
cp .env.production.example .env.production
```

Then edit `.env.production` and set:

- `PUBLIC_BASE_URL`
- `LABEL_STUDIO_URL`
- `LABEL_STUDIO_API_TOKEN`
- `LABEL_STUDIO_SECRET_KEY`
- `ROBOFLOW_API_KEY` if external Roboflow inference is allowed

Important:

- Keep real secrets only in `.env.production`
- Do not commit `.env.production`
- `ROBOFLOW_API_KEY` may be left empty to keep `real_detection_v1` unavailable

## 4. First Deployment Steps

Create persistent directories:

```bash
sudo mkdir -p /data/medical-ai-label-demo/data
sudo mkdir -p /data/medical-ai-label-demo/label-studio
sudo chown -R $USER:$USER /data/medical-ai-label-demo
```

Prepare the environment file:

```bash
cp .env.production.example .env.production
```

Edit `.env.production`, then run:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## 5. Start Command

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## 6. Stop Command

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production down
```

## 7. View Logs

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
```

Inspect a single service:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f model_service
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f label-studio
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f frontend
```

## 8. Data Directories

Persistent data is expected in:

- `${APP_DATA_DIR}` on the host for:
  - SQLite database
  - uploaded datasets
  - export archives
- `${LABEL_STUDIO_DATA_DIR}` on the host for:
  - Label Studio data
  - Label Studio internal state

Default container-side paths:

- backend data: `/data`
- Label Studio data: `/label-studio/data`

## 9. Port Exposure

Recommended external exposure:

- `80:80`

Do not expose directly:

- `5173`
- `8000`
- `8080`
- `9000`

HTTPS can be added later through `443` and a certificate workflow such as Certbot or an upstream load balancer.

## 10. Security Notes

- Do not commit `.env.production`
- Do not commit model weights, uploaded images, SQLite files, or export archives
- `model_service` should remain internal only
- Label Studio raw port `8080` should remain internal only
- Backend API docs should not be exposed in production; the provided Nginx config blocks `/docs`, `/redoc`, and `/openapi.json`

Current backend CORS in the application code is permissive for local development:

```text
allow_origins=["*"]
```

Before public rollout, tighten CORS to the actual production origin.

This deployment guide is for an HTTP internal test environment. HTTPS, domain binding, and formal access control are not complete yet.

## 11. Roboflow External API Risk Notes

- `real_detection_v1` depends on an external Roboflow API when `ROBOFLOW_API_KEY` is configured
- If you are handling real medical data, evaluate compliance and privacy requirements before enabling Roboflow
- If external inference is not allowed, leave `ROBOFLOW_API_KEY` empty so the real detection path stays unavailable
- The demo can continue to run with mock models even when Roboflow is disabled

## 12. Upload Size Notes

The Nginx reverse proxy is configured with:

```text
client_max_body_size 500M;
```

This is intended for internal trial uploads and future larger ultrasound assets.

If your deployment allows larger files or more users, review:

- Nginx body size
- backend request timeout
- disk capacity
- export storage cleanup policy

## 13. Frontend Build Note

`VITE_API_BASE_URL` is injected at build time in the frontend image.

Recommended production value:

```text
/api
```

That keeps browser requests same-origin and lets Nginx proxy them to the backend.

## 14. Label Studio Setup

Connect to the server using the configured SSH alias:

```bash
ssh lab-server
```

Do not store jump host or server passwords in the repository.

After the first deployment:

1. Open `/label-studio/` through the server URL.
2. Create the initial Label Studio administrator account.
3. Open Label Studio account settings and create or copy a Personal Access Token.
4. Write the token into `.env.production` as `LABEL_STUDIO_API_TOKEN`.
5. Restart the backend after changing the token:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d backend
```

Set a stable `LABEL_STUDIO_SECRET_KEY` in `.env.production` before relying on sessions. If this value changes, existing Label Studio sessions may be invalidated.

After changing `LABEL_STUDIO_SECRET_KEY`, `LABEL_STUDIO_URL`, or `PUBLIC_BASE_URL`, restart Label Studio and the frontend gateway:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d label-studio frontend
```

## 15. Label Studio URL Note

Because the backend both calls Label Studio APIs and returns Label Studio URLs to the browser, `LABEL_STUDIO_URL` should be set to the externally reachable reverse-proxy URL, for example:

```text
http://your-domain.example/label-studio
```

Do not set it to `http://label-studio:8080` in production, otherwise browser-facing links will point to an internal hostname.

## 16. Deployment Verification

Run these checks after deployment:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production config
docker compose -f docker-compose.prod.yml --env-file .env.production ps
curl -I http://127.0.0.1/
curl http://127.0.0.1/health
curl http://127.0.0.1/api/models
curl -IL http://127.0.0.1/label-studio/
```

Expected results:

- only the frontend container publishes port `80`
- `/health` returns backend JSON
- `/api/models` returns the model registry
- `/label-studio/` reaches the Label Studio login flow
- `real_detection_v1` is `not_configured` when `ROBOFLOW_API_KEY` is empty
