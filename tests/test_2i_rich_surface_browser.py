"""The live writing surface, driven in real Chromium.

This is the test that matters for "bold this word": it types into the actual
page, selects actual text, clicks the actual button, and then checks three
things every time -- what the writer sees, what the model holds, and that the
words themselves were not altered.

No server, account, network or GitHub Actions. Opens 2i straight from disk,
the way Josie does.
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
        except Exception as exc:  # pragma: no cover - environment guard
            pytest.skip(f"Chromium unavailable: {exc}")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.route(
            "**/*",
            lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort(),
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(PAGE.as_uri())
        page.wait_for_function(
            "typeof initializing !== 'undefined' && !initializing && !!window.twoiRichSurface",
            timeout=20000,
        )
        yield page
        assert not errors, errors
        browser.close()


def _type(page, text):
    """Write text through the plain surface, then turn formatting on."""
    page.locator("#soloTextarea").click()
    page.keyboard.press("Control+a")
    page.keyboard.insert_text(text)
    page.locator("#twoiRichToggle").click()
    page.wait_for_selector("#twoiRichSurface p")


def _select(page, index, start, end):
    page.evaluate(
        """([index,start,end]) => window.twoiRichSurface.node
             .querySelectorAll('p')[index] && (() => {
               const p = window.twoiRichSurface.node.querySelectorAll('p')[index];
               const walk = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
               const spots = [];
               let node, total = 0;
               while ((node = walk.nextNode())) { spots.push([node, total, total + node.nodeValue.length]); total += node.nodeValue.length; }
               const at = pos => { for (const [n,a,b] of spots) if (pos <= b) return [n, pos - a]; return [p, 0]; };
               const [sn,so] = at(start), [en,eo] = at(end);
               const range = document.createRange();
               range.setStart(sn, so); range.setEnd(en, eo);
               const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
               document.dispatchEvent(new Event('selectionchange'));
             })()""",
        [index, start, end],
    )


def _runs(page, index=0):
    return page.evaluate(
        "index => (manuscriptFormat.inline||[]).filter(r=>r.index===index).flatMap(r=>r.runs)", index
    )


def test_toggle_carries_the_words_both_ways(page):
    _type(page, "First paragraph.\nSecond paragraph.")
    assert page.locator("#twoiRichSurface").is_visible()
    assert not page.locator("#soloTextarea").is_visible()
    assert page.locator("#twoiRichSurface p").count() == 2
    assert page.inner_text("#twoiRichSurface").strip().startswith("First paragraph.")
    page.locator("#twoiRichToggle").click()
    assert page.locator("#soloTextarea").is_visible()
    assert page.input_value("#soloTextarea") == "First paragraph.\nSecond paragraph."
    assert page.evaluate("committed.join('\\n')") == "First paragraph.\nSecond paragraph."


def test_bold_one_word_and_leave_the_words_alone(page):
    _type(page, "The quick brown fox")
    _select(page, 0, 4, 9)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    assert _runs(page) == [{"start": 4, "end": 9, "bold": True}]
    assert page.evaluate("committed[0]") == "The quick brown fox", "the text itself must not change"
    assert page.locator("#twoiRichSurface p span[style*='font-weight']").inner_text() == "quick"
    weight = page.evaluate(
        "getComputedStyle(document.querySelector('#twoiRichSurface p span')).fontWeight"
    )
    assert weight in ("700", "bold"), weight


def test_the_button_lights_up_for_the_selection(page):
    _type(page, "The quick brown fox")
    _select(page, 0, 4, 9)
    bold = page.locator("#twoiFormatBar button[aria-label^='Bold']")
    bold.click()
    _select(page, 0, 4, 9)
    assert bold.get_attribute("aria-pressed") == "true"
    _select(page, 0, 10, 15)
    assert bold.get_attribute("aria-pressed") == "false"


def test_bold_on_a_partly_bold_selection_bolds_all_of_it(page):
    _type(page, "abcdefghij")
    _select(page, 0, 0, 4)
    bold = page.locator("#twoiFormatBar button[aria-label^='Bold']")
    bold.click()
    _select(page, 0, 0, 8)
    bold.click()
    assert _runs(page) == [{"start": 0, "end": 8, "bold": True}]


def test_ctrl_b_i_u_reach_the_manuscript(page):
    _type(page, "shortcut text")
    for combo, mark in (("Control+b", "bold"), ("Control+i", "italic"), ("Control+u", "underline")):
        _select(page, 0, 0, 8)
        page.keyboard.press(combo)
        assert any(r.get(mark) for r in _runs(page)), combo
    assert page.evaluate("committed[0]") == "shortcut text"


def test_typing_inside_a_bold_phrase_keeps_it_bold(page):
    _type(page, "The quick fox")
    _select(page, 0, 4, 9)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    _select(page, 0, 7, 7)
    page.keyboard.insert_text("ii")
    page.wait_for_function("committed[0]==='The quiiick fox'")
    runs = _runs(page)
    assert runs and runs[0]["bold"] is True
    assert runs[0]["start"] == 4 and runs[0]["end"] == 11, runs


def test_formatting_survives_turning_the_surface_off_and_on(page):
    _type(page, "keep this bold")
    _select(page, 0, 10, 14)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    before = _runs(page)
    page.locator("#twoiRichToggle").click()
    assert page.input_value("#soloTextarea") == "keep this bold"
    page.locator("#twoiRichToggle").click()
    page.wait_for_selector("#twoiRichSurface p")
    assert _runs(page) == before
    assert page.locator("#twoiRichSurface p span[style*='font-weight']").inner_text() == "bold"


def test_undo_takes_the_formatting_back_off(page):
    _type(page, "undo this")
    _select(page, 0, 0, 4)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    assert _runs(page)
    page.locator("#twoiRichSurface").click()
    page.keyboard.press("Control+z")
    assert _runs(page) == []
    assert page.evaluate("committed[0]") == "undo this", "undo must not take words with it"


def test_a_locked_paragraph_refuses_formatting(page):
    _type(page, "locked paragraph")
    page.evaluate("lockedLines.add(0); window.twoiRichSurface.refresh()")
    _select(page, 0, 0, 6)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    assert _runs(page) == []
    assert page.evaluate(
        "document.querySelector('#twoiRichSurface p').getAttribute('contenteditable')"
    ) == "false"


def test_colour_size_and_font_are_stored_and_shown(page):
    _type(page, "coloured text")
    _select(page, 0, 0, 8)
    page.evaluate("window.twoiRichSurface.apply({color:'#8b0000',size:18,font:'Georgia'})")
    runs = _runs(page)
    assert runs == [{"start": 0, "end": 8, "font": "Georgia", "size": 18, "color": "#8b0000"}], runs
    style = page.evaluate("document.querySelector('#twoiRichSurface p span').getAttribute('style')")
    assert "color" in style and "18pt" in style and "Georgia" in style


def test_clear_removes_formatting_but_not_text(page):
    _type(page, "formatted words here")
    _select(page, 0, 0, 9)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    _select(page, 0, 0, 20)
    page.locator("#twoiFormatBar button[aria-label^='Remove all formatting']").click()
    assert _runs(page) == []
    assert page.evaluate("committed[0]") == "formatted words here"


def test_paste_brings_the_words_without_foreign_markup(page):
    _type(page, "start ")
    page.locator("#twoiRichSurface").click()
    page.evaluate("""() => {
      const p = document.querySelector('#twoiRichSurface p');
      const walk = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
      const node = walk.nextNode();
      const range = document.createRange();
      range.setStart(node, node.nodeValue.length); range.collapse(true);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
    }""")
    page.evaluate("""() => {
      const data = new DataTransfer();
      data.setData('text/plain', 'pasted');
      data.setData('text/html', '<b onclick="alert(1)">pasted</b>');
      document.querySelector('#twoiRichSurface').dispatchEvent(
        new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true}));
    }""")
    page.wait_for_function("committed[0].includes('pasted')")
    assert page.evaluate("document.querySelector('#twoiRichSurface').innerHTML.includes('onclick')") is False
    assert _runs(page) == []


def test_insert_date_puts_text_in_the_manuscript(page):
    _type(page, "dated: ")
    page.locator("#twoiRichSurface").click()
    page.evaluate("window.twoiRichSurface.insert('2026-11-21')")
    page.wait_for_function("committed[0].includes('2026-11-21')")


def test_collab_mode_stands_the_surface_down_and_write_brings_it_back(page):
    _type(page, "collab test")
    assert page.evaluate("window.twoiRichSurface.active()") is True
    page.locator("#modeBadge").click()
    assert page.evaluate("coWriting") is True
    assert page.evaluate("window.twoiRichSurface.active()") is False
    assert not page.locator("#twoiRichSurface").is_visible()
    page.locator("#modeBadge").click()
    assert page.evaluate("window.twoiRichSurface.active()") is True


def test_formatted_export_carries_the_runs(page):
    _type(page, "exported bold here")
    _select(page, 0, 9, 13)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    html = page.evaluate(
        "TwoiFormatCore.exportHtml('T', committed.slice(), syncManuscriptFormat(), chapters)"
    )
    assert "font-weight:bold" in html
    assert ">bold<" in html
    assert "exported" in html


def test_word_count_still_follows_the_live_surface(page):
    _type(page, "one two three four five")
    page.locator("#twoiRichSurface").click()
    page.evaluate("window.twoiRichSurface.insert(' six')")
    page.wait_for_function("document.getElementById('wordCount').textContent.startsWith('6')")


# --------------------------------------------------------------------------
# Integration: the parts of 2i that were written against the textarea and must
# keep working while the live surface is the thing being typed into.
# --------------------------------------------------------------------------

def test_find_and_replace_still_works_with_the_surface_on(page):
    _type(page, "the cat sat\nthe cat is here")
    _select(page, 0, 4, 7)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    page.evaluate("openModal('frModalBackdrop')")
    page.locator("#frFind").fill("cat")
    page.locator("#frReplace").fill("fox")
    page.locator("#frReplaceAllBtn").click()
    assert page.evaluate("committed.join('|')") == "the fox sat|the fox is here"
    assert "2 replacement" in page.inner_text("#frResult")
    page.evaluate("closeModal('frModalBackdrop')")
    assert page.inner_text("#twoiRichSurface").find("fox") >= 0


def test_the_paragraph_dialog_acts_on_the_paragraph_the_caret_is_in(page):
    _type(page, "first para\nsecond para\nthird para")
    _select(page, 1, 3, 3)
    page.evaluate("document.dispatchEvent(new Event('selectionchange'))")
    assert page.evaluate("soloTextarea.selectionStart") == len("first para\n") + 3


def test_word_and_character_count_match_the_live_surface(page):
    _type(page, "one two three")
    page.locator("#twoiRichSurface").click()
    page.evaluate("window.twoiRichSurface.insert(' four')")
    page.wait_for_function("committed[0]==='one two three four'")
    page.wait_for_function("document.getElementById('wordCount').textContent.startsWith('4')")


def test_formatting_survives_a_reload_from_browser_recovery(page):
    _type(page, "recovered bold text")
    _select(page, 0, 10, 14)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    runs_before = _runs(page)
    assert runs_before
    page.evaluate("writeRecovery()")
    page.reload()
    page.wait_for_function(
        "typeof initializing !== 'undefined' && !initializing && !!window.twoiRichSurface",
        timeout=20000,
    )
    page.wait_for_function("committed.join('\\n').includes('recovered bold text')", timeout=10000)
    assert _runs(page) == runs_before, "a reload must bring the formatting back with the words"
    page.locator("#twoiRichToggle").click()
    page.wait_for_selector("#twoiRichSurface p")
    assert page.locator("#twoiRichSurface p span[style*='font-weight']").inner_text() == "bold"


def test_a_second_paragraph_keeps_its_own_formatting(page):
    _type(page, "alpha line\nbeta line")
    _select(page, 1, 0, 4)
    page.locator("#twoiFormatBar button[aria-label^='Italic']").click()
    assert _runs(page, 0) == []
    assert _runs(page, 1) == [{"start": 0, "end": 4, "italic": True}]
    page.locator("#twoiRichSurface").click()
    page.evaluate("""() => {
      const p = document.querySelectorAll('#twoiRichSurface p')[0];
      const node = document.createTreeWalker(p, NodeFilter.SHOW_TEXT).nextNode();
      const range = document.createRange();
      range.setStart(node, 0); range.collapse(true);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
    }""")
    page.keyboard.insert_text("new ")
    page.wait_for_function("committed[0]==='new alpha line'")
    assert _runs(page, 1) == [{"start": 0, "end": 4, "italic": True}], "editing one paragraph must not disturb another"


def test_enter_makes_a_new_paragraph_and_keeps_the_rest_formatted(page):
    _type(page, "bold head\ntail")
    _select(page, 0, 0, 4)
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    page.evaluate("""() => {
      const p = document.querySelectorAll('#twoiRichSurface p')[1];
      const node = document.createTreeWalker(p, NodeFilter.SHOW_TEXT).nextNode();
      const range = document.createRange();
      range.setStart(node, node.nodeValue.length); range.collapse(true);
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
    }""")
    page.keyboard.press("Enter")
    page.keyboard.insert_text("third")
    page.wait_for_function("committed.length===3 && committed[2]==='third'")
    assert _runs(page, 0) == [{"start": 0, "end": 4, "bold": True}]
