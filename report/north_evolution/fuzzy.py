"""Explainable Sugeno-style fuzzy acceptance scores for this isolated prototype.

Degrees and rule consequents are configurable demonstration choices, not calibrated
truth probabilities. Protection and accepted corrections are explicit state rules.
"""
import math


def membership(x):
    x=max(0.,min(1.,float(x)))
    return dict(low=1. if x<=.2 else max(0.,(.5-x)/.3),
                medium=max(0.,min((x-.2)/.3,(.8-x)/.3)),
                high=1. if x>=.8 else max(0.,(x-.5)/.3))


def score(*,quality=.85,age_days=0,half_life=365,support=0.,conflict=0.,protected=False,status='active'):
    if status in {'superseded','retracted'}:
        return dict(score=0.,state_rule='Excluded from current acceptance; historical score retained separately',rules=[],inputs={})
    if protected:
        return dict(score=1.,state_rule='Protected: no ordinary decay or unaccepted contradiction can lower the score',rules=[],
                    inputs=dict(quality=quality,age_days=age_days,support=support,conflict=conflict))
    freshness=1. if half_life is None else 2.**(-max(0.,age_days)/half_life)
    q,f,s,c=map(membership,(quality,freshness,support,conflict))
    rules=[]
    def rule(name,strength,target):
        if strength>0:rules.append(dict(rule=name,firing=round(strength,6),consequent=target))
    rule('Reliable source AND weak conflict',min(q['high'],c['low']),.96)
    rule('Moderate source AND weak conflict',min(q['medium'],c['low']),.82)
    rule('Weak source AND weak conflict',min(q['low'],c['low']),.48)
    rule('Fresh AND reliable AND weak conflict',min(f['high'],q['high'],c['low']),.98)
    rule('Aging evidence AND weak conflict',min(f['medium'],c['low']),.78)
    rule('Stale evidence AND weak conflict',min(f['low'],c['low']),.50)
    rule('Some support AND reliable AND weak conflict',min(s['medium'],q['high'],c['low']),.98)
    rule('Strong independent support AND reliable AND weak conflict',min(s['high'],q['high'],c['low']),.99)
    rule('Moderate unresolved conflict',c['medium'],.50)
    rule('Strong unresolved conflict',c['high'],.18)
    denominator=sum(r['firing'] for r in rules)
    target=sum(r['firing']*r['consequent'] for r in rules)/denominator if denominator else .5
    acceptance=min(.99,max(0.,.99*target*freshness))
    return dict(score=round(acceptance,6),state_rule='Ordinary degree of current acceptance, capped below 1',
                inputs=dict(quality=quality,age_days=age_days,half_life_days=half_life,freshness=round(freshness,6),support=support,conflict=conflict),
                membership=dict(quality=q,freshness=f,support=s,conflict=c),rules=rules,
                weighted_consequent=round(target,6),formula='min(0.99, 0.99 * weighted_rule_consequent * freshness)')


def relationship(old,new,*,aliases=None,explicit_change=False,explicit_correction=False,same_time=False):
    """Typed-slot comparison after hand-reviewed normalization; not an NLP parser."""
    aliases=aliases or {}
    def canonical(v):return aliases.get(v,v) if isinstance(v,str) else v
    if (old['subject'],old['slot'],old['scope'])!=(new['subject'],new['slot'],new['scope']):
        return 'ADDITIVE','Different subject, property, or scope; no replacement.'
    if canonical(old['value'])==canonical(new['value']):
        return 'CONFIRMS','Same typed proposition after accepted identity resolution.'
    if old['cardinality']!='single' or new['cardinality']!='single':
        return 'ADDITIVE','Multiple values are allowed; difference is not contradiction.'
    if explicit_correction and same_time:
        return 'CONTRADICTS_AND_SUPERSEDES','Explicit accepted correction targets the same exclusive property and assertion context.'
    if explicit_change:
        return 'SUPERSEDES','Explicit change replaces latest state while retaining the prior historical claim.'
    if same_time:
        return 'CONTRADICTS','Different mutually exclusive values in the same asserted context; resolution still required.'
    return 'POSSIBLE_CONFLICT','Values differ, but overlapping event validity or explicit replacement is not established.'


def transition(old,new,relation,*,accepted=False):
    """A new report alone never receives a protected score of one."""
    a,b=dict(old),dict(new)
    if accepted and relation in {'SUPERSEDES','CONTRADICTS_AND_SUPERSEDES'}:
        a.update(status='retracted' if relation=='CONTRADICTS_AND_SUPERSEDES' else 'superseded',
                 historical_score=a['score'],score=0.)
        b.update(status='active',protected=bool(a.get('protected')),score=1. if a.get('protected') else b['score'])
    elif relation in {'CONTRADICTS','CONTRADICTS_AND_SUPERSEDES','POSSIBLE_CONFLICT'}:
        a['status']='disputed';b['status']='disputed'
    return a,b
