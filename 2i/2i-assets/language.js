/* 2i's offline dictionary and thesaurus.
 *
 * Josie, 2026-11-21: "Writing is the #1 thing you can do easiest offline. So
 * goddamn right we have to have a spell check. And a dictionary. And a
 * thesaurus."
 *
 * Data: WordNet 3.1, Princeton University, built into 2i/2i-assets/language/
 * by tools/language/build_language_data.mjs. 147,478 words, 207,235 senses.
 * Princeton's licence allows commercial use free of charge provided the
 * project is credited; the credit is shown in the panel and the licence is
 * kept beside the data. Do not remove either.
 *
 * It loads one letter at a time, and only on the first word that needs it,
 * because the whole thing is 18 MB and Josie works on two or three phones and
 * a laptop on bad data. Looking up "monument" costs the "m" file and nothing
 * else.
 *
 * It loads with a <script> tag rather than fetch(), deliberately: a browser
 * refuses fetch() on a file:// URL, and 2i has to work opened straight from
 * disk, with no server and no network at all.
 */
(function installLanguage(){
  'use strict';

  // Maps, never plain objects. WordNet contains "constructor", "toString" and
  // "__proto__"; on a plain object those collide with Object.prototype and a
  // lookup for "constructor" would return a function instead of a definition.
  const entries = new Map();          // word -> {senses, antonyms}
  const loaded  = new Map();          // letter -> Promise

  // The shards call this as they load.
  window.TwoiLanguageShard = function(letter, text){
    for (const line of String(text).split('\n')) {
      if (!line) continue;
      const [word, body, antonyms] = line.split('\t');
      if (!word || !body) continue;
      entries.set(word, {
        senses: body.split('|').map(part => {
          const [pos, definition, synonyms] = part.split('^');
          return {
            pos,
            definition: definition || '',
            synonyms: synonyms ? synonyms.split(',').filter(Boolean) : []
          };
        }),
        antonyms: antonyms ? antonyms.split(',').filter(Boolean) : []
      });
    }
  };

  const base = (document.currentScript && document.currentScript.src
    ? document.currentScript.src.replace(/[^/]*$/, '')
    : '2i-assets/') + 'language/';

  function shardFor(word){
    const first = word[0];
    return /^[a-z]$/.test(first) ? first : '_';
  }
  function load(letter){
    if (loaded.has(letter)) return loaded.get(letter);
    const promise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = base + 'dict-' + (letter === '_' ? 'other' : letter) + '.js';
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => {
        script.remove();
        loaded.delete(letter);       // a failed load must not poison later tries
        reject(Error('The dictionary for "' + letter + '" could not be opened.'));
      };
      document.head.append(script);
    });
    loaded.set(letter, promise);
    return promise;
  }

  // Irregular forms. WordNet ships these as .exc files; the npm package does
  // not include them, so the common ones are carried here. Every target is
  // checked against the built data by tests/test_2i_language_node.js -- an
  // entry pointing at a word WordNet does not have is a failing test, not a
  // silent dead end.
  const IRREGULAR = new Map(Object.entries({
    // verbs
    was:'be', were:'be', been:'be', am:'be', is:'be', are:'be',
    had:'have', has:'have', did:'do', does:'do', done:'do',
    went:'go', gone:'go', said:'say', made:'make', knew:'know', known:'know',
    took:'take', taken:'take', came:'come', saw:'see', seen:'see',
    got:'get', gotten:'get', gave:'give', given:'give', found:'find',
    thought:'think', told:'tell', became:'become', left:'leave', felt:'feel',
    brought:'bring', began:'begin', begun:'begin', kept:'keep', held:'hold',
    wrote:'write', written:'write', stood:'stand', heard:'hear', let:'let',
    meant:'mean', met:'meet', ran:'run', paid:'pay', sat:'sit', spoke:'speak',
    spoken:'speak', lay:'lie', led:'lead', grew:'grow', grown:'grow',
    lost:'lose', fell:'fall', fallen:'fall', sent:'send', built:'build',
    understood:'understand', drew:'draw', drawn:'draw', broke:'break',
    broken:'break', spent:'spend', cut:'cut', rose:'rise', risen:'rise',
    drove:'drive', driven:'drive', bought:'buy', wore:'wear', worn:'wear',
    chose:'choose', chosen:'choose', ate:'eat', eaten:'eat', flew:'fly',
    flown:'fly', forgot:'forget', forgotten:'forget',
    threw:'throw', thrown:'throw', sang:'sing', sung:'sing',
    sold:'sell', taught:'teach', caught:'catch', fought:'fight', slept:'sleep',
    swam:'swim', swum:'swim', stole:'steal', stolen:'steal', hid:'hide', hidden:'hide',
    bit:'bite', bitten:'bite', blew:'blow', blown:'blow', froze:'freeze',
    frozen:'freeze', shook:'shake', shaken:'shake', struck:'strike',
    woke:'wake', woken:'wake', wound:'wind', sank:'sink', sunk:'sink',
    // nouns
    children:'child', men:'man', women:'woman', people:'person', feet:'foot',
    teeth:'tooth', geese:'goose', mice:'mouse', lice:'louse', oxen:'ox',
    lives:'life', knives:'knife', wives:'wife', leaves:'leaf', halves:'half',
    wolves:'wolf', thieves:'thief', shelves:'shelf', selves:'self',
    loaves:'loaf', calves:'calf', scarves:'scarf',
    // adjectives and adverbs
    better:'good', best:'good', worse:'bad', worst:'bad',
    further:'far', furthest:'far', farther:'far', farthest:'far',
    more:'many', most:'many', less:'little', least:'little'
  }));

  // WordNet's own detachment rules, the common ones.
  const RULES = [
    [/ies$/, 'y'], [/ches$/, 'ch'], [/shes$/, 'sh'], [/xes$/, 'x'],
    [/zes$/, 'z'], [/sses$/, 'ss'], [/ses$/, 's'], [/ves$/, 'f'],
    [/men$/, 'man'], [/s$/, ''],
    [/ied$/, 'y'], [/ied$/, 'ie'], [/ed$/, 'e'], [/ed$/, ''],
    [/ying$/, 'ie'], [/ing$/, 'e'], [/ing$/, ''],
    [/est$/, ''], [/est$/, 'e'], [/er$/, ''], [/er$/, 'e'],
    [/iest$/, 'y'], [/ier$/, 'y'], [/ly$/, '']
  ];

  // Forms of a word to try, best first. A doubled final consonant before -ing
  // or -ed ("running", "stopped") is undoubled as well.
  function forms(word){
    const list = [word];
    const irregular = IRREGULAR.get(word);
    if (irregular) list.push(irregular);
    for (const [pattern, replacement] of RULES) {
      if (!pattern.test(word)) continue;
      const stem = word.replace(pattern, replacement);
      if (stem.length > 1) list.push(stem);
      const doubled = /^(.*?)([bdfglmnprt])\2$/.exec(stem);
      if (doubled) list.push(doubled[1] + doubled[2]);
    }
    return [...new Set(list)];
  }

  const normalise = raw => String(raw == null ? '' : raw)
    .toLowerCase()
    .replace(/[‘’]/g, "'")
    // Strip punctuation from both ends but keep it inside, so 'monument' and
    // "monument" resolve while don't and o'clock survive intact.
    .replace(/^[^a-z0-9]+|[^a-z0-9]+$/g, '')
    .trim();

  /** Look a word up. Resolves to null when the word is not in WordNet.
   *
   * An exact match wins, but many inflected forms are WordNet headwords in
   * their own right and the entry alone is not what a writer meant. Look up
   * "stopped" and WordNet has it as an adjective, "(of a nose) blocked" --
   * true, and useless to someone who meant the verb. So when a different root
   * form also exists it comes back as `root`, and the panel shows both.
   */
  async function lookup(raw){
    const word = normalise(raw);
    if (!word) return null;
    const candidates = forms(word);
    await Promise.all([...new Set(candidates.map(shardFor))].map(load));
    let result = null;
    for (const form of candidates) {
      const found = entries.get(form);
      if (!found) continue;
      if (!result) { result = {word: form, typed: form !== word ? word : null, ...found, root: null}; continue; }
      if (form !== result.word) { result.root = {word: form, senses: found.senses, antonyms: found.antonyms}; break; }
    }
    return result;
  }

  /** Synonyms for a word, flattened and in sense order, without repeats. */
  async function synonyms(raw){
    const found = await lookup(raw);
    if (!found) return [];
    const seen = new Set(), out = [];
    const senses = found.senses.concat(found.root ? found.root.senses : []);
    for (const sense of senses) for (const synonym of sense.synonyms) {
      const key = synonym.toLowerCase();
      if (key === found.word || seen.has(key)) continue;
      seen.add(key);
      out.push(synonym);
    }
    return out;
  }

  async function antonyms(raw){
    const found = await lookup(raw);
    return found ? found.antonyms.slice() : [];
  }

  window.TwoiLanguage = {
    lookup, synonyms, antonyms, forms, normalise,
    loadedLetters: () => [...loaded.keys()],
    size: () => entries.size,
    credit: 'WordNet 3.1 · Princeton University'
  };
})();
