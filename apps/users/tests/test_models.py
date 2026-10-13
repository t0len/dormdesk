from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.users.constants import Role
from apps.users.models import StudentProfile, User


class UserRoleTests(TestCase):
    def test_staff_roles_open_admin(self) -> None:
        commandant = self._create("commandant@dormdesk.test", Role.COMMANDANT)
        security = self._create("security@dormdesk.test", Role.SECURITY)
        student = self._create("student@dormdesk.test", Role.STUDENT)

        self.assertTrue(commandant.is_staff)
        self.assertTrue(security.is_staff)
        self.assertFalse(student.is_staff)

    def test_student_role_removes_admin_access(self) -> None:
        user = self._create("staff@dormdesk.test", Role.COMMANDANT)
        user.role = Role.STUDENT
        user.save()
        user.refresh_from_db()
        self.assertFalse(user.is_staff)

    def test_superuser_defaults_to_commandant(self) -> None:
        admin = User.objects.create_superuser(
            email="admin@dormdesk.test",
            password="Dormdesk-pass-1",
            first_name="Админ",
            last_name="Админов",
            phone="+77010000009",
        )
        self.assertEqual(admin.role, Role.COMMANDANT)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def _create(self, email: str, role: str) -> User:
        return User.objects.create_user(
            email=email,
            password="Dormdesk-pass-1",
            first_name="Имя",
            last_name="Фамилия",
            phone="+77010000000",
            role=role,
        )


class StudentProfileTests(TestCase):
    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="student@dormdesk.test",
            password="Dormdesk-pass-1",
            first_name="Аня",
            last_name="Иванова",
            phone="+77010000001",
            role=Role.STUDENT,
        )

    def test_course_must_be_between_1_and_4(self) -> None:
        for course in (0, 5):
            with self.subTest(course=course):
                profile = StudentProfile(
                    user=self.student,
                    student_number=f"ST-{course}",
                    faculty="Информационные технологии",
                    group="ИС-21",
                    course=course,
                )
                with self.assertRaises(ValidationError):
                    profile.save()

    def test_profile_belongs_only_to_student(self) -> None:
        commandant = User.objects.create_user(
            email="commandant@dormdesk.test",
            password="Dormdesk-pass-1",
            first_name="Борис",
            last_name="Сергеев",
            phone="+77010000002",
            role=Role.COMMANDANT,
        )
        profile = StudentProfile(
            user=commandant,
            student_number="ST-100",
            faculty="Информационные технологии",
            group="ИС-21",
            course=2,
        )
        with self.assertRaises(ValidationError):
            profile.save()

    def test_valid_profile_is_stored(self) -> None:
        profile = StudentProfile.objects.create(
            user=self.student,
            student_number="ST-100",
            faculty="Информационные технологии",
            group="ИС-21",
            course=2,
        )
        self.assertEqual(self.student.student_profile, profile)
