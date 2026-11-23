"""2i's own offline spell check, in real Chromium, opened from disk.

No server and no network: every request that is not a file:// read is aborted
and recorded, and the test fails if anything tried to leave the machine.
"""
import time
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"


@pytest.fixture()
def page():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium unavailable: {exc}")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        offsite = []

        def route(r):
            if r.request.url.startswith("file:"):
                return r.continue_()
            offsite.append(r.request.url)
            return r.abort()

        context.route("**/*", route)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(PAGE.as_uri())
        page.wait_for_function(
            "typeof initializing !== 'undefined' && !initializing && !!window.TwoiSpell && TwoiSpell.isReady()",
            timeout=30000,
        )
        yield page
        assert not errors, errors
        assert not offsite, offsite
        browser.close()


def _write(page, text):
    page.locator("#soloTextarea").click()
    page.keyboard.press("Control+a")
    page.keyboard.insert_text(text)


def _marked(page):
    return page.evaluate(
        "[...document.querySelectorAll('.twoi-spell-mirror .twoi-misspelled')].map(s => s.textContent)")


def _wait_marked(page, expected):
    page.wait_for_function(
        "(want) => JSON.stringify([...document.querySelectorAll('.twoi-spell-mirror .twoi-misspelled')]"
        ".map(s => s.textContent)) === JSON.stringify(want)", arg=expected, timeout=8000)


def _right_click_word(page, index=0):
    box = page.locator(".twoi-spell-mirror .twoi-misspelled").nth(index).bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, button="right")
    page.wait_for_selector(".twoi-spell-menu")


def test_it_loads_from_disk_with_no_network_and_the_browsers_own_check_is_off(page):
    assert page.evaluate("TwoiSpell.isReady()")
    for selector in ("#soloTextarea", "#draftArea"):
        assert page.evaluate(f"document.querySelector('{selector}').spellcheck") is False
    assert page.evaluate("twoiRichSurface.node.spellcheck") is False


def test_misspelled_words_are_underlined_and_correct_ones_are_not(page):
    _write(page, "The manuscript is on the typewriter. I recieve teh letter and accomodate you.")
    _wait_marked(page, ["recieve", "teh", "accomodate"])


def test_the_underlines_sit_on_the_words_they_belong_to(page):
    _write(page, "A short line with a recieve in it.\n" + "word " * 400 + "\nand a last seperate one.")
    _wait_marked(page, ["recieve", "seperate"])
    same = page.evaluate("""() => {
      const area = document.querySelector('#soloTextarea');
      const mirror = document.querySelector('.twoi-spell-mirror.on');
      return {
        text: mirror.textContent.replace(/\\u200b$/, '') === area.value,
        height: mirror.scrollHeight === area.scrollHeight,
        width: mirror.clientWidth === area.clientWidth,
      };
    }""")
    assert same == {"text": True, "height": True, "width": True}, same
    # Scrolled to the bottom, the underline for the last word is where that word is drawn.
    page.evaluate("document.querySelector('#soloTextarea').scrollTop = 99999")
    page.wait_for_timeout(100)
    scrolls = page.evaluate("[document.querySelector('#soloTextarea').scrollTop, document.querySelector('.twoi-spell-mirror.on').scrollTop]")
    assert scrolls[0] == scrolls[1] and scrolls[0] > 0, scrolls
    page.screenshot(path="/tmp/spell_underlines.png")


def test_right_click_offers_the_fix_and_undo_takes_it_back(page):
    _write(page, "I will recieve it.")
    _wait_marked(page, ["recieve"])
    _right_click_word(page)
    options = page.locator(".twoi-spell-menu button").all_inner_texts()
    assert options[0] == "receive", options
    assert any(o.startswith("Add") for o in options) and any(o.startswith("Ignore") for o in options)
    page.locator(".twoi-spell-menu button", has_text="receive").first.click()
    assert page.locator("#soloTextarea").input_value() == "I will receive it."
    _wait_marked(page, [])
    page.locator("#soloTextarea").focus()
    page.keyboard.press("Control+z")
    assert page.locator("#soloTextarea").input_value() == "I will recieve it."


def test_a_name_can_be_added_for_good_or_ignored_and_it_survives_a_reload(page):
    _write(page, "Zorbleton walked in. Zorbleton's coat was wet. Then teh rain.")
    _wait_marked(page, ["Zorbleton", "Zorbleton's", "teh"])   # the possessive is one word, and passes once the name is added
    _right_click_word(page, 0)
    page.locator(".twoi-spell-menu button", has_text="Add").click()
    _wait_marked(page, ["teh"])
    assert page.evaluate("JSON.parse(localStorage.getItem('twoi.spell.personal.v1'))") == ["Zorbleton"]
    _right_click_word(page, 0)
    page.locator(".twoi-spell-menu button", has_text="Ignore").click()
    _wait_marked(page, [])


def test_the_panel_lists_every_misspelling_and_fixes_all_of_one_word(page):
    _write(page, "First recieve here.\nSecond recieve there and a seperate one.")
    _wait_marked(page, ["recieve", "recieve", "seperate"])
    page.evaluate("TwoiSpellPanel.open()")
    page.wait_for_selector("#twoiSpelling .twoi-spell-row")
    assert page.locator("#twoiSpelling .twoi-spell-word").all_inner_texts() == ["recieve", "seperate"]
    assert "2 words to look at" in page.locator("#twoiSpelling [role=status]").inner_text()
    page.locator("#twoiSpelling .twoi-spell-row").first.locator("button", has_text="receive").click()
    page.wait_for_function("document.querySelector('#soloTextarea').value.includes('Second receive')")
    assert page.locator("#soloTextarea").input_value() == "First receive here.\nSecond receive there and a seperate one."
    page.wait_for_function("document.querySelectorAll('#twoiSpelling .twoi-spell-row').length === 1")
    page.locator("#twoiSpelling .twoi-spell-row button", has_text="separate").click()
    page.wait_for_function("document.querySelector('#twoiSpelling [role=status]').textContent.startsWith('No misspelled')")


def test_it_is_in_the_references_menu(page):
    assert "Check spelling" in page.evaluate("document.body.innerHTML")


def test_the_live_writing_surface_is_underlined_too_and_fixable(page):
    _write(page, "A recieve on the live page.\nAnd teh second line.")
    page.evaluate("twoiRichSurface.set(true)")
    page.wait_for_function("CSS.highlights.has('twoi-misspelled') && CSS.highlights.get('twoi-misspelled').size === 2", timeout=8000)
    words = page.evaluate("[...CSS.highlights.get('twoi-misspelled')].map(r => r.toString())")
    assert words == ["recieve", "teh"], words
    box = page.evaluate("""() => {
      const r = [...CSS.highlights.get('twoi-misspelled')][0].getBoundingClientRect();
      return {x: r.x + r.width / 2, y: r.y + r.height / 2};
    }""")
    page.mouse.click(box["x"], box["y"], button="right")
    page.wait_for_selector(".twoi-spell-menu")
    page.locator(".twoi-spell-menu button", has_text="receive").first.click()
    page.wait_for_function("committed[0] === 'A receive on the live page.'", timeout=5000)
    page.wait_for_function("CSS.highlights.get('twoi-misspelled').size === 1", timeout=8000)


def test_a_long_manuscript_stays_responsive(page):
    paragraph = "The writer sat at the typewriter and wrote a long chapter about the moon and the sea. "
    page.evaluate("(t) => { const a = document.querySelector('#soloTextarea'); a.value = t; a.dispatchEvent(new Event('input', {bubbles: true})); }",
                  paragraph * 1500 + "one recieve at the end")
    _wait_marked(page, ["recieve"])
    started = time.time()
    page.locator("#soloTextarea").click()
    page.keyboard.press("Control+End")
    for letter in " xyz teh ":
        page.keyboard.press(letter if letter != " " else "Space")
    elapsed = time.time() - started
    assert elapsed < 6, f"typing into a 20,000-word manuscript took {elapsed:.1f}s"
    _wait_marked(page, ["recieve", "xyz", "teh"])
