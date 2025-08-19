from rest_framework import serializers
from django.utils import timezone
from .models import Quiz, Question, Choice, QuizAttempt, Answer
import random


class ChoiceSerializer(serializers.ModelSerializer):
    """Serializer pour les choix de réponse"""
    
    class Meta:
        model = Choice
        fields = ['id', 'choice_text', 'is_correct', 'order', 'explanation']
        extra_kwargs = {
            'is_correct': {'write_only': True},  # Ne pas exposer les bonnes réponses
            'explanation': {'write_only': True}  # Seulement après tentative
        }


class ChoicePublicSerializer(serializers.ModelSerializer):
    """Serializer public pour les choix (sans réponses correctes)"""
    
    class Meta:
        model = Choice
        fields = ['id', 'choice_text', 'order']


class ChoiceWithCorrectionsSerializer(serializers.ModelSerializer):
    """Serializer avec corrections pour après tentative"""
    
    class Meta:
        model = Choice
        fields = ['id', 'choice_text', 'is_correct', 'order', 'explanation']


class QuestionSerializer(serializers.ModelSerializer):
    """Serializer pour les questions (version instructeur)"""
    choices = ChoiceSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'question_type', 'points', 'order',
            'explanation', 'image', 'correct_number', 'tolerance', 
            'correct_text', 'case_sensitive', 'choices'
        ]


class QuestionPublicSerializer(serializers.ModelSerializer):
    """Serializer public pour les questions (version étudiants)"""
    choices = ChoicePublicSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'question_type', 'points', 'order',
            'image', 'choices'
        ]
    
    def to_representation(self, instance):
        """Personnalise la représentation selon le quiz"""
        data = super().to_representation(instance)
        
        # Si le quiz a l'option de mélanger les réponses
        quiz = instance.quiz
        if quiz.randomize_answers and 'choices' in data:
            choices = data['choices']
            random.shuffle(choices)
            data['choices'] = choices
        
        return data


class QuestionWithCorrectionsSerializer(serializers.ModelSerializer):
    """Serializer avec corrections après tentative"""
    choices = ChoiceWithCorrectionsSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_text', 'question_type', 'points', 'order',
            'explanation', 'image', 'correct_number', 'tolerance', 
            'correct_text', 'case_sensitive', 'choices'
        ]


class QuizSerializer(serializers.ModelSerializer):
    """Serializer pour les quiz (version instructeur)"""
    questions = QuestionSerializer(many=True, read_only=True)
    total_questions = serializers.ReadOnlyField()
    total_points = serializers.ReadOnlyField()
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'course', 'lesson', 'instructor',
            'quiz_type', 'difficulty', 'time_limit', 'max_attempts', 'passing_score',
            'randomize_questions', 'randomize_answers', 'show_correct_answers',
            'show_score_immediately', 'is_published', 'is_required',
            'available_from', 'available_until', 'created_at', 'updated_at',
            'total_questions', 'total_points', 'questions'
        ]
        read_only_fields = ['id', 'instructor', 'created_at', 'updated_at']


class QuizPublicSerializer(serializers.ModelSerializer):
    """Serializer public pour les quiz (version étudiants)"""
    total_questions = serializers.ReadOnlyField()
    total_points = serializers.ReadOnlyField()
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'quiz_type', 'difficulty', 'time_limit',
            'max_attempts', 'passing_score', 'available_from', 'available_until',
            'total_questions', 'total_points'
        ]


class QuizDetailPublicSerializer(serializers.ModelSerializer):
    """Serializer détaillé public avec questions"""
    questions = QuestionPublicSerializer(many=True, read_only=True)
    total_questions = serializers.ReadOnlyField()
    total_points = serializers.ReadOnlyField()
    time_remaining = serializers.SerializerMethodField()
    can_take_quiz = serializers.SerializerMethodField()
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'quiz_type', 'difficulty', 'time_limit',
            'max_attempts', 'passing_score', 'total_questions', 'total_points',
            'questions', 'time_remaining', 'can_take_quiz'
        ]
    
    def get_time_remaining(self, obj):
        """Retourne le temps restant pour un quiz avec limite de temps"""
        user = self.context['request'].user
        if not user.is_authenticated:
            return None
        
        # Cherche une tentative en cours
        current_attempt = obj.attempts.filter(
            user=user, 
            status='in_progress'
        ).first()
        
        if current_attempt:
            return current_attempt.get_time_remaining()
        return None
    
    def get_can_take_quiz(self, obj):
        """Vérifie si l'utilisateur peut passer le quiz"""
        user = self.context['request'].user
        if not user.is_authenticated:
            return False, "Connexion requise"
        
        return obj.can_user_take_quiz(user)
    
    def to_representation(self, instance):
        """Personnalise l'ordre des questions si randomisation activée"""
        data = super().to_representation(instance)
        
        if instance.randomize_questions and 'questions' in data:
            questions = data['questions']
            random.shuffle(questions)
            data['questions'] = questions
        
        return data


class AnswerSubmissionSerializer(serializers.Serializer):
    """Serializer pour soumettre des réponses"""
    question_id = serializers.UUIDField()
    selected_choices = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    text_answer = serializers.CharField(required=False, allow_blank=True)
    numerical_answer = serializers.FloatField(required=False, allow_null=True)
    
    def validate(self, data):
        """Valide que le type de réponse correspond au type de question"""
        question_id = data.get('question_id')
        
        try:
            question = Question.objects.get(id=question_id)
        except Question.DoesNotExist:
            raise serializers.ValidationError("Question introuvable")
        
        question_type = question.question_type
        
        if question_type in ['multiple_choice', 'single_choice', 'true_false']:
            if 'selected_choices' not in data or not data['selected_choices']:
                raise serializers.ValidationError("Choix requis pour ce type de question")
        elif question_type == 'numerical':
            if 'numerical_answer' not in data or data['numerical_answer'] is None:
                raise serializers.ValidationError("Réponse numérique requise")
        elif question_type in ['short_answer', 'essay']:
            if 'text_answer' not in data or not data['text_answer'].strip():
                raise serializers.ValidationError("Réponse textuelle requise")
        
        return data


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Serializer pour les tentatives de quiz"""
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    time_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'quiz_title', 'user', 'user_name', 'status',
            'attempt_number', 'score', 'points_earned', 'total_points',
            'passed', 'started_at', 'submitted_at', 'time_taken',
            'expires_at', 'time_remaining', 'feedback'
        ]
        read_only_fields = [
            'id', 'attempt_number', 'score', 'points_earned', 'total_points',
            'passed', 'started_at', 'submitted_at', 'time_taken', 'expires_at'
        ]
    
    def get_time_remaining(self, obj):
        """Retourne le temps restant en secondes"""
        return obj.get_time_remaining()


class QuizAttemptDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour les tentatives avec réponses"""
    answers = serializers.SerializerMethodField()
    quiz_questions = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz', 'user', 'status', 'attempt_number',
            'score', 'points_earned', 'total_points', 'passed',
            'started_at', 'submitted_at', 'time_taken',
            'answers', 'quiz_questions', 'feedback'
        ]
    
    def get_answers(self, obj):
        """Retourne les réponses de l'utilisateur"""
        return obj.get_answers_data()
    
    def get_quiz_questions(self, obj):
        """Retourne les questions avec corrections si autorisé"""
        if obj.quiz.show_correct_answers and obj.status in ['submitted', 'graded']:
            questions = obj.quiz.questions.all().order_by('order')
            return QuestionWithCorrectionsSerializer(questions, many=True).data
        return []


class QuizStartSerializer(serializers.Serializer):
    """Serializer pour démarrer un quiz"""
    quiz_id = serializers.UUIDField()
    
    def validate_quiz_id(self, value):
        """Valide l'existence du quiz"""
        try:
            quiz = Quiz.objects.get(id=value)
        except Quiz.DoesNotExist:
            raise serializers.ValidationError("Quiz introuvable")
        
        user = self.context['request'].user
        can_take, message = quiz.can_user_take_quiz(user)
        if not can_take:
            raise serializers.ValidationError(message)
        
        return value


class QuizSubmissionSerializer(serializers.Serializer):
    """Serializer pour soumettre un quiz complet"""
    attempt_id = serializers.UUIDField()
    answers = AnswerSubmissionSerializer(many=True)
    
    def validate_attempt_id(self, value):
        """Valide l'existence de la tentative"""
        user = self.context['request'].user
        
        try:
            attempt = QuizAttempt.objects.get(id=value, user=user)
        except QuizAttempt.DoesNotExist:
            raise serializers.ValidationError("Tentative introuvable")
        
        if attempt.status != 'in_progress':
            raise serializers.ValidationError("Cette tentative n'est plus modifiable")
        
        if attempt.is_expired():
            attempt.status = 'expired'
            attempt.save()
            raise serializers.ValidationError("Le temps imparti est écoulé")
        
        return value


class QuizResultsSerializer(serializers.ModelSerializer):
    """Serializer pour les résultats détaillés d'une tentative"""
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    questions_results = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'quiz_title', 'attempt_number', 'status', 'score',
            'points_earned', 'total_points', 'passed', 'started_at',
            'submitted_at', 'time_taken', 'feedback', 'questions_results'
        ]
    
    def get_questions_results(self, obj):
        """Retourne les résultats détaillés par question"""
        if not obj.quiz.show_correct_answers:
            return []
        
        results = []
        answers_data = obj.get_answers_data()
        
        for question in obj.quiz.questions.all().order_by('order'):
            question_id = str(question.id)
            user_answer = answers_data.get(question_id)
            is_correct = question.check_answer(user_answer) if user_answer else False
            
            result = {
                'question_id': question.id,
                'question_text': question.question_text,
                'question_type': question.question_type,
                'points': question.points,
                'points_earned': question.points if is_correct else 0,
                'is_correct': is_correct,
                'user_answer': user_answer,
                'explanation': question.explanation,
            }
            
            # Ajouter les détails des choix pour QCM/QCU/Vrai-Faux
            if question.question_type in ['multiple_choice', 'single_choice', 'true_false']:
                result['choices'] = ChoiceWithCorrectionsSerializer(
                    question.choices.all().order_by('order'), 
                    many=True
                ).data
            
            results.append(result)
        
        return results