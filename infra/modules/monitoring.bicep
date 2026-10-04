// Log Analytics (pay-per-GB with a daily cap) + workspace-based Application Insights.
param location string
param tags object
param logAnalyticsName string
param appInsightsName string
param dailyQuotaGb int = 1
param retentionInDays int = 30

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: retentionInDays
    workspaceCapping: { dailyQuotaGb: dailyQuotaGb }
  }
}

resource appi 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
  }
}

output logAnalyticsId string = law.id
output logAnalyticsName string = law.name
output appInsightsId string = appi.id
