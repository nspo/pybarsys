from django.conf import settings
from django.test.runner import DiscoverRunner


class FastPasswordHasherRunner(DiscoverRunner):
    """Test runner that swaps in a cheap password hasher for the duration of the run.

    Django's default PBKDF2 hasher is deliberately slow, which is right in production
    and pointless in tests. The view tests create users with passwords and log in in
    almost every setUp, so hashing dominated the run time - swapping the hasher makes
    the suite more than 20x faster.

    Only test runs are affected: `settings.PASSWORD_HASHERS` is left untouched
    everywhere else, so production keeps PBKDF2.
    """

    def setup_test_environment(self, **kwargs) -> None:
        super().setup_test_environment(**kwargs)
        settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
