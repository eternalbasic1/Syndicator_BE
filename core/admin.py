from django.contrib import admin

# Register your models here.
from .models import CustomUser, FriendList, FriendRequest, Transactions, Splitwise

admin.site.register(CustomUser)
admin.site.register(FriendList)
admin.site.register(FriendRequest)
admin.site.register(Transactions)
admin.site.register(Splitwise)
