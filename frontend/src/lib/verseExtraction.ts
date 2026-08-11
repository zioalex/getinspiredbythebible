/**
 * Extracts verse references from text
 * Matches formats like: "John 3:16", "1 John 2:3", "Song of Solomon 1:1", etc.
 * Also supports localized formats: "Giovanni 3:16" (Italian), "1. Mose 1:1" (German),
 * "Плач Иеремии 3:3" (Russian), "耶利米哀歌 3:3" (Chinese), "예레미야 애가 3:3" (Korean),
 * "يوحنا 3:16" (Arabic), "यूहन्ना 3:16" (Hindi), "João 3:16" (Portuguese).
 *
 * All 11 languages are bundled in LOCALIZED_BOOK_TO_ENGLISH so verse links work
 * immediately. The backend API via updateBookNames() may add extra aliases at runtime.
 */

// Note on circular imports: versePatterns.ts imports LOCALIZED_BOOK_TO_ENGLISH
// from this module.  JavaScript ES modules resolve circular imports via live
// bindings, so the static import below is safe: versePatterns.ts only reads
// LOCALIZED_BOOK_TO_ENGLISH at its own module-init time (which runs after
// this module's const is initialised), and extractVerseReferences() is only
// ever called after both modules are fully loaded.
import { createVersePatternGlobal as _createVersePatternGlobal } from "./versePatterns";
import { normalizeTraditionalToSimplified } from "./chineseScript";

/**
 * Maps localized book names (lowercased) to canonical English book names (lowercased).
 * Bundled fallback covers ALL supported languages so that verse references are
 * recognised immediately — even before the API-provided book names load.
 * The API call (updateBookNames) may still add extra aliases at runtime.
 */
export const LOCALIZED_BOOK_TO_ENGLISH: Record<string, string> = {
  // ── English (common aliases) ────────────────────────────────────────────
  psalm: "psalms",
  "song of solomon": "song of solomon",

  // ── Italian (Riveduta 1927) ─────────────────────────────────────────────
  genesi: "genesis",
  esodo: "exodus",
  levitico: "leviticus",
  numeri: "numbers",
  deuteronomio: "deuteronomy",
  giosuè: "joshua",
  giudici: "judges",
  rut: "ruth",
  "1 samuele": "1 samuel",
  "2 samuele": "2 samuel",
  "1 re": "1 kings",
  "2 re": "2 kings",
  "1 cronache": "1 chronicles",
  "2 cronache": "2 chronicles",
  esdra: "ezra",
  nehemia: "nehemiah",
  ester: "esther",
  giobbe: "job",
  salmi: "psalms",
  salmo: "psalms",
  proverbi: "proverbs",
  ecclesiaste: "ecclesiastes",
  "cantico dei cantici": "song of solomon",
  isaia: "isaiah",
  geremia: "jeremiah",
  lamentazioni: "lamentations",
  ezechiele: "ezekiel",
  daniele: "daniel",
  osea: "hosea",
  gioele: "joel",
  abdia: "obadiah",
  giona: "jonah",
  michea: "micah",
  abacuc: "habakkuk",
  sofonia: "zephaniah",
  aggeo: "haggai",
  zaccaria: "zechariah",
  malachia: "malachi",
  matteo: "matthew",
  marco: "mark",
  luca: "luke",
  giovanni: "john",
  atti: "acts",
  romani: "romans",
  "1 corinzi": "1 corinthians",
  "2 corinzi": "2 corinthians",
  galati: "galatians",
  efesini: "ephesians",
  filippesi: "philippians",
  colossesi: "colossians",
  "1 tessalonicesi": "1 thessalonians",
  "2 tessalonicesi": "2 thessalonians",
  "1 timoteo": "1 timothy",
  "2 timoteo": "2 timothy",
  tito: "titus",
  filemone: "philemon",
  ebrei: "hebrews",
  giacomo: "james",
  "1 pietro": "1 peter",
  "2 pietro": "2 peter",
  "1 giovanni": "1 john",
  "2 giovanni": "2 john",
  "3 giovanni": "3 john",
  giuda: "jude",
  apocalisse: "revelation",

  // ── German (Schlachter 1951) ────────────────────────────────────────────
  "1. mose": "genesis",
  "2. mose": "exodus",
  "3. mose": "leviticus",
  "4. mose": "numbers",
  "5. mose": "deuteronomy",
  josua: "joshua",
  richter: "judges",
  ruth: "ruth",
  "1. samuel": "1 samuel",
  "2. samuel": "2 samuel",
  "1. könige": "1 kings",
  "2. könige": "2 kings",
  "1. chronik": "1 chronicles",
  "2. chronik": "2 chronicles",
  esra: "ezra",
  // nehemia: already mapped by Italian
  // esther: English name
  hiob: "job",
  psalmen: "psalms",
  sprüche: "proverbs",
  prediger: "ecclesiastes",
  hohelied: "song of solomon",
  "hohes lied": "song of solomon",
  jesaja: "isaiah",
  jeremia: "jeremiah",
  klagelieder: "lamentations",
  hesekiel: "ezekiel",
  // daniel: English name
  // hosea: English name
  // joel: English name
  // amos: English name
  obadja: "obadiah",
  jona: "jonah",
  micha: "micah",
  // nahum: English name
  habakuk: "habakkuk",
  zephanja: "zephaniah",
  zefanja: "zephaniah",
  // haggai: English name
  sacharja: "zechariah",
  maleachi: "malachi",
  matthäus: "matthew",
  markus: "mark",
  lukas: "luke",
  johannes: "john",
  apostelgeschichte: "acts",
  römer: "romans",
  "1. korinther": "1 corinthians",
  "2. korinther": "2 corinthians",
  galater: "galatians",
  epheser: "ephesians",
  philipper: "philippians",
  kolosser: "colossians",
  "1. thessalonicher": "1 thessalonians",
  "2. thessalonicher": "2 thessalonians",
  "1. timotheus": "1 timothy",
  "2. timotheus": "2 timothy",
  titus: "titus",
  philemon: "philemon",
  hebräer: "hebrews",
  jakobus: "james",
  "1. petrus": "1 peter",
  "2. petrus": "2 peter",
  "1. johannes": "1 john",
  "2. johannes": "2 john",
  "3. johannes": "3 john",
  judas: "jude",
  offenbarung: "revelation",

  // ── Spanish (Reina Valera 1909) ─────────────────────────────────────────
  génesis: "genesis",
  éxodo: "exodus",
  levítico: "leviticus",
  números: "numbers",
  // deuteronomio: already mapped by Italian
  josué: "joshua",
  jueces: "judges",
  // rut: already mapped by Italian
  "1 reyes": "1 kings",
  "2 reyes": "2 kings",
  "1 crónicas": "1 chronicles",
  "2 crónicas": "2 chronicles",
  esdras: "ezra",
  nehemías: "nehemiah",
  // ester: already mapped
  // job: English name
  salmos: "psalms",
  proverbios: "proverbs",
  eclesiastés: "ecclesiastes",
  cantares: "song of solomon",
  isaías: "isaiah",
  jeremías: "jeremiah",
  lamentaciones: "lamentations",
  ezequiel: "ezekiel",
  // daniel: English name
  oseas: "hosea",
  // joel: English name
  amós: "amos",
  abdías: "obadiah",
  jonás: "jonah",
  miqueas: "micah",
  nahúm: "nahum",
  // habacuc: already mapped by Italian
  sofonías: "zephaniah",
  hageo: "haggai",
  zacarías: "zechariah",
  malaquías: "malachi",
  mateo: "matthew",
  marcos: "mark",
  lucas: "luke",
  juan: "john",
  hechos: "acts",
  romanos: "romans",
  "1 corintios": "1 corinthians",
  "2 corintios": "2 corinthians",
  gálatas: "galatians",
  efesios: "ephesians",
  filipenses: "philippians",
  colosenses: "colossians",
  "1 tesalonicenses": "1 thessalonians",
  "2 tesalonicenses": "2 thessalonians",
  // 1 timoteo, 2 timoteo, tito: already mapped by Italian
  filemón: "philemon",
  hebreos: "hebrews",
  santiago: "james",
  "1 pedro": "1 peter",
  "2 pedro": "2 peter",
  "1 juan": "1 john",
  "2 juan": "2 john",
  "3 juan": "3 john",
  // judas: already mapped by German
  apocalipsis: "revelation",

  // ── French (Louis Segond 1910) ──────────────────────────────────────────
  genèse: "genesis",
  exode: "exodus",
  lévitique: "leviticus",
  nombres: "numbers",
  deutéronome: "deuteronomy",
  // josué: already mapped by Spanish
  juges: "judges",
  // ruth: already mapped
  "1 rois": "1 kings",
  "2 rois": "2 kings",
  "1 chroniques": "1 chronicles",
  "2 chroniques": "2 chronicles",
  // esdras: already mapped by Spanish
  néhémie: "nehemiah",
  // esther: English name
  // job: English name
  psaumes: "psalms",
  psaume: "psalms",
  proverbes: "proverbs",
  ecclésiaste: "ecclesiastes",
  "cantique des cantiques": "song of solomon",
  ésaïe: "isaiah",
  jérémie: "jeremiah",
  // lamentations: English name
  ézéchiel: "ezekiel",
  // daniel: English name
  osée: "hosea",
  joël: "joel",
  // amos: English name
  abdias: "obadiah",
  jonas: "jonah",
  michée: "micah",
  // nahum: English name
  // habacuc: already mapped
  sophonie: "zephaniah",
  aggée: "haggai",
  zacharie: "zechariah",
  malachie: "malachi",
  matthieu: "matthew",
  marc: "mark",
  luc: "luke",
  jean: "john",
  "actes des apôtres": "acts",
  romains: "romans",
  "1 corinthiens": "1 corinthians",
  "2 corinthiens": "2 corinthians",
  galates: "galatians",
  éphésiens: "ephesians",
  philippiens: "philippians",
  colossiens: "colossians",
  "1 thessaloniciens": "1 thessalonians",
  "2 thessaloniciens": "2 thessalonians",
  "1 timothée": "1 timothy",
  "2 timothée": "2 timothy",
  tite: "titus",
  philémon: "philemon",
  hébreux: "hebrews",
  jacques: "james",
  "1 pierre": "1 peter",
  "2 pierre": "2 peter",
  "1 jean": "1 john",
  "2 jean": "2 john",
  "3 jean": "3 john",
  jude: "jude",
  apocalypse: "revelation",

  // ── Portuguese (Almeida Atualizada) ─────────────────────────────────────
  gênesis: "genesis",
  êxodo: "exodus",
  // levítico: already mapped by Spanish
  // números: already mapped by Spanish
  deuteronômio: "deuteronomy",
  // josué: already mapped
  juízes: "judges",
  rute: "ruth",
  "1 reis": "1 kings",
  "2 reis": "2 kings",
  "1 crônicas": "1 chronicles",
  "2 crônicas": "2 chronicles",
  // esdras: already mapped
  neemias: "nehemiah",
  // ester: already mapped
  jó: "job",
  // salmos: already mapped by Spanish
  provérbios: "proverbs",
  eclesiastes: "ecclesiastes",
  "cântico dos cânticos": "song of solomon",
  // isaías: already mapped by Spanish
  jeremias: "jeremiah",
  lamentações: "lamentations",
  // ezequiel: already mapped by Spanish
  // daniel: English name
  oseias: "hosea",
  // joel: English name
  // amós: already mapped by Spanish
  obadias: "obadiah",
  // jonas: already mapped by French
  miquéias: "micah",
  naum: "nahum",
  habacuque: "habakkuk",
  sofonias: "zephaniah",
  ageu: "haggai",
  zacarias: "zechariah",
  malaquias: "malachi",
  mateus: "matthew",
  // marcos: already mapped by Spanish
  // lucas: already mapped by Spanish
  joão: "john",
  atos: "acts",
  // romanos: already mapped by Spanish
  "1 coríntios": "1 corinthians",
  "2 coríntios": "2 corinthians",
  // gálatas: already mapped by Spanish
  efésios: "ephesians",
  // filipenses: already mapped by Spanish
  colossenses: "colossians",
  "1 tessalonicenses": "1 thessalonians",
  "2 tessalonicenses": "2 thessalonians",
  "1 timóteo": "1 timothy",
  "2 timóteo": "2 timothy",
  // tito: already mapped
  filemom: "philemon",
  hebreus: "hebrews",
  tiago: "james",
  // 1 pedro: already mapped by Spanish
  // 2 pedro: already mapped by Spanish
  "1 joão": "1 john",
  "2 joão": "2 john",
  "3 joão": "3 john",
  // judas: already mapped
  apocalipse: "revelation",

  // ── Arabic (Smith & Van Dyke) ───────────────────────────────────────────
  تكوين: "genesis",
  خروج: "exodus",
  لاويين: "leviticus",
  عدد: "numbers",
  تثنية: "deuteronomy",
  يشوع: "joshua",
  القضاة: "judges",
  قضاة: "judges",
  راعوث: "ruth",
  "1 صموئيل": "1 samuel",
  "2 صموئيل": "2 samuel",
  "1 الملوك": "1 kings",
  "2 الملوك": "2 kings",
  "1 ملوك": "1 kings", // without article (LLM citation form)
  "2 ملوك": "2 kings", // without article (LLM citation form)
  "1 أخبار الأيام": "1 chronicles",
  "2 أخبار الأيام": "2 chronicles",
  عزرا: "ezra",
  نحميا: "nehemiah",
  أستير: "esther",
  أيوب: "job",
  المزامير: "psalms",
  مزمور: "psalms",
  مزامير: "psalms",
  الأمثال: "proverbs",
  أمثال: "proverbs",
  الجامعة: "ecclesiastes",
  جامعة: "ecclesiastes",
  "نشيد الأنشاد": "song of solomon",
  "نشيد الأناشيد": "song of solomon",
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
  أعمال: "acts",
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

  // ── Hindi (IRV Bible) ───────────────────────────────────────────────────
  उत्पत्ति: "genesis",
  निर्गमन: "exodus",
  लैव्यव्यवस्था: "leviticus",
  लेवियतियुस: "leviticus", // alternate transliteration used by some LLMs
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

  // ── Hindi aliases (oblique-case ों/anusvara ending dropped) ─────────────
  // LLMs and casual usage commonly drop the trailing ं these canonical IRV
  // names use — mirrors HINDI_ALIASES in api/utils/translation_registry.py.
  न्यायियो: "judges",
  "1 राजाओ": "1 kings",
  "2 राजाओ": "2 kings",
  रोमियो: "romans",
  "1 कुरिन्थियो": "1 corinthians",
  "2 कुरिन्थियो": "2 corinthians",
  गलातियो: "galatians",
  इफिसियो: "ephesians",
  कुलुस्सियो: "colossians",
  "1 थिस्सलुनीकियो": "1 thessalonians",
  "2 थिस्सलुनीकियो": "2 thessalonians",
  इब्रानियो: "hebrews",
  "1 पतरस": "1 peter",
  "2 पतरस": "2 peter",
  "1 यूहन्ना": "1 john",
  "2 यूहन्ना": "2 john",
  "3 यूहन्ना": "3 john",
  यहूदा: "jude",
  प्रकाशितवाक्य: "revelation",

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

  // ── Russian abbreviations (commonly used by LLMs) ─────────────────────────
  ин: "john",
  мф: "matthew",
  мк: "mark",
  лк: "luke",
  пс: "psalms",
  рим: "romans",
  быт: "genesis",
  ис: "isaiah",
  откр: "revelation",
  деян: "acts",
  гал: "galatians",
  еф: "ephesians",
  кол: "colossians",
  евр: "hebrews",
  иак: "james",
  флп: "philippians",
  флм: "philemon",

  // ── Russian ё/е variants ──────────────────────────────────────────────────
  иёв: "job",

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

  // ── Russian (Synodal dash-format: "1-я", "1-е", "2-я", "3-я") ────────────
  "1-я царств": "1 samuel",
  "2-я царств": "2 samuel",
  "3-я царств": "1 kings",
  "4-я царств": "2 kings",
  "1-я паралипоменон": "1 chronicles",
  "2-я паралипоменон": "2 chronicles",
  "1-е коринфянам": "1 corinthians",
  "2-е коринфянам": "2 corinthians",
  "1-е фессалоникийцам": "1 thessalonians",
  "2-е фессалоникийцам": "2 thessalonians",
  "1-е тимофею": "1 timothy",
  "2-е тимофею": "2 timothy",
  "1-е петра": "1 peter",
  "2-е петра": "2 peter",
  "1-е иоанна": "1 john",
  "2-е иоанна": "2 john",
  "3-е иоанна": "3 john",
  "2-я петра": "2 peter",

  // ── Chinese (中文和合本 CUV) ───────────────────────────────────────────────
  创世记: "genesis",
  创世纪: "genesis", // common variant: 纪 (era) instead of CUV-canonical 记 (record)
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

  // ── Chinese 记↔纪 swap aliases (LLMs confuse these homophones) ────────────
  出埃及纪: "exodus",
  利未纪: "leviticus",
  民数纪: "numbers",
  申命纪: "deuteronomy",
  约书亚纪: "joshua",
  士师纪: "judges",
  路得纪: "ruth",
  撒母耳纪上: "1 samuel",
  撒母耳纪下: "2 samuel",
  列王记上: "1 kings", // CUV uses 纪 for Kings; variant uses 记
  列王记下: "2 kings",
  以斯拉纪: "ezra",
  尼希米纪: "nehemiah",
  以斯帖纪: "esther",
  约伯纪: "job",

  // ── Chinese Catholic 思高本 (Studium Biblicum) names ──────────────────────
  玛窦福音: "matthew",
  马尔谷福音: "mark",
  若望福音: "john",
  宗徒大事录: "acts",
  默示录: "revelation",
  格林多前书: "1 corinthians",
  格林多后书: "2 corinthians",
  若望一书: "1 john",
  若望二书: "2 john",
  若望三书: "3 john",
  雅各伯书: "james",
  犹达书: "jude",

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
  "예레미야 애가": "lamentations", // canonical form with space
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

  // ── Korean aliases (short forms LLMs commonly produce) ─────────────────────
  계시록: "revelation", // Short for 요한계시록
  애가: "lamentations", // Short for 예레미야 애가
  행전: "acts", // Short for 사도행전
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
  // The set of valid book names changed — drop the cache so isKnownBook()
  // rebuilds it (including any newly added API-provided aliases).
  _cachedKnownBooks = null;
}

// ---------------------------------------------------------------------------
// Known-book allowlist
// ---------------------------------------------------------------------------

// Lazily-built set of every recognised book name (lowercased).  Populated on
// first call to isKnownBook() and invalidated by updateBookNames().
let _cachedKnownBooks: Set<string> | null = null;

/**
 * Returns the set of all recognised book names (lowercased).
 *
 * The set is the union of:
 *   - every KEY of LOCALIZED_BOOK_TO_ENGLISH   (all localized names, e.g.
 *     "hiob", "5. mose", "약한복음", "1 царств"), and
 *   - every VALUE of LOCALIZED_BOOK_TO_ENGLISH (the 66 English canonical
 *     names, e.g. "job", "genesis", "1 samuel", "song of solomon").
 *
 * Including the English values means plain English references ("John 3:16")
 * are recognised even though English book names are not stored as keys.
 */
function getKnownBooks(): Set<string> {
  if (_cachedKnownBooks !== null) {
    return _cachedKnownBooks;
  }
  const known = new Set<string>();
  for (const [localized, english] of Object.entries(
    LOCALIZED_BOOK_TO_ENGLISH,
  )) {
    known.add(localized.toLowerCase());
    known.add(english.toLowerCase());
  }
  _cachedKnownBooks = known;
  return known;
}

/**
 * Returns true when `book` is a real Bible book name in any supported language.
 *
 * Used to validate the book portion of a regex match before treating it as a
 * verse reference.  The verse regex deliberately accepts any "Word digit:digit"
 * shape (to stay language-agnostic), so this allowlist is what prevents prose
 * like "Trost der Hoffnung 5:5", clock times like "um 14:30", and greedy
 * over-matches from being marked as verses.
 */
export function isKnownBook(book: string): boolean {
  const key = book.trim().toLowerCase();
  const known = getKnownBooks();
  // Traditional Chinese retry (BITB-025): the book-name set only stores
  // Simplified forms, so a Traditional-script name (e.g. "約翰福音") needs
  // its Simplified form tried too. Normalize the candidate, never the set.
  return known.has(key) || known.has(normalizeTraditionalToSimplified(key));
}

/**
 * Normalize a book name to its lowercase English canonical form.
 * If the name is already English (or another Western language handled by
 * fuzzy matching), it is returned as-is (lowercased).
 */
function normalizeBookName(book: string): string {
  const lower = book.toLowerCase();
  if (lower in LOCALIZED_BOOK_TO_ENGLISH) {
    return LOCALIZED_BOOK_TO_ENGLISH[lower];
  }
  // Traditional Chinese retry (BITB-025) — see isKnownBook above.
  const simplified = normalizeTraditionalToSimplified(lower);
  return LOCALIZED_BOOK_TO_ENGLISH[simplified] ?? lower;
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
/**
 * Normalize Devanagari digits (०-९, U+0966-U+096F) to ASCII digits (0-9).
 * Returns the string unchanged if no Devanagari digits are present.
 */
function normalizeDevanagariDigits(s: string): string {
  return s.replace(/[\u0966-\u096F]/g, (ch) =>
    String(ch.charCodeAt(0) - 0x0966),
  );
}

/**
 * Normalize Eastern Arabic digits (٠-٩, U+0660-U+0669) to ASCII digits (0-9).
 */
function normalizeEasternArabicDigits(s: string): string {
  return s.replace(/[\u0660-\u0669]/g, (ch) =>
    String(ch.charCodeAt(0) - 0x0660),
  );
}

/**
 * Normalize non-ASCII digit systems to ASCII.
 * Handles Devanagari (०-९) and Eastern Arabic (٠-٩) numerals.
 */
export function normalizeDigits(s: string): string {
  return normalizeEasternArabicDigits(normalizeDevanagariDigits(s));
}

/**
 * Strip Arabic tashkeel (diacritics U+064B–U+065F, U+0670) and tatweel
 * (kashida U+0640) from text so that vowelised forms like يُوحَنَّا
 * match the canonical يوحنا in the lookup table.
 *
 * Also normalizes French guillemets «» (U+00AB/U+00BB) to CJK guillemets
 * 《》 (U+300A/U+300B) so the existing bracket handling covers Arabic «…».
 */
function normalizeArabicText(text: string): string {
  return text
    .replace(/[\u064B-\u065F\u0670\u0640]/g, "")
    .replace(/\u00AB/g, "\u300A")
    .replace(/\u00BB/g, "\u300B");
}

export function extractVerseReferences(text: string): Set<string> {
  // Preprocess: strip Arabic tashkeel/tatweel, normalize guillemets, and
  // convert Traditional Chinese book names to Simplified (BITB-025). This
  // function returns a Set of "book:chapter:verse" keys, not offsets into
  // the original text, so overwriting `text` outright is safe here (unlike
  // linkifyVerses.ts / ChatMessage.tsx, which must preserve the original
  // script in what's displayed to the user).
  text = normalizeTraditionalToSimplified(normalizeArabicText(text));

  // Use the shared verse pattern (auto-generated from LOCALIZED_BOOK_TO_ENGLISH).
  // Imported from versePatterns — the circular reference is safe because
  // versePatterns only accesses LOCALIZED_BOOK_TO_ENGLISH at module init time,
  // which completes before extractVerseReferences is ever called.
  const versePattern = _createVersePatternGlobal();

  const references = new Set<string>();

  // Iterate with exec() (not matchAll) so we can rewind the scanner on a
  // rejected match — see the isKnownBook branch below.
  let match: RegExpExecArray | null;
  while ((match = versePattern.exec(text)) !== null) {
    const book = match[1].trim();

    // Skip anything whose "book" is not a real Bible book in any supported
    // language.  This rejects conjunctions ("e 51:17", "und 3:16"), prose that
    // happens to contain numbers ("Trost der Hoffnung 5:5"), clock times
    // ("um 14:30") and greedy over-matches — none of which are verses.
    //
    // Rewind on rejection: a greedy alternative can swallow the words *before*
    // a real reference (e.g. "you of Psalm 56:9" → book "you of Psalm"), so a
    // rejected match may still hide a valid reference inside it.  Reset the
    // scanner to one character past the start of the rejected match so the
    // embedded reference ("Psalm 56:9") is still extracted.  `lastIndex` only
    // ever advances, so this cannot loop forever.
    if (!isKnownBook(book)) {
      versePattern.lastIndex = match.index + 1;
      continue;
    }

    // Normalize Devanagari (३→3) and Eastern Arabic (٣→3) digits
    const chapter = normalizeDigits(match[2]);
    const verse = normalizeDigits(match[3]);
    // Range end (e.g. the "18" in "3:16-18"), if present — see versePatterns.ts
    // group 4. isVerseReferenced() parses this suffix to test every verse in
    // [start, end], so omitting it here would silently drop range verses
    // after the first from citation matching.
    const verseEnd = match[4] ? normalizeDigits(match[4]) : null;

    // Normalize the book name to English before storing, so that
    // isVerseReferenced() can match against English verse.reference values.
    const normalizedBook = normalizeBookName(book);
    const reference = verseEnd
      ? `${normalizedBook} ${chapter}:${verse}-${verseEnd}`
      : `${normalizedBook} ${chapter}:${verse}`;
    references.add(reference);
  }

  return references;
}

/**
 * Checks if a verse matches any of the given references
 * Handles fuzzy matching for book names (e.g., "Psalm" vs "Psalms")
 * Also handles non-Latin book names (Hindi, Korean, Arabic, Chinese, Russian)
 * by normalizing them to their lowercase English canonical form before lookup.
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

  // Also check using book/chapter/verse fields for more accurate matching.
  // Normalize the book name to English so that non-Latin scripts (Hindi,
  // Korean, Arabic, Chinese, Russian) resolve to the same English key that
  // the backend puts in the `references` Set (e.g. "Philippians 4:7").
  const normalizedBook = normalizeBookName(verse.book);
  const altRef = `${normalizedBook} ${verse.chapter}:${verse.verse}`;
  if (references.has(altRef)) {
    return true;
  }

  // Check if any referenced verse matches this one (partial match)
  for (const ref of Array.from(references)) {
    // Check if references are similar (handles "Psalm" vs "Psalms", etc.)
    // The optional trailing group captures the END of a verse range, since the
    // backend emits cited ranges as "John 3:16-18" (hyphen) or "Psalms 23:1–6"
    // (en-dash). Every verse within [start, end] must count as referenced.
    const refParts = ref.match(/(.+)\s+(\d+):(\d+)(?:\s*[-–]\s*(\d+))?/);
    if (refParts) {
      const refBook = refParts[1].toLowerCase();
      const refChapter = parseInt(refParts[2], 10);
      const refVerseStart = parseInt(refParts[3], 10);
      const refVerseEnd = refParts[4]
        ? parseInt(refParts[4], 10)
        : refVerseStart;

      // Fuzzy book name matching — use the already-normalized English form so
      // non-Latin scripts are compared on equal footing.
      const verseBook = normalizedBook;
      const bookMatches =
        verseBook === refBook ||
        verseBook.startsWith(refBook) ||
        refBook.startsWith(verseBook) ||
        verseBook.replace(/s$/, "") === refBook.replace(/s$/, ""); // Handle Psalm/Psalms

      if (
        bookMatches &&
        verse.chapter === refChapter &&
        verse.verse >= refVerseStart &&
        verse.verse <= refVerseEnd
      ) {
        return true;
      }
    }
  }

  return false;
}
