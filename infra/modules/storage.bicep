// ADLS Gen2 landing zone (target of an OneLake shortcut). Shared keys off, OAuth by default.
param location string
param tags object
param name string
param sku string = 'Standard_LRS'
param readerPrincipalId string

var blobReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1' // Storage Blob Data Reader

resource st 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: sku }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: st
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
    containerDeleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [
  for c in ['landing', 'partner-share']: {
    parent: blob
    name: c
    properties: { publicAccess: 'None' }
  }
]

resource reader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(st.id, readerPrincipalId, blobReader)
  scope: st
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobReader)
    principalId: readerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output id string = st.id
output name string = st.name
