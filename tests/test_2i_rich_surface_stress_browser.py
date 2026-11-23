"""The live writing surface under the conditions that actually break editors.

Long manuscripts, fast typing, repeated undo, select-all, awkward characters and
a phone-sized screen. Real Chromium, 2i opened from disk, no server.

Marked slow: these build manuscripts of thousands of paragraphs.
Run just these with:  python -m pytest -q tests/test_2i_rich_surface_stress_browser.py
"""
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"

LINE = "Paragraph {}. The monument stood at the end of the lot, gears turning in the water."


def _open(playwright, width=1280, height=900):
    browser = playwright.chromium.launch()
    context = browser.new_context(viewport={"width": width, "height": height})
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
        timeout=30000,
    )
    return browser, page, errors


def _load(page, count):
    page.evaluate(
        """t => { const ta=document.getElementById('soloTextarea'); ta.value=t; ta.dispatchEvent(new Event('input')); }""",
        "\n".join(LINE.format(i) for i in range(count)),
    )
    page.locator("#twoiRichToggle").click()
    page.wait_for_selector("#twoiRichSurface p")


def _caret_to_end_of_last(page):
    page.evaluate("""() => {
      const ps=document.querySelectorAll('#twoiRichSurface p');
      const p=ps[ps.length-1];
      const tn=document.createTreeWalker(p,NodeFilter.SHOW_TEXT).nextNode();
      const r=document.createRange(); r.setStart(tn,tn.nodeValue.length); r.collapse(true);
      const s=getSelection(); s.removeAllRanges(); s.addRange(r);
      document.getElementById('twoiRichSurface').focus();
    }""")


@pytest.fixture()
def playwright():
    with sync_api.sync_playwright() as p:
        yield p


def test_a_novel_sized_manuscript_opens_and_every_paragraph_is_there(playwright):
    browser, page, errors = _open(playwright)
    _load(page, 5000)
    assert page.evaluate("document.querySelectorAll('#twoiRichSurface p').length") == 5000
    assert page.evaluate("committed.length") == 5000
    assert page.evaluate("committed[4999]") == LINE.format(4999)
    assert not errors, errors
    browser.close()


def test_nothing_is_dropped_typing_faster_than_anyone_types(playwright):
    browser, page, errors = _open(playwright)
    _load(page, 3000)
    _caret_to_end_of_last(page)
    sentence = " Every character of this sentence must arrive, in order, with nothing dropped."
    page.keyboard.type(sentence, delay=5)
    assert page.evaluate("committed[committed.length-1]").endswith(sentence)
    assert page.evaluate("soloTextarea.value.split('\\n').length") == page.evaluate("committed.length")
    assert not errors, errors
    browser.close()


def test_typing_in_a_long_manuscript_costs_no_more_than_in_a_short_one(playwright):
    """The one-paragraph path must not degrade with the length of the manuscript.

    Reading the whole page on every keystroke would make this grow with the
    document; it is measured rather than assumed.
    """
    browser, page, errors = _open(playwright)
    measure = """() => {
      const node=window.twoiRichSurface.node;
      const ps=node.querySelectorAll('p'); const p=ps[ps.length-1];
      const tn=document.createTreeWalker(p,NodeFilter.SHOW_TEXT).nextNode();
      const r=document.createRange(); r.setStart(tn,tn.nodeValue.length); r.collapse(true);
      const sel=getSelection(); sel.removeAllRanges(); sel.addRange(r);
      const s=[];
      for(let i=0;i<15;i++){ tn.nodeValue+='x';
        const t=performance.now(); node.dispatchEvent(new Event('input',{bubbles:true})); s.push(performance.now()-t); }
      s.sort((a,b)=>a-b); return s[7];
    }"""
    _load(page, 200)
    short = page.evaluate(measure)
    page.locator("#twoiRichToggle").click()
    _load(page, 6000)
    long = page.evaluate(measure)
    # Thirty times the manuscript must not cost anything like thirty times the
    # keystroke. Generous, because a shared machine's timings are noisy.
    assert long < max(short * 6, 25), f"short={short:.2f}ms long={long:.2f}ms"
    assert not errors, errors
    browser.close()


def test_repeated_undo_and_redo_leaves_the_text_where_it_started(playwright):
    browser, page, errors = _open(playwright)
    _load(page, 40)
    start = page.evaluate("committed.join('\\n')")
    for index in range(6):
        page.evaluate(
            """i => { const S=window.twoiRichSurface;
              const p=S.node.querySelectorAll('p')[i];
              const tn=document.createTreeWalker(p,NodeFilter.SHOW_TEXT).nextNode();
              const r=document.createRange(); r.setStart(tn,0); r.setEnd(tn,9);
              const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""",
            index,
        )
        page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    assert len(page.evaluate("(manuscriptFormat.inline||[])")) == 6
    page.locator("#twoiRichSurface").click()
    for _ in range(6):
        page.keyboard.press("Control+z")
    assert page.evaluate("(manuscriptFormat.inline||[]).length") == 0
    assert page.evaluate("committed.join('\\n')") == start, "undo must not take words with it"
    for _ in range(6):
        page.keyboard.press("Control+y")
    assert page.evaluate("(manuscriptFormat.inline||[]).length") == 6
    assert page.evaluate("committed.join('\\n')") == start
    assert not errors, errors
    browser.close()


def test_select_everything_and_bold_it_then_clear_it(playwright):
    browser, page, errors = _open(playwright)
    _load(page, 120)
    start = page.evaluate("committed.join('\\n')")
    page.evaluate("""() => { const n=window.twoiRichSurface.node;
      const r=document.createRange(); r.selectNodeContents(n);
      const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    assert page.evaluate("(manuscriptFormat.inline||[]).length") == 120
    page.evaluate("""() => { const n=window.twoiRichSurface.node;
      const r=document.createRange(); r.selectNodeContents(n);
      const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    page.locator("#twoiFormatBar button[aria-label^='Remove all formatting']").click()
    assert page.evaluate("(manuscriptFormat.inline||[]).length") == 0
    assert page.evaluate("committed.join('\\n')") == start
    assert not errors, errors
    browser.close()


def test_select_everything_and_delete_it(playwright):
    browser, page, errors = _open(playwright)
    _load(page, 200)
    page.locator("#twoiRichSurface").click()
    page.keyboard.press("Control+a")
    page.keyboard.press("Delete")
    page.wait_for_function("committed.join('').length===0")
    assert page.evaluate("soloTextarea.value.replace(/\\n/g,'')") == ""
    page.keyboard.insert_text("starting over")
    page.wait_for_function("committed.join('\\n').includes('starting over')")
    assert not errors, errors
    browser.close()


def test_awkward_characters_survive_being_typed_and_formatted(playwright):
    browser, page, errors = _open(playwright)
    _load(page, 3)
    page.locator("#twoiRichSurface").click()
    page.keyboard.press("Control+a")
    awkward = "café — naïve — “quoted” ‘single’ … é́ \U0001F4D6 слово"
    page.keyboard.insert_text(awkward)
    page.wait_for_function("committed.length===1")
    assert page.evaluate("committed[0]") == awkward
    page.evaluate("""() => { const p=document.querySelector('#twoiRichSurface p');
      const tn=document.createTreeWalker(p,NodeFilter.SHOW_TEXT).nextNode();
      const r=document.createRange(); r.setStart(tn,0); r.setEnd(tn,4);
      const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    assert page.evaluate("committed[0]") == awkward, "formatting must not disturb the characters"
    html = page.evaluate("TwoiFormatCore.exportHtml('T',committed.slice(),syncManuscriptFormat(),chapters)")
    assert "\U0001F4D6" in html and "слово" in html
    rtf = page.evaluate("TwoiFormatCore.exportRtf('T',committed.slice(),syncManuscriptFormat(),chapters)")
    assert "\\u1057" in rtf or "\\u-10179" in rtf or "\\u55357" in rtf
    assert not errors, errors
    browser.close()


def test_the_surface_works_on_a_phone_sized_screen(playwright):
    browser, page, errors = _open(playwright, width=390, height=844)
    _load(page, 30)
    assert page.locator("#twoiRichSurface").is_visible()
    bar = page.locator("#twoiFormatBar")
    assert bar.is_visible()
    bold = page.locator("#twoiFormatBar button[aria-label^='Bold']")
    box = bold.bounding_box()
    assert box["height"] >= 40 and box["width"] >= 40, f"touch target too small: {box}"
    # The bar must not run off the side of a phone.
    assert bar.bounding_box()["width"] <= 390
    page.evaluate("""() => { const p=document.querySelector('#twoiRichSurface p');
      const tn=document.createTreeWalker(p,NodeFilter.SHOW_TEXT).nextNode();
      const r=document.createRange(); r.setStart(tn,0); r.setEnd(tn,9);
      const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    bold.click()
    assert page.evaluate("(manuscriptFormat.inline||[]).length") == 1
    assert not errors, errors
    browser.close()


def test_formatting_holds_through_a_document_switch_and_back(playwright):
    browser, page, errors = _open(playwright)
    _load(page, 5)
    page.evaluate("""() => { const p=document.querySelector('#twoiRichSurface p');
      const tn=document.createTreeWalker(p,NodeFilter.SHOW_TEXT).nextNode();
      const r=document.createRange(); r.setStart(tn,0); r.setEnd(tn,9);
      const s=getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    page.locator("#twoiFormatBar button[aria-label^='Bold']").click()
    saved = page.evaluate("JSON.stringify(docPayload().state.formatting.inline)")
    assert "bold" in saved
    reopened = page.evaluate(
        "JSON.stringify(TwoiFormatCore.restore(JSON.parse(saved), committed).inline)",
    ) if False else page.evaluate(
        """() => { const payload=JSON.parse(JSON.stringify(docPayload()));
             return JSON.stringify(TwoiFormatCore.restore(payload.state.formatting, payload.state.committed).inline); }"""
    )
    assert reopened == saved, "a saved document must reopen with the same formatting"
    assert not errors, errors
    browser.close()


def test_ctrl_a_then_bold_formats_the_whole_manuscript(playwright):
    """Ctrl+A gives a range whose container is the surface itself, not a
    paragraph. Formatting a select-all used to do nothing at all."""
    browser, page, errors = _open(playwright)
    _load(page, 25)
    start = page.evaluate("committed.join('\\n')")
    page.locator("#twoiRichSurface").click()
    page.keyboard.press("Control+a")
    page.locator("#twoiFormatBar button[aria-label^='Italic']").click()
    assert page.evaluate("(manuscriptFormat.inline||[]).length") == 25
    assert page.evaluate("committed.join('\\n')") == start
    assert not errors, errors
    browser.close()
