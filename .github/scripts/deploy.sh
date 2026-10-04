#!/usr/bin/env bash
# Deployment steps, used by .github/workflows/deploy.yml and teardown.yml.
# Inputs (environment):
#   DEPLOY_TOOL   terraform | bicep
#   TARGET_ENV    dev | prod
#   LOCATION      Azure region (default eastus2)
#   FABRIC_ADMINS comma-separated capacity admins (UPNs or object ids)
#   ARM_* / AZURE_*  set by azure/login (OIDC) and the workflow env
#
#   deploy.sh provision   create/update the Azure resources, write outputs to $GITHUB_OUTPUT
#   deploy.sh fabric      find or create the Fabric workspace on the capacity, publish items (fabric-cicd)
#   deploy.sh smoke       post-deploy checks: resources exist, capacity active, keyless, items present
#   deploy.sh suspend     pause the Fabric capacity (dev, after smoke tests) so it stops billing
#   deploy.sh destroy     tear the environment down (teardown workflow only)
set -euo pipefail

TOOL="${DEPLOY_TOOL:-terraform}"
ENV_NAME="${TARGET_ENV:?TARGET_ENV is required}"
LOCATION="${LOCATION:-eastus2}"
STACK="infra/terraform"
OUT="${GITHUB_OUTPUT:-/dev/stdout}"
FABRIC_API="https://api.fabric.microsoft.com/v1"
WORKSPACE_NAME="ws-fabricbi-${ENV_NAME}"

region_short() {
  case "$LOCATION" in
    eastus) echo eus ;; eastus2) echo eus2 ;; westus2) echo wus2 ;; westus3) echo wus3 ;;
    centralus) echo cus ;; swedencentral) echo sdc ;; westeurope) echo weu ;;
    northeurope) echo neu ;; uksouth) echo uks ;; *) echo "${LOCATION:0:6}" ;;
  esac
}
RG="rg-fabricbi-${ENV_NAME}-$(region_short)-001"

tf_init() {
  : "${TFSTATE_RESOURCE_GROUP:?set repo/environment variable TFSTATE_RESOURCE_GROUP}"
  : "${TFSTATE_STORAGE_ACCOUNT:?set repo/environment variable TFSTATE_STORAGE_ACCOUNT}"
  terraform -chdir="$STACK" init -input=false \
    -backend-config="envs/${ENV_NAME}.backend.hcl" \
    -backend-config="resource_group_name=${TFSTATE_RESOURCE_GROUP}" \
    -backend-config="storage_account_name=${TFSTATE_STORAGE_ACCOUNT}" \
    -backend-config="container_name=${TFSTATE_CONTAINER:-tfstate}"
}

admins_json() { jq -cn --arg a "${FABRIC_ADMINS:-}" '$a | split(",") | map(select(length > 0))'; }

provision() {
  if [[ "$TOOL" == "terraform" ]]; then
    tf_init
    terraform -chdir="$STACK" apply -auto-approve -input=false \
      -var-file="envs/${ENV_NAME}.tfvars" -var "location=${LOCATION}" -var "fabric_admins=$(admins_json)"
    rg=$(terraform -chdir="$STACK" output -raw AZURE_RESOURCE_GROUP)
    cap=$(terraform -chdir="$STACK" output -raw fabricCapacityName)
  else
    az group create --name "$RG" --location "$LOCATION" \
      --tags env="$ENV_NAME" owner=jagadish.meduri project=fabric-enterprise-bi cost-center=portfolio workload=fabricbi managed-by=bicep -o none
    outputs=$(az deployment group create --resource-group "$RG" --name "fabricbi-${GITHUB_RUN_ID:-local}" \
      --template-file infra/main.bicep --parameters "infra/main.parameters.${ENV_NAME}.json" \
      --parameters regionShort="$(region_short)" fabricAdmins="$(admins_json)" \
      --query properties.outputs -o json)
    rg="$RG"
    cap=$(jq -r .fabricCapacityName.value <<<"$outputs")
  fi
  { echo "resource_group=$rg"; echo "capacity_name=$cap"; } >>"$OUT"
}

fabric_token() { az account get-access-token --resource https://api.fabric.microsoft.com --query accessToken -o tsv; }
fabric() {
  # Fabric items are not ARM resources: the workspace and its items go through the Fabric REST API.
  # The pipeline identity must be allowed to use Fabric APIs (tenant setting for service principals)
  # and be a capacity admin or contributor.
  : "${CAPACITY_NAME:?CAPACITY_NAME is required (use a trial capacity by setting FABRIC_CAPACITY_ID instead)}"
  tok=$(fabric_token)
  hdr=(-H "Authorization: Bearer $tok" -H "Content-Type: application/json")
  cap_id="${FABRIC_CAPACITY_ID:-$(curl -fsS "${hdr[@]}" "$FABRIC_API/capacities" | jq -r --arg n "$CAPACITY_NAME" '.value[] | select(.displayName == $n) | .id')}"
  [[ -n "$cap_id" ]] || { echo "::error::capacity $CAPACITY_NAME not visible to the pipeline identity"; exit 1; }
  ws_id=$(curl -fsS "${hdr[@]}" "$FABRIC_API/workspaces" | jq -r --arg n "$WORKSPACE_NAME" '.value[] | select(.displayName == $n) | .id')
  if [[ -z "$ws_id" ]]; then
    ws_id=$(curl -fsS -X POST "${hdr[@]}" "$FABRIC_API/workspaces" \
      -d "$(jq -cn --arg n "$WORKSPACE_NAME" --arg c "$cap_id" '{displayName: $n, capacityId: $c, description: "Fabric enterprise BI (managed by GitHub Actions)"}')" | jq -r .id)
    echo "created workspace $WORKSPACE_NAME ($ws_id)"
  else
    curl -fsS -X POST "${hdr[@]}" "$FABRIC_API/workspaces/$ws_id/assignToCapacity" -d "{\"capacityId\": \"$cap_id\"}" >/dev/null
  fi
  pip install --quiet fabric-cicd azure-identity
  python scripts/publish_fabric_items.py --workspace-id "$ws_id" --environment "$ENV_NAME"
  echo "workspace_id=$ws_id" >>"$OUT"
}

smoke() {
  : "${RESOURCE_GROUP:?}"
  n=$(az resource list -g "$RESOURCE_GROUP" --query "length(@)" -o tsv)
  [[ "$n" -ge 6 ]] || { echo "::error::expected resources in $RESOURCE_GROUP, found $n"; exit 1; }
  echo "$n resources in $RESOURCE_GROUP"
  local_auth=$(az eventhubs namespace list -g "$RESOURCE_GROUP" --query "[?disableLocalAuth!=\`true\`] | length(@)" -o tsv)
  [[ "$local_auth" == "0" ]] || { echo "::error::an Event Hubs namespace allows SAS keys"; exit 1; }
  shared=$(az storage account list -g "$RESOURCE_GROUP" --query "[?allowSharedKeyAccess!=\`false\`] | length(@)" -o tsv)
  [[ "$shared" == "0" ]] || { echo "::error::a storage account allows shared keys"; exit 1; }
  if [[ -n "${CAPACITY_NAME:-}" ]]; then
    state=$(az resource show -g "$RESOURCE_GROUP" -n "$CAPACITY_NAME" --resource-type Microsoft.Fabric/capacities --query properties.state -o tsv)
    [[ "$state" == "Active" ]] || { echo "::error::Fabric capacity state is $state"; exit 1; }
  fi
  if [[ -n "${WORKSPACE_ID:-}" ]]; then
    tok=$(fabric_token)
    items=$(curl -fsS -H "Authorization: Bearer $tok" "$FABRIC_API/workspaces/$WORKSPACE_ID/items" | jq -r '.value[].displayName')
    for want in lh_retail eh_retail nb_silver nb_gold sm_retail_sales; do
      grep -qx "$want" <<<"$items" || { echo "::error::Fabric item $want missing"; exit 1; }
    done
    echo "Fabric items present in workspace"
  fi
}

suspend() {
  : "${RESOURCE_GROUP:?}" "${CAPACITY_NAME:?}"
  id=$(az resource show -g "$RESOURCE_GROUP" -n "$CAPACITY_NAME" --resource-type Microsoft.Fabric/capacities --query id -o tsv)
  az rest --method post --url "https://management.azure.com${id}/suspend?api-version=2023-11-01" >/dev/null
  echo "capacity $CAPACITY_NAME suspended (no compute charges while paused)"
}

destroy() {
  if [[ "$TOOL" == "terraform" ]]; then
    tf_init
    terraform -chdir="$STACK" destroy -auto-approve -input=false \
      -var-file="envs/${ENV_NAME}.tfvars" -var "location=${LOCATION}" -var "fabric_admins=$(admins_json)"
  else
    az group delete --name "$RG" --yes
  fi
  echo "Fabric workspace $WORKSPACE_NAME is not an ARM resource: delete it in the Fabric portal or with DELETE $FABRIC_API/workspaces/<id>."
}

"$@"
