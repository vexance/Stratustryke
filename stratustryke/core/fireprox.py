import tldextract
import datetime
from stratustryke.core.credential import AWSCredential

class FireProx(object):
    def __init__(self, cred: AWSCredential, help_msg: str = None) -> None:
        self.help = help_msg
        self.region = cred._default_region
        self.session = cred.session().client('apigateway')


    def get_template(self, url: str):
        if url[-1] == '/':
            url = url[:-1]

        title = 'fireprox_{}'.format(
            tldextract.extract(url).domain
        )
        version_date = f'{datetime.datetime.now():%Y-%m-%dT%XZ}'
        template = '''
        {
          "swagger": "2.0",
          "info": {
            "version": "{{version_date}}",
            "title": "{{title}}"
          },
          "basePath": "/",
          "schemes": [
            "https"
          ],
          "paths": {
            "/": {
              "get": {
                "parameters": [
                  {
                    "name": "proxy",
                    "in": "path",
                    "required": true,
                    "type": "string"
                  },
                  {
                    "name": "X-My-X-Forwarded-For",
                    "in": "header",
                    "required": false,
                    "type": "string"
                  }
                ],
                "responses": {},
                "x-amazon-apigateway-integration": {
                  "uri": "{{url}}/",
                  "responses": {
                    "default": {
                      "statusCode": "200"
                    }
                  },
                  "requestParameters": {
                    "integration.request.path.proxy": "method.request.path.proxy",
                    "integration.request.header.X-Forwarded-For": "method.request.header.X-My-X-Forwarded-For"
                  },
                  "passthroughBehavior": "when_no_match",
                  "httpMethod": "ANY",
                  "cacheNamespace": "irx7tm",
                  "cacheKeyParameters": [
                    "method.request.path.proxy"
                  ],
                  "type": "http_proxy"
                }
              },
              "post": {
                "parameters": [
                  {
                    "name": "proxy",
                    "in": "path",
                    "required": true,
                    "type": "string"
                  },
                  {
                    "name": "X-My-X-Forwarded-For",
                    "in": "header",
                    "required": false,
                    "type": "string"
                  }
                ],
                "responses": {},
                "x-amazon-apigateway-integration": {
                  "uri": "{{url}}/",
                  "responses": {
                    "default": {
                      "statusCode": "200"
                    }
                  },
                  "requestParameters": {
                    "integration.request.path.proxy": "method.request.path.proxy",
                    "integration.request.header.X-Forwarded-For": "method.request.header.X-My-X-Forwarded-For"
                  },
                  "passthroughBehavior": "when_no_match",
                  "httpMethod": "ANY",
                  "cacheNamespace": "irx7tm",
                  "cacheKeyParameters": [
                    "method.request.path.proxy"
                  ],
                  "type": "http_proxy"
                }
              }
            },
            "/{proxy+}": {
              "x-amazon-apigateway-any-method": {
                "produces": [
                  "application/json"
                ],
                "parameters": [
                  {
                    "name": "proxy",
                    "in": "path",
                    "required": true,
                    "type": "string"
                  },
                  {
                    "name": "X-My-X-Forwarded-For",
                    "in": "header",
                    "required": false,
                    "type": "string"
                  }
                ],
                "responses": {},
                "x-amazon-apigateway-integration": {
                  "uri": "{{url}}/{proxy}",
                  "responses": {
                    "default": {
                      "statusCode": "200"
                    }
                  },
                  "requestParameters": {
                    "integration.request.path.proxy": "method.request.path.proxy",
                    "integration.request.header.X-Forwarded-For": "method.request.header.X-My-X-Forwarded-For"
                  },
                  "passthroughBehavior": "when_no_match",
                  "httpMethod": "ANY",
                  "cacheNamespace": "irx7tm",
                  "cacheKeyParameters": [
                    "method.request.path.proxy"
                  ],
                  "type": "http_proxy"
                }
              }
            }
          }
        }
        '''
        template = template.replace('{{url}}', url)
        template = template.replace('{{title}}', title)
        template = template.replace('{{version_date}}', version_date)

        return str.encode(template)


    def create_api(self, url) -> tuple:
        if not url:
            return (False, 'Target not supplied')

        template = self.get_template(url)
        response = self.session.import_rest_api(
            parameters={'endpointConfigurationTypes': 'REGIONAL'},
            body=template
        )

        resource_id, proxy_url = self.create_deployment(response['id'])
        return (True, f'({response["id"]}) {response["name"]} => {proxy_url} ({url})')


    # Pretty sure this can get axed, commenting out for now to be sure!
    # def update_api(self, api_id, url):
    #     if not any([api_id, url]):
    #         self.error('Please provide a valid API ID and URL end-point')

    #     if url[-1] == '/':
    #         url = url[:-1]

    #     resource_id = self.get_resource(api_id)
    #     if resource_id:
    #         response = self.session.update_integration(
    #             restApiId=api_id,
    #             resourceId=resource_id,
    #             httpMethod='ANY',
    #             patchOperations=[
    #                 {
    #                     'op': 'replace',
    #                     'path': '/uri',
    #                     'value': '{}/{}'.format(url, r'{proxy}'),
    #                 },
    #             ]
    #         )
    #         return response['uri'].replace('/{proxy}', '') == url
    #     else:
    #         self.error(f'Unable to update, no valid resource for {api_id}')
            

    def delete_api(self, api_id):
        if not api_id:
            return (False, 'Fireprox API id not supplied')
        
        items = self.list_api(api_id, silenced=True)
        for item in items:
            item_api_id = item['id']
            if item_api_id == api_id:
                response = self.session.delete_rest_api(
                    restApiId=api_id
                )
                return (True, f'Removed Fireprox API \'{api_id}\'')
            
        return (False, f'Specified API id \'{api_id}\' not found')
    

    def list_api(self, deleted_api_id=None, silenced=False):
        response = self.session.get_rest_apis()
        api_info = []
        for item in response['items']:
            try:
                created_dt = item['createdDate']
                api_id = item['id']
                name = item['name']
                proxy_url = self.get_integration(api_id).replace('{proxy}', '')
                url = f'https://{api_id}.execute-api.{self.region}.amazonaws.com/fireprox/'
                api_info.append({'id': api_id, 'proxy_target': proxy_url, 'proxy_endpoint': url})
            except:
                pass

        return api_info


    def create_deployment(self, api_id):
        if not api_id: return (False, 'Valid API id not provided')

        response = self.session.create_deployment(
            restApiId=api_id,
            stageName='fireprox',
            stageDescription='FireProx Prod',
            description='FireProx Production Deployment'
        )
        resource_id = response['id']
        return (resource_id, f'https://{api_id}.execute-api.{self.region}.amazonaws.com/fireprox/')


    def get_resource(self, api_id):
        if not api_id:
            return (False, 'Valid API id not provided')
        response = self.session.get_resources(restApiId=api_id)
        items = response['items']
        for item in items:
            item_id = item['id']
            item_path = item['path']
            if item_path == '/{proxy+}':
                return item_id
        return None


    def get_integration(self, api_id):
        if not api_id: return (False, 'Valid API id not provided')
        
        resource_id = self.get_resource(api_id)
        response = self.session.get_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='ANY'
        )
        return response['uri']
    
