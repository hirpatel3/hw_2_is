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

import logging
import string
import random

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
    student_id = models.IntegerField(primary_key=True)
    student_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

class InstructorProfile(models.Model):
    """
    This table stores all the instructor's names and their emails. It allows you to
    query to find out what clases an instrcutor is taking and also find out 
    about their contact info like email if you ever need help. 
    """
    instructor_id = models.IntegerField(primary_key=True)
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
    course_id = models.IntegerField(primary_key=True)
    course_name = models.CharField(max_length=255)
    instructor = models.ForeignKey(InstructorProfile, null=False, on_delete=models.PROTECT)
    meeting_schedule = models.CharField(255)



# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------
class Enrollment(models.Model):
    """
    This table connects the students to their courses. It does this by referencing 
    the primary keys in the StudentProfile table and the Course table. 
    """
    pk = models.CompositePrimaryKey("student", "course")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)




# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------
class Lecture(models.Model):
    """
    This table links the QR code uploads for each lectures and maintains the date
    and course. The QR code is unique for each lecture. The QR identifier is the 
    unique string that identifies the QR code for that lecture class.
    """
    lecture_id = models.IntegerField(primary_key=True)
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
    qr_id = models.ImageField(primary_key=True)
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


