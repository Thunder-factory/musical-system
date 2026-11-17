from apps.recommendations.models import ListeningHistory, UserTasteProfile

def recalculate_profile(user):
    """
    Recalcula el perfil de gustos del usuario basado en su historial.
    Se ejecuta después de registrar una reproducción.
    """
    history = list(
        ListeningHistory.objects
        .filter(user=user)
        .select_related('tag')
        .order_by('-play_count', '-last_played_at')[:20]
    )

    top_tags = [
        {'tag_id': item.tag.id, 'name': item.tag.name, 'score': item.play_count}
        for item in history
    ]
    top_genres = [
        tag for tag, item in zip(top_tags, history)
        if item.tag.category == 'genre'
    ]
    top_moods = [
        tag for tag, item in zip(top_tags, history)
        if item.tag.category == 'mood'
    ]

    profile, _ = UserTasteProfile.objects.update_or_create(
        user=user,
        defaults={'top_tags': top_tags, 'top_genres': top_genres, 'top_moods': top_moods}
    )
    return profile
