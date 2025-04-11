from celery import shared_task
from celery.result import AsyncResult
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from library.util import get_overdue_loans
from .models import Loan, Book
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
import logging


logger = get_task_logger(__name__)


@shared_task(
    bind=True,  # Allows access to task instance
    max_retries=3,  # Maximum retry attempts
    default_retry_delay=60,  # Retry after 60 seconds
    autoretry_for=(Exception,)  # Automatically retry for these exceptions
)
def send_loan_notification(loan_id):
    
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass
    
@shared_task
def send_overdue_notification():
    now = timezone.now()
    overdue_loans = Loan.objects.filter(due_date__lt=now,is_returned=False).select_related('book','member')
    for loan in overdue_loans:
        member_email = loan.member.user.email
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYour loan for the book with title "{loan.book.title}" is overdue.\nPlease return it.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    
    