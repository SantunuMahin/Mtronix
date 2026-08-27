from django.shortcuts import redirect
from django.urls import reverse


class LoginRequiredMiddleware:
    """
    Redirects unauthenticated users to the login page for all HTML views.
    Excludes: login/logout pages, Django Admin, and static files.
    """
    EXEMPT_PREFIXES = (
        '/accounts/login/',
        '/accounts/logout/',
        '/admin/',
        '/static/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Skip middleware for exempt paths
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        if not request.user.is_authenticated:
            login_url = reverse('accounts:login')
            return redirect(f'{login_url}?next={request.path}')

        return self.get_response(request)
