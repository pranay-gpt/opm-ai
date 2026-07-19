# Self-Hosted Runner Setup for OPM Flow Integration Tests

This document describes how to set up a self-hosted GitHub Actions runner with OPM Flow 2026.04+ installed to run the integration test suite (`.github/workflows/ci-integration.yml`).

## Prerequisites

- A Linux machine (Ubuntu 24.04 "Noble" recommended)
- 4 GB+ RAM, 2+ CPUs
- Internet access to install packages from OPM PPA
- GitHub repository admin access to register the runner

## 1. Install OPM Flow on Ubuntu 24.04

```bash
# Add OPM PPA
sudo add-apt-repository -y ppa:opm/opm
sudo apt-get update

# Install OPM Flow and Python bindings
sudo apt-get install -y \
    opm-simulators \
    python3-opm-simulators \
    python3-opm-common \
    resinsight

# Verify installation
flow --version
# Should show: OPM Flow 2026.04.x (or newer)
python3 -c "import opm.simulators; print('Python bindings OK')"
```

**Note**: The exact PPA package names may vary. Verify with:
```bash
apt-cache search opm | grep -E "flow|simulator|common"
```

If the PPA doesn't have the expected packages, you may need to build OPM Flow from source or use the official OPM Docker image as a base.

## 2. Install GitHub Actions Self-Hosted Runner

```bash
# Create a folder for the runner
mkdir -p ~/actions-runner && cd ~/actions-runner

# Download the latest runner (check GitHub releases for latest version)
curl -o actions-runner-linux-x64-2.319.1.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.319.1/actions-runner-linux-x64-2.319.1.tar.gz

# Extract
tar xzf ./actions-runner-linux-x64-2.319.1.tar.gz

# Configure (replace with your repo URL and token from GitHub Settings > Actions > Runners)
./config.sh --url https://github.com/<your-org>/opm-ai --token <your-token> \
  --labels self-hosted,linux,opm-flow

# Install as a service (optional, for auto-start on boot)
sudo ./svc.sh install
sudo ./svc.sh start
```

## 3. Verify Runner Registration

1. Go to your GitHub repository **Settings > Actions > Runners**
2. Verify the runner appears with labels: `self-hosted`, `linux`, `opm-flow`
3. The runner should show as "Idle" (green)

## 4. Enable the Integration Workflow

The workflow `.github/workflows/ci-integration.yml` is triggered manually via `workflow_dispatch`. 

To run it:
1. Go to **Actions** tab in GitHub
2. Select "CI Integration (Self-Hosted)" workflow
3. Click "Run workflow"
4. Optionally enable "Run SPE1 integration test"
5. Click "Run workflow"

The workflow will only run on runners with the `opm-flow` label (i.e., your self-hosted runner).

## 5. Verify Flow is Accessible in Runner Context

The runner runs as a service user. Verify `flow` is in PATH:

```bash
# As the runner service user (typically the user who ran config.sh)
which flow
flow --version
```

If `flow` is not found, ensure the runner service user has `/usr/bin` in PATH, or add to the runner's environment:
```bash
# In ~/.bashrc or runner's env file
export PATH="/usr/bin:$PATH"
```

## 6. Run Integration Tests Locally (for debugging)

On the self-hosted machine, you can run the integration tests manually:

```bash
cd /path/to/opm-ai
pip install -e ".[dev]"
pytest tests/integration/test_dataset_validation.py::test_scenario_deck_lints_and_validates -v
pytest tests/integration/test_runner_spe1.py -v
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `flow: command not found` | Ensure OPM PPA packages installed; check PATH for runner user |
| `flow --version` shows old version | PPA may have older version; consider building from source |
| `MPI_Init_thread failed` / `ORTED error` | Use `mpirun --oversubscribe` or pin `libopenmpi-dev=4.1.6` |
| `libopm-common.so not found` | `apt-get install -y libopm-common` |
| Runner shows offline | Check service status: `sudo systemctl status actions.runner.*` |
| Tests timeout | Increase `timeout-minutes` in workflow; ensure 4GB+ RAM available |

## Security Notes

- Self-hosted runners have access to your repository code and secrets
- Only use self-hosted runners on trusted infrastructure
- Consider ephemeral runners (GitHub Actions `actions-runner-controller` on Kubernetes) for better isolation
- The `ci-integration.yml` workflow does not expose secrets to the runner by default

## Alternative: Docker-based Runner

If you prefer not to install OPM Flow on the host, you can run the integration tests inside Docker:

```dockerfile
# Dockerfile.integration
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:opm/opm && apt-get update && \
    apt-get install -y opm-simulators python3-opm-simulators python3-opm-common python3-pip && \
    pip install pytest
WORKDIR /app
COPY . .
RUN pip install -e ".[dev]"
ENTRYPOINT ["pytest", "tests/integration/", "-v"]
```

Then in the workflow, use `container:` instead of `runs-on:`. This requires the runner to have Docker installed but doesn't need OPM Flow on the host.