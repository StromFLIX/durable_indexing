@description('Name of the resource.')
param name string
@description('Location to deploy the resource. Defaults to the location of the resource group.')
param location string = resourceGroup().location
@description('Tags for the resource.')
param tags object = {}
@description('Whether to enable public network access. Defaults to Enabled.')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

module openAi 'br/public:avm/res/cognitive-services/account:0.7.2' = {
  name: '${name}-deployment'
  scope: resourceGroup()
  params: {
    tags: tags
    name: name
    location: location
    kind: 'OpenAI'
    publicNetworkAccess: publicNetworkAccess
    customSubDomainName: name
    sku: 'S0'
    deployments: [
      {
        name: 'embedding'
        model: {
          format: 'OpenAI'
          name: 'text-embedding-3-large'
          version: '1'
        }
        sku: {
          name: 'Standard'
          capacity: 100
        }
      }
    ]
    disableLocalAuth: true
  }
}

@description('ID for the deployed OpenAI resource.')
output id string = openAi.outputs.resourceId
@description('Name for the deployed OpenAI resource.')
output name string = openAi.outputs.name
@description('Endpoint for the deployed OpenAI resource.')
output endpoint string = openAi.outputs.endpoint
@description('Identity principal ID for the deployed OpenAI resource.')
output systemIdentityPrincipalId string = openAi.outputs.systemAssignedMIPrincipalId
