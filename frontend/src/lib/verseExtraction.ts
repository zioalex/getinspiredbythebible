/**
 * Extracts verse references from text
 * Matches formats like: "John 3:16", "1 John 2:3", "Song of Solomon 1:1", etc.
 * Also supports localized formats: "Giovanni 3:16" (Italian), "1. Mose 1:1" (German),
 * "Плач Иеремии 3:3" (Russian), "耶利米哀歌 3:3" (Chinese), "예레미야 애가 3:3" (Korean),
 * "يوحنا 3:16" (Arabic), "यूहन्ना 3:16" (Hindi), "João 3:16" (Portuguese).
 */

// Note on circular imports: versePatterns.ts imports LOCALIZED_BOOK_TO_ENGLISH
// from this module.  JavaScript ES modules resolve circular imports via live
// bindings, so the static import below is safe: versePatterns.ts only reads
// LOCALIZED_BOOK_TO_ENGLISH at its own module-init time (which runs after
// this module's const is initialised), and extractVerseReferences() is only
// ever called after both modules are fully loaded.
import { createVersePatternGlobal as _createVersePatternGlobal } from "./versePatterns";

/**
 * Maps localized book names (lowercased) to canonical English book names (lowercased).
 * Covers Russian (nominative + genitive), Chinese, and Korean.
 * English and other Western-language names pass through unchanged.
 */
export const LOCALIZED_BOOK_TO_ENGLISH: Record<string, string> = {
  // ── Russian (nominative forms) ───────────────────────────────────────────
  бытие: "genesis",
  исход: "exodus",
  левит: "leviticus",
  числа: "numbers",
  второзаконие: "deuteronomy",
  "иисус навин": "joshua",
  судьи: "judges",
  руфь: "ruth",
  "1 царств": "1 samuel",
  "2 царств": "2 samuel",
  "3 царств": "1 kings",
  "4 царств": "2 kings",
  "1 паралипоменон": "1 chronicles",
  "2 паралипоменон": "2 chronicles",
  ездра: "ezra",
  неемия: "nehemiah",
  есфирь: "esther",
  иов: "job",
  псалтирь: "psalms",
  притчи: "proverbs",
  екклесиаст: "ecclesiastes",
  "песня песней": "song of solomon",
  "песни песней": "song of solomon",
  исаия: "isaiah",
  иеремия: "jeremiah",
  "плач иеремии": "lamentations",
  иезекиль: "ezekiel",
  даниил: "daniel",
  осия: "hosea",
  иоиль: "joel",
  амос: "amos",
  авдий: "obadiah",
  иона: "jonah",
  михей: "micah",
  наум: "nahum",
  аввакум: "habakkuk",
  софония: "zephaniah",
  аггей: "haggai",
  захария: "zechariah",
  малахия: "malachi",
  матфей: "matthew",
  марк: "mark",
  лука: "luke",
  иоанн: "john",
  "деяния апостолов": "acts",
  деяния: "acts",
  римлянам: "romans",
  "1 коринфянам": "1 corinthians",
  "2 коринфянам": "2 corinthians",
  галатам: "galatians",
  ефесянам: "ephesians",
  филиппийцам: "philippians",
  колоссянам: "colossians",
  "1 фессалоникийцам": "1 thessalonians",
  "2 фессалоникийцам": "2 thessalonians",
  "1 тимофею": "1 timothy",
  "2 тимофею": "2 timothy",
  титу: "titus",
  филимону: "philemon",
  евреям: "hebrews",
  иаков: "james",
  "1 петра": "1 peter",
  "2 петра": "2 peter",
  "1 иоанна": "1 john",
  "2 иоанна": "2 john",
  "3 иоанна": "3 john",
  иуда: "jude",
  откровение: "revelation",

  // ── Russian (genitive forms — used after chapter/verse references) ────────
  бытия: "genesis",
  исхода: "exodus",
  левита: "leviticus",
  числ: "numbers",
  второзакония: "deuteronomy",
  руфи: "ruth",
  псалтири: "psalms",
  притч: "proverbs",
  екклесиаста: "ecclesiastes",
  исаии: "isaiah",
  иеремии: "jeremiah",
  иезекиля: "ezekiel",
  даниила: "daniel",
  осии: "hosea",
  иоиля: "joel",
  ионы: "jonah",
  михея: "micah",
  наума: "nahum",
  аввакума: "habakkuk",
  софонии: "zephaniah",
  аггея: "haggai",
  захарии: "zechariah",
  малахии: "malachi",
  матфея: "matthew",
  марка: "mark",
  луки: "luke",
  иоанна: "john",
  деяний: "acts",
  иакова: "james",
  иуды: "jude",
  откровения: "revelation",

  // ── Chinese (中文和合本 CUV) ───────────────────────────────────────────────
  创世记: "genesis",
  出埃及记: "exodus",
  利未记: "leviticus",
  民数记: "numbers",
  申命记: "deuteronomy",
  约书亚记: "joshua",
  士师记: "judges",
  路得记: "ruth",
  撒母耳记上: "1 samuel",
  撒母耳记下: "2 samuel",
  列王纪上: "1 kings",
  列王纪下: "2 kings",
  历代志上: "1 chronicles",
  历代志下: "2 chronicles",
  以斯拉记: "ezra",
  尼希米记: "nehemiah",
  以斯帖记: "esther",
  约伯记: "job",
  诗篇: "psalms",
  箴言: "proverbs",
  传道书: "ecclesiastes",
  雅歌: "song of solomon",
  以赛亚书: "isaiah",
  耶利米书: "jeremiah",
  耶利米哀歌: "lamentations",
  以西结书: "ezekiel",
  但以理书: "daniel",
  何西阿书: "hosea",
  约珥书: "joel",
  阿摩司书: "amos",
  俄巴底亚书: "obadiah",
  约拿书: "jonah",
  弥迦书: "micah",
  那鸿书: "nahum",
  哈巴谷书: "habakkuk",
  西番雅书: "zephaniah",
  哈该书: "haggai",
  撒迦利亚书: "zechariah",
  玛拉基书: "malachi",
  马太福音: "matthew",
  马可福音: "mark",
  路加福音: "luke",
  约翰福音: "john",
  使徒行传: "acts",
  罗马书: "romans",
  哥林多前书: "1 corinthians",
  哥林多后书: "2 corinthians",
  加拉太书: "galatians",
  以弗所书: "ephesians",
  腓立比书: "philippians",
  歌罗西书: "colossians",
  帖撒罗尼迦前书: "1 thessalonians",
  帖撒罗尼迦后书: "2 thessalonians",
  提摩太前书: "1 timothy",
  提摩太后书: "2 timothy",
  提多书: "titus",
  腓利门书: "philemon",
  希伯来书: "hebrews",
  雅各书: "james",
  彼得前书: "1 peter",
  彼得后书: "2 peter",
  约翰一书: "1 john",
  约翰二书: "2 john",
  约翰三书: "3 john",
  犹大书: "jude",
  启示录: "revelation",

  // ── Korean (개역개정 KRV) ──────────────────────────────────────────────────
  창세기: "genesis",
  출애굽기: "exodus",
  레위기: "leviticus",
  민수기: "numbers",
  신명기: "deuteronomy",
  여호수아: "joshua",
  사사기: "judges",
  룻기: "ruth",
  사무엘상: "1 samuel",
  사무엘하: "2 samuel",
  열왕기상: "1 kings",
  열왕기하: "2 kings",
  역대상: "1 chronicles",
  역대하: "2 chronicles",
  에스라: "ezra",
  느헤미야: "nehemiah",
  에스더: "esther",
  욥기: "job",
  시편: "psalms",
  잠언: "proverbs",
  전도서: "ecclesiastes",
  아가: "song of solomon",
  이사야: "isaiah",
  예레미야: "jeremiah",
  예레미야애가: "lamentations",
  "예레미야 애가": "lamentations",
  에스겔: "ezekiel",
  다니엘: "daniel",
  호세아: "hosea",
  요엘: "joel",
  아모스: "amos",
  오바댜: "obadiah",
  요나: "jonah",
  미가: "micah",
  나훔: "nahum",
  하박국: "habakkuk",
  스바냐: "zephaniah",
  학개: "haggai",
  스가랴: "zechariah",
  말라기: "malachi",
  마태복음: "matthew",
  마가복음: "mark",
  누가복음: "luke",
  요한복음: "john",
  사도행전: "acts",
  로마서: "romans",
  고린도전서: "1 corinthians",
  고린도후서: "2 corinthians",
  갈라디아서: "galatians",
  에베소서: "ephesians",
  빌립보서: "philippians",
  골로새서: "colossians",
  데살로니가전서: "1 thessalonians",
  데살로니가후서: "2 thessalonians",
  디모데전서: "1 timothy",
  디모데후서: "2 timothy",
  디도서: "titus",
  빌레몬서: "philemon",
  히브리서: "hebrews",
  야고보서: "james",
  베드로전서: "1 peter",
  베드로후서: "2 peter",
  요한일서: "1 john",
  요한이서: "2 john",
  요한삼서: "3 john",
  유다서: "jude",
  요한계시록: "revelation",

  // ── Portuguese (Almeida Atualizada / almeida) ─────────────────────────────
  // Only entries with Portuguese-unique spellings (different from Spanish/French/Italian)
  // are listed here, to avoid overriding behaviour tested in the existing Spanish and
  // Italian comprehensive tests (e.g. "salmos" and "romanos" are shared with Spanish).
  gênesis: "genesis",
  êxodo: "exodus",
  levítico: "leviticus",
  deuteronômio: "deuteronomy",
  juízes: "judges",
  rute: "ruth",
  "1 reis": "1 kings",
  "2 reis": "2 kings",
  "1 crônicas": "1 chronicles",
  "2 crônicas": "2 chronicles",
  neemias: "nehemiah",
  jó: "job",
  provérbios: "proverbs",
  eclesiastes: "ecclesiastes",
  "cântico dos cânticos": "song of solomon",
  jeremias: "jeremiah",
  lamentações: "lamentations",
  oseias: "hosea",
  obadias: "obadiah",
  miquéias: "micah",
  naum: "nahum",
  habacuque: "habakkuk",
  sofonias: "zephaniah",
  ageu: "haggai",
  zacarias: "zechariah",
  malaquias: "malachi",
  mateus: "matthew",
  joão: "john",
  atos: "acts",
  "1 coríntios": "1 corinthians",
  "2 coríntios": "2 corinthians",
  colossenses: "colossians",
  "1 tessalonicenses": "1 thessalonians",
  "2 tessalonicenses": "2 thessalonians",
  "1 timóteo": "1 timothy",
  "2 timóteo": "2 timothy",
  filemom: "philemon",
  hebreus: "hebrews",
  tiago: "james",
  "1 joão": "1 john",
  "2 joão": "2 john",
  "3 joão": "3 john",
  apocalipse: "revelation",

  // ── Arabic (Smith & Van Dyke / arabicsv) ─────────────────────────────────
  // Note: Arabic book names in the feed sometimes use definite-article prefix ال.
  // Both the prefixed and un-prefixed forms are listed where the LLM may vary.
  تكوين: "genesis",
  خروج: "exodus",
  لاويين: "leviticus",
  عدد: "numbers",
  تثنية: "deuteronomy",
  يشوع: "joshua",
  القضاة: "judges",
  راعوث: "ruth",
  "1 صموئيل": "1 samuel",
  "2 صموئيل": "2 samuel",
  "1 الملوك": "1 kings",
  "2 الملوك": "2 kings",
  "1 أخبار الأيام": "1 chronicles",
  "2 أخبار الأيام": "2 chronicles",
  عزرا: "ezra",
  نحميا: "nehemiah",
  أستير: "esther",
  أيوب: "job",
  المزامير: "psalms",
  مزامير: "psalms",
  الأمثال: "proverbs",
  أمثال: "proverbs",
  الجامعة: "ecclesiastes",
  جامعة: "ecclesiastes",
  "نشيد الأنشاد": "song of solomon",
  إشعياء: "isaiah",
  إرميا: "jeremiah",
  "مراثي إرميا": "lamentations",
  حزقيال: "ezekiel",
  دانيال: "daniel",
  هوشع: "hosea",
  يوئيل: "joel",
  عاموس: "amos",
  عوبديا: "obadiah",
  يونان: "jonah",
  ميخا: "micah",
  ناحوم: "nahum",
  حبقوق: "habakkuk",
  صفنيا: "zephaniah",
  حجي: "haggai",
  زكريا: "zechariah",
  ملاخي: "malachi",
  متى: "matthew",
  مرقس: "mark",
  لوقا: "luke",
  يوحنا: "john",
  "أعمال الرسل": "acts",
  رومية: "romans",
  "1 كورنثوس": "1 corinthians",
  "2 كورنثوس": "2 corinthians",
  غلاطية: "galatians",
  أفسس: "ephesians",
  فيليبي: "philippians",
  كولوسي: "colossians",
  "1 تسالونيكي": "1 thessalonians",
  "2 تسالونيكي": "2 thessalonians",
  "1 تيموثاوس": "1 timothy",
  "2 تيموثاوس": "2 timothy",
  تيطس: "titus",
  فليمون: "philemon",
  عبرانيين: "hebrews",
  يعقوب: "james",
  "1 بطرس": "1 peter",
  "2 بطرس": "2 peter",
  "1 يوحنا": "1 john",
  "2 يوحنا": "2 john",
  "3 يوحنا": "3 john",
  يهوذا: "jude",
  الرؤيا: "revelation",
  رؤيا: "revelation",

  // ── Hindi (IRV Bible / hindi) ─────────────────────────────────────────────
  उत्पत्ति: "genesis",
  निर्गमन: "exodus",
  लैव्यव्यवस्था: "leviticus",
  गिनती: "numbers",
  व्यवस्थाविवरण: "deuteronomy",
  यहोशू: "joshua",
  न्यायियों: "judges",
  रूत: "ruth",
  "1 शमूएल": "1 samuel",
  "2 शमूएल": "2 samuel",
  "1 राजाओं": "1 kings",
  "2 राजाओं": "2 kings",
  "1 इतिहास": "1 chronicles",
  "2 इतिहास": "2 chronicles",
  एज्रा: "ezra",
  नहेम्याह: "nehemiah",
  एस्तेर: "esther",
  अय्यूब: "job",
  "भजन संहिता": "psalms",
  नीतिवचन: "proverbs",
  सभोपदेशक: "ecclesiastes",
  श्रेष्ठगीत: "song of solomon",
  यशायाह: "isaiah",
  यिर्मयाह: "jeremiah",
  विलापगीत: "lamentations",
  यहेजकेल: "ezekiel",
  दानिय्येल: "daniel",
  होशे: "hosea",
  योएल: "joel",
  आमोस: "amos",
  ओबद्याह: "obadiah",
  योना: "jonah",
  मीका: "micah",
  नहूम: "nahum",
  हबक्कूक: "habakkuk",
  सपन्याह: "zephaniah",
  हाग्गै: "haggai",
  जकर्याह: "zechariah",
  मलाकी: "malachi",
  मत्ती: "matthew",
  मरकुस: "mark",
  लूका: "luke",
  यूहन्ना: "john",
  "प्रेरितों के काम": "acts",
  रोमियों: "romans",
  "1 कुरिन्थियों": "1 corinthians",
  "2 कुरिन्थियों": "2 corinthians",
  गलातियों: "galatians",
  इफिसियों: "ephesians",
  फिलिप्पियों: "philippians",
  कुलुस्सियों: "colossians",
  "1 थिस्सलुनीकियों": "1 thessalonians",
  "2 थिस्सलुनीकियों": "2 thessalonians",
  "1 तीमुथियुस": "1 timothy",
  "2 तीमुथियुस": "2 timothy",
  तीतुस: "titus",
  फिलेमोन: "philemon",
  इब्रानियों: "hebrews",
  याकूब: "james",
  "1 पतरस": "1 peter",
  "2 पतरस": "2 peter",
  "1 यूहन्ना": "1 john",
  "2 यूहन्ना": "2 john",
  "3 यूहन्ना": "3 john",
  यहूदा: "jude",
  प्रकाशितवाक्य: "revelation",
};

/**
 * Merge API-provided book name mappings into LOCALIZED_BOOK_TO_ENGLISH.
 * Called once after fetching /api/v1/scripture/book-names.
 * New entries are lowercased to match the existing convention.
 */
export function updateBookNames(apiData: Record<string, string>): void {
  for (const [localized, english] of Object.entries(apiData)) {
    const key = localized.toLowerCase();
    if (!(key in LOCALIZED_BOOK_TO_ENGLISH)) {
      LOCALIZED_BOOK_TO_ENGLISH[key] = english.toLowerCase();
    }
  }
}

/**
 * Normalize a book name to its lowercase English canonical form.
 * If the name is already English (or another Western language handled by
 * fuzzy matching), it is returned as-is (lowercased).
 */
function normalizeBookName(book: string): string {
  const lower = book.toLowerCase();
  return LOCALIZED_BOOK_TO_ENGLISH[lower] ?? lower;
}

/**
 * Extracts verse references from text, normalizing all book names to their
 * lowercase English canonical form so that `isVerseReferenced` can match
 * them against the English `verse.reference` returned by the backend.
 *
 * Supported formats:
 * - English:  "John 3:16", "1 John 2:3", "Song of Solomon 1:1"
 * - Italian:  "Giovanni 3:16", "Salmi 23:1"
 * - German:   "1. Mose 1:1", "Römer 8:28", "Johannes 3:16"
 * - Russian:  "Иоанна 3:16", "Псалтири 23:1", "Бытия 1:1", "Плач Иеремии 3:3"
 * - Chinese:  "约翰福音 3:16", "诗篇 23:1", "耶利米哀歌 3:3"
 * - Korean:   "요한복음 3:16", "시편 23:1", "예레미야 애가 3:3"
 */
export function extractVerseReferences(text: string): Set<string> {
  // Conjunctions that should not be treated as book names
  // English: "and", German: "und", Italian: "e", Spanish: "y", French: "et", etc.
  const CONJUNCTIONS = new Set(["e", "and", "und", "y", "et", "o", "a"]);

  // Use the shared verse pattern (auto-generated from LOCALIZED_BOOK_TO_ENGLISH).
  // Imported from versePatterns — the circular reference is safe because
  // versePatterns only accesses LOCALIZED_BOOK_TO_ENGLISH at module init time,
  // which completes before extractVerseReferences is ever called.
  const versePattern = _createVersePatternGlobal();

  const references = new Set<string>();
  const matches = Array.from(text.matchAll(versePattern));

  for (const match of matches) {
    const book = match[1].trim();
    const chapter = match[2];
    const verse = match[3];

    // Skip if the book name is a conjunction (e.g., "e 51:17", "and 8:28")
    if (CONJUNCTIONS.has(book.toLowerCase())) {
      continue;
    }

    // Normalize the book name to English before storing, so that
    // isVerseReferenced() can match against English verse.reference values.
    const normalizedBook = normalizeBookName(book);
    references.add(`${normalizedBook} ${chapter}:${verse}`);
  }

  return references;
}

/**
 * Checks if a verse matches any of the given references
 * Handles fuzzy matching for book names (e.g., "Psalm" vs "Psalms")
 */
export function isVerseReferenced(
  verse: { book: string; chapter: number; verse: number; reference?: string },
  references: Set<string>,
): boolean {
  // Normalize the verse reference for comparison (handle undefined)
  const normalizedRef = verse.reference?.toLowerCase();

  // Check if this verse's reference is mentioned (only if reference exists)
  if (normalizedRef && references.has(normalizedRef)) {
    return true;
  }

  // Also check using book/chapter/verse fields for more accurate matching
  const altRef = `${verse.book.toLowerCase()} ${verse.chapter}:${verse.verse}`;
  if (references.has(altRef)) {
    return true;
  }

  // Check if any referenced verse matches this one (partial match)
  for (const ref of Array.from(references)) {
    // Check if references are similar (handles "Psalm" vs "Psalms", etc.)
    const refParts = ref.match(/(.+)\s+(\d+):(\d+)/);
    if (refParts) {
      const refBook = refParts[1].toLowerCase();
      const refChapter = refParts[2];
      const refVerse = refParts[3];

      // Fuzzy book name matching
      const verseBook = verse.book.toLowerCase();
      const bookMatches =
        verseBook === refBook ||
        verseBook.startsWith(refBook) ||
        refBook.startsWith(verseBook) ||
        verseBook.replace(/s$/, "") === refBook.replace(/s$/, ""); // Handle Psalm/Psalms

      if (
        bookMatches &&
        verse.chapter === parseInt(refChapter) &&
        verse.verse === parseInt(refVerse)
      ) {
        return true;
      }
    }
  }

  return false;
}
