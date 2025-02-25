@description('Location for all resources')
param location string = resourceGroup().location

@description('Name of Event Hub\'s namespace')
param eventHubNamespaceName string = 'eventHub${uniqueString(resourceGroup().id)}'

resource eventHubNamespace 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: eventHubNamespaceName
  location: location
  sku: {
    capacity: 1
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {}
}

resource eventHubNamespaceAuthRule 'Microsoft.EventHub/namespaces/authorizationRules@2024-01-01' = {
  parent: eventHubNamespace
  name: '${eventHubNamespaceName}-func-access'
  properties: {
    rights: [
      'Listen'
      'Send'
      'Manage'
    ]
  }
}


output eventHubNamespaceName string = eventHubNamespace.name
output eventHubNamespaceAuthRuleName string = eventHubNamespaceAuthRule.name
