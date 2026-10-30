"""
views.py — HTTP request handlers for AttendanceChimp.

Each view corresponds to one URL endpoint.  Views receive an HTTP request,
interact with the database via models.py, and return an HTTP response.
"""

from django.shortcuts import render, redirect
from django.http import (HttpResponse, HttpResponseForbidden,
                         HttpResponseBadRequest, JsonResponse)
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from datetime import datetime
import zoneinfo
from .models import StudentProfile, InstructorProfile
import json
import io

# from .models import (InstructorProfile, StudentProfile, Course, Enrollment,
#                      Lecture, QRCodeUpload, is_instructor, is_student,
#                      getUploadsForCourse)

CDT = zoneinfo.ZoneInfo("America/Chicago")


# ---------------------------------------------------------------------------
# HW2  — index, time, sum
# ---------------------------------------------------------------------------

def index(request):
    """Render the home page (index.html)."""
    date = datetime.now(CDT)
    context = context = {
            "time_view": date.strftime('%H:%M'),
            "user": request.user,
        }
    return render(request, 'app/index.html', context)

def time_view(request):
    date = datetime.now(CDT)
    return HttpResponse(date.strftime('%H:%M'))

def sum_view(request):
    n1 = float(request.GET.get('n1'))
    n2 = float(request.GET.get('n2'))
    return HttpResponse(f"<p>{float(n1+n2)}</p>")


# ---------------------------------------------------------------------------
# HW4  — user creation
# ---------------------------------------------------------------------------
def new(request):
    return render(request, "app/new.html")

def createUser(request):
    email = request.POST.get('email')
    if User.objects.filter(email=email).exists():
            return HttpResponse("Email already exists.", status=400)
    user_name = request.POST.get('user_name')
    password = request.POST.get('password')
    is_student = request.POST.get('is_student')

    sign_up = User.objects.create_user(
        username=user_name,
        email=email,
        password=password
    )

    if is_student == "yes":
        StudentProfile.objects.create(user=sign_up,student_name=user_name,email=email
        )
    else:
        InstructorProfile.objects.create(user=sign_up,instructor_name=user_name,email=email
        )

    login(request, sign_up)
    return HttpResponse("Account successfully created!", status=200)




# ---------------------------------------------------------------------------
# HW5  — courses, lectures, QR uploads, dump
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# HW6  — getUploads
# ---------------------------------------------------------------------------



