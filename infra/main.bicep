// Azure footprint for the Fabric enterprise BI build (resource-group scope). Same resources, names
// and tags as infra/terraform. Fabric workspace items are not ARM resources: the deploy pipeline
// creates them through the Fabric REST API / fabric-cicd after this template is deployed.
targetScope = 'resourceGroup'

@description('Workload token used in names.')
param workload string = 'fabricbi'

@allowed(['dev', 'test', 'prod'])
param environmentName string = 'dev'

param location string = resourceGroup().location

@description('Region short code used in names (eus2 for eastus2).')
param regionShort string = 'eus2'

param instance string = '001'

@description('Create an F-SKU capacity. false = use a Fabric trial capacity (no Azure charge).')
param deployFabricCapacity bool = true

@allowed(['F2', 'F4', 'F8', 'F16', 'F32', 'F64', 'F128', 'F256', 'F512', 'F1024', 'F2048'])
param fabricSku string = 'F2'

@description('Fabric capacity administrators (UPNs or object ids).')
param fabricAdmins array = []

@allowed(['Basic', 'Standard', 'Premium'])
param eventHubsSku string = 'Basic'

@description('F1 is free but limited to one per subscription; use B1 if one exists.')
param iotHubSku string = 'F1'

@allowed(['Standard_LRS', 'Standard_ZRS', 'Standard_GZRS'])
param storageSku string = 'Standard_LRS'

param deployPurview bool = false

@description('Log Analytics daily cap in GB (-1 = none).')
param logDailyQuotaGb int = 1

param purgeProtection bool = false

@description('Opt-in: VNet with an NSG-protected private-endpoint subnet, private endpoints for Key Vault and (when deployed) Purview account + portal, public access off on both. Off by default to keep the demo cheap.')
param privateNetworking bool = false

param tags object = {
  env: environmentName
  owner: 'jagadish.meduri'
  project: 'fabric-enterprise-bi'
  'cost-center': 'portfolio'
  workload: workload
  'managed-by': 'bicep'
}

var base = '${workload}-${environmentName}-${regionShort}-${instance}'
var kvName = take('kv-${workload}-${environmentName}-${instance}', 24)
var purviewName = 'pview-${base}'
var kvPurviewAccess = privateNetworking ? 'Disabled' : 'Enabled'
var alnum = toLower(replace('${workload}${environmentName}${regionShort}${instance}', '-', ''))

resource ingestIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${base}-ingest'
  location: location
  tags: tags
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    tags: tags
    logAnalyticsName: 'log-${base}'
    appInsightsName: 'appi-${base}'
    dailyQuotaGb: logDailyQuotaGb
  }
}

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    location: location
    tags: tags
    name: kvName
    purgeProtection: purgeProtection
    readerPrincipalId: ingestIdentity.properties.principalId
    logAnalyticsId: monitoring.outputs.logAnalyticsId
    publicNetworkAccess: kvPurviewAccess
  }
}

module streaming 'modules/streaming.bicep' = {
  name: 'streaming'
  params: {
    location: location
    tags: tags
    namespaceName: 'evhns-${base}'
    iotHubName: 'iot-${base}'
    eventHubsSku: eventHubsSku
    iotHubSku: iotHubSku
    receiverPrincipalId: ingestIdentity.properties.principalId
    logAnalyticsId: monitoring.outputs.logAnalyticsId
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    tags: tags
    name: take('st${alnum}', 24)
    sku: storageSku
    readerPrincipalId: ingestIdentity.properties.principalId
  }
}

module fabric 'modules/fabric.bicep' = if (deployFabricCapacity) {
  name: 'fabric'
  params: {
    location: location
    tags: tags
    name: take('fc${alnum}', 63)
    sku: fabricSku
    admins: fabricAdmins
  }
}

module purview 'modules/purview.bicep' = if (deployPurview) {
  name: 'purview'
  params: {
    location: location
    tags: tags
    name: purviewName
    managedResourceGroupName: 'rg-${base}-purview-managed'
    storageAccountName: storage.outputs.name
    publicNetworkAccess: kvPurviewAccess
  }
}

// ---- optional private networking for Key Vault and Purview (off by default; not deployed) ----
module network 'modules/network.bicep' = if (privateNetworking) {
  name: 'network'
  params: {
    location: location
    tags: tags
    name: 'vnet-${base}'
    dnsZones: [
      { key: 'keyvault', zone: 'privatelink.vaultcore.azure.net' }
      { key: 'purview', zone: 'privatelink.purview.azure.com' }
      { key: 'purviewstudio', zone: 'privatelink.purviewstudio.azure.com' }
    ]
  }
}

var peTargets = concat(
  [{ name: 'keyvault', id: resourceId('Microsoft.KeyVault/vaults', kvName), group: 'vault', zone: 'keyvault' }],
  deployPurview
    ? [
        { name: 'purview-account', id: resourceId('Microsoft.Purview/accounts', purviewName), group: 'account', zone: 'purview' }
        { name: 'purview-portal', id: resourceId('Microsoft.Purview/accounts', purviewName), group: 'portal', zone: 'purviewstudio' }
      ]
    : []
)

module privateEndpoints 'modules/private-endpoint.bicep' = [for pe in (privateNetworking ? peTargets : []): {
  name: 'pe-${pe.name}'
  params: {
    location: location
    tags: tags
    name: 'pe-${pe.name}-${base}'
    subnetId: network!.outputs.peSubnetId
    targetResourceId: pe.id
    groupId: pe.group
    dnsZoneIds: [network!.outputs.zoneIds[pe.zone]]
  }
  dependsOn: [keyVault, purview]
}]

output AZURE_RESOURCE_GROUP string = resourceGroup().name
output fabricCapacityName string = deployFabricCapacity ? take('fc${alnum}', 63) : ''
output eventHubsNamespace string = streaming.outputs.namespaceName
output iotHubName string = streaming.outputs.iotHubName
output storageAccount string = storage.outputs.name
output keyVaultName string = keyVault.outputs.name
output logAnalyticsName string = monitoring.outputs.logAnalyticsName
output purviewAccount string = deployPurview ? purviewName : ''
output ingestIdentityClientId string = ingestIdentity.properties.clientId
