# Container Runs

Container runs activate when `container_image` (or `container_runtime`) is set.
Defaults:
- Image: `registry.nersc.gov/amsc014/superfacility/pele:latest`
- ALCF image: `docker://registry.nersc.gov/amsc014/superfacility/pele:latest`

## Local (Docker)

Example config override:

```yaml
environment: local
container_image: registry.nersc.gov/amsc014/superfacility/pele:latest
container_runtime: docker
```

## NERSC Perlmutter (podman-hpc)

Example config override:

```yaml
environment: perlmutter
container_image: registry.nersc.gov/amsc014/superfacility/pele:latest
container_runtime: podman-hpc
```

Reference: https://docs.nersc.gov/development/containers/podman-hpc/overview/

## ALCF (Apptainer)

Example config override:

```yaml
environment: alcf
container_image: docker://registry.nersc.gov/amsc014/superfacility/pele:latest
container_runtime: apptainer
```
