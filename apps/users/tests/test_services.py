from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from apps.users.constants import Role
from apps.users.models import User
from apps.users.services import is_commandant, is_security, is_student


class RoleServiceTests(TestCase):
    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="student@dormdesk.test",
            password="Dormdesk-pass-1",
            first_name="Аня",
            last_name="Иванова",
            phone="+77010000001",
            role=Role.STUDENT,
        )
        self.commandant = User.objects.create_user(
            email="commandant@dormdesk.test",
            password="Dormdesk-pass-1",
            first_name="Борис",
            last_name="Сергеев",
            phone="+77010000002",
            role=Role.COMMANDANT,
        )
        self.security = User.objects.create_user(
            email="security@dormdesk.test",
            password="Dormdesk-pass-1",
            first_name="Галина",
            last_name="Орлова",
            phone="+77010000003",
            role=Role.SECURITY,
        )

    def test_role_checks(self) -> None:
        self.assertTrue(is_student(self.student))
        self.assertFalse(is_commandant(self.student))
        self.assertFalse(is_security(self.student))

        self.assertTrue(is_commandant(self.commandant))
        self.assertFalse(is_student(self.commandant))

        self.assertTrue(is_security(self.security))
        self.assertFalse(is_student(self.security))

    def test_anonymous_user_has_no_role(self) -> None:
        anonymous = AnonymousUser()
        self.assertFalse(is_student(anonymous))
        self.assertFalse(is_commandant(anonymous))
        self.assertFalse(is_security(anonymous))
