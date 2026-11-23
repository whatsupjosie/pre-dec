"""The typewriter's key clicks and line-end bell, in real Chromium.

Audio cannot be heard here, so every tone is counted at the Web Audio API
instead: the page's AudioContext is replaced before 2i loads with a recorder
that notes each oscillator's type and frequency. A click is a triangle at
940 Hz, the bell a sine at 1450 Hz, which is what studio-desk.js asks for.

Josie's rule for this feature, in her words: "audio effects must be optional."
So the first thing tested is that it is silent until she turns it on.
"""
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"
SEATED = "?studio_room=dressing_room&studio_view=typewriter_sitting&desk=typewriter"

# Installed before any page script runs.
RECORDER = """
window.__tones = [];
class RecordingAudioContext {
  constructor(){ this.state='running'; this.currentTime=0; this.destination={}; }
  resume(){ return Promise.resolve(); }
  close(){ return Promise.resolve(); }
  createGain(){ const g={gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}}; return g; }
  createOscillator(){
    const self=this;
    return {
      type:'', frequency:{ setValueAtTime(v){ this._v=v; }, exponentialRampToValueAtTime(){} },
      connect(){}, disconnect(){},
      start(){ self.currentTime += 0.5;
               window.__tones.push({type:this.type, hz:this.frequency._v}); },
      stop(){}, onended:null
    };
  }
}
window.AudioContext = RecordingAudioContext;
window.webkitAudioContext = RecordingAudioContext;
"""


def _open(playwright, storage=None, url_suffix=SEATED):
    browser = playwright.chromium.launch()
    context = browser.new_context(viewport={"width": 1280, "height": 900},
                                  storage_state=storage)
    context.route(
        "**/*",
        lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort(),
    )
    context.add_init_script(RECORDER)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(PAGE.as_uri() + url_suffix)
    page.wait_for_function(
        "typeof initializing !== 'undefined' && !initializing && !!document.getElementById('twoiAudioOptions')",
        timeout=20000,
    )
    return browser, context, page, errors


def _enable(page, clicks=True, bell=True):
    boxes = page.locator("#twoiAudioOptions input[type=checkbox]")
    if clicks:
        boxes.nth(0).check()
    if bell:
        boxes.nth(1).check()


def _type_in_textarea(page, text):
    page.locator("#soloTextarea").click()
    page.keyboard.type(text, delay=30)


def _tones(page):
    return page.evaluate("window.__tones")


@pytest.fixture()
def playwright():
    with sync_api.sync_playwright() as p:
        yield p


def test_the_machine_is_silent_until_she_turns_the_sound_on(playwright):
    browser, _, page, errors = _open(playwright)
    boxes = page.locator("#twoiAudioOptions input[type=checkbox]")
    assert boxes.count() == 2
    assert boxes.nth(0).is_checked() is False
    assert boxes.nth(1).is_checked() is False
    _type_in_textarea(page, "typing with the sound off")
    assert _tones(page) == [], "nothing may sound until she asks for it"
    assert not errors, errors
    browser.close()


def test_keys_click_and_the_line_end_rings(playwright):
    browser, _, page, errors = _open(playwright)
    _enable(page)
    _type_in_textarea(page, "abc")
    clicks = [t for t in _tones(page) if t["type"] == "triangle"]
    assert len(clicks) == 3, _tones(page)
    assert clicks[0]["hz"] == 940
    page.keyboard.press("Enter")
    bells = [t for t in _tones(page) if t["type"] == "sine"]
    assert len(bells) == 1, _tones(page)
    assert bells[0]["hz"] == 1450
    assert not errors, errors
    browser.close()


def test_each_switch_is_independent(playwright):
    browser, _, page, errors = _open(playwright)
    _enable(page, clicks=False, bell=True)
    _type_in_textarea(page, "abc")
    page.keyboard.press("Enter")
    kinds = {t["type"] for t in _tones(page)}
    assert kinds == {"sine"}, f"only the bell was asked for: {_tones(page)}"
    assert not errors, errors
    browser.close()


def test_the_choice_is_remembered(playwright):
    # Reloaded in the same browser, because storage_state does not carry
    # localStorage for a file:// origin -- that is the harness, not the feature.
    browser, _, page, errors = _open(playwright)
    _enable(page)
    page.reload()
    page.wait_for_function(
        "typeof initializing !== 'undefined' && !initializing && !!document.getElementById('twoiAudioOptions')",
        timeout=20000,
    )
    boxes = page.locator("#twoiAudioOptions input[type=checkbox]")
    assert boxes.nth(0).is_checked() is True
    assert boxes.nth(1).is_checked() is True
    _type_in_textarea(page, "ab")
    assert len([t for t in _tones(page) if t["type"] == "triangle"]) == 2
    assert not errors, errors
    browser.close()


def test_pasting_does_not_rattle_the_keys(playwright):
    browser, _, page, errors = _open(playwright)
    _enable(page)
    page.locator("#soloTextarea").click()
    page.evaluate("""() => {
      const ta=document.getElementById('soloTextarea');
      const data=new DataTransfer(); data.setData('text/plain','a pasted paragraph of some length');
      ta.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));
    }""")
    page.wait_for_timeout(80)
    assert _tones(page) == [], "a paste is not typing"
    assert not errors, errors
    browser.close()


def test_the_machine_is_silent_in_the_other_looks(playwright):
    browser, _, page, errors = _open(playwright)
    _enable(page)
    page.evaluate("twoiSetPresentation('notebook')")
    _type_in_textarea(page, "abc")
    assert _tones(page) == [], "only the typewriter makes a noise"
    assert page.evaluate("getComputedStyle(document.getElementById('twoiAudioOptions')).display") == "none"
    page.evaluate("twoiSetPresentation('typewriter')")
    page.keyboard.type("de", delay=30)
    assert len(_tones(page)) == 2
    assert not errors, errors
    browser.close()


def test_the_formatting_surface_sounds_the_same_as_the_plain_page(playwright):
    browser, _, page, errors = _open(playwright)
    _enable(page)
    _type_in_textarea(page, "seed")
    before = len(_tones(page))
    page.locator("#twoiRichToggle").click()
    page.wait_for_selector("#twoiRichSurface p")
    page.locator("#twoiRichSurface").click()
    page.keyboard.type("xyz", delay=30)
    clicks = [t for t in _tones(page) if t["type"] == "triangle"]
    assert len(clicks) == before + 3, _tones(page)
    page.keyboard.press("Enter")
    assert [t for t in _tones(page) if t["type"] == "sine"], "Enter rings on the live surface too"
    assert page.evaluate("committed.join('|')").startswith("seedxyz"), page.evaluate("committed")
    assert not errors, errors
    browser.close()


def test_a_script_typing_into_the_page_stays_silent(playwright):
    """Only a real keystroke sounds. Untrusted events are ignored, so tests,
    the AI writing into the draft and anything scripted do not play a note."""
    browser, _, page, errors = _open(playwright)
    _enable(page)
    page.evaluate("""() => {
      const ta=document.getElementById('soloTextarea');
      ta.value='written by a script';
      ta.dispatchEvent(new Event('input',{bubbles:true}));
    }""")
    page.wait_for_timeout(60)
    assert _tones(page) == []
    assert not errors, errors
    browser.close()


# --------------------------------------------------------------------------
# Page zoom: Josie, 2026-11-21 -- "at the bottom of the screen, you can still
# have the roller and the bay where the letter stamps are... and then just
# above that is the full page."
# --------------------------------------------------------------------------

def test_page_zoom_gives_the_page_the_column_and_keeps_the_machine_below(playwright):
    browser, _, page, errors = _open(playwright)
    zoom = page.locator("#twoiTypewriterPage")
    assert zoom.is_visible()
    assert zoom.get_attribute("aria-pressed") == "false"
    assert not page.locator("#twoiPageMachine").is_visible()
    zoom.click()
    assert zoom.get_attribute("aria-pressed") == "true"
    strip = page.locator("#twoiPageMachine")
    assert strip.is_visible(), "the roller and type bars must still be there"
    assert not page.locator("#twoiDeskScene").is_visible(), "the small machine steps aside"
    box = strip.bounding_box()
    editor = page.locator("#soloEditor").bounding_box()
    assert box["y"] > editor["y"], "the machine sits below the page, not above it"
    assert box["height"] < editor["height"], "the page gets the column, the machine a strip"
    assert not errors, errors
    browser.close()


def test_page_zoom_does_not_cost_the_sidebars(playwright):
    browser, _, page, errors = _open(playwright)
    page.locator("#twoiTypewriterPage").click()
    assert page.locator("#sidebar").is_visible()
    assert page.locator("#chatSection").is_visible()
    assert page.locator("#refSection").is_visible()
    assert page.locator("#twoiMenuBar").is_visible()
    assert not errors, errors
    browser.close()


def test_you_can_still_hear_the_typewriting_in_the_zoom(playwright):
    browser, _, page, errors = _open(playwright)
    _enable(page)
    page.locator("#twoiTypewriterPage").click()
    _type_in_textarea(page, "abc")
    clicks = [t for t in _tones(page) if t["type"] == "triangle"]
    assert len(clicks) == 3, _tones(page)
    assert not errors, errors
    browser.close()


def test_one_set_of_sound_switches_follows_the_machine(playwright):
    browser, _, page, errors = _open(playwright)
    assert page.evaluate("document.getElementById('twoiAudioOptions').closest('figure')?.id") == "twoiDeskScene"
    page.locator("#twoiTypewriterPage").click()
    assert page.evaluate("document.getElementById('twoiAudioOptions').parentElement.id") == "twoiPageMachine"
    assert page.locator("#twoiAudioOptions input").count() == 2, "one set of switches, not two"
    page.locator("#twoiTypewriterPage").click()
    assert page.evaluate("document.getElementById('twoiAudioOptions').closest('figure')?.id") == "twoiDeskScene"
    assert not errors, errors
    browser.close()


def test_leaving_the_typewriter_puts_the_zoom_away(playwright):
    browser, _, page, errors = _open(playwright)
    page.locator("#twoiTypewriterPage").click()
    assert page.evaluate("document.body.dataset.twoiTypewriterPage") == "on"
    page.evaluate("twoiSetPresentation('notebook')")
    assert page.evaluate("document.body.dataset.twoiTypewriterPage") is None
    assert not page.locator("#twoiTypewriterPage").is_visible()
    assert not page.locator("#twoiPageMachine").is_visible()
    page.evaluate("twoiSetPresentation('typewriter')")
    assert page.locator("#twoiTypewriterPage").is_visible()
    assert page.locator("#twoiTypewriterPage").get_attribute("aria-pressed") == "false"
    assert not errors, errors
    browser.close()
