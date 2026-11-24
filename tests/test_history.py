"""Synthetic historical evidence; no personal data or real backend required."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from pydantic import ValidationError

from fitness.archive import AnalystStore
from fitness.history import HistoricalAnalysis, aggregate, delta, phase_hint, similar_sessions
from fitness.history_models import HistoricalAssignment, HistoricalPreparation, HistoryComparison, HistoryPeriod
from intervals.intervals_client import IntervalsClient


def activity(key='a', day='2024-02-06', **changes):
    return dict(id=key, date=day, source='activity', name='Example Build W3/S1', sport='Ride',
                duration_sec=3600, distance_m=30000, tss=40, avg_watts=150, avg_hr=130,
                ftp=200, weight=70, reference=f'activity:{key}', **changes)


@pytest.fixture
def service(tmp_path):
    client=SimpleNamespace(athlete_id='synthetic',
        get_historical_activities=Mock(return_value=[activity()]), get_calendar=Mock(return_value=[]),
        get_wellness_history=Mock(return_value=[]), get_historical_session_details=Mock(return_value={'intervals': []}),
        get_historical_comments=Mock(return_value=dict(comments=[dict(text='Nicht müde, aber abgebrochen wegen Defekt.',personal=True,created='2024-02-06')],possibly_truncated=False)))
    return HistoricalAnalysis(client, AnalystStore(tmp_path))


def period():
    return HistoryPeriod(start=date(2024,2,1),end=date(2024,2,29))


def test_cache_reuses_overlapping_month_and_keeps_sources_separate(service):
    first=service.period(period())
    second=service.period(HistoryPeriod(start=date(2024,2,5),end=date(2024,2,11)))
    service.client.get_historical_activities.assert_called_once()
    assert first['metrics']['sessions']['value']==1
    assert second['activities'][0]['ftp']==200
    assert second['sources'][0]['status']=='cached'
    assert second['activities'][0]['assignment']['confidence']=='candidate'


def test_unavailable_activity_source_is_not_zero(service):
    service.client.get_historical_activities.side_effect=httpx.ConnectError('synthetic')
    result=service.period(period())
    assert result['metrics']['sessions']['value'] is None
    assert result['metrics']['tss']['value'] is None
    assert result['sources'][0]['status']=='unavailable'


def test_partial_missing_totals_and_wellness_are_explicit():
    rows=[activity(),activity('b')]; rows[1]['tss']=None
    m=aggregate(rows,[dict(ctl=0,tsb=-10)],date(2024,2,1),date(2024,2,7),True)
    assert m['tss']['value'] is None and m['tss']['known']==1
    assert m['ctl']['value']==0 and m['ctl']['status']=='partial'
    assert m['tsb']['value']==-10
    assert m['lit_hit']['value'] is None
    assert delta(0,5)==dict(absolute=5,percent=None)
    assert delta(None,5)['absolute'] is None


def test_phase_hint_and_manual_override_persist(service):
    hint=phase_hint(activity())
    assert hint['phase']=='Build' and hint['week']==3 and hint['anchor']=='2024-01-22'
    service.period(period())
    service.save_preparation(HistoricalPreparation(id='past',name='Past',start='2024-01-01',end='2024-03-01'))
    service.save_assignment(HistoricalAssignment(reference='activity:a',preparation_id='past',phase='Base',week=1))
    result=service.period(period())
    assert result['activities'][0]['assignment']['confidence']=='manual'
    assert result['activities'][0]['assignment']['phase']=='Base'
    assert result['activities'][0]['name']=='Example Build W3/S1'
    with pytest.raises(ValueError):
        service.save_assignment(HistoricalAssignment(reference='activity:missing',phase='Build'))


def test_pairing_avoids_sport_mismatch_reuse_and_self():
    old=[activity(),activity('c')];new=[activity('b'),activity('d')]
    pairs=similar_sessions(old,new)
    assert len(pairs)==2 and len({p['a'] for p in pairs})==2
    assert all(p['comparability']=='limited' for p in pairs)
    assert similar_sessions(old,[dict(activity('x'),sport='Run')])==[]
    assert similar_sessions([activity()],[activity()])==[]


def test_comments_preserve_negation_and_do_not_claim_sentiment(service):
    notes=service.comments('a')
    assert notes['comments'][0]['text'].startswith('Nicht müde')
    assert set(notes['comments'][0]['topics'])=={'Ermüdung','Abbruch'}
    assert 'sentiment' not in notes['comments'][0]
    service.period(period())
    with pytest.raises(ValueError):service.session_pair('a','unknown')


def test_race_alignment_uses_explicit_date_and_sport_filter(service):
    p=period().model_copy(update={'race_date':date(2024,6,1)})
    result=service.compare(HistoryComparison(a=p,b=p,sport='Run'))
    assert result['a']['metrics']['sessions']['value']==0
    assert result['a']['weekly'][0]['race_week'] < 0
    assert result['a']['race_date']=='2024-06-01'
    assert result['a']['metrics']['ctl']['value'] is None
    with pytest.raises(ValidationError):HistoryPeriod(start='2025-01-01',end='2024-01-01')
    with pytest.raises(ValidationError):HistoryPeriod(start='2024-01-01',end='2026-01-01')


def test_client_snapshot_uses_local_date_and_preserves_historical_threshold():
    client=IntervalsClient.__new__(IntervalsClient); client.athlete_id='test'
    client._get=Mock(return_value=[dict(id='x',start_date_local='2024-02-06T00:30:00',start_date='2024-02-05T23:30:00Z',name='Test',type='Ride',icu_ftp=180,icu_weight=60,moving_time=0,icu_training_load=0)])
    rows=client.get_historical_activities(date(2024,2,6),date(2024,2,6))
    assert rows[0]['date']=='2024-02-06' and rows[0]['ftp']==180
    assert rows[0]['tss']==0 and rows[0]['avg_watts'] is None
    client._get=Mock(return_value=[dict(type='TEXT',content='My note',athlete_id='test',created='2024-02-06'),dict(type='TEXT',content='Coach note',athlete_id='other'),dict(type='TEXT',content='Removed',deleted='2024-02-07')])
    notes=client.get_historical_comments('x')['comments']
    assert len(notes)==2 and notes[0]['personal'] and not notes[1]['personal']


def test_wellness_failure_does_not_publish_partial_comparison(service):
    service.client.get_wellness_history.side_effect=httpx.ConnectError('synthetic')
    r=service.compare(HistoryComparison(a=period(),b=period(),sport='Ride'))
    assert r['a']['metrics']['ctl']['status']=='unavailable'
    assert r['a']['metrics']['sessions']['value']==1


def test_rate_limit_prevents_further_live_requests(service):
    response=httpx.Response(429,headers={'Retry-After':'120'},request=httpx.Request('GET','https://example.test'))
    service.client.get_historical_activities.side_effect=httpx.HTTPStatusError('rate limited',request=response.request,response=response)
    r=service.period(period())
    assert r['sources'][0]['http_status']==429
    service.client.get_calendar.assert_not_called()
    service.client.get_wellness_history.assert_not_called()
    service.period(period())
    service.client.get_historical_activities.assert_called_once()


def test_cached_historical_snapshot_is_isolated_by_athlete(service):
    service.period(period())
    service.client.athlete_id='other-synthetic'
    service.client.get_historical_activities.reset_mock()
    HistoricalAnalysis(service.client,service.store).period(period())
    service.client.get_historical_activities.assert_called_once()


def test_original_comments_and_details_join_measured_pairs(service):
    service.client.get_historical_activities.return_value=[activity(),activity('b',day='2024-02-13')]
    service.period(period())
    pair=service.session_pair('a','b')
    assert pair['comments_a']['comments'][0]['personal'] is True
    assert pair['a']['details']['intervals']==[]
    assert pair['observations'][0]['evidence']==['activity:a','activity:b']
    assert pair['comparability']['comparability']=='limited'


def test_history_http_validation_and_persistence(service, monkeypatch):
    import api
    from fastapi.testclient import TestClient
    monkeypatch.setattr(api,'historical_analysis',service)
    client=TestClient(api.app)
    payload=dict(a=period().model_dump(mode='json'),b=period().model_dump(mode='json'))
    assert client.post('/analyst/history/compare',json=payload).json()['a']['metrics']['sessions']['value']==1
    assert client.post('/analyst/history/compare',json=dict(payload,sport='wrong')).status_code==422
    assert client.put('/analyst/history/assignment',json=dict(reference='activity:missing')).status_code==422
    assert client.put('/analyst/history/preparation',json=dict(id='test',name='Test',start='2024-01-01',end='2024-03-01')).status_code==200
    assert client.put('/analyst/history/assignment',json=dict(reference='activity:a',preparation_id='test',phase='Base',week=1)).status_code==200
    assert client.get('/analyst/history/catalog').json()['assignments'][0]['phase']=='Base'
    assert client.get('/analyst/history/pair',params=dict(a_id='a',b_id='missing')).status_code==422


def test_history_template_and_proxy_failures(monkeypatch):
    from dashboard import routes
    from tests.test_dashboard import DashboardRouteTests
    from fastapi import HTTPException
    html=routes.comparison_page(DashboardRouteTests._request()).body.decode()
    assert 'Trainingsvergleich' in html and 'comparison.js' in html
    monkeypatch.setattr(routes._api_client,'request',Mock(side_effect=httpx.ConnectError('synthetic')))
    with pytest.raises(HTTPException) as error:routes.history_catalog_proxy()
    assert error.value.status_code==502
