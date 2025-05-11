from rest_framework import renderers
from rest_framework.utils import json

class CustomJSONRenderer(renderers.JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response_data = {}
        
        # Check if the response contains an error
        if 'error' in data:
            response_data['error'] = data['error']
        else:
            response_data['data'] = data
        
        # Add status code if available
        if renderer_context and 'response' in renderer_context:
            response = renderer_context['response']
            response_data['status'] = response.status_code
        
        return json.dumps(response_data)

class CustomBrowsableAPIRenderer(renderers.BrowsableAPIRenderer):
    def get_context(self, data, accepted_media_type, renderer_context):
        context = super().get_context(data, accepted_media_type, renderer_context)
        
        # Add custom template context
        context['title'] = 'API Documentation'
        context['description'] = 'Interactive API documentation'
        
        return context

class CustomHTMLRenderer(renderers.TemplateHTMLRenderer):
    template_name = 'api/custom_template.html'
    
    def get_template_context(self, data, renderer_context):
        context = super().get_template_context(data, renderer_context)
        
        # Add custom context data
        context['title'] = 'API Response'
        context['data'] = data
        
        return context 