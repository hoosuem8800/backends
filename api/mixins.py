from rest_framework import mixins, viewsets
from .permissions import IsOwnerOrReadOnly, IsOwnerOrDoctor, IsOwnerOrAdmin

class OwnerMixin:
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class OwnerOrDoctorMixin:
    permission_classes = [IsOwnerOrDoctor]

class OwnerOrAdminMixin:
    permission_classes = [IsOwnerOrAdmin]

class OwnerOrReadOnlyMixin:
    permission_classes = [IsOwnerOrReadOnly]

class CreateListRetrieveViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    pass

class CreateListRetrieveUpdateViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet
):
    pass

class ListRetrieveViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    pass

class CreateRetrieveViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    pass 