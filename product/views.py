from product.models import Category, Product, Review, ProductImage
from product.serializers import CategorySerializer, ProductSerializer, ReviewSerializer, ProductImageSerializer
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from product.filters import ProductFilter
from rest_framework.filters import SearchFilter, OrderingFilter
from product.paginations import DefaultPagination
from api.permissions import IsAdminOrReadOnly
from product.permissions import IsReviewAuthorOrReadonly
from drf_yasg.utils import swagger_auto_schema

class CategoryViewSet(ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ProductViewSet(ModelViewSet):
    """
    API endpoint for managing products in the e-commerce store
     - Allows authenticated admin to create, update, and delete products
     - Allows users to browse and filter product
     - Support searching by name, description, and category
     - Support ordering by price and updated_at
    """
    @swagger_auto_schema(
        operation_summary="Create a product by admin",
        operation_description="This allow an admin to create a product",
        request_body=ProductSerializer,
        responses={
            201: ProductSerializer,
            400: "Bad Request"
        }
    )
    def create(self, request, *args, **kwargs):
        """Only authenticated admin can create product"""
        return super().create(request, *args, **kwargs)
    
    serializer_class = ProductSerializer
    pagination_class = DefaultPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'category__name']
    ordering_fields = ['price', 'updated_at']
    permission_classes = [IsAdminOrReadOnly]
    def get_queryset(self):
        return Product.objects.prefetch_related('images').all()

class ProductImageViewSet(ModelViewSet):
    serializer_class = ProductImageSerializer
    permission_classes = [IsAdminOrReadOnly]
    def perform_create(self, serializer):
        serializer.save(product_id=self.kwargs.get('product_pk'))
    def get_queryset(self):
        return ProductImage.objects.filter(product_id=self.kwargs.get('product_pk'))

class ReviewViewSet(ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsReviewAuthorOrReadonly]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)
    
    def get_queryset(self):
        return Review.objects.filter(product=self.kwargs.get('product_pk'))
    
    def get_serializer_context(self):
        return {'product_id': self.kwargs.get('product_pk')}