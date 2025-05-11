from django_filters import rest_framework as filters
from .models import Scan, Appointment, Payment

class ScanFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name='upload_date', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='upload_date', lookup_expr='lte')
    status = filters.CharFilter(field_name='status')
    
    class Meta:
        model = Scan
        fields = ['start_date', 'end_date', 'status']

class AppointmentFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name='date_time', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='date_time', lookup_expr='lte')
    status = filters.CharFilter(field_name='status')
    
    class Meta:
        model = Appointment
        fields = ['start_date', 'end_date', 'status']

class PaymentFilter(filters.FilterSet):
    start_date = filters.DateFilter(field_name='created_at', lookup_expr='gte')
    end_date = filters.DateFilter(field_name='created_at', lookup_expr='lte')
    status = filters.CharFilter(field_name='status')
    payment_method = filters.CharFilter(field_name='payment_method')
    
    class Meta:
        model = Payment
        fields = ['start_date', 'end_date', 'status', 'payment_method'] 