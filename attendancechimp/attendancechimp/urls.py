from django.contrib import admin
from django.urls import path, include
from app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('app/', include('app.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', views.index, name='home'),
    path('index.html', views.index, name='index_html'),
    path("new_course", views.new_course, name="new_course"),
    path("new_lecture", views.new_lecture, name="new_lecture"),
    path("new_qr_upload", views.new_qr_upload, name="new_qr_upload"),
    path("createCourse", views.createCourse, name="createCourse"),
    path("createLecture", views.createLecture, name="createLecture"),
    path("createQRCodeUpload", views.createQRCodeUpload, name="createQRCodeUpload"),
    path("dumpUploads", views.dumpUploads, name="dumpUploads"),
]
