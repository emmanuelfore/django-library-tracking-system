from celery import shared_task
from celery.utils.log import get_task_logger
from .models import Loan
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
def check_overdue_loans():
    try:
        now = timezone.now().date()
        overdue_loans = Loan.objects.filter(
            due_date__lt=now, 
            is_returned=False
        ).select_related('book', 'member', 'member__user')
        
        total_overdue = overdue_loans.count()
        notifications_sent = 0
        
        for loan in overdue_loans:
            # Validate member and user data
            if not loan.member or not loan.member.user:
                logger.warning(f"Incomplete member data for loan {loan.id}")
                continue
            
            member_email = loan.member.user.email
            
            # Skip if no email
            if not member_email:
                logger.warning(f"No email for member {loan.member.user.username}")
                continue
            
            try:
                send_mail(
                    subject='Overdue Book Notification',
                    message=f'Hello {loan.member.user.username},\n\n'
                            f'Your loan for the book with title "{loan.book.title}" is overdue.\n'
                            f'Loan Details:\n'
                            f'- Book: {loan.book.title}\n'
                            f'- Due Date: {loan.due_date}\n'
                            f'- Days Overdue: {(now - loan.due_date).days}\n\n'
                            f'Please return the book to the library as soon as possible.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[member_email],
                    fail_silently=False, 
                )
                notifications_sent += 1
                logger.info(f"Overdue notification sent for loan {loan.id}")
            except Exception as email_error:
                logger.error(f"Failed to send overdue notification for loan {loan.id}: {str(email_error)}")
        
        # Log task completion statistics
        logger.info(f"Overdue Loan Check Complete. Total Loans: {total_overdue}, Notifications Sent: {notifications_sent}")
        
        return {
            'total_overdue_loans': total_overdue,
            'notifications_sent': notifications_sent
        }
    
    except Exception as task_error:
        # Comprehensive error handling for the entire task
        logger.critical(f"Overdue Loan Check Task Failed: {str(task_error)}")
        raise