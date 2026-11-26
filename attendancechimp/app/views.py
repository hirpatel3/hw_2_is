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
from .models import StudentProfile, InstructorProfile, Course, Lecture, QRCodeUpload, getUploadsForCourse, decodeQR
from django.utils import timezone
import uuid
import json
import io
import random
import string

# from .models import (InstructorProfile, StudentProfile, Course, Enrollment,
#                      Lecture, QRCodeUpload, is_instructor, is_student,
#                      getUploadsForCourse)

CDT = zoneinfo.ZoneInfo("America/Chicago")

# I did use an LLM to help me parse the time and help to create the helper function.

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
    if not request.user.is_authenticated or not InstructorProfile.objects.filter(user=request.user).exists(): 
        return HttpResponse("Instructor Login is Required.", status=401)
   
    course_name = (request.POST.get("course_name") or request.POST.get("course-name") or "").strip()
    start = parse_time(request.POST.get("start-time"))
    end = parse_time(request.POST.get("end-time"))
    days_of_week = ["mon", "tue", "wed", "thu", "fri"]
    days = []
    for day in days_of_week:
        if request.POST.get(f"day-{day}"):
            days.append(day)
    
    Course.objects.create(
        course_name=course_name,
        instructor=request.user.instructorprofile,
        meeting_schedule=f"{','.join(days)} {start:%H:%M}-{end:%H:%M}",
    )
    return HttpResponse("Course was successfully created.", status=200)

@csrf_exempt
def createLecture(request):
    if not request.user.is_authenticated or not InstructorProfile.objects.filter(user=request.user).exists():
        return HttpResponse("Instructor Login is Required.", status=401)
    course_name = request.POST.get("choice", "").strip()
    qr_id = request.POST.get("qrdata", "").strip() 
    if not qr_id:
        alphabet = string.ascii_letters + string.digits
        qr_id = ''.join(random.choices(alphabet, k=16))
    course = Course.objects.get(course_name=course_name)
    Lecture.objects.create(
        course=course,
        date=timezone.now(),
        QR_identifier=qr_id
    )

    return HttpResponse("Lecture was successfully created.", status=200)

@csrf_exempt
def createQRCodeUpload(request):
    if not request.user.is_authenticated or not StudentProfile.objects.filter(user=request.user).exists(): 
                return HttpResponse("Instructor Login is Required.", status=401)
    
    image_qr = request.FILES.get("imageUpload")
    student = StudentProfile.objects.get(user=request.user)
    lecture = None
    text = decodeQR(image_qr)
    if not text is None:
        lecture = Lecture.objects.filter(QR_identifier=text).first()
        
    if text is None or lecture is None:
        QRCodeUpload.objects.create(
                qr_image=image_qr,
                student=student,
                time=timezone.now(),
                lecture=lecture
            )
        return HttpResponse("QR code did not work.", status=401)
    else:
        QRCodeUpload.objects.create(
            qr_image=image_qr,
            student=student,
            time=timezone.now(),
            lecture=lecture
        )
    return HttpResponse("QR Code uploaded successfully.", status=200)
    
def dumpUploads(request):
    if not request.user.is_authenticated or not InstructorProfile.objects.filter(user=request.user).exists():
        return HttpResponse("Instructor Login is Required.", status=401)

    uploads = QRCodeUpload.objects.select_related('student__user').all()
    data = []
    for upload in uploads:
        data.append({
            "username": upload.student.user.username,
            "upload_time": upload.time.strftime("%Y-%m-%d %H:%M:%S")
        })

    return JsonResponse(data, safe=False)

def getUploads(request):
    if not request.user.is_authenticated or not InstructorProfile.objects.filter(user=request.user).exists():
        return HttpResponse("Instructor Login is Required.", status=401)
    course_var = request.GET.get("course")
    if not course_var:
        return JsonResponse({"error": "Missing course parameter"}, status=400)
    uploads_qr = getUploadsForCourse(course_var)
    if uploads_qr is None:
        return JsonResponse([], safe=False)
    
    obj = []
    for qr in uploads_qr:
        dic = {"username": qr.student.user.username, "upload_time": timezone.localtime(qr.time).strftime("%Y-%m-%d %H:%M:%S")}
        obj.append(dic)
    return JsonResponse(obj, safe=False)
# ---------------------------------------------------------------------------
# HW6  — getUploads
# ---------------------------------------------------------------------------



