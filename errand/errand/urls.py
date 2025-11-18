"""
URL configuration for errand project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from errands import views as errands_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Root dispatcher: serve API list for authenticated/JSON clients, otherwise
    # redirect anonymous browser users to the web login page.
    path('', errands_views.root_dispatch, name='root_dispatch'),
    path('api/user/', include("user.urls")),
    path('api/errands/', include("errands.urls")),
    path('api/payment/', include("payment.urls")),
    # also include a namespaced copy so tests and templates can reverse as 'payment:...'
    path('payment_ns/', include(("payment.urls", "payment"), namespace="payment")),
    # Web (server-rendered) front-end (mounted with 'errands' namespace so
    # templates and redirects can reverse 'errands:list')
    path('', include(("errands.urls", "errands"), namespace="errands")),
    path('user/', include('user.urls')),
]

