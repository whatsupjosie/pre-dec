"""Closed-Airlock access, durable host alerts and admission through the real host."""
import json
import secrets

import httpx
import pytest

from tests.test_data_checkpoint_host_recovery import Host
from tests.test_guest_identity import CONSENTS, profile
from modules.credentials import CredentialStore
from modules.guest_identity import sign_visit


def test_closed_airlock_and_host_alerts_in_chromium(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    data = tmp_path / 'data'
    data.mkdir()
    host = Host(data, tmp_path / 'airlock-host.log')
    host.start()
    try:
        password = secrets.token_urlsafe(20) + 'Aa9!'
        with httpx.Client(base_url=host.base, trust_env=False) as api:
            created = api.post('/api/auth/setup', json={
                'username':'host-owner', 'password':password, 'confirm_password':password,
            })
            assert created.status_code == 201, created.text
            owner_headers = {'Authorization':'Bearer ' + created.json()['access_token']}
        with httpx.Client(base_url=host.base, trust_env=False) as outsider:
            assert outsider.get('/api/guests/events').status_code == 401
            assert outsider.get('/api/chat/rooms/world').status_code == 401
            assert outsider.get('/static/world_walk.html').status_code == 401
            assert outsider.get('/studio', headers={'Accept':'text/html'}).headers['location'].endswith('?mode=join')
            assert outsider.post('/api/guests/arrival/status', json={'ticket':'f'*64}).json() == {'status':'expired'}
            with playwright.sync_playwright() as runtime, runtime.chromium.launch() as browser:
                staff = browser.new_page()
                staff.goto(host.base + '/login?next=/2i/chat')
                staff.fill('#loginUser', 'host-owner')
                staff.fill('#loginPass', password)
                staff.click('#loginBtn')
                staff.wait_for_url('**/2i/chat')
                guest = browser.new_page(viewport={'width':390,'height':844})
                guest.goto(host.base + '/walk')
                guest.wait_for_url('**/static/human_visits.html?mode=join')
                playwright.expect(guest.locator('#enter')).to_be_hidden()
                guest.get_by_label('Screen name').fill('Night Visitor')
                guest.get_by_role('button', name='Page the door staff').click()
                playwright.expect(guest.locator('#arrival-status')).to_contain_text('have been paged')
                playwright.expect(staff.get_by_text('Night Visitor · Airlock')).to_be_visible()
                staff.get_by_role('link', name='Open host event log').click()
                playwright.expect(staff.get_by_text('Night Visitor · Airlock')).to_be_visible()
                staff.get_by_role('link', name='Door station').click()
                staff.get_by_role('button', name='Invite to sign in').click()
                playwright.expect(guest.locator('#prepared')).to_be_visible(timeout=10000)
                playwright.expect(guest.locator('#enter')).to_be_hidden()

                challenge = guest.locator('#challengeOut').input_value()
                home = CredentialStore(tmp_path/'visitor-home')
                signed = sign_visit(home, profile(), json.loads(challenge), CONSENTS)
                guest.locator("summary", has_text="Exchange the card manually").click()
                guest.locator('#proofIn').fill(json.dumps(signed))
                guest.get_by_role('button', name='Send my card').click()
                playwright.expect(guest.locator('#status')).to_contain_text('Waiting for your host')
                playwright.expect(guest.locator('#enter')).to_be_hidden()
                staff.get_by_role('button', name='Refresh waiting room').click()
                staff.get_by_role('button', name='Approve visit').click()
                playwright.expect(guest.locator('#enter')).to_be_visible(timeout=10000)
                staff.goto(host.base + '/host-events')
                playwright.expect(staff.get_by_text('Night Visitor · Airlock').first).to_be_visible()

            issued = outsider.post('/api/guests/invites', headers=owner_headers, json={'returning_auto':True}).json()['invite_code']
            repeat = outsider.post('/api/guests/challenge', json={'invite_code':issued}).json()
            signed = sign_visit(home, profile(), repeat['challenge'], CONSENTS)
            assert outsider.post('/api/guests/request', json=signed).status_code == 201
            lease = outsider.post('/api/guests/status', json={'poll_token':repeat['poll_token']}).json()
            assert lease.get('access_token')
            guest_headers = {'Authorization':'Bearer ' + lease['access_token']}
            request = outsider.post('/api/guests/host-request', headers=guest_headers,
                                    json={'room':'green_room','detail':'May I speak to the host?'})
            assert request.status_code == 201, request.text
            assert outsider.get('/api/guests/events', headers=guest_headers).status_code == 403
            # A guest cannot make a security recommendation.
            report_body = {'room':'studio','user_id':profile()['user_id'],'detail':'Review this report before ejecting.'}
            assert outsider.post('/api/guests/security-report', headers=guest_headers, json=report_body).status_code == 403
            report = outsider.post('/api/guests/security-report', headers=owner_headers, json=report_body)
            assert report.status_code == 201, report.text
            events = outsider.get('/api/guests/events', headers=owner_headers).json()['events']
            assert any(e['kind']=='host_request' and e['room']=='green_room' for e in events)
            assert any(e['event_id']==report.json()['event_id'] and e['kind']=='security_report' for e in events)
            assert outsider.get('/api/auth/verify',headers=guest_headers).status_code == 200
            with playwright.sync_playwright() as runtime, runtime.chromium.launch() as browser:
                staff = browser.new_page()
                staff.goto(host.base + '/login?next=/host-events')
                staff.fill('#loginUser', 'host-owner')
                staff.fill('#loginPass', password)
                staff.click('#loginBtn')
                staff.wait_for_url('**/host-events')
                alert = staff.locator('.host-event').filter(has_text='Security recommends ejection')
                playwright.expect(alert).to_be_visible()
                alert.get_by_role('button', name='Read room transcript').click()
                playwright.expect(alert.get_by_text('Recent room transcript')).to_be_visible()
                staff.once('dialog', lambda dialog: dialog.accept())
                alert.get_by_role('button', name='Confirm ejection').click()
                playwright.expect(staff.locator('[data-event-status]')).to_contain_text('was ejected')
            assert outsider.get('/api/auth/verify',headers=guest_headers).status_code == 401
    finally:
        host.stop()


def test_owner_pass_lets_named_arrival_enter_without_signing_until_production_ends(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    data = tmp_path / 'data'
    data.mkdir()
    with httpx.Client(trust_env=False) as api:
        host = Host(data, tmp_path / 'session-pass-host.log')
        host.start()
        try:
            password = secrets.token_urlsafe(20) + 'Aa9!'
            setup = api.post(host.base + '/api/auth/setup', json={
                'username':'host-owner', 'password':password, 'confirm_password':password,
            })
            owner = {'Authorization':'Bearer ' + setup.json()['access_token']}
            slate = api.post(host.base + '/api/studio/slate', headers=owner, json={'action':'create'}).json()['slate']
            with playwright.sync_playwright() as runtime, runtime.chromium.launch() as browser:
                staff, visitor = browser.new_page(), browser.new_page()
                staff.goto(host.base + '/login?next=/static/human_visits.html?mode=host')
                staff.fill('#loginUser', 'host-owner')
                staff.fill('#loginPass', password)
                staff.click('#loginBtn')
                staff.wait_for_url('**/human_visits.html?mode=host')
                visitor.goto(host.base + '/walk')
                visitor.get_by_label('Screen name').fill('Guest of the owner')
                visitor.get_by_role('button', name='Page the door staff').click()
                playwright.expect(visitor.locator('#enter')).to_be_hidden()
                staff.once('dialog', lambda dialog: dialog.accept())
                staff.get_by_role('button', name='Issue session pass').click()
                playwright.expect(visitor.locator('#enter')).to_be_visible(timeout=10000)
                playwright.expect(visitor.locator('#prepared')).to_be_hidden()
                playwright.expect(staff.locator('#active-passes')).to_contain_text('Guest of the owner')
                token = visitor.evaluate("sessionStorage.getItem('pubcast_token')")
                guest = {'Authorization':'Bearer ' + token}
                assert api.get(host.base + '/api/auth/verify', headers=guest).status_code == 200
                ended = api.post(host.base + '/api/studio/slate', headers=owner,
                                 json={'action':'end','revision':slate['revision']})
                assert ended.status_code == 200, ended.text
                assert api.get(host.base + '/api/auth/verify', headers=guest).status_code == 401
                visitor.goto(host.base + '/walk')
                visitor.wait_for_url('**/human_visits.html?mode=join')
        finally:
            host.stop()
