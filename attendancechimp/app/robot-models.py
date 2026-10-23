# The LLM I used for this was Claude and I gave it this prompt:
# can you generate a models.py for these speciifcations InstructorProfile / StudentProfile tables (instead of one Users table – think why. . . )
# • Course table with at least name, instructor, meeting schedule
# • Enrollment table: links students to courses (many-to-many)
# • Lecture table: linked to a course, has a date and a QR identifier
# • QRCodeUpload table: linked to a student and (optionally) a lecture and define Django model classes for each table from the ER
# diagram (see Django documentation / class slides). Write a detailed doc string and, if applicable,
# helper functions.
"""
models.py - Data layer for a QR-code based lecture attendance system.

ER OVERVIEW
-----------
                      +--------------------+
   auth.User 1--1 --> | InstructorProfile  |
        |             +---------+----------+
        |                       | 1
        |                       |
        |                       | N
        |             +---------v----------+   1      N  +-----------+
        |             |       Course       |-------------| Lecture   |
        |             +---------+----------+             +-----+-----+
        |                       | 1                            | 1
        |                       | N                            | 0..N
        |             +---------v----------+             +-----v--------+
   auth.User 1--1 --> |    Enrollment      |             | QRCodeUpload |
        |             |  (student<->course)|             +-----^--------+
        |             +---------^----------+                   | N
        |                       | N                            |
        |             +---------+----------+ 1                 |
        +-----------> |   StudentProfile   |-------------------+
                      +--------------------+

WHY TWO PROFILE TABLES INSTEAD OF ONE "USERS" TABLE?
----------------------------------------------------
Instructors and students are different kinds of actors:

1. Different attributes. Students have a student number, major and year;
   instructors have an employee id, department and office. One combined
   table would need many nullable columns ("student_id" empty for every
   instructor and vice versa), which weakens data integrity.
2. Different relationships. Only instructors can *teach* a Course and only
   students can be *enrolled* in one. With separate tables the foreign keys
   enforce this at the database level: Course.instructor must point to an
   InstructorProfile, Enrollment.student must point to a StudentProfile. With a
   single table, a student could be assigned as an instructor and nothing
   in the schema would stop it.
3. Different permissions. Instructors create lectures and view attendance;
   students upload QR codes. Separate tables make role checks simple
   (hasattr(user, "instructor_profile")) and keep authorization logic clean.
4. Extensibility. Role-specific fields can evolve independently.

Authentication itself (username, password, e-mail) stays in Django's built-in
User model (settings.AUTH_USER_MODEL). Each profile is a OneToOne extension of
it, which is the pattern recommended by the Django documentation.

NOTES
-----
* Enrollment is the explicit "through" table of a many-to-many relationship
  between StudentProfile and Course, so it can carry extra data (date, status)
  and a uniqueness constraint (a student can enroll in a course only once).
* Lecture.qr_identifier is a random UUID. The instructor's QR code encodes it;
  when a student uploads a photo of the QR code, the decoded text is matched
  against this identifier to determine which lecture was attended.
* QRCodeUpload.lecture is optional (null=True): an upload is stored first and
  may be linked to a lecture later, once the QR code has been decoded, or may
  remain unlinked if the code is invalid/unreadable.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# --------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------

class InstructorProfile(models.Model):
    """
    Extra information for a user who teaches courses.

    One-to-one with the auth user. Deleting the user deletes the profile.
    Deleting an instructor who still has courses is blocked
    (see Course.instructor, on_delete=PROTECT).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="instructor_profile",
    )
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, blank=True)
    office = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        """Display name, falling back to the username if no name is set."""
        return self.user.get_full_name() or self.user.get_username()


class StudentProfile(models.Model):
    """
    Extra information for a user who attends courses.

    One-to-one with the auth user. Courses are reached through Enrollment
    (see the `courses` property).
    """

    YEAR_CHOICES = [
        (1, "Freshman"),
        (2, "Sophomore"),
        (3, "Junior"),
        (4, "Senior"),
        (5, "Graduate"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    student_id = models.CharField(max_length=20, unique=True)
    major = models.CharField(max_length=100, blank=True)
    year = models.PositiveSmallIntegerField(choices=YEAR_CHOICES, default=1)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]

    def __str__(self):
        return f"{self.full_name} ({self.student_id})"

    @property
    def full_name(self):
        """Display name, falling back to the username if no name is set."""
        return self.user.get_full_name() or self.user.get_username()

    @property
    def courses(self):
        """QuerySet of Courses in which this student is actively enrolled."""
        return Course.objects.filter(
            enrollments__student=self,
            enrollments__status=Enrollment.Status.ACTIVE,
        )

    def is_enrolled_in(self, course):
        """True if the student is actively enrolled in `course`."""
        return self.enrollments.filter(
            course=course, status=Enrollment.Status.ACTIVE
        ).exists()


# --------------------------------------------------------------------------
# Courses and enrollment
# --------------------------------------------------------------------------

class Course(models.Model):
    """
    A course taught by exactly one instructor.

    The meeting schedule is stored as:
      * meeting_days - comma-separated weekday codes, e.g. "MON,WED,FRI"
      * start_time / end_time - time of day each meeting takes place
      * location - room or building
      * start_date / end_date - the term during which the course runs

    Students are linked through Enrollment; `students` is the convenience
    many-to-many accessor.
    """

    DAY_CHOICES = [
        ("MON", "Monday"),
        ("TUE", "Tuesday"),
        ("WED", "Wednesday"),
        ("THU", "Thursday"),
        ("FRI", "Friday"),
        ("SAT", "Saturday"),
        ("SUN", "Sunday"),
    ]
    # Maps datetime.weekday() (Monday=0) to our day codes.
    _WEEKDAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

    name = models.CharField(max_length=200)
    code = models.CharField(
        max_length=20, unique=True, help_text="Catalog code, e.g. CS101"
    )
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(
        InstructorProfile,
        on_delete=models.PROTECT,  # don't silently delete courses
        related_name="courses",
    )
    students = models.ManyToManyField(
        StudentProfile,
        through="Enrollment",
        related_name="enrolled_courses",
        blank=True,
    )

    # Meeting schedule
    meeting_days = models.CharField(
        max_length=27,
        help_text='Comma-separated day codes, e.g. "MON,WED,FRI"',
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=100, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    # ---- validation -----------------------------------------------------

    def clean(self):
        """Validate schedule fields (called by ModelForms / full_clean())."""
        valid = {code for code, _ in self.DAY_CHOICES}
        days = self.meeting_days_list
        if not days:
            raise ValidationError({"meeting_days": "Select at least one day."})
        bad = [d for d in days if d not in valid]
        if bad:
            raise ValidationError(
                {"meeting_days": f"Invalid day code(s): {', '.join(bad)}"}
            )
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot precede start date."})

    # ---- helpers --------------------------------------------------------

    @property
    def meeting_days_list(self):
        """Meeting days as a list of codes, e.g. ['MON', 'WED']."""
        return [d.strip().upper() for d in self.meeting_days.split(",") if d.strip()]

    @property
    def schedule_display(self):
        """Human readable schedule, e.g. 'MON, WED 10:00-11:15 (Room 204)'."""
        times = f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"
        place = f" ({self.location})" if self.location else ""
        return f"{', '.join(self.meeting_days_list)} {times}{place}"

    def meets_on(self, date):
        """True if the course normally meets on `date` (a date object)."""
        if self.start_date and date < self.start_date:
            return False
        if self.end_date and date > self.end_date:
            return False
        return self._WEEKDAY_CODES[date.weekday()] in self.meeting_days_list

    def create_lecture(self, date=None):
        """
        Create (or fetch, if it already exists) the Lecture for `date`
        (default: today). The new lecture gets a fresh QR identifier.
        Returns (lecture, created).
        """
        date = date or timezone.localdate()
        return Lecture.objects.get_or_create(course=self, date=date)


class Enrollment(models.Model):
    """
    Links a student to a course (explicit many-to-many "through" table).

    A (student, course) pair may exist only once. `status` lets us keep the
    history of dropped enrollments instead of deleting rows.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DROPPED = "dropped", "Dropped"
        COMPLETED = "completed", "Completed"

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="enrollments"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="enrollments"
    )
    enrolled_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )

    class Meta:
        ordering = ["course__code", "student__user__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course"], name="unique_student_course"
            )
        ]

    def __str__(self):
        return f"{self.student} -> {self.course} [{self.status}]"


# --------------------------------------------------------------------------
# Lectures and QR uploads
# --------------------------------------------------------------------------

def generate_qr_identifier():
    """Return a new random identifier (UUID4 as a 32-char hex string)."""
    return uuid.uuid4().hex


class Lecture(models.Model):
    """
    One session of a course on a particular date.

    `qr_identifier` is the secret value encoded in the QR code displayed in
    class. A student proves attendance by uploading an image of that code.
    The identifier is generated automatically and is unique across all lectures.
    """

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="lectures"
    )
    date = models.DateField(default=timezone.localdate)
    topic = models.CharField(max_length=200, blank=True)
    qr_identifier = models.CharField(
        max_length=64,
        unique=True,
        default=generate_qr_identifier,
        editable=False,
    )

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "date"], name="unique_lecture_per_course_date"
            )
        ]

    def __str__(self):
        return f"{self.course.code} on {self.date}"

    # ---- helpers --------------------------------------------------------

    @property
    def qr_payload(self):
        """
        The exact string that should be encoded into the QR image.
        Prefixed so that unrelated QR codes can be rejected early.
        """
        return f"LECTURE:{self.qr_identifier}"

    def regenerate_qr(self):
        """Issue a new QR identifier (e.g. if the old one leaked)."""
        self.qr_identifier = generate_qr_identifier()
        self.save(update_fields=["qr_identifier"])
        return self.qr_identifier

    @classmethod
    def from_qr_payload(cls, payload):
        """
        Look up a Lecture from decoded QR text. Returns None if the payload
        is malformed or matches no lecture.
        """
        if not payload or not payload.startswith("LECTURE:"):
            return None
        identifier = payload.split(":", 1)[1].strip()
        return cls.objects.filter(qr_identifier=identifier).first()

    def attendees(self):
        """StudentProfiles with a valid upload for this lecture."""
        return StudentProfile.objects.filter(
            qr_uploads__lecture=self,
            qr_uploads__status=QRCodeUpload.Status.VALID,
        ).distinct()

    def absentees(self):
        """Actively enrolled students with no valid upload for this lecture."""
        enrolled = StudentProfile.objects.filter(
            enrollments__course=self.course,
            enrollments__status=Enrollment.Status.ACTIVE,
        )
        return enrolled.exclude(pk__in=self.attendees().values("pk"))


def qr_upload_path(instance, filename):
    """Store uploads under qr_uploads/<student_id>/<filename>."""
    return f"qr_uploads/{instance.student.student_id}/{filename}"


class QRCodeUpload(models.Model):
    """
    An image of a QR code uploaded by a student as proof of attendance.

    `lecture` is optional: right after upload it is empty. Once the code is
    decoded, `resolve_lecture()` fills it in. If the code is unreadable or
    unknown the upload stays unlinked and is marked INVALID, so the raw upload
    is preserved for auditing or manual review.

    Status lifecycle:  PENDING -> VALID | INVALID
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VALID = "valid", "Valid"
        INVALID = "invalid", "Invalid"

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="qr_uploads"
    )
    lecture = models.ForeignKey(
        Lecture,
        on_delete=models.SET_NULL,  # keep the upload even if lecture is removed
        null=True,
        blank=True,
        related_name="qr_uploads",
    )
    image = models.ImageField(upload_to=qr_upload_path)
    decoded_value = models.CharField(
        max_length=255, blank=True, help_text="Text decoded from the QR image"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [models.Index(fields=["student", "lecture"])]

    def __str__(self):
        target = self.lecture or "unlinked"
        return f"{self.student.student_id} -> {target} [{self.status}]"

    def resolve_lecture(self, decoded_value=None, save=True):
        """
        Link this upload to a lecture using the decoded QR text.

        An upload is VALID only when:
          1. the QR payload matches a known Lecture, and
          2. the student is actively enrolled in that lecture's course.
        Otherwise it is marked INVALID (and, in case 2, left unlinked).

        Returns the status after processing.
        """
        if decoded_value is not None:
            self.decoded_value = decoded_value

        lecture = Lecture.from_qr_payload(self.decoded_value)
        if lecture is not None and self.student.is_enrolled_in(lecture.course):
            self.lecture = lecture
            self.status = self.Status.VALID
        else:
            self.lecture = None
            self.status = self.Status.INVALID

        if save:
            self.save()
        return self.status

    @property
    def is_valid(self):
        return self.status == self.Status.VALID