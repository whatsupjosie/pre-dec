"""2i's offline dictionary and thesaurus, in real Chromium, opened from disk.

No server and no network: the test aborts every request that is not a file://
read, so if anything tried to reach the internet these tests would fail.
"""
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
            "typeof initializing !== 'undefined' && !initializing && !!window.TwoiLanguage",
            timeout=20000,
        )
        yield page
        assert not errors, errors
        # Nothing the dictionary does may touch the network.
        assert not [u for u in offsite if "language" in u or "dict-" in u], offsite
        browser.close()


def _write(page, text):
    page.locator("#soloTextarea").click()
    page.keyboard.press("Control+a")
    page.keyboard.insert_text(text)


def test_nothing_is_loaded_until_a_word_is_looked_up(page):
    assert page.evaluate("TwoiLanguage.loadedLetters().length") == 0
    assert page.evaluate("TwoiLanguage.size()") == 0


def test_a_word_is_defined_offline(page):
    result = page.evaluate("async () => await TwoiLanguage.lookup('monument')")
    assert result["word"] == "monument"
    assert "commemorate" in result["senses"][0]["definition"]
    assert "memorial" in result["senses"][0]["synonyms"]
    assert page.evaluate("TwoiLanguage.loadedLetters()") == ["m"]


def test_only_the_letter_needed_is_fetched(page):
    page.evaluate("async () => await TwoiLanguage.lookup('gear')")
    assert page.evaluate("TwoiLanguage.loadedLetters()") == ["g"]
    page.evaluate("async () => await TwoiLanguage.lookup('water')")
    assert sorted(page.evaluate("TwoiLanguage.loadedLetters()")) == ["g", "w"]


def test_the_panel_opens_on_the_word_the_caret_is_in(page):
    _write(page, "The monument stood at the end of the lot.")
    page.evaluate("""() => {
      const t = document.getElementById('soloTextarea');
      t.focus(); t.setSelectionRange(8, 8);   // inside "monument"
    }""")
    page.evaluate("TwoiDictionary.open()")
    page.wait_for_selector("#twoiDictionary[open]")
    page.wait_for_function("document.querySelector('#twoiDictionaryBody li')")
    assert page.input_value("#twoiDictionary input[type=search]") == "monument"
    assert "commemorate" in page.inner_text("#twoiDictionaryBody")
    assert "Princeton" in page.inner_text(".twoi-dictionary-credit")


def test_antonyms_are_shown(page):
    page.evaluate("TwoiDictionary.open('good')")
    page.wait_for_selector("#twoiDictionary[open]")
    page.wait_for_function("document.querySelector('.twoi-dictionary-antonyms')")
    text = page.inner_text(".twoi-dictionary-antonyms")
    assert "evil" in text or "bad" in text


def test_a_synonym_can_be_put_into_the_manuscript_but_only_when_asked(page):
    _write(page, "The monument stood there.")
    page.evaluate("""() => {
      const t = document.getElementById('soloTextarea');
      t.focus(); t.setSelectionRange(4, 12);   // select "monument"
    }""")
    page.evaluate("TwoiDictionary.open()")
    page.wait_for_function("document.querySelector('.twoi-dictionary-use')")
    before = page.input_value("#soloTextarea")
    assert before == "The monument stood there."
    page.locator(".twoi-dictionary-chip", has_text="memorial").locator(
        ".twoi-dictionary-use"
    ).first.click()
    page.wait_for_function("!document.getElementById('twoiDictionary')")
    assert page.input_value("#soloTextarea") == "The memorial stood there."
    assert page.evaluate("committed.join('\\n')") == "The memorial stood there."


def test_opening_the_panel_never_changes_the_manuscript(page):
    _write(page, "The monument stood there.")
    page.evaluate("TwoiDictionary.open('monument')")
    page.wait_for_function("document.querySelector('#twoiDictionaryBody li')")
    page.locator(".twoi-dictionary-word").first.click()
    page.wait_for_timeout(300)
    page.keyboard.press("Escape")
    assert page.input_value("#soloTextarea") == "The monument stood there."


def test_an_invented_name_says_so_rather_than_calling_it_wrong(page):
    page.evaluate("TwoiDictionary.open('Purfluous')")
    page.wait_for_selector("#twoiDictionary[open]")
    page.wait_for_function(
        "document.querySelector('#twoiDictionary [role=status]').textContent.includes('not in the dictionary')"
    )
    status = page.inner_text("#twoiDictionary [role=status]")
    assert "not the same as being misspelled" in status


def test_a_clicked_synonym_looks_itself_up(page):
    page.evaluate("TwoiDictionary.open('monument')")
    page.wait_for_function("document.querySelector('.twoi-dictionary-word')")
    page.locator(".twoi-dictionary-word", has_text="memorial").first.click()
    page.wait_for_function(
        "document.querySelector('#twoiDictionary input[type=search]').value === 'memorial'"
    )
    assert "memorial" in page.inner_text("#twoiDictionary [role=status]")


def test_use_replaces_the_word_on_the_formatting_surface_too(page):
    """With the live surface on, soloTextarea is hidden and the selection lives
    in the contenteditable. The synonym must replace the word, not land beside it."""
    _write(page, "The monument stood there.")
    page.locator("#twoiRichToggle").click()
    page.wait_for_selector("#twoiRichSurface p")
    page.evaluate("""() => {
      const p = document.querySelector('#twoiRichSurface p');
      const node = document.createTreeWalker(p, NodeFilter.SHOW_TEXT).nextNode();
      const r = document.createRange(); r.setStart(node, 4); r.setEnd(node, 12);
      const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    }""")
    page.evaluate("TwoiDictionary.open()")
    page.wait_for_function("document.querySelector('.twoi-dictionary-use')")
    assert page.input_value("#twoiDictionary input[type=search]") == "monument"
    page.locator(".twoi-dictionary-chip", has_text="memorial").locator(
        ".twoi-dictionary-use"
    ).first.click()
    page.wait_for_function("!document.getElementById('twoiDictionary')")
    page.wait_for_function("committed[0] === 'The memorial stood there.'")
    assert page.evaluate("committed[0]") == "The memorial stood there."


def test_the_caret_alone_is_enough_on_the_formatting_surface(page):
    _write(page, "The monument stood there.")
    page.locator("#twoiRichToggle").click()
    page.wait_for_selector("#twoiRichSurface p")
    page.evaluate("""() => {
      const p = document.querySelector('#twoiRichSurface p');
      const node = document.createTreeWalker(p, NodeFilter.SHOW_TEXT).nextNode();
      const r = document.createRange(); r.setStart(node, 8); r.collapse(true);
      const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    }""")
    page.evaluate("TwoiDictionary.open()")
    page.wait_for_function("document.querySelector('#twoiDictionaryBody li')")
    assert page.input_value("#twoiDictionary input[type=search]") == "monument"
