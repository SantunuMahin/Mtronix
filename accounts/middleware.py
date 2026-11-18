from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


class LoginRequiredMiddleware:
    """
    Redirects unauthenticated users to the login page for HTML views,
    or returns 401 JSON for API and AJAX requests.
    Excludes: login/logout pages, Django Admin, and static files.
    """
    EXEMPT_PREFIXES = (
        '/accounts/login/',
        '/accounts/logout/',
        '/admin/',
        '/static/',
        '/sw.js',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Skip middleware for exempt paths
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        if not request.user.is_authenticated:
            # For JSON / API endpoints or AJAX requests, return 401 JSON instead of HTML redirect
            if (
                path.startswith('/sales/barcode-lookup/')
                or path.startswith('/products/api/')
                or request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('Accept', '')
            ):
                return JsonResponse({'success': False, 'error': 'Authentication required. Please log in.'}, status=401)

            login_url = reverse('accounts:login')
            return redirect(f'{login_url}?next={request.path}')

        return self.get_response(request)
