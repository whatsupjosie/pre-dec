"""Touch-key events must edit 2i's authoritative textarea, not a demo buffer.

Standalone synthetic host: uses the ACTUAL production typewriter console, key
adapter and studio-desk scripts through intercepted localhost routes. No real
server, account or network required. Requires Chromium/Playwright.

Rewritten 2026-11-21 for the current studio-desk design. It previously drove
`#twoiTouchableTypewriter` -> `#twoiLiveKeysFrame`, a tap-to-open keys panel that
no longer exists: in typewriter view the live console is embedded directly as
`#twoiTypewriterConsole`, with `#twoiTypewriterExpand` to enlarge the keys. That
is closer to what Josie asked for -- real touch and mouse hotspots on the keys,
no extra tap to reach them -- so the test follows the code, not the old UI. What
is being tested is unchanged: keys reach the real manuscript, an inactive view
and a spoofed message cannot write, and Collab types into the draft.
"""
from pathlib import Path
from urllib.parse import urlsplit

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]

# studio-desk.js builds its scene inside #notebookFrame and relays keys through
# window.TwoiTypewriterInput, so both have to exist here as they do in 2i.
PARENT = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<section id="mcSection"><div class="section-body"></div></section>
<div class="top-bar"></div>
<div id="notebookFrame"></div>
<textarea id="soloTextarea">Original</textarea><textarea id="draftArea"></textarea>
<script>
const reachFileMode=false;
const $=id=>document.getElementById(id);
const soloTextarea=$('soloTextarea'),draftArea=$('draftArea');
let coWriting=false,initializing=false,generating=false,chatSending=false,editingIdx=null;
let networked=false,serverReady=false,committed=['Original'],buffer=[];
let render=function(){};
async function preserveBeforeSwitch(){return true;}
function rememberStudioResume(){return true;}
window.receivedInputs=0;window.writerNotes=[];
function addChat(role,message){writerNotes.push({role,message});}
soloTextarea.addEventListener('input',()=>receivedInputs++);
draftArea.addEventListener('input',()=>receivedInputs++);
</script>
<script src="/static/2i_studio_bridge.js"></script>
<script src="/2i/2i-assets/typewriter-key-bridge.js"></script>
<script src="/2i/2i-assets/typewriter-input.js"></script>
<script src="/2i/2i-assets/studio-desk.js"></script>
</body></html>"""

CHILD = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<div id="painted" style="width:900px;height:600px;position:relative"></div>
<script src="/static/typewriter_console_demo.js"></script>
<script>
document.dispatchEvent(new CustomEvent('pubcast:console-ready', {
 detail:{frame:document.getElementById('painted'),manifest:{paper:{x:0.2,y:0.05,w:0.6,h:0.32}}}
}));
</script>
</body></html>"""

SOURCES = {
    "/static/2i_studio_bridge.js": "static/2i_studio_bridge.js",
    "/static/typewriter_console_demo.js": "static/typewriter_console_demo.js",
    "/2i/2i-assets/typewriter-key-bridge.js": "2i/2i-assets/typewriter-key-bridge.js",
    "/2i/2i-assets/typewriter-input.js": "2i/2i-assets/typewriter-input.js",
    "/2i/2i-assets/studio-desk.js": "2i/2i-assets/studio-desk.js",
}


@pytest.fixture()
def app():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium unavailable: {exc}")
        context = browser.new_context(viewport={"width": 1024, "height": 768})
        # Count every tone at the Web Audio API; sound cannot be heard here.
        context.add_init_script("""
          window.__tones = [];
          class RecordingAudioContext {
            constructor(){ this.state='running'; this.currentTime=0; this.destination={}; }
            resume(){ return Promise.resolve(); } close(){ return Promise.resolve(); }
            createGain(){ return {gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}}; }
            createOscillator(){ const self=this; return {
              type:'', frequency:{setValueAtTime(v){this._v=v;},exponentialRampToValueAtTime(){}},
              connect(){}, disconnect(){},
              start(){ self.currentTime += 0.5; window.__tones.push({type:this.type, hz:this.frequency._v}); },
              stop(){}, onended:null }; }
          }
          window.AudioContext = RecordingAudioContext;
          window.webkitAudioContext = RecordingAudioContext;
        """)
        errors = []

        def serve(route):
            request = urlsplit(route.request.url)
            if request.hostname != "localhost":
                return route.abort()
            if request.path == "/test-parent":
                return route.fulfill(status=200, body=PARENT, content_type="text/html")
            if request.path == "/typewriter-console":
                return route.fulfill(status=200, body=CHILD, content_type="text/html")
            if request.path in SOURCES:
                file = ROOT / SOURCES[request.path]
                return route.fulfill(status=200, body=file.read_bytes(), content_type="text/javascript")
            return route.fulfill(status=404, body="Not found")

        context.route("**/*", serve)
        page = context.new_page()
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto("http://localhost/test-parent")
        page.evaluate("twoiSetPresentation('typewriter')")
        page.evaluate(
            "soloTextarea.focus(); soloTextarea.setSelectionRange(soloTextarea.value.length,soloTextarea.value.length)"
        )
        console = page.frame_locator("#twoiTypewriterConsole")
        console.locator("#painted").wait_for()
        # The console announces itself; wait for that handshake before keying.
        page.wait_for_function("document.getElementById('twoiTypewriterConsole').dataset.ready==='true'")
        yield page, console
        assert errors == [], errors
        browser.close()


def _key(console, char, text=""):
    console.locator("#painted").evaluate(
        "(el,key) => el.dispatchEvent(new CustomEvent('pubcast:key', {detail:key}))",
        {"char": char, "text": text, "source": "pointer"},
    )


def test_touch_keyboard_edits_real_manuscript_and_preserves_native_undo(app):
    page, console = app
    _key(console, "A", "X")
    page.wait_for_function("soloTextarea.value==='OriginalX'")
    assert page.evaluate("receivedInputs") == 1
    _key(console, "SHIFT", "")
    assert page.input_value("#soloTextarea") == "OriginalX"
    assert page.evaluate("writerNotes.length") == 0, page.evaluate("writerNotes")
    _key(console, "BACKSPACE", "")
    page.wait_for_function("soloTextarea.value==='Original'")
    _key(console, "RETURN", "\n")
    page.wait_for_function("soloTextarea.value==='Original\\n'")
    assert page.evaluate("receivedInputs") == 3
    page.locator("#soloTextarea").focus()
    page.keyboard.press("Control+z")
    assert page.input_value("#soloTextarea") == "Original"


def test_inactive_view_and_spoofed_messages_cannot_edit_document(app):
    page, console = app
    # Leaving typewriter view is what "closing the keyboard" is now: the relay
    # only accepts keys while the typewriter is the active presentation.
    page.evaluate("twoiSetPresentation('standard')")
    _key(console, "A", "X")
    page.wait_for_timeout(60)
    assert page.input_value("#soloTextarea") == "Original"
    # A message that did not come from the console's own frame is refused even
    # while the typewriter is active.
    page.evaluate("twoiSetPresentation('typewriter')")
    page.evaluate("window.postMessage({type:'pubcast:2i-key',key:{char:'A',text:'X'}},location.origin)")
    page.wait_for_timeout(60)
    assert page.input_value("#soloTextarea") == "Original"


def test_collab_routes_to_draft_not_approved_manuscript(app):
    page, console = app
    page.evaluate("coWriting=true; draftArea.focus()")
    _key(console, "A", "Draft")
    page.wait_for_function("draftArea.value==='Draft'")
    assert page.input_value("#soloTextarea") == "Original"


def test_expand_and_collapse_the_keys(app):
    page, console = app
    expand = page.locator("#twoiTypewriterExpand")
    assert expand.get_attribute("aria-expanded") == "false"
    expand.click()
    assert expand.get_attribute("aria-expanded") == "true"
    page.keyboard.press("Escape")
    assert expand.get_attribute("aria-expanded") == "false"


def test_keys_reach_the_live_formatting_surface_when_it_is_on(app):
    """With the formatting surface on, soloTextarea is hidden and holds only a
    mirror. A key pressed on the machine has to land in the surface, or the
    words go into the mirror and are overwritten at the next model update."""
    page, console = app
    page.evaluate("""() => {
      // a minimal stand-in for the live surface, recording what reaches it
      window.__surfaceKeys = [];
      window.twoiRichSurface = {
        active: () => true,
        key: (k) => { window.__surfaceKeys.push(k.text || k.char); return true; }
      };
    }""")
    _key(console, "A", "X")
    page.wait_for_function("window.__surfaceKeys.length === 1")
    assert page.evaluate("window.__surfaceKeys") == ["X"]
    assert page.input_value("#soloTextarea") == "Original", "the hidden mirror must not be typed into"


def test_a_surface_that_refuses_the_key_falls_back_to_the_manuscript(app):
    page, console = app
    page.evaluate("""() => { window.twoiRichSurface = {active: () => true, key: () => false}; }""")
    _key(console, "A", "X")
    page.wait_for_function("soloTextarea.value==='OriginalX'")


def test_a_key_on_the_machine_makes_one_sound_not_two(app):
    """static/typewriter_sound.js already clicks for every key pressed on the
    console. 2i must not add a second click on top of it for the same keystroke.
    Typing on the keyboard, where the console makes no sound, still clicks."""
    page, console = app
    boxes = page.locator("#twoiAudioOptions input[type=checkbox]")
    boxes.nth(0).check()
    _key(console, "A", "X")
    page.wait_for_function("soloTextarea.value==='OriginalX'")
    page.wait_for_timeout(80)
    assert page.evaluate("window.__tones") == [], "the console already clicked for that key"
    page.locator("#soloTextarea").focus()
    page.keyboard.type("yz", delay=30)
    clicks = [t for t in page.evaluate("window.__tones") if t["type"] == "triangle"]
    assert len(clicks) == 2, page.evaluate("window.__tones")
