from django.urls import path
from .views import (
    AllTransactionView, 
    CheckFriendRequestStatusView, 
    CreateTransactionView, 
    PortfolioView, 
    RegisterView, 
    LoginView, 
    SyndicateView, 
    AddMutualFriendView, 
    UpdateFriendRequestStatusView,
    UserSplitwiseView,
    TransactionSplitwiseView,
    db_health_check
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name="register"),
    path('login/', LoginView.as_view(), name="login"),
    path('portfolio/', PortfolioView.as_view(), name="portfolio"),
    path("syndicate/", SyndicateView.as_view(), name="syndicate"),
    path("create_friend/", AddMutualFriendView.as_view(), name="create_friend_list"),
    path("check_friend_request_status/", CheckFriendRequestStatusView.as_view(), name="check_friend_request_status"),
    path("update_friend_request_status/", UpdateFriendRequestStatusView.as_view(), name="update_friend_request_status"),
    path("all_transaction/", AllTransactionView.as_view(), name="all_transaction"),
    path("create_transaction/", CreateTransactionView.as_view(), name="create_transaction"),
    
    # New Splitwise endpoints
    path("my_splitwise/", UserSplitwiseView.as_view(), name="user_splitwise"),
    path("transaction/<uuid:transaction_id>/splitwise/", TransactionSplitwiseView.as_view(), name="transaction_splitwise"),
    path("health/db/", db_health_check, name="db_health_check"),

]