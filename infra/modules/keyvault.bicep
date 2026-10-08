// Key Vault in RBAC mode; the ingest identity may read secrets. Purge protection on in prod.
param location string
param tags object
param name string
param purgeProtection bool = false
param readerPrincipalId string
param logAnalyticsId string
@description('Disabled when private networking puts the vault behind a private endpoint.')
@allowed(['Enabled', 'Disabled'])
param publicNetworkAccess string = 'Enabled'

var secretsUser = '4633458b-17de-408a-b874-0445c86b69e6'

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: purgeProtection ? true : null
    publicNetworkAccess: publicNetworkAccess
    networkAcls: { bypass: 'AzureServices', defaultAction: publicNetworkAccess == 'Enabled' ? 'Allow' : 'Deny' }
  }
}

resource reader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, readerPrincipalId, secretsUser)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', secretsUser)
    principalId: readerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource diag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'to-log-analytics'
  scope: kv
  properties: {
    workspaceId: logAnalyticsId
    logs: [{ categoryGroup: 'audit', enabled: true }]
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

output id string = kv.id
output name string = kv.name
