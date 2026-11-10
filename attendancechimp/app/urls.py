from django.urls import path, include
from . import views
urlpatterns = [
  path('time', views.time_view, name='time'),
  path('sum', views.sum_view, name='sum'),
  path('', views.index, name='home'),
  path('index.html', views.index, name='index_html'),
  path('new', views.new, name='new'),
  path('createUser', views.createUser, name='createUser'),
  path('accounts/', include('django.contrib.auth.urls')), 
  path("new_course", views.new_course, name="new_course"),
  path("new_lecture", views.new_lecture, name="new_lecture"),
  path("new_qr_upload", views.new_qr_upload, name="new_qr_upload"),
  path("createCourse", views.createCourse, name="createCourse"),
  path("createLecture", views.createLecture, name="createLecture"),
]
