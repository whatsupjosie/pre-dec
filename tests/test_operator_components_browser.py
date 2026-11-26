"""Chromium operator component regressions; host/API responses are test doubles."""
from pathlib import Path
import os
import pytest

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://localhost:8765'

@pytest.fixture
def browser_context():
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch(executable_path=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE'), args=['--no-sandbox'])
        except pw.Error as exc:
            pytest.skip('Chromium unavailable: '+str(exc).splitlines()[0])
        context = browser.new_context(viewport={'width': 390, 'height': 844})
        try:
            yield context
        finally:
            context.close()
            browser.close()

def test_camera_buttons_keyboard_and_lock(browser_context):
    page = browser_context.new_page()
    page.set_content('''<section id="panel"><select data-framing-target><option value="preview">Preview</option><option value="program">Program</option></select><input type="checkbox" data-framing-keys><button data-framing-action="left">Left</button><button data-framing-action="in">Zoom</button><button data-framing-action="reset">Reset</button><output data-framing-status></output></section><input id="editor">''')
    page.add_script_tag(path=ROOT/'static/operator_camera_framing.js')
    page.evaluate('''() => {const initial={id:'p',label:'Preview',center:[.5,.5],zoom:2};window.shots={preview:structuredClone(initial),program:{...structuredClone(initial),id:'g',label:'Program'}};window.blocked=false;window.controls=PubCastCameraFraming.mount({panel:document.querySelector('#panel'),current:r=>shots[r],allowed:()=>blocked?'Pool active':'',change:(r,a)=>{shots[r]=PubCastCameraFraming.adjust(shots[r],a)},reset:r=>{shots[r]={...shots[r],center:[.5,.5],zoom:2}}});}''')
    page.get_by_text('Left',exact=True).click()
    assert page.evaluate('shots.preview.center[0]') < .5
    assert page.evaluate('shots.program.center[0]') == .5
    page.locator('[data-framing-keys]').check()
    page.evaluate('document.activeElement.blur()')
    page.keyboard.press('d')
    assert page.evaluate('shots.preview.center[0]') == .5
    page.locator('#editor').fill('wasd')
    page.keyboard.press('a')
    assert page.evaluate('shots.preview.center[0]') == .5
    page.locator('[data-framing-target]').select_option('program')
    page.get_by_text('Zoom',exact=True).click()
    assert page.evaluate('shots.program.zoom') == 2.2
    page.get_by_text('Reset',exact=True).click()
    assert page.evaluate('shots.program.zoom') == 2
    page.evaluate('blocked=true;controls.refresh()')
    assert page.get_by_text('Zoom',exact=True).is_disabled()
    page.evaluate('document.activeElement.blur()')
    page.keyboard.press('d')
    assert page.evaluate('shots.program.center[0]') == .5

def test_confidence_hold_blackout_and_failure(browser_context):
    page = browser_context.new_page()
    page.add_script_tag(path=ROOT/'static/operator_confidence_guard.js')
    page.evaluate('''() => {window.latest=[];window.nextState={};window.responseMode='ok';window.fetch=async (_,options)=>{if(responseMode==='fail')throw Error('offline');if(responseMode==='pending')return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true}));return {ok:true,json:async()=>nextState};};window.guard=PubCastConfidenceGuard.create({setSources:(...s)=>{latest=s},stop:()=>{}},()=>({program:'p',preview:'v',sources:[{id:'p'},{id:'v'}]}));}''')
    page.evaluate('guard.poll()')
    assert page.evaluate('latest') == ['p','v']
    page.evaluate('() => {window.release=guard.hold()}')
    assert page.evaluate('latest') == [None,None]
    page.evaluate('guard.poll()')
    assert page.evaluate('latest') == [None,None]
    page.evaluate('nextState={blackout:true};release()')
    page.wait_for_function('latest[0]===null&&latest[1]==="v"')
    page.evaluate('nextState={};guard.poll()')
    assert page.evaluate('latest') == ['p','v']
    page.evaluate('responseMode="pending";guard.poll()')
    assert page.evaluate('latest') == [None,None]
    page.evaluate('responseMode="ok";guard.poll()')
    assert page.evaluate('latest') == ['p','v']
    page.evaluate('responseMode="fail";guard.poll()')
    assert page.evaluate('latest') == [None,None]

def test_prompter_validation(browser_context):
    page = browser_context.new_page()
    page.add_script_tag(path=ROOT/'static/operator_prompter_handoff.js')
    assert page.evaluate("PubCastPrompterHandoff.valid('a'.repeat(32))")
    assert not page.evaluate("PubCastPrompterHandoff.valid('not-a-token')")
    assert page.evaluate("() => {let message;PubCastPrompterHandoff.send('  ',(m,b)=>message=[m,b]);return message}") == ['Enter a script first', True]
    assert page.evaluate("() => {let message;PubCastPrompterHandoff.send('x'.repeat(200001),(m,b)=>message=[m,b]);return message}") == ['Script exceeds 200,000 characters', True]

def test_prompter_script_handoff(browser_context):
    source = (ROOT/'static/operator_prompter_handoff.js').read_text()
    browser_context.route(BASE+'/**', lambda route: route.fulfill(status=200, content_type='text/html', body='<button id="send">Send</button><output id="status"></output><script>'+source+'</script><script>if(location.hash){PubCastPrompterHandoff.receive(s=>document.getElementById("status").textContent=s)}else document.querySelector("#send").onclick=()=>PubCastPrompterHandoff.send("Line one\\nLine two",(m)=>document.getElementById("status").textContent=m)</script>'))
    page = browser_context.new_page()
    try:
        page.goto(BASE+'/')
    except pw.Error as exc:
        if 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc):
            pytest.skip('Browser policy blocks the isolated origin')
        raise
    with page.expect_popup() as popup_info:
        page.locator('#send').click()
    popup = popup_info.value
    popup.wait_for_function('document.getElementById("status").textContent==="Line one\\nLine two"')
    page.wait_for_function('document.getElementById("status").textContent.includes("Script received")')
    assert 'handoff=' not in popup.url
    assert popup.evaluate('window.opener===null')
