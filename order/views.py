from rest_framework.viewsets import GenericViewSet, ModelViewSet
from rest_framework.mixins import RetrieveModelMixin, DestroyModelMixin
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponseRedirect

from order.models import Cart, CartItem, Order
from order.serializers import (
    CartSerializer,
    CartItemSerializer,
    AddCartItemSerializer,
    UpdateCartItemSerializer,
    OrderSerializer,
    CreateOrderSerializer,
    UpdateOrderSerializer,
    EmptySerializer
)
from order.services import OrderService
from sslcommerz_lib import SSLCOMMERZ
from django.conf import settings as main_settings





class CartViewSet(RetrieveModelMixin, DestroyModelMixin, GenericViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Cart.objects.none()
        return Cart.objects.prefetch_related('items__product').filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        existing_cart = Cart.objects.filter(user=request.user).first()
        if existing_cart:
            serializer = self.get_serializer(existing_cart)
            return Response(serializer.data, status=status.HTTP_200_OK)

        cart = Cart.objects.create(user=request.user)
        serializer = self.get_serializer(cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CartItemViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AddCartItemSerializer
        elif self.request.method == 'PATCH':
            return UpdateCartItemSerializer
        return CartItemSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['cart_id'] = self.kwargs.get('cart_pk')
        return context

    def get_queryset(self):
        return CartItem.objects.select_related('product').filter(cart_id=self.kwargs.get('cart_pk'))


class OrderViewset(ModelViewSet):
    http_method_names = ['get', 'post', 'delete', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ['update_status', 'destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'cancel':
            return EmptySerializer
        if self.action == 'create':
            return CreateOrderSerializer
        elif self.action == 'update_status':
            return UpdateOrderSerializer
        return OrderSerializer

    def get_serializer_context(self):
        if getattr(self, 'swagger_fake_view', False):
            return super().get_serializer_context()
        return {'user_id': self.request.user.id, 'user': self.request.user}

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Order.objects.none()
        if self.request.user.is_staff:
            return Order.objects.prefetch_related('items__product').all()
        return Order.objects.prefetch_related('items__product').filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        OrderService.cancel_order(order=order, user=request.user)
        return Response({'status': 'Order canceled'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        serializer = UpdateOrderSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        updated_status = serializer.validated_data.get('status', 'unknown')
        return Response({'status': f'Order status updated to {updated_status}'}, status=status.HTTP_200_OK)
    
@api_view(['POST'])
def initiate_payment(request):
    user = request.user
    order_id = request.data.get("orderId")

    # 1️⃣ Validate order belongs to user
    try:
        order = Order.objects.prefetch_related('items').get(id=order_id, user=user)
    except Order.DoesNotExist:
        return Response({"error": "Invalid order"}, status=400)

    # 2️⃣ Prevent double payment
    if order.status == "Paid":
        return Response({"error": "Order already paid"}, status=400)

    # 3️⃣ Calculate from DB (NOT frontend)
    amount = order.total_price
    num_items = order.items.count()

    settings = {
        'store_id': main_settings.SSLCOMMERZ_STORE_ID,
        'store_pass': main_settings.SSLCOMMERZ_STORE_PASS,
        'issandbox': True  # False in production
    }

    sslcz = SSLCOMMERZ(settings)

    post_body = {
        'total_amount': amount,
        'currency': "BDT",
        'tran_id': f"txn_{order.id}",
        'success_url': f"{main_settings.BACKEND_URL}/api/v1/payment/success/",
        'fail_url': f"{main_settings.BACKEND_URL}/api/v1/payment/fail/",
        'cancel_url': f"{main_settings.BACKEND_URL}/api/v1/payment/cancel/",
        'ipn_url': f"{main_settings.BACKEND_URL}/api/v1/payment/ipn/",
        'emi_option': 0,
        'cus_name': f"{user.first_name} {user.last_name}",
        'cus_email': user.email,
        'cus_phone': user.phone_number,
        'cus_add1': user.address,
        'cus_city': "Dhaka",
        'cus_country': "Bangladesh",
        'shipping_method': "NO",
        'multi_card_name': "",
        'num_of_item': num_items,
        'product_name': "E-commerce Order",
        'product_category': "General",
        'product_profile': "general"
    }

    response = sslcz.createSession(post_body)

    if response.get("status") == "SUCCESS":
        return Response({
            "payment_url": response.get("GatewayPageURL")
        })

    return Response({
        "error": response
    }, status=400)

@api_view(['POST'])
def payment_success(request):
    print("Inside success")
    order_id = request.data.get("tran_id").split('_')[1]
    order = Order.objects.get(id=order_id)
    order.status = "Ready To Ship"
    order.save()
    return HttpResponseRedirect(f"{main_settings.FRONTEND_URL}/dashboard/orders/")


@api_view(['POST'])
def payment_cancel(request):
    return HttpResponseRedirect(f"{main_settings.FRONTEND_URL}/dashboard/orders/")


@api_view(['POST'])
def payment_fail(request):
    print("Inside fail")
    return HttpResponseRedirect(f"{main_settings.FRONTEND_URL}/dashboard/orders/")