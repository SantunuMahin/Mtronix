import calendar
import datetime

from django.utils import timezone
import pytz

BD_TZ = pytz.timezone('Asia/Dhaka')


def get_date_range_for_period(period: str, default_period: str = 'today'):
    """
    Calculate timezone-aware (BD_TZ) start/end datetimes and a human-readable
    label for a given period ('today', 'week', 'month', 'year', 'all').
    """
    normalized = (period or default_period).lower()
    now = timezone.now().astimezone(BD_TZ)
    midnight = {'hour': 0, 'minute': 0, 'second': 0, 'microsecond': 0}
    end_of_day = {'hour': 23, 'minute': 59, 'second': 59, 'microsecond': 999999}

    if normalized == 'today':
        start = now.replace(**midnight)
        end = now.replace(**end_of_day)
        label = f"Today ({start.strftime('%b %d, %Y')})"
    elif normalized == 'week':
        start = (now - datetime.timedelta(days=now.weekday())).replace(**midnight)
        end = now.replace(**end_of_day)
        label = f"This Week ({start.strftime('%b %d')} - {end.strftime('%b %d, %Y')})"
    elif normalized == 'month':
        start = now.replace(day=1, **midnight)
        last_day = calendar.monthrange(now.year, now.month)[1]
        end = now.replace(day=last_day, **end_of_day)
        label = f"This Month ({start.strftime('%B %Y')})"
    elif normalized == 'year':
        start = now.replace(month=1, day=1, **midnight)
        end = now.replace(month=12, day=31, **end_of_day)
        label = f"This Year ({start.strftime('%Y')})"
    else:
        start = None
        end = None
        label = 'All Time'

    return start, end, label
