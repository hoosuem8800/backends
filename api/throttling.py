from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, ScopedRateThrottle

class AnonBurstRateThrottle(AnonRateThrottle):
    scope = 'anon_burst'
    rate = '10/minute'

class AnonSustainedRateThrottle(AnonRateThrottle):
    scope = 'anon_sustained'
    rate = '100/day'

class UserBurstRateThrottle(UserRateThrottle):
    scope = 'user_burst'
    rate = '20/minute'

class UserSustainedRateThrottle(UserRateThrottle):
    scope = 'user_sustained'
    rate = '200/day'

class DoctorBurstRateThrottle(UserRateThrottle):
    scope = 'doctor_burst'
    rate = '30/minute'

class DoctorSustainedRateThrottle(UserRateThrottle):
    scope = 'doctor_sustained'
    rate = '300/day'

class AdminBurstRateThrottle(UserRateThrottle):
    scope = 'admin_burst'
    rate = '50/minute'

class AdminSustainedRateThrottle(UserRateThrottle):
    scope = 'admin_sustained'
    rate = '500/day'

class RegistrationThrottle(ScopedRateThrottle):
    scope = 'registration'
    rate = '5/hour'

class LoginThrottle(ScopedRateThrottle):
    scope = 'login'
    rate = '10/hour'

class FileUploadThrottle(ScopedRateThrottle):
    scope = 'file_upload'
    rate = '20/hour'

class PaymentThrottle(ScopedRateThrottle):
    scope = 'payment'
    rate = '30/hour' 