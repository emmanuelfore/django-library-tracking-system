import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'library_system.settings')

app = Celery('library_system')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'send-overdue-notifications': {
        'task': 'library.tasks.send_overdue_notification',
        'schedule': crontab(hour=0, minute=0),  # Daily at 0:00
    }
}

# Optional: Global Celery configuration
app.conf.timezone = 'UTC'
