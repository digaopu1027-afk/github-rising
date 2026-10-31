"""Pure ranking rules. No network, clock or filesystem dependencies."""
from datetime import datetime
from fractions import Fraction

CATEGORIES = ['AI', '开发工具', '效率办公', '设计创作', '学习教育', '其他']
MIN_HOURS, MAX_HOURS = 22, 26


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('A snapshot timestamp must include a timezone')
    return parsed


def eligible(repo, approved_licenses):
    return (repo.get('visibility') == 'public' and not repo.get('fork')
            and not repo.get('archived') and not repo.get('disabled')
            and repo.get('license') in approved_licenses)


def observe(current, previous):
    row = dict(current)
    row.update(delta=None, growth_rate=None, rising_score=None,
               window_start=None, window_end=current['sampled_at'],
               window_hours=None, observation='warming')
    if previous is None:
        return row
    hours = (timestamp(current['sampled_at']) - timestamp(previous['sampled_at'])).total_seconds() / 3600
    row.update(window_start=previous['sampled_at'], window_hours=round(hours, 3))
    if not MIN_HOURS <= hours <= MAX_HOURS:
        row['observation'] = 'invalid_window'
        return row
    delta = current['stars'] - previous['stars']
    baseline = previous['stars']
    row.update(delta=delta, growth_rate=(delta / baseline if baseline else None),
               rising_score=delta / max(baseline, 100), observation='ready')
    return row


def build_rankings(rows):
    candidates = [r for r in rows if r['observation'] == 'ready'
                  and r['stars'] >= 50 and r['delta'] > 0]

    def growth(row):
        baseline = row['stars'] - row['delta']
        # A true zero baseline has undefined growth, rather than infinity.
        return Fraction(row['delta'], baseline) if baseline else Fraction(-1)

    hot = sorted(candidates, key=lambda r: (-r['delta'], -growth(r), r['id']))[:50]
    rising = sorted((r for r in candidates if r['stars'] <= 5000 and r['delta'] >= 10),
                    key=lambda r: (-Fraction(r['delta'], max(r['stars'] - r['delta'], 100)),
                                   -r['delta'], r['id']))[:20]
    def ranked(items):
        return [dict(row, rank=i + 1) for i, row in enumerate(items)]
    return ranked(hot), ranked(rising)


def classify(repo, readme=''):
    # Classification is an editable heuristic; it is not a quality judgment.
    text = (' '.join(repo.get('topics', [])) + ' ' + repo.get('description', '')
            + ' ' + repo.get('full_name', '')).lower()
    groups = [
        ('AI', ['llm', 'artificial-intelligence', 'machine-learning', ' ai ', 'agent', 'diffusion', 'chatgpt', 'claude', 'language model']),
        ('设计创作', ['design', 'video', 'animation', 'drawing', 'photo', 'music', 'creative', 'image editor']),
        ('效率办公', ['productivity', 'note-taking', 'notes', 'calendar', 'office', 'bookmark', 'email', 'workflow automation']),
        ('学习教育', ['education', 'tutorial', 'learning', 'course', 'awesome', 'learn-', 'interview', 'book']),
        ('开发工具', ['developer', 'framework', 'testing', 'database', 'cli', 'compiler', 'terminal', 'library', 'editor', 'api', 'sdk', 'browser']),
    ]
    category = next((name for name, words in groups if any(w in text for w in words)), '其他')
    if any(word in text for word in ['awesome', 'tutorial', 'course', 'collection', 'resources', 'book', 'skills']):
        kind = '教程／资源'
    elif any(word in text for word in ['framework', 'library', 'sdk', 'component']):
        kind = '库／框架'
    else:
        kind = '应用／工具'
    return category, kind
