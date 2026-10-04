# Architecture decision records

Short records of the decisions that shape this repo: the context, what was chosen, and what it
costs. A new decision gets the next number; a reversed decision is marked `Superseded` and links to
its replacement rather than being deleted.

| File | What it does |
|---|---|
| [`README.md`](README.md) | This index |
| [`0001-bicep-and-terraform.md`](0001-bicep-and-terraform.md) | Bicep and Terraform for the same Azure resources |
| [`0002-local-lakehouse-stand-in.md`](0002-local-lakehouse-stand-in.md) | Local Parquet and DuckDB as the OneLake stand-in, offline by default |
| [`0003-oidc-and-managed-identity.md`](0003-oidc-and-managed-identity.md) | OIDC for the pipeline, managed identity at runtime, keys turned off |
| [`0004-eval-gates-block-the-build.md`](0004-eval-gates-block-the-build.md) | Eval gates block the build |
| [`0005-deploy-gated-off.md`](0005-deploy-gated-off.md) | Ship the deploy pipeline switched off |
| [`0006-fabric-items-via-rest-and-fabric-cicd.md`](0006-fabric-items-via-rest-and-fabric-cicd.md) | Fabric items through the Fabric REST API and fabric-cicd, not ARM |
