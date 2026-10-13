from django.test import TestCase
from django.urls import reverse

from apps.users.constants import Role
from apps.users.models import StudentProfile, User

PASSWORD = "Dormdesk-pass-1"


class RegistrationTests(TestCase):
    def test_student_registers_with_profile(self) -> None:
        response = self.client.post(
            reverse("users:register"),
            {
                "email": "student@dormdesk.test",
                "first_name": "Аня",
                "last_name": "Иванова",
                "phone": "+77010000001",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "student_number": "ST-100",
                "faculty": "Информационные технологии",
                "group": "ИС-21",
                "course": 2,
                "role": Role.COMMANDANT,
            },
        )
        self.assertRedirects(response, reverse("users:home"))
        user = User.objects.get(email="student@dormdesk.test")
        self.assertEqual(user.role, Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertEqual(user.student_profile.student_number, "ST-100")
        self.assertEqual(user.student_profile.course, 2)

    def test_registration_rejects_mismatched_passwords(self) -> None:
        response = self.client.post(
            reverse("users:register"),
            {
                "email": "student@dormdesk.test",
                "first_name": "Аня",
                "last_name": "Иванова",
                "phone": "+77010000001",
                "password1": PASSWORD,
                "password2": "Other-pass-2",
                "student_number": "ST-100",
                "faculty": "Информационные технологии",
                "group": "ИС-21",
                "course": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="student@dormdesk.test").exists())


class SessionTests(TestCase):
    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="student@dormdesk.test",
            password=PASSWORD,
            first_name="Аня",
            last_name="Иванова",
            phone="+77010000001",
            role=Role.STUDENT,
        )
        StudentProfile.objects.create(
            user=self.student,
            student_number="ST-100",
            faculty="Информационные технологии",
            group="ИС-21",
            course=2,
        )
        self.commandant = User.objects.create_user(
            email="commandant@dormdesk.test",
            password=PASSWORD,
            first_name="Борис",
            last_name="Сергеев",
            phone="+77010000002",
            role=Role.COMMANDANT,
        )

    def test_login_and_logout_by_email(self) -> None:
        response = self.client.post(
            reverse("users:login"),
            {"username": "student@dormdesk.test", "password": PASSWORD},
        )
        self.assertRedirects(response, reverse("users:home"))
        response = self.client.post(reverse("users:logout"))
        self.assertRedirects(response, reverse("users:home"))

    def test_home_links_depend_on_role(self) -> None:
        self.client.force_login(self.student)
        response = self.client.get(reverse("users:home"))
        self.assertContains(response, "Заселение")
        self.assertContains(response, "Заявка на ремонт")
        self.assertContains(response, "Гостевой пропуск")
        self.assertNotContains(response, 'href="/admin/"')

        self.client.force_login(self.commandant)
        response = self.client.get(reverse("users:home"))
        self.assertContains(response, 'href="/admin/"')
        self.assertNotContains(response, "Заявка на ремонт")

    def test_profile_requires_login(self) -> None:
        response = self.client.get(reverse("users:profile"))
        self.assertRedirects(
            response,
            f"{reverse('users:login')}?next={reverse('users:profile')}",
        )

    def test_student_edits_phone_group_and_course_only(self) -> None:
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("users:profile"),
            {
                "phone": "+77019998877",
                "group": "ИС-22",
                "course": 3,
                "faculty": "Другой факультет",
                "student_number": "ST-999",
            },
        )
        self.assertRedirects(response, reverse("users:profile"))
        self.student.refresh_from_db()
        profile = self.student.student_profile
        profile.refresh_from_db()
        self.assertEqual(self.student.phone, "+77019998877")
        self.assertEqual(profile.group, "ИС-22")
        self.assertEqual(profile.course, 3)
        self.assertEqual(profile.faculty, "Информационные технологии")
        self.assertEqual(profile.student_number, "ST-100")

    def test_password_change_keeps_session(self) -> None:
        self.client.force_login(self.student)
        new_password = "North-window-42"
        response = self.client.post(
            reverse("users:password_change"),
            {
                "old_password": PASSWORD,
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )
        self.assertRedirects(response, reverse("users:password_change_done"))
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password(new_password))
        follow = self.client.get(reverse("users:profile"))
        self.assertEqual(follow.status_code, 200)


class AdminTests(TestCase):
    def setUp(self) -> None:
        self.admin = User.objects.create_superuser(
            email="admin@dormdesk.test",
            password=PASSWORD,
            first_name="Админ",
            last_name="Админов",
            phone="+77010000009",
        )
        self.student = User.objects.create_user(
            email="student@dormdesk.test",
            password=PASSWORD,
            first_name="Аня",
            last_name="Иванова",
            phone="+77010000001",
            role=Role.STUDENT,
        )
        StudentProfile.objects.create(
            user=self.student,
            student_number="ST-100",
            faculty="Информационные технологии",
            group="ИС-21",
            course=2,
        )
        self.client.force_login(self.admin)

    def test_changelist_filters_by_role_and_searches_student_number(self) -> None:
        url = reverse("admin:users_user_changelist")
        security = User.objects.create_user(
            email="security@dormdesk.test",
            password=PASSWORD,
            first_name="Галина",
            last_name="Орлова",
            phone="+77010000003",
            role=Role.SECURITY,
        )
        by_role = self.client.get(url, {"role__exact": Role.STUDENT})
        self.assertContains(by_role, "student@dormdesk.test")
        self.assertContains(by_role, "1 результат")
        self.assertNotContains(by_role, security.email)

        by_number = self.client.get(url, {"q": "ST-100"})
        self.assertContains(by_number, "student@dormdesk.test")

        by_last_name = self.client.get(url, {"q": "Иванова"})
        self.assertContains(by_last_name, "student@dormdesk.test")

    def test_change_page_shows_profile_inline(self) -> None:
        response = self.client.get(
            reverse("admin:users_user_change", args=[self.student.pk])
        )
        self.assertContains(response, "ST-100")
        self.assertContains(response, "студенческого")

    def test_deactivate_action(self) -> None:
        response = self.client.post(
            reverse("admin:users_user_changelist"),
            {
                "action": "deactivate_users",
                "_selected_action": [str(self.student.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
