// Optional private networking (privateNetworking=true): a VNet with a private-endpoint subnet behind
// an NSG, and private DNS zones linked to the VNet. Mirrors infra/terraform/modules/private-network.
// Not deployed.
param location string
param tags object
param name string
param addressPrefix string = '10.60.0.0/16'
@description('Private DNS zones: [{ key, zone }]')
param dnsZones array

// Default rules only; tighten per client policy.
resource nsg 'Microsoft.Network/networkSecurityGroups@2024-05-01' = {
  name: 'nsg-${name}'
  location: location
  tags: tags
  properties: { securityRules: [] }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: [addressPrefix] }
    subnets: [
      {
        name: 'pe'
        properties: { addressPrefix: cidrSubnet(addressPrefix, 24, 2), networkSecurityGroup: { id: nsg.id }, privateEndpointNetworkPolicies: 'Disabled' }
      }
    ]
  }
}

resource dns 'Microsoft.Network/privateDnsZones@2020-06-01' = [for z in dnsZones: {
  name: z.zone
  location: 'global'
  tags: tags
}]

resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [for (z, i) in dnsZones: {
  parent: dns[i]
  name: 'link-${name}'
  location: 'global'
  properties: { virtualNetwork: { id: vnet.id }, registrationEnabled: false }
}]

output peSubnetId string = vnet.properties.subnets[0].id
output nsgId string = nsg.id
output zoneIds object = toObject(dnsZones, z => z.key, z => resourceId('Microsoft.Network/privateDnsZones', z.zone))
