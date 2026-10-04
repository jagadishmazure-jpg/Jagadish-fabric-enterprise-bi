// Event Hubs (live checkouts) + IoT Hub (freezer sensors), both read by a Fabric Eventstream.
// Event Hubs uses Entra ID only (local auth off). Basic allows only $Default, so the Eventstream
// consumer group is created on Standard and above.
param location string
param tags object
param namespaceName string
param iotHubName string
param eventHubsSku string = 'Basic'
param iotHubSku string = 'F1'
param receiverPrincipalId string
param logAnalyticsId string

var receiverRole = 'a638d3c7-ab3a-418d-83e6-5f17a39d4fde' // Azure Event Hubs Data Receiver

resource ns 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  tags: tags
  sku: { name: eventHubsSku, tier: eventHubsSku, capacity: 1 }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
  }
}

resource hub 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: ns
  name: 'pos-events'
  properties: {
    partitionCount: 2
    messageRetentionInDays: 1
  }
}

resource cg 'Microsoft.EventHub/namespaces/eventhubs/consumergroups@2024-01-01' = if (eventHubsSku != 'Basic') {
  parent: hub
  name: 'fabric-eventstream'
}

resource iot 'Microsoft.Devices/IotHubs@2023-06-30' = {
  name: iotHubName
  location: location
  tags: tags
  sku: { name: iotHubSku, capacity: 1 }
  properties: {
    minTlsVersion: '1.2'
    routing: {
      fallbackRoute: {
        name: '$fallback'
        source: 'DeviceMessages'
        condition: 'true'
        endpointNames: ['events']
        isEnabled: true
      }
    }
  }
}

resource iotCg 'Microsoft.Devices/IotHubs/eventHubEndpoints/ConsumerGroups@2023-06-30' = {
  name: '${iot.name}/events/fabric-eventstream'
  properties: { name: 'fabric-eventstream' }
}

resource receiver 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(ns.id, receiverPrincipalId, receiverRole)
  scope: ns
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', receiverRole)
    principalId: receiverPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource nsDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'to-log-analytics'
  scope: ns
  properties: {
    workspaceId: logAnalyticsId
    logs: [{ categoryGroup: 'allLogs', enabled: true }]
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

resource iotDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'to-log-analytics'
  scope: iot
  properties: {
    workspaceId: logAnalyticsId
    logs: [{ categoryGroup: 'allLogs', enabled: true }]
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

output namespaceName string = ns.name
output iotHubName string = iot.name
