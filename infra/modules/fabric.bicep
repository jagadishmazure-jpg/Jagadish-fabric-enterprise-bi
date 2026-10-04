// Microsoft Fabric capacity. Billed per hour while running; pause it when idle.
param location string
param tags object
param name string
param sku string = 'F2'
param admins array

resource capacity 'Microsoft.Fabric/capacities@2023-11-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: sku, tier: 'Fabric' }
  properties: {
    administration: { members: admins }
  }
}

output name string = capacity.name
output id string = capacity.id
