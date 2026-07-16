# CVAT Video B-line Spike

This branch evaluates CVAT as a possible video annotation backend for the lung ultrasound B-line workflow:

1. Upload full cine-loop videos.
2. Preview the full video.
3. Mark keyframes in the annotation backend.
4. Draw B-line polygons on selected frames.
5. Review issues.
6. Export images, binary masks, manifest, and skipped records.

## Local CVAT

- Run CVAT outside this repository, preferably from the official CVAT Docker Compose setup.
- Use a local-only port such as `8081` or `8090`; avoid `8080` because the existing local Label Studio setup uses it.
- Do not copy the CVAT repository, media volumes, task exports, videos, or annotation zips into this project.
- Keep real credentials only in a local `.env` file.

Example environment variables:

```env
CVAT_URL=http://localhost:8081
CVAT_USERNAME=
CVAT_PASSWORD=
CVAT_ACCESS_TOKEN=
CVAT_ORGANIZATION=
```

The project-side health check is:

```text
GET /api/integrations/cvat/health
```

It intentionally never returns passwords or tokens.

## Current Local Finding

Docker CLI and Docker Compose are installed, but the Docker Desktop Linux engine is not reachable in the current environment. Because of that, live CVAT UI/API validation could not be completed in this spike pass.

## Mapping Proposal

- Platform video dataset maps to one CVAT Project.
- Platform `VideoItem` maps to one CVAT Task.
- CVAT Job is the annotation/review work unit.
- Image tasks continue to use the existing Label Studio flow.

## Label Proposal

- `B-line`: polygon shape.
- `Keyframe`: tag with reason attribute:
  `first_clear`, `most_obvious`, `appear`, `disappear`, `count_change`, `confluent_most_obvious`, `boundary_change`, `issue_frame`, `manual`.
- `FrameDecision`: tag or attribute:
  `positive`, `negative`, `uncertain`.
- Do not treat a frame with no polygon as negative unless it has an explicit negative decision.

## iframe / Embedding Notes

CVAT may block embedding depending on deployment headers, authentication state, and reverse proxy configuration. Do not patch CVAT source for embedding during this spike. Prefer opening the CVAT task/job URL in a new tab unless a supported reverse-proxy configuration is validated.

## Not Included In This Spike

- Production CVAT deployment.
- CVAT source code or volumes.
- Video AI pre-annotation.
- CVAT track annotation.
- Double annotation, arbitration, or consensus automation.
- Final CVAT export parser.
