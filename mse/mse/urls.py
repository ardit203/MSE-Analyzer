"""
URL configuration for mse project.

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
from django.urls import path

from django.conf import settings
from django.conf.urls.static import static
from App.views import *

urlpatterns = [
    path('admin/', admin.site.urls),
    path('save_query_params/', save_query_params, name='save_query_params'),
    #
    path('<str:lang>/home/', home, name='home'),
    path('home/', redirect_home),
    #
    path('<str:lang>/issuers-data/', issuers_data, name='issuers-data'),
    path('issuers-data/', redirect_issuers_data),

    path('<str:lang>/visualization/', visualization, name='visualization'),
    path('visualization/', redirect_visualization),

    path('<str:lang>/technical/', technical, name='technical'),
    path('technical/', redirect_technical),

    path('<str:lang>/fundamental/', fundamental, name='fundamental'),
    path('<str:lang>/fundamental/news/<str:issuer>/<str:document_id>', news, name='news'),
    path('fundamental/', redirect_fundamental),

    path('<str:lang>/prediction/', prediction, name='prediction'),
    path('prediction/', redirect_prediction),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
