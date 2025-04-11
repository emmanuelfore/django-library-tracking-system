from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .pagination import BookPagination
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer
from datetime import timedelta
from rest_framework.decorators import action
from django.db.models import F
from django.contrib.auth.models import User
from django.utils import timezone
from .tasks import send_loan_notification

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer


class BookViewSet(viewsets.ModelViewSet):
    """
    Optimized BookViewSet with:
    - Efficient query retrieval
    - Pagination
    - Minimal database queries
    """
    queryset = Book.objects.select_related('author').prefetch_related('loan_set')
    serializer_class = BookSerializer
    
    pagination_class = BookPagination

    def get_queryset(self):
        """
        Customize queryset retrieval with optional filtering
        
        Supports:
        - Genre filtering
        - Author filtering
        - Search by title
        """
        queryset = super().get_queryset()
        
        genre = self.request.query_params.get('genre')
        if genre:
            queryset = queryset.filter(genre__icontains=genre)
        
        author_id = self.request.query_params.get('author_id')
        if author_id:
            queryset = queryset.filter(author_id=author_id)
        
        title = self.request.query_params.get('title')
        if title:
            queryset = queryset.filter(title__icontains=title)
        
        return queryset

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        """
        Optimized book loan process
        
        Features:
        - Efficient book and member retrieval
        - Minimal database writes
        - Async notification
        """
        book = Book.objects.select_related('author').get(pk=pk)
        
        if book.available_copies < 1:
            return Response(
                {'error': 'No available copies.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        member_id = request.data.get('member_id')
        
        try:
            member = Member.objects.select_related('user').get(id=member_id)
        except Member.DoesNotExist:
            return Response(
                {'error': 'Member does not exist.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        loan = Loan.objects.create(
            book=book, 
            member=member, 
            loan_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=14)  
        )
        
        Book.objects.filter(pk=book.pk).update(available_copies=F('available_copies') - 1)
        
        send_loan_notification.delay(loan.id)
        
        return Response(
            {'status': 'Book loaned successfully.'},
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        """
        Optimized book return process
        
        Features:
        - Efficient book and loan retrieval
        - Minimal database writes
        """
        book = Book.objects.select_related('author').get(pk=pk)
        member_id = request.data.get('member_id')
        
        try:
            loan = Loan.objects.select_related('book', 'member').get(
                book=book, 
                member__id=member_id, 
                is_returned=False
            )
        except Loan.DoesNotExist:
            return Response(
                {'error': 'Active loan does not exist.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        Loan.objects.filter(pk=loan.pk).update(
            is_returned=True, 
            return_date=timezone.now().date()
        )
        
        Book.objects.filter(pk=book.pk).update(available_copies=F('available_copies') + 1)
        
        return Response(
            {'status': 'Book returned successfully.'},
            status=status.HTTP_200_OK
        )

        
class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=['GET'], url_path='top-active')
    def top_active(self, request):
        """
        Retrieve top 5 members with the most active loans.
        
        Efficient query using:
        - annotate() for counting active loans
        - select_related() to minimize database queries
        - order by active loan count
        """
        try:
            top_members = (
                Member.objects
                .annotate(active_loans_count=Count(
                    'loan', 
                    filter=Q(loan__is_returned=False)
                ))
                .select_related('user')
                .order_by('-active_loans_count')
                .filter(active_loans_count__gt=0)[:5]
            )
            
            # Prepare response data
            response_data = [
                {
                    'id': member.id,
                    'username': member.user.username,
                    'email': member.user.email,
                    'active_loans': member.active_loans_count
                } 
                for member in top_members
            ]
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response(
                {'error': 'Unable to retrieve top active members'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer
    
    @action(detail=True, methods = ['POST'], url_path='extend-due-date')
    def extend_due_date(self, request, pk=None):
        loan = self.get_object()
        
        # Check if loan is already returned
        if loan.is_returned:
            return Response(
                {'status': 'Cannot extend a returned loan'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if loan is already overdue
        if loan.due_date < timezone.now():
            return Response(
                {'status': 'Loan is already overdue'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get and validate additional days
        additional_days = request.data.get('additional_days')
        
        try:
            additional_days = int(additional_days)
            if additional_days < 1:
                return Response(
                    {'status': 'Additional days must be greater than 0'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'status': 'Invalid additional days'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Extend due date
        loan.due_date = loan.due_date + timedelta(days=additional_days)
        loan.save()
        
        # Serialize and return updated loan details
        updated_details = LoanSerializer(loan)
        return Response(
            updated_details.data,
            status=status.HTTP_200_OK
        )