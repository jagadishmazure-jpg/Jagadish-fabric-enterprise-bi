# `.github/scripts`

Shell steps called by the deploy and teardown workflows, so the YAML stays short and the steps
can be run by hand in an emergency.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This file |
| [`deploy.sh`](deploy.sh) | `provision` (Terraform or Bicep), `fabric` (workspace + item publish through the Fabric REST API and fabric-cicd), `smoke`, `suspend` (pause the capacity) and `destroy` |

Check it parses with `bash -n .github/scripts/deploy.sh`. It needs an Azure login to do anything; see [deployment.md](../../docs/deployment.md) and the [implementation guide](../../docs/implementation-guide.md).
