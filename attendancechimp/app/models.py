"""
models.py — Data model for AttendanceChimp.

AttendanceChimp is an electronic class attendance tool.  Instructors create
courses and lectures; each lecture is assigned a random QR code.  Students
photograph the QR code and upload the image.  The system decodes the QR code,
matches it to a lecture, and records the attendance.

Entities
--------
- CourseProfile   : extends Django User → instructor-specific data
- StudentProfile  : extends Django User → student-specific data
- Course          : a course taught by one instructor
- Enrollment      : junction table linking students to courses
- Lecture         : a single class meeting (has a QR-code identifier)
- QRCodeUpload    : a student's uploaded QR-code photograph
"""

from django.db import models
from django.contrib.auth.models import User
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import string
import random
from PIL import Image
from pyzbar.pyzbar import decode as zbar_decode

logger = logging.getLogger(__name__) # set up tracking, auditing, and debugging
                                                               # allows using logger.warning(), logger.error(), 
                                                               # logger.info(), etc. Better than print() for debuggin... 


# ---------------------------------------------------------------------------
# User profiles
# ---------------------------------------------------------------------------
class StudentProfile(models.Model): 
    """
    This table stores all the student's names and their emails. It allows you to
    query to see what each student's name is and easilt find their email.
    """
    student_id = models.AutoField(primary_key=True)
    student_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

class InstructorProfile(models.Model):
    """
    This table stores all the instructor's names and their emails. It allows you to
    query to find out what clases an instrcutor is taking and also find out 
    about their contact info like email if you ever need help. 
    """
    instructor_id = models.AutoField(primary_key=True)
    instructor_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    



# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------
class Course(models.Model):
    """
    This class gives the description of the course. It provides the name of the 
    student enrolled in the course and the instructor that is teaching it. For 
    student and instructor, null is set to false in order to to get an accurate
    count of students and to make sure there is no unknown identites in the course. 
    It also provides the course's meeting schedule. 
    """
    course_id = models.AutoField(primary_key=True)
    course_name = models.CharField(max_length=255)
    instructor = models.ForeignKey(InstructorProfile, null=False, on_delete=models.PROTECT)
    meeting_schedule = models.CharField(max_length=255)



# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------
class Enrollment(models.Model):
    """
    This table connects the students to their courses. It does this by referencing 
    the primary keys in the StudentProfile table and the Course table. 
    """
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"],
                name="unique_student_course"
            )
        ]




# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------
class Lecture(models.Model):
    """
    This table links the QR code uploads for each lectures and maintains the date
    and course. The QR code is unique for each lecture. The QR identifier is the 
    unique string that identifies the QR code for that lecture class.
    """
    lecture_id = models.AutoField(primary_key=True)
    date = models.DateField()
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    QR_identifier = models.CharField(max_length=255, unique=True)



# ---------------------------------------------------------------------------
# QR Code Upload
# ---------------------------------------------------------------------------
class QRCodeUpload(models.Model):
    """
    This keeps track of what student uploaded the QR code during class. This allows
    the instructors to know who was there for proof of attendance.
    """
    qr_id = models.AutoField(primary_key=True)
    qr_image = models.ImageField(upload_to="qr_uploads/")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    lecture = models.ForeignKey(Lecture, null=True, on_delete=models.SET_NULL)
    time = models.DateTimeField()




# ---------------------------------------------------------------------------
# Helper / API functions
# ---------------------------------------------------------------------------

def QRcode_check(student_id, qr_code):
    """
    This API function returns the lecture that the student is enrolled into and where the scan was done
    to sure to check that the student is enrolled in the lecture they scanned the QR code for. 
    """
    lecture = Lecture.objects.filter(qr_identifier=qr_code, course__enrollment__student=student_id).first()
    if lecture is None:
        raise ValueError("QR code does not match a lecture they are enrollled into.")
    return lecture


def getUploadsForCourse(course):
    if not Course.objects.filter(course_name=course).exists():
        return []
    course_obj = Course.objects.get(course_name=course)

    days, times = course_obj.meeting_schedule.lower().split()
    start_str, end_str = times.split("-")
    start = datetime.strptime(start_str, "%H:%M").time()
    end = datetime.strptime(end_str, "%H:%M").time()

    day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    uploads = QRCodeUpload.objects.filter(lecture__course=course_obj)

    uploads_good = []
    for upload in uploads:
        local_time = upload.time.astimezone(ZoneInfo("America/Chicago"))

        if day_names[local_time.weekday()] not in days:
            continue
        if not (start <= local_time.time() <= end):
            continue

        uploads_good.append(upload)

    return uploads_good

# attendancechimp/app/models.py, next to getUploadsForCourse
def decodeQR(image):
    try:
        image_qr = Image.open(image)
        image_res = zbar_decode(image_qr)
    except Exception:
        return None
    qr_lst = image_qr[0].data.decode("utf-8")
    if qr_lst is None:
        return None
    return qr_lst
