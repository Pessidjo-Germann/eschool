# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an intelligent educational platform (e-school) built with Django 4.2+ that provides an e-learning ecosystem with integrated payment systems and AI assistant capabilities. The platform serves learners, instructors, and administrators with personalized learning experiences and comprehensive course management.

## Architecture

This Django project follows a modular architecture designed to scale into the following apps:
- `users/` - Multi-role authentication system (learners, instructors, administrators)
- `courses/` - Course content management with multimedia support
- `payments/` - Transaction handling with Orange Money/Mobile Money integration
- `quiz/` - Assessment and evaluation system
- `analytics/` - Performance tracking and progress visualization
- `chatbot/` - AI-powered virtual assistant using OpenAI/Gemini API

Currently, this is a fresh Django project with only the base configuration.

## Technology Stack

- **Backend**: Django 5.0+ with Django REST Framework
- **Database**: PostgreSQL (currently using SQLite for development)
- **Frontend**: Django Templates + HTMX (with optional React/Vue.js)
- **Payment**: Orange Money / Mobile Money / Stripe APIs
- **AI**: OpenAI API or Gemini for chatbot functionality
- **Analytics**: Pandas + Chart.js for visualizations
- **Cache**: Redis for performance optimization

## Development Commands

### Running the Server
```bash
python3 manage.py runserver
```

### Database Management
```bash
python3 manage.py migrate
python3 manage.py makemigrations
python3 manage.py createsuperuser
```

### Project Structure
The main Django project is named `eschool` and contains standard Django configuration files in the `eschool/` directory.

## Key Features to Implement

1. **Multi-role user system** with distinct permissions for visitors, learners, instructors, and administrators
2. **Course management** with multimedia content upload and structured modules/lessons
3. **Payment integration** with local payment providers (Orange Money priority)
4. **Assessment system** with quizzes and automated grading
5. **Analytics dashboard** showing progression rates, scores, and learning time
6. **AI chatbot** for support, course recommendations, and intelligent notifications
7. **REST API** for future mobile application development

## Current State

This is a fresh Django installation with:
- Standard Django 4.2.23 configuration
- SQLite database (to be migrated to PostgreSQL)
- Basic URL routing with admin interface
- Default Django apps installed

The project requires initial setup of the modular app structure and implementation of the educational platform features described in the project specification.