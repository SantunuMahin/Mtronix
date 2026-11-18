from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required
from accounts.models import UserProfile


def login_view(request):
    """
    Handles user login. On GET: renders the login form.
    On POST: authenticates credentials and redirects to 'next' or dashboard.
    """
    # If already logged in, go straight to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Honour the ?next= parameter only if it is a safe local URL
            next_url = request.GET.get('next') or request.POST.get('next') or ''
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    """Logs the user out on POST and redirects to the login page."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


@admin_required
def user_list(request):
    """List all staff accounts and allow creating a new user with a role."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', UserProfile.STOREKEEPER)
        valid_roles = {choice[0] for choice in UserProfile.ROLE_CHOICES}

        if not username or not password:
            messages.error(request, 'Username and password are required.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
        elif role not in valid_roles:
            messages.error(request, 'Invalid role selected.')
        else:
            name_parts = full_name.split(None, 1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            new_user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            new_user.profile.role = role
            new_user.profile.save(update_fields=['role'])
            messages.success(request, f'User "{username}" created with role {new_user.profile.get_role_display()}.')
            return redirect('accounts:users')

    users = User.objects.select_related('profile').order_by('username')
    return render(
        request,
        'accounts/users.html',
        {
            'users': users,
            'role_choices': UserProfile.ROLE_CHOICES,
        },
    )


@admin_required
@require_POST
def user_update_role(request, pk):
    target_user = get_object_or_404(User.objects.select_related('profile'), pk=pk)
    new_role = request.POST.get('role', '').strip()
    valid_roles = {choice[0] for choice in UserProfile.ROLE_CHOICES}
    if new_role not in valid_roles:
        messages.error(request, 'Invalid role selected.')
        return redirect('accounts:users')

    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    profile.role = new_role
    profile.save(update_fields=['role'])
    messages.success(request, f'Updated "{target_user.username}" role to {profile.get_role_display()}.')
    return redirect('accounts:users')


@admin_required
@require_POST
def user_toggle_active(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if target_user.pk == request.user.pk:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('accounts:users')

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active'])
    state = 'activated' if target_user.is_active else 'deactivated'
    messages.success(request, f'User "{target_user.username}" {state}.')
    return redirect('accounts:users')
