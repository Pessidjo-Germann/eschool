from django import template
import re

register = template.Library()

@register.filter
def replace(value, arg):
    """
    Remplace une chaîne par une autre dans la valeur donnée.
    Usage: {{ value|replace:"ancien,nouveau" }}
    """
    if not arg:
        return value
    
    try:
        # Séparer par '|' au lieu de ',' pour éviter les conflits avec les URLs
        if '|' in arg:
            old, new = arg.split('|', 1)
        else:
            old, new = arg.split(',', 1)
        return str(value).replace(old, new)
    except ValueError:
        return value

@register.filter  
def vimeo_embed(value):
    """
    Convertit une URL Vimeo en URL d'embed
    Usage: {{ lesson.video_url|vimeo_embed }}
    """
    if not value:
        return value
    
    value = str(value)
    # Convertir vimeo.com/123456 en player.vimeo.com/video/123456
    if 'vimeo.com/' in value and 'player.vimeo.com' not in value:
        value = value.replace('vimeo.com/', 'player.vimeo.com/video/')
    
    return value

@register.filter
def youtube_embed(value):
    """
    Convertit une URL YouTube en URL d'embed
    Usage: {{ lesson.video_url|youtube_embed }}
    """
    if not value:
        return value
    
    value = str(value)
    # Convertir youtube.com/watch?v=123 en youtube.com/embed/123
    if 'youtube.com/watch?v=' in value:
        video_id = value.split('watch?v=')[1].split('&')[0]
        value = f"https://www.youtube.com/embed/{video_id}"
    elif 'youtu.be/' in value:
        video_id = value.split('youtu.be/')[1].split('?')[0]
        value = f"https://www.youtube.com/embed/{video_id}"
    
    return value

@register.filter
def difficulty_color(difficulty):
    """
    Retourne une classe CSS basée sur le niveau de difficulté
    """
    colors = {
        'beginner': 'success',
        'intermediate': 'warning', 
        'advanced': 'danger',
        'expert': 'dark'
    }
    return colors.get(difficulty.lower(), 'secondary')

@register.filter
def duration_format(minutes):
    """
    Formate la durée en minutes vers un format lisible
    """
    if not minutes:
        return "0 min"
    
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    
    if hours > 0:
        return f"{hours}h {mins}min" if mins > 0 else f"{hours}h"
    return f"{mins}min"

@register.filter
def truncate_words_html(value, arg):
    """
    Tronque le texte HTML en préservant les balises
    """
    try:
        length = int(arg)
    except (ValueError, TypeError):
        return value
    
    # Supprimer les balises HTML pour compter les mots
    import re
    text_only = re.sub(r'<[^>]+>', '', str(value))
    words = text_only.split()
    
    if len(words) <= length:
        return value
    
    # Tronquer et ajouter ...
    truncated_words = words[:length]
    return ' '.join(truncated_words) + '...'
