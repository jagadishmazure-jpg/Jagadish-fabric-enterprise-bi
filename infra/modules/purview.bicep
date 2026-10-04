// Microsoft Purview account; its identity can read the landing storage for scans.
param location string
param tags object
param name string
param managedResourceGroupName string
param storageAccountName string

var blobReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

resource pv 'Microsoft.Purview/accounts@2021-12-01' = {
  name: name
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {
    managedResourceGroupName: managedResourceGroupName
    publicNetworkAccess: 'Enabled'
  }
}

resource st 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource scan 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(st.id, name, blobReader)
  scope: st
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobReader)
    principalId: pv.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output name string = pv.name
