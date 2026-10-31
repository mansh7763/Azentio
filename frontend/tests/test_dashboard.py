"""C-owned projection/API contract tests. Run from repo root with pytest frontend/tests."""
import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.api.dashboard import project
from app.api.sample_data import ALERTS, DETECTION_RUN
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def result():
    return SimpleNamespace(alerts=ALERTS, run=DETECTION_RUN)


def test_counts_reconcile_and_low_is_not_actionable(result):
    s = project(result)
    assert s['alerts_total'] == sum(s['counts_by_band'].values()) == 3
    assert s['flagged_total'] == 2
    assert s['records_processed'] == DETECTION_RUN.records_processed


@pytest.mark.parametrize('filters,ids', [
    ({'customer_id':'C002'}, ['ALT-1']),
    ({'txn_id':'T-9001'}, ['ALT-1']),
    ({'product':'current'}, ['ALT-3']),
    ({'band':'Low'}, ['ALT-3']),
    ({'detection_type':'DV-01'}, ['ALT-2']),
    ({'date_from':date(2026,10,2)}, []),
    ({'date_to':date(2026,9,30)}, []),
    ({'band':'High','product':'current'}, []),
    ({'date_from':date(2026,10,1),'date_to':date(2026,10,1)}, ['ALT-1','ALT-2','ALT-3']),
])
def test_filters(result,filters,ids):
    assert [a['alert_id'] for a in project(result, **filters)['alerts']] == ids


def test_linked_customer_filter(result):
    from app.schemas import AlertEntity
    alert = ALERTS[1].model_copy(deep=True)
    alert.entities.append(AlertEntity(entity_type='customer',entity_id='linked'))
    result.alerts = [alert]
    assert project(result,customer_id='linked')['alerts_total'] == 1


def test_empty(result):
    result.alerts=[]
    s=project(result)
    assert s['alerts_total']==s['flagged_total']==0
    assert s['over_time']==[]


def test_http_filters_and_validation(monkeypatch,result):
    monkeypatch.setattr('app.api.dashboard.latest_run',lambda session:DETECTION_RUN)
    monkeypatch.setattr('app.api.dashboard.latest_alerts',lambda session:ALERTS)
    client=TestClient(app)
    assert client.get('/api/dashboard/summary?band=High').json()['alerts_total']==1
    assert client.get('/api/dashboard/summary?date_from=bad').status_code==422
    assert client.get('/api/dashboard/summary?date_from=2026-10-02&date_to=2026-10-01').status_code==422


def test_source_note_states():
    from app.api.dashboard import source_note
    assert 'No records are stored yet' in source_note(None, {}, {'transactions': 0}, False)
    assert 'not scored yet' in source_note(None, {}, {'transactions': 5}, False)
    note = source_note('RUN-1', {'transactions': 1200, 'customers': 19}, {}, False)
    assert 'RUN-1' in note and '19 customers, 1,200 transactions' in note and 'changed' not in note
    assert 'changed since this run' in source_note('RUN-1', {'transactions': 1}, {'transactions': 2}, True)


def test_reads_share_the_stored_run_and_never_create_runs():
    """Upload -> detect -> dashboard/alerts/cases agree on one run; reads never run detection; reruns add no duplicate cases."""
    client = TestClient(app)
    client.post('/api/demo/load')
    run_id = client.post('/api/detect/run').json()['run']['run_id']
    first, second = client.get('/api/dashboard/summary').json(), client.get('/api/dashboard/summary').json()
    assert first['run_id'] == second['run_id'] == run_id and not first['run_stale']
    assert {k: v for k, v in first['records_processed'].items() if v} == {k: v for k, v in first['records_stored'].items() if v}
    alert_ids = {a['alert_id'] for a in client.get('/api/alerts?include_low=true').json()['items']}
    assert alert_ids == {a['alert_id'] for a in first['alerts']}
    cases = client.get('/api/cases').json()['items']
    linked = {i for c in cases for i in c['alert_ids']}
    assert {a['alert_id'] for a in first['alerts'] if a['band'] != 'Low'} <= linked

    csv = ('txn_id,sender_account,timestamp,amount,beneficiary_account\n'
           'T-UP-1,A-C001,2026-10-30T10:00:00Z,"1,250.00",B-NEW\n'
           'T-UP-2,A-C001,not-a-date,-5,B-NEW\n')
    report = client.post('/api/ingest', files={'file': ('upload.csv', csv, 'text/csv')}, data={'entity_type': 'transactions'}).json()
    assert (report['accepted'], report['rejected']) == (1, 1)
    assert client.get(f"/api/ingest/batches/{report['batch_id']}/rejected").json()['items'][0]['raw']['txn_id'] == 'T-UP-2'
    stale = client.get('/api/dashboard/summary').json()
    assert stale['run_id'] == run_id and stale['run_stale'] and 'changed since this run' in stale['source_note']

    client.post('/api/detect/run')
    fresh = client.get('/api/dashboard/summary').json()
    assert fresh['run_id'] != run_id and not fresh['run_stale']
    assert fresh['records_processed']['transactions'] == first['records_processed']['transactions'] + 1
    after = client.get('/api/cases').json()['items']
    assert {c['case_id'] for c in cases} <= {c['case_id'] for c in after}
    assert len({c['case_id'] for c in after}) == len(after)


def test_blank_text_filters_mean_no_filter(result):
    everything = [a['alert_id'] for a in project(result)['alerts']]
    assert [a['alert_id'] for a in project(result, customer_id='  ', txn_id=' ', product='')['alerts']] == everything
    assert [a['alert_id'] for a in project(result, customer_id=' c002 ')['alerts']] == ['ALT-1']
