from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
# from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Quiz, Question, Choice, QuizAttempt, Answer
from .serializers import (
    QuizSerializer, QuizPublicSerializer, QuizDetailPublicSerializer,
    QuestionSerializer, QuizAttemptSerializer, QuizAttemptDetailSerializer,
    QuizStartSerializer, QuizSubmissionSerializer, QuizResultsSerializer,
    AnswerSubmissionSerializer
)
from courses.permissions import IsInstructorOrReadOnly, IsOwnerOrReadOnly
import random
import json


class QuizViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des quiz"""
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    filterset_fields = ['quiz_type', 'difficulty', 'is_published', 'course']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'title', 'difficulty']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filtre les quiz selon le rôle de l'utilisateur"""
        user = self.request.user
        
        if user.role == 'instructor':
            # Les instructeurs voient leurs propres quiz
            return Quiz.objects.filter(instructor=user).select_related('course', 'lesson')
        else:
            # Les étudiants voient seulement les quiz publiés des cours auxquels ils sont inscrits
            return Quiz.objects.filter(
                is_published=True,
                course__enrollments__user=user
            ).select_related('course', 'lesson')
    
    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action et le rôle"""
        user = self.request.user
        
        if self.action == 'retrieve':
            if user.role == 'instructor' and self.get_object().instructor == user:
                return QuizSerializer
            else:
                return QuizDetailPublicSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return QuizSerializer
        else:
            if user.role == 'instructor':
                return QuizSerializer
            else:
                return QuizPublicSerializer
    
    def perform_create(self, serializer):
        """Assigne l'instructeur lors de la création"""
        if self.request.user.role != 'instructor':
            raise PermissionDenied("Seuls les instructeurs peuvent créer des quiz")
        serializer.save(instructor=self.request.user)
    
    def perform_update(self, serializer):
        """Vérifie les permissions avant mise à jour"""
        quiz = self.get_object()
        if quiz.instructor != self.request.user:
            raise PermissionDenied("Vous ne pouvez modifier que vos propres quiz")
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def start_quiz(self, request, pk=None):
        """Démarre une nouvelle tentative de quiz"""
        quiz = self.get_object()
        user = request.user
        
        # Vérifier si l'utilisateur peut passer le quiz
        can_take, message = quiz.can_user_take_quiz(user)
        if not can_take:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier s'il y a déjà une tentative en cours
        existing_attempt = QuizAttempt.objects.filter(
            quiz=quiz, user=user, status='in_progress'
        ).first()
        
        if existing_attempt:
            # Vérifier si elle n'a pas expiré
            if existing_attempt.is_expired():
                existing_attempt.status = 'expired'
                existing_attempt.save()
            else:
                # Retourner la tentative existante
                serializer = QuizAttemptSerializer(existing_attempt)
                return Response({
                    'message': 'Tentative existante trouvée',
                    'attempt': serializer.data
                })
        
        # Créer une nouvelle tentative
        with transaction.atomic():
            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                user=user
            )
            
            # Générer l'ordre des questions
            questions = list(quiz.questions.all().values_list('id', flat=True))
            if quiz.randomize_questions:
                random.shuffle(questions)
            
            attempt.set_questions_order(questions)
            attempt.save()
        
        serializer = QuizAttemptSerializer(attempt)
        return Response({
            'message': 'Quiz démarré avec succès',
            'attempt': serializer.data
        })
    
    @action(detail=True, methods=['get'])
    def attempt_status(self, request, pk=None):
        """Récupère le statut de la tentative en cours"""
        quiz = self.get_object()
        user = request.user
        
        attempt = QuizAttempt.objects.filter(
            quiz=quiz, user=user, status='in_progress'
        ).first()
        
        if not attempt:
            return Response({'error': 'Aucune tentative en cours'}, status=status.HTTP_404_NOT_FOUND)
        
        # Vérifier expiration
        if attempt.is_expired():
            attempt.status = 'expired'
            attempt.save()
            return Response({'error': 'Tentative expirée'}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = QuizAttemptSerializer(attempt)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def save_answer(self, request, pk=None):
        """Sauvegarde une réponse à une question"""
        quiz = self.get_object()
        user = request.user
        
        # Récupérer la tentative en cours
        attempt = QuizAttempt.objects.filter(
            quiz=quiz, user=user, status='in_progress'
        ).first()
        
        if not attempt:
            return Response({'error': 'Aucune tentative en cours'}, status=status.HTTP_400_BAD_REQUEST)
        
        if attempt.is_expired():
            attempt.status = 'expired'
            attempt.save()
            return Response({'error': 'Tentative expirée'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider les données de réponse
        answer_serializer = AnswerSubmissionSerializer(data=request.data)
        if not answer_serializer.is_valid():
            return Response(answer_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        question_id = str(answer_serializer.validated_data['question_id'])
        
        # Vérifier que la question appartient au quiz
        question = get_object_or_404(Question, id=question_id, quiz=quiz)
        
        # Sauvegarder la réponse dans les données JSON
        answers_data = attempt.get_answers_data()
        
        # Préparer la réponse selon le type de question
        if question.question_type in ['multiple_choice', 'single_choice', 'true_false']:
            answers_data[question_id] = answer_serializer.validated_data.get('selected_choices', [])
        elif question.question_type == 'numerical':
            answers_data[question_id] = answer_serializer.validated_data.get('numerical_answer')
        else:  # text, essay
            answers_data[question_id] = answer_serializer.validated_data.get('text_answer', '')
        
        attempt.set_answers_data(answers_data)
        attempt.save()
        
        return Response({'message': 'Réponse sauvegardée'})
    
    @action(detail=True, methods=['post'])
    def submit_quiz(self, request, pk=None):
        """Soumet le quiz complet"""
        quiz = self.get_object()
        user = request.user
        
        # Récupérer la tentative en cours
        attempt = QuizAttempt.objects.filter(
            quiz=quiz, user=user, status='in_progress'
        ).first()
        
        if not attempt:
            return Response({'error': 'Aucune tentative en cours'}, status=status.HTTP_400_BAD_REQUEST)
        
        if attempt.is_expired():
            attempt.status = 'expired'
            attempt.save()
            return Response({'error': 'Tentative expirée'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Soumettre la tentative
        with transaction.atomic():
            attempt.submit_attempt()
        
        # Créer les objets Answer individuels pour un suivi détaillé
        self._create_individual_answers(attempt)
        
        # Retourner les résultats
        if quiz.show_score_immediately:
            results_serializer = QuizResultsSerializer(attempt)
            return Response({
                'message': 'Quiz soumis avec succès',
                'results': results_serializer.data
            })
        else:
            return Response({
                'message': 'Quiz soumis avec succès',
                'attempt_id': attempt.id
            })
    
    def _create_individual_answers(self, attempt):
        """Crée les objets Answer individuels à partir des données JSON"""
        answers_data = attempt.get_answers_data()
        
        for question in attempt.quiz.questions.all():
            question_id = str(question.id)
            if question_id in answers_data:
                user_answer = answers_data[question_id]
                
                # Créer ou mettre à jour l'objet Answer
                answer, created = Answer.objects.get_or_create(
                    attempt=attempt,
                    question=question,
                    defaults={
                        'text_answer': '',
                        'numerical_answer': None
                    }
                )
                
                # Assigner la réponse selon le type
                if question.question_type in ['multiple_choice', 'single_choice', 'true_false']:
                    if isinstance(user_answer, list):
                        choices = Choice.objects.filter(id__in=user_answer)
                        answer.selected_choices.set(choices)
                elif question.question_type == 'numerical':
                    answer.numerical_answer = user_answer
                else:  # text, essay
                    answer.text_answer = user_answer or ''
                
                answer.save()  # Cela déclenchera la vérification automatique
    
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """Récupère les résultats d'un quiz pour l'utilisateur"""
        quiz = self.get_object()
        user = request.user
        
        # Récupérer les tentatives de l'utilisateur
        attempts = QuizAttempt.objects.filter(
            quiz=quiz, 
            user=user,
            status__in=['submitted', 'graded']
        ).order_by('-submitted_at')
        
        if not attempts.exists():
            return Response({'error': 'Aucune tentative complétée'}, status=status.HTTP_404_NOT_FOUND)
        
        # Retourner la dernière tentative
        latest_attempt = attempts.first()
        serializer = QuizResultsSerializer(latest_attempt)
        
        return Response(serializer.data)


class QuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour consulter les tentatives de quiz"""
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [OrderingFilter]
    filterset_fields = ['status', 'passed', 'quiz']
    ordering_fields = ['started_at', 'score']
    ordering = ['-started_at']
    
    def get_queryset(self):
        """Filtre les tentatives selon le rôle"""
        user = self.request.user
        
        if user.role == 'instructor':
            # Les instructeurs voient les tentatives de leurs quiz
            return QuizAttempt.objects.filter(
                quiz__instructor=user
            ).select_related('quiz', 'user')
        else:
            # Les étudiants voient seulement leurs tentatives
            return QuizAttempt.objects.filter(user=user).select_related('quiz')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return QuizAttemptDetailSerializer
        return QuizAttemptSerializer
