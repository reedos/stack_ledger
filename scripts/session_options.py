"""Operator-only session choices; never source or model supplied permissions."""
LAYERS = ('energy', 'chips', 'infrastructure', 'models', 'applications')
MODES = {'monitoring': 0, 'balanced': 25, 'exploratory': 75, 'discovery': 100}
SOURCE_KINDS = {
    'official': ('Filings & official data', 1, 'official data'),
    'earnings': ('Earnings & investor relations', 2, 'earnings'),
    'technical': ('Products, engineering & blogs', 3, 'technology'),
    'newsroom': ('Press releases & newsrooms', 4, 'announcement'),
    'news': ('News & analyst leads', 5, 'news'),
    'social': ('Official social accounts', 6, 'announcement'),
    'unclassified': ('Unclassified registered sources', None, ''),
}


def add_arguments(parser):
    parser.add_argument('--direction', choices=MODES, default='balanced')
    parser.add_argument('--layers', nargs='+', choices=LAYERS)
    parser.add_argument('--source-kinds', nargs='+', choices=SOURCE_KINDS)


def choice_args(args):
    result = ['--direction', args.direction]
    for name in ('layers', 'source_kinds'):
        value = getattr(args, name)
        if value:
            result += ['--'+name.replace('_', '-'), *value]
    return result


def selected_sources(queue, registry, layers=None, kinds=None):
    from source_policy import collection_for
    ranks = {SOURCE_KINDS[k][1] for k in kinds} if kinds else None
    return [s for s in queue if (not layers or set(layers) & set(s['layers']))
            and (ranks is None or collection_for(registry, s).get('rank') in ranks)]


def split_budget(total, percent):
    if not 0 <= percent <= 100 or total < 1:
        raise ValueError('Invalid allocation')
    private = total if percent == 100 else (0 if percent == 0 or total < 2 else max(1, total*percent//100))
    return {'monitoring': total-private, 'discovery': private}


def stopped(root, session_id=None):
    return (root/'.local/stop-research-loop').exists() or bool(session_id and
        (root/'.local/sessions'/session_id/'stop').exists())
