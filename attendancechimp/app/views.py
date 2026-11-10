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
from django.views.decorators.http import require_GET
from .models import StudentProfile, InstructorProfile
from django.contrib.auth.decorators import login_required
from .models import StudentProfile, InstructorProfile, Course
from .models import StudentProfile, InstructorProfile, Course, Lecture
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
@require_GET
def new(request):
    return render(request, "app/new.html")

@csrf_exempt
def createUser(request):
    if request.method != "POST":
        return HttpResponse("Not allowed", status=405)
    email = request.POST.get('email')
    if User.objects.filter(email=email).exists():
            return HttpResponse("Email already exists.", status=400)
    user_name = request.POST.get('user_name')
    if not user_name:
        return HttpResponse("Username is required.", status=400)
    password = request.POST.get('password')
    is_student = request.POST.get('is_student')

    sign_up = User.objects.create_user(
        username=user_name,
        email=email,
        password=password
    )
    if is_student == "0":
        InstructorProfile.objects.create(user=sign_up,instructor_name=user_name,email=email)
    else:
        StudentProfile.objects.create(user=sign_up,student_name=user_name,email=email)
    return HttpResponse("Account was successfully created.", status=200)




# ---------------------------------------------------------------------------
# HW5  — courses, lectures, QR uploads, dump
# ---------------------------------------------------------------------------
DAYS = ["mon", "tue", "wed", "thu", "fri"]


def is_instructor_user(user):
    return user.is_authenticated and InstructorProfile.objects.filter(user=user).exists()


def parse_time(value):
    """Accepts HH:MM or HH:MM:SS (browser time inputs send either)."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except (ValueError, TypeError):
            pass
    return None


@login_required
def new_course(request):
    return render(request, 'app/new_course.html')


@login_required
def new_lecture(request):
    return render(request, 'app/new_lecture.html', {"courses": Course.objects.all()})


@login_required
def new_qr_upload(request):
    return render(request, 'app/new_qr_upload.html')


@csrf_exempt
def createCourse(request):
    if request.method != "POST":
            return HttpResponse("That is not allowed", status=405)
    if not InstructorProfile.objects.filter(user=request.user).exists(): 
        return HttpResponse("Instructor Login is Required.", status=401)
   


    course_name = request.POST.get("course-name", "").strip()
    start = parse_time(request.POST.get("start-time"))
    end = parse_time(request.POST.get("end-time"))
    days = {d: bool(request.POST.get(f"day-{d}")) for d in DAYS}

    if not course_name:
        return HttpResponse("course-name is required.", status=400)
    if start is None or end is None:
        return HttpResponse("start-time and end-time must be in HH:MM format.", status=400)
    if not any(days.values()):
        return HttpResponse("Please select at least one day.", status=400)

    Course.objects.create(
        name=course_name,
        start_time=start, 
        end_time=end,
        instructor=request.user.instructorprofile,
        **days,
    )
    return HttpResponse("Course was successfully created.", status=200)

@csrf_exempt
def createLecture(request):
    if not is_instructor_user(request.user):
        return HttpResponse("Instructor login required.", status=401)
    if request.method != "POST":
        return HttpResponse("Not allowed", status=405)

    course_name = request.POST.get("choice", "").strip()
    if not course_name:
        return HttpResponse("This choice is required.", status=400)

    try:
        course = Course.objects.get(name=course_name)
    except Course.DoesNotExist:
        return HttpResponse("Course not found.", status=404)

    Lecture.objects.create(course=course)
    return HttpResponse("Lecture was successfully created.", status=200)

# ---------------------------------------------------------------------------
# HW6  — getUploads
# ---------------------------------------------------------------------------



