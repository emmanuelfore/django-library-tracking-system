# tests/test_tasks.py
from rest_framework import status
from datetime import timezone
from django.test import TestCase
from django.core import mail
from django.contrib.auth.models import User
from django.conf import settings
from unittest.mock import patch

from library.models import Member, Book, Author, Loan
from library.tasks import check_overdue_loans, send_loan_notification

def test_overdue_loans_notification(self):
    """
    Test overdue loan notification task
    """
    # Create an overdue loan
    overdue_loan = Loan.objects.create(
        book=self.book,
        member=self.member,
        loan_date=timezone.now().date() - timezone.timedelta(days=30),
        due_date=timezone.now().date() - timezone.timedelta(days=15),
        is_returned=False
    )
    
    mail.outbox = []
    
    check_overdue_loans()
    
    self.assertEqual(len(mail.outbox), 1)
    email = mail.outbox[0]
    
    self.assertEqual(email.subject, 'Overdue Book Notification')
    self.assertIn(self.book.title, email.body)
    self.assertEqual(email.to, [self.user.email])

def test_top_active_members_viewset(self):
    """
    Test top active members endpoint in MemberViewSet
    """
    # Create multiple members with different active loan counts
    user1 = User.objects.create_user(username='active1', email='active1@example.com')
    user2 = User.objects.create_user(username='active2', email='active2@example.com')
    user3 = User.objects.create_user(username='active3', email='active3@example.com')
    
    member1 = Member.objects.create(user=user1)
    member2 = Member.objects.create(user=user2)
    member3 = Member.objects.create(user=user3)
    
    # Create multiple active loans for members
    for _ in range(3):
        Loan.objects.create(
            book=self.book, 
            member=member1, 
            is_returned=False
        )
    
    for _ in range(2):
        Loan.objects.create(
            book=self.book, 
            member=member2, 
            is_returned=False
        )
    
    # Get top active members
    response = self.client.get('/api/members/top-active/')
    
    # Verify response
    self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    # Check response data
    self.assertEqual(len(response.data), 2)  # Top 2 active members
    self.assertEqual(response.data[0]['username'], 'active1')
    self.assertEqual(response.data[0]['active_loans'], 3)
    self.assertEqual(response.data[1]['username'], 'active2')
    self.assertEqual(response.data[1]['active_loans'], 2)