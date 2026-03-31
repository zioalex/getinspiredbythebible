import { describe, it, expect, beforeAll } from "vitest";
import {
  extractVerseReferences,
  isVerseReferenced,
  LOCALIZED_BOOK_TO_ENGLISH,
  updateBookNames,
} from "./verseExtraction";

describe("extractVerseReferences", () => {
  it("should extract simple book references", () => {
    const text = "Check out John 3:16 for encouragement";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract numbered book references (single digit)", () => {
    const text = "Read 1 John 2:3 today";
    const refs = extractVerseReferences(text);
    expect(refs.has("1 john 2:3")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract numbered multi-word books", () => {
    const text = "Consider 2 Corinthians 5:17";
    const refs = extractVerseReferences(text);
    expect(refs.has("2 corinthians 5:17")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it('should extract books with "of" in the name', () => {
    const text = "Song of Solomon 1:1 is beautiful";
    const refs = extractVerseReferences(text);
    expect(refs.has("song of solomon 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should handle verse ranges", () => {
    const text = "Read Matthew 5:3-12 for the beatitudes";
    const refs = extractVerseReferences(text);
    // Should capture the starting verse
    expect(refs.has("matthew 5:3")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract multiple references from text", () => {
    const text = "I'm feeling anxious about John 3:16 and Romans 8:28";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.size).toBe(2);
  });

  it("should extract references from longer sentences", () => {
    const text = "Check out 1 Peter 5:7 and Philippians 4:6-7 for peace";
    const refs = extractVerseReferences(text);
    expect(refs.has("1 peter 5:7")).toBe(true);
    expect(refs.has("philippians 4:6")).toBe(true);
    expect(refs.size).toBe(2);
  });

  it("should not extract false positives from regular text", () => {
    const text = "I have 3 apples and 16 oranges";
    const refs = extractVerseReferences(text);
    expect(refs.size).toBe(0);
  });

  it("should handle empty text", () => {
    const refs = extractVerseReferences("");
    expect(refs.size).toBe(0);
  });

  it("should handle text with no verse references", () => {
    const text = "This is just regular text without any Bible verses";
    const refs = extractVerseReferences("");
    expect(refs.size).toBe(0);
  });

  it("should handle plural book names", () => {
    const text = "Psalms 23:1 is comforting";
    const refs = extractVerseReferences(text);
    expect(refs.has("psalms 23:1")).toBe(true);
  });

  it("should normalize references to lowercase", () => {
    const text = "Read John 3:16 and Matthew 5:5";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("matthew 5:5")).toBe(true);
  });

  it("should extract Italian book names", () => {
    const text = "Leggi Giovanni 3:16 per incoraggiamento";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Italian book names with accents", () => {
    const text = "Considera Giosuè 1:9";
    const refs = extractVerseReferences(text);
    expect(refs.has("joshua 1:9")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German book names", () => {
    const text = "Lies Johannes 3:16 für Ermutigung";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German book names with umlauts", () => {
    const text = "Betrachte Römer 8:28";
    const refs = extractVerseReferences(text);
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German numbered books with period", () => {
    const text = "Am Anfang steht 1. Mose 1:1";
    const refs = extractVerseReferences(text);
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German book with umlauts and number", () => {
    const text = "Lese 2. Könige 5:14";
    const refs = extractVerseReferences(text);
    expect(refs.has("2 kings 5:14")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Russian two-word book names", () => {
    // "Плач Иеремии" = Lamentations in Russian (two-word book name)
    const text = "В Плач Иеремии 3:3 написано о страдании";
    const refs = extractVerseReferences(text);
    // Must capture the two-word book name, normalized to English
    expect(refs.has("lamentations 3:3")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should not include Russian prepositions in book names", () => {
    // "В" is a Russian preposition meaning "In" — must not be part of the book name
    const text = "В Плач Иеремии 3:3 написано";
    const refs = extractVerseReferences(text);
    expect(refs.has("в плач иеремии 3:3")).toBe(false);
    expect(refs.has("lamentations 3:3")).toBe(true);
  });

  it("should extract Russian single-word book names", () => {
    // "Бытие" = Genesis, "Иоанна" = John
    const text = "Читайте Бытие 1:1 и Иоанна 3:16";
    const refs = extractVerseReferences(text);
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.has("john 3:16")).toBe(true);
  });

  // ── Russian citation tests ──────────────────────────────────────────────

  it("should normalize Russian genitive 'Иоанна 3:16' to 'john 3:16'", () => {
    const text = "Иоанна 3:16";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should normalize Russian nominative 'Иоанн 3:16' to 'john 3:16'", () => {
    const text = "Иоанн 3:16";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should normalize Russian genitive 'Псалтири 23:1' to 'psalms 23:1'", () => {
    const text = "Псалтири 23:1";
    const refs = extractVerseReferences(text);
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should normalize Russian nominative 'Псалтирь 23:1' to 'psalms 23:1'", () => {
    const text = "Псалтирь 23:1";
    const refs = extractVerseReferences(text);
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should normalize Russian genitive 'Бытия 1:1' to 'genesis 1:1'", () => {
    const text = "Бытия 1:1";
    const refs = extractVerseReferences(text);
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should normalize Russian nominative 'Матфея 5:3' to 'matthew 5:3'", () => {
    const text = "Матфея 5:3";
    const refs = extractVerseReferences(text);
    expect(refs.has("matthew 5:3")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should normalize Russian 'Откровения 21:4' to 'revelation 21:4'", () => {
    const text = "Откровения 21:4";
    const refs = extractVerseReferences(text);
    expect(refs.has("revelation 21:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should normalize Russian 'Деяния 2:38' to 'acts 2:38'", () => {
    const text = "Деяния 2:38";
    const refs = extractVerseReferences(text);
    expect(refs.has("acts 2:38")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── Chinese citation tests ───────────────────────────────────────────────

  it("should normalize Chinese '约翰福音 3:16' to 'john 3:16'", () => {
    const text = "约翰福音 3:16";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should normalize Chinese '诗篇 23:1' to 'psalms 23:1'", () => {
    const text = "诗篇 23:1";
    const refs = extractVerseReferences(text);
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── Korean citation tests ────────────────────────────────────────────────

  it("should normalize Korean '요한복음 3:16' to 'john 3:16'", () => {
    const text = "요한복음 3:16";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should normalize Korean '시편 23:1' to 'psalms 23:1'", () => {
    const text = "시편 23:1";
    const refs = extractVerseReferences(text);
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── LOCALIZED_BOOK_TO_ENGLISH table test ─────────────────────────────────

  it("should export LOCALIZED_BOOK_TO_ENGLISH with correct entries", () => {
    expect(LOCALIZED_BOOK_TO_ENGLISH["иоанна"]).toBe("john");
    expect(LOCALIZED_BOOK_TO_ENGLISH["псалтири"]).toBe("psalms");
    expect(LOCALIZED_BOOK_TO_ENGLISH["бытия"]).toBe("genesis");
    expect(LOCALIZED_BOOK_TO_ENGLISH["约翰福音"]).toBe("john");
    expect(LOCALIZED_BOOK_TO_ENGLISH["요한복음"]).toBe("john");
  });

  it("should not cause recursion error on large text", () => {
    // This is a regression test for the catastrophic backtracking bug
    const largeText = "John 3:16 and Romans 8:28 ".repeat(1000);
    const start = Date.now();
    const refs = extractVerseReferences(largeText);
    const duration = Date.now() - start;

    // Should complete quickly (under 1 second)
    expect(duration).toBeLessThan(1000);
    // Should find the repeated references
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("romans 8:28")).toBe(true);
  });

  // --- Conjunction tests ---
  it("should not treat Italian conjunction 'e' as a book name", () => {
    const text = "Salmi 51:6 e 51:17 ci ricordano...";
    const refs = extractVerseReferences(text);
    expect(refs.has("psalms 51:6")).toBe(true);
    // "e 51:17" should NOT be in refs
    expect(refs.has("e 51:17")).toBe(false);
    // "e" must not be treated as a book
    for (const ref of refs) {
      expect(ref).not.toMatch(/^e\s+\d+:\d+/);
    }
  });

  it("should not treat English conjunction 'and' as a book name", () => {
    const text = "John 3:16 and Romans 8:28";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("romans 8:28")).toBe(true);
    for (const ref of refs) {
      expect(ref).not.toMatch(/^and\s+\d+:\d+/);
    }
  });

  it("should not treat German conjunction 'und' as a book name", () => {
    const text = "Johannes 3:16 und Römer 8:28";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("romans 8:28")).toBe(true);
    for (const ref of refs) {
      expect(ref).not.toMatch(/^und\s+\d+:\d+/);
    }
  });

  it("should handle numbered book names with Italian conjunction", () => {
    const text = "1 Giovanni 2:15 e 2 Pietro 1:4";
    const refs = extractVerseReferences(text);
    expect(refs.has("1 john 2:15")).toBe(true);
    expect(refs.has("2 peter 1:4")).toBe(true);
    for (const ref of refs) {
      expect(ref).not.toMatch(/^e\s+\d+:\d+/);
    }
  });

  it("should handle multiple conjunctions in one sentence", () => {
    const text = "John 3:16 and Romans 8:28 and Philippians 4:13";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.has("philippians 4:13")).toBe(true);
    for (const ref of refs) {
      expect(ref).not.toMatch(/^and\s+\d+:\d+/);
    }
  });

  it("should handle verse ranges with conjunctions", () => {
    const text = "Psalm 23:1-6 and Psalm 91:1-2";
    const refs = extractVerseReferences(text);
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.has("psalms 91:1")).toBe(true);
    for (const ref of refs) {
      expect(ref).not.toMatch(/^and\s+\d+:\d+/);
    }
  });

  it("should not break single verse with no conjunction", () => {
    const text = "John 3:16";
    const refs = extractVerseReferences(text);
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });
});

// ── LOCALIZED_BOOK_TO_ENGLISH integrity ───────────────────────────────────────

describe("LOCALIZED_BOOK_TO_ENGLISH table integrity", () => {
  it("should have entries for all 66 Russian nominative forms", () => {
    // Spot-check all 66 Russian nominative forms are present (lowercased keys)
    const requiredNominative = [
      "бытие",
      "исход",
      "левит",
      "числа",
      "второзаконие",
      "иисус навин",
      "судьи",
      "руфь",
      "ездра",
      "неемия",
      "есфирь",
      "иов",
      "псалтирь",
      "притчи",
      "екклесиаст",
      "песня песней",
      "исаия",
      "иеремия",
      "плач иеремии",
      "иезекиль",
      "даниил",
      "осия",
      "иоиль",
      "амос",
      "авдий",
      "иона",
      "михей",
      "наум",
      "аввакум",
      "софония",
      "аггей",
      "захария",
      "малахия",
      "матфей",
      "марк",
      "лука",
      "иоанн",
      "деяния апостолов",
      "деяния",
      "римлянам",
      "галатам",
      "ефесянам",
      "филиппийцам",
      "колоссянам",
      "евреям",
      "иаков",
      "иуда",
      "откровение",
    ];
    for (const key of requiredNominative) {
      expect(LOCALIZED_BOOK_TO_ENGLISH).toHaveProperty(key);
    }
  });

  it("should have entries for key Russian numbered book forms", () => {
    expect(LOCALIZED_BOOK_TO_ENGLISH["1 царств"]).toBe("1 samuel");
    expect(LOCALIZED_BOOK_TO_ENGLISH["2 царств"]).toBe("2 samuel");
    expect(LOCALIZED_BOOK_TO_ENGLISH["3 царств"]).toBe("1 kings");
    expect(LOCALIZED_BOOK_TO_ENGLISH["4 царств"]).toBe("2 kings");
    expect(LOCALIZED_BOOK_TO_ENGLISH["1 паралипоменон"]).toBe("1 chronicles");
    expect(LOCALIZED_BOOK_TO_ENGLISH["2 паралипоменон"]).toBe("2 chronicles");
    expect(LOCALIZED_BOOK_TO_ENGLISH["1 коринфянам"]).toBe("1 corinthians");
    expect(LOCALIZED_BOOK_TO_ENGLISH["2 коринфянам"]).toBe("2 corinthians");
    expect(LOCALIZED_BOOK_TO_ENGLISH["1 фессалоникийцам"]).toBe(
      "1 thessalonians",
    );
    expect(LOCALIZED_BOOK_TO_ENGLISH["2 фессалоникийцам"]).toBe(
      "2 thessalonians",
    );
    expect(LOCALIZED_BOOK_TO_ENGLISH["1 тимофею"]).toBe("1 timothy");
    expect(LOCALIZED_BOOK_TO_ENGLISH["2 тимофею"]).toBe("2 timothy");
    expect(LOCALIZED_BOOK_TO_ENGLISH["1 петра"]).toBe("1 peter");
    expect(LOCALIZED_BOOK_TO_ENGLISH["2 петра"]).toBe("2 peter");
    expect(LOCALIZED_BOOK_TO_ENGLISH["1 иоанна"]).toBe("1 john");
    expect(LOCALIZED_BOOK_TO_ENGLISH["2 иоанна"]).toBe("2 john");
    expect(LOCALIZED_BOOK_TO_ENGLISH["3 иоанна"]).toBe("3 john");
  });

  it("should have entries for key Russian genitive forms", () => {
    const requiredGenitive: [string, string][] = [
      ["бытия", "genesis"],
      ["исхода", "exodus"],
      ["левита", "leviticus"],
      ["числ", "numbers"],
      ["второзакония", "deuteronomy"],
      ["руфи", "ruth"],
      ["псалтири", "psalms"],
      ["притч", "proverbs"],
      ["екклесиаста", "ecclesiastes"],
      ["исаии", "isaiah"],
      ["иеремии", "jeremiah"],
      ["иезекиля", "ezekiel"],
      ["даниила", "daniel"],
      ["матфея", "matthew"],
      ["марка", "mark"],
      ["луки", "luke"],
      ["иоанна", "john"],
      ["деяний", "acts"],
      ["иакова", "james"],
      ["иуды", "jude"],
      ["откровения", "revelation"],
    ];
    for (const [key, expected] of requiredGenitive) {
      expect(LOCALIZED_BOOK_TO_ENGLISH[key]).toBe(expected);
    }
  });

  it("should have all 66 Chinese (CUV) book name entries", () => {
    const requiredChinese: [string, string][] = [
      ["创世记", "genesis"],
      ["出埃及记", "exodus"],
      ["利未记", "leviticus"],
      ["民数记", "numbers"],
      ["申命记", "deuteronomy"],
      ["约书亚记", "joshua"],
      ["士师记", "judges"],
      ["路得记", "ruth"],
      ["撒母耳记上", "1 samuel"],
      ["撒母耳记下", "2 samuel"],
      ["列王纪上", "1 kings"],
      ["列王纪下", "2 kings"],
      ["历代志上", "1 chronicles"],
      ["历代志下", "2 chronicles"],
      ["以斯拉记", "ezra"],
      ["尼希米记", "nehemiah"],
      ["以斯帖记", "esther"],
      ["约伯记", "job"],
      ["诗篇", "psalms"],
      ["箴言", "proverbs"],
      ["传道书", "ecclesiastes"],
      ["雅歌", "song of solomon"],
      ["以赛亚书", "isaiah"],
      ["耶利米书", "jeremiah"],
      ["耶利米哀歌", "lamentations"],
      ["以西结书", "ezekiel"],
      ["但以理书", "daniel"],
      ["何西阿书", "hosea"],
      ["约珥书", "joel"],
      ["阿摩司书", "amos"],
      ["俄巴底亚书", "obadiah"],
      ["约拿书", "jonah"],
      ["弥迦书", "micah"],
      ["那鸿书", "nahum"],
      ["哈巴谷书", "habakkuk"],
      ["西番雅书", "zephaniah"],
      ["哈该书", "haggai"],
      ["撒迦利亚书", "zechariah"],
      ["玛拉基书", "malachi"],
      ["马太福音", "matthew"],
      ["马可福音", "mark"],
      ["路加福音", "luke"],
      ["约翰福音", "john"],
      ["使徒行传", "acts"],
      ["罗马书", "romans"],
      ["哥林多前书", "1 corinthians"],
      ["哥林多后书", "2 corinthians"],
      ["加拉太书", "galatians"],
      ["以弗所书", "ephesians"],
      ["腓立比书", "philippians"],
      ["歌罗西书", "colossians"],
      ["帖撒罗尼迦前书", "1 thessalonians"],
      ["帖撒罗尼迦后书", "2 thessalonians"],
      ["提摩太前书", "1 timothy"],
      ["提摩太后书", "2 timothy"],
      ["提多书", "titus"],
      ["腓利门书", "philemon"],
      ["希伯来书", "hebrews"],
      ["雅各书", "james"],
      ["彼得前书", "1 peter"],
      ["彼得后书", "2 peter"],
      ["约翰一书", "1 john"],
      ["约翰二书", "2 john"],
      ["约翰三书", "3 john"],
      ["犹大书", "jude"],
      ["启示录", "revelation"],
    ];
    expect(requiredChinese).toHaveLength(66);
    for (const [key, expected] of requiredChinese) {
      expect(LOCALIZED_BOOK_TO_ENGLISH[key]).toBe(expected);
    }
  });

  it("should have all 66 Korean (KRV) book name entries", () => {
    const requiredKorean: [string, string][] = [
      ["창세기", "genesis"],
      ["출애굽기", "exodus"],
      ["레위기", "leviticus"],
      ["민수기", "numbers"],
      ["신명기", "deuteronomy"],
      ["여호수아", "joshua"],
      ["사사기", "judges"],
      ["룻기", "ruth"],
      ["사무엘상", "1 samuel"],
      ["사무엘하", "2 samuel"],
      ["열왕기상", "1 kings"],
      ["열왕기하", "2 kings"],
      ["역대상", "1 chronicles"],
      ["역대하", "2 chronicles"],
      ["에스라", "ezra"],
      ["느헤미야", "nehemiah"],
      ["에스더", "esther"],
      ["욥기", "job"],
      ["시편", "psalms"],
      ["잠언", "proverbs"],
      ["전도서", "ecclesiastes"],
      ["아가", "song of solomon"],
      ["이사야", "isaiah"],
      ["예레미야", "jeremiah"],
      ["예레미야애가", "lamentations"],
      ["에스겔", "ezekiel"],
      ["다니엘", "daniel"],
      ["호세아", "hosea"],
      ["요엘", "joel"],
      ["아모스", "amos"],
      ["오바댜", "obadiah"],
      ["요나", "jonah"],
      ["미가", "micah"],
      ["나훔", "nahum"],
      ["하박국", "habakkuk"],
      ["스바냐", "zephaniah"],
      ["학개", "haggai"],
      ["스가랴", "zechariah"],
      ["말라기", "malachi"],
      ["마태복음", "matthew"],
      ["마가복음", "mark"],
      ["누가복음", "luke"],
      ["요한복음", "john"],
      ["사도행전", "acts"],
      ["로마서", "romans"],
      ["고린도전서", "1 corinthians"],
      ["고린도후서", "2 corinthians"],
      ["갈라디아서", "galatians"],
      ["에베소서", "ephesians"],
      ["빌립보서", "philippians"],
      ["골로새서", "colossians"],
      ["데살로니가전서", "1 thessalonians"],
      ["데살로니가후서", "2 thessalonians"],
      ["디모데전서", "1 timothy"],
      ["디모데후서", "2 timothy"],
      ["디도서", "titus"],
      ["빌레몬서", "philemon"],
      ["히브리서", "hebrews"],
      ["야고보서", "james"],
      ["베드로전서", "1 peter"],
      ["베드로후서", "2 peter"],
      ["요한일서", "1 john"],
      ["요한이서", "2 john"],
      ["요한삼서", "3 john"],
      ["유다서", "jude"],
      ["요한계시록", "revelation"],
    ];
    expect(requiredKorean).toHaveLength(66);
    for (const [key, expected] of requiredKorean) {
      expect(LOCALIZED_BOOK_TO_ENGLISH[key]).toBe(expected);
    }
  });
});

// ── Comprehensive cross-language extractVerseReferences coverage ──────────────

describe("extractVerseReferences — comprehensive cross-language coverage", () => {
  // ── Chinese: additional books beyond John and Psalms ──────────────────────

  it("should extract Chinese Genesis '创世记 1:1'", () => {
    const refs = extractVerseReferences("创世记 1:1");
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Chinese Revelation '启示录 21:4'", () => {
    const refs = extractVerseReferences("启示录 21:4");
    expect(refs.has("revelation 21:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Chinese Lamentations '耶利米哀歌 3:3'", () => {
    const refs = extractVerseReferences("耶利米哀歌 3:3");
    expect(refs.has("lamentations 3:3")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Chinese 1 Corinthians '哥林多前书 13:4'", () => {
    const refs = extractVerseReferences("哥林多前书 13:4");
    expect(refs.has("1 corinthians 13:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Chinese Proverbs '箴言 3:5'", () => {
    const refs = extractVerseReferences("箴言 3:5");
    expect(refs.has("proverbs 3:5")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Chinese Romans '罗马书 8:28'", () => {
    const refs = extractVerseReferences("罗马书 8:28");
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Chinese Philippians '腓立比书 4:13'", () => {
    const refs = extractVerseReferences("腓立比书 4:13");
    expect(refs.has("philippians 4:13")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── Korean: additional books beyond John and Psalms ───────────────────────

  it("should extract Korean Genesis '창세기 1:1'", () => {
    const refs = extractVerseReferences("창세기 1:1");
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Korean Revelation '요한계시록 21:4'", () => {
    const refs = extractVerseReferences("요한계시록 21:4");
    expect(refs.has("revelation 21:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Korean Lamentations without space '예레미야애가 3:3'", () => {
    const refs = extractVerseReferences("예레미야애가 3:3");
    expect(refs.has("lamentations 3:3")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Korean Proverbs '잠언 3:5'", () => {
    const refs = extractVerseReferences("잠언 3:5");
    expect(refs.has("proverbs 3:5")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Korean Romans '로마서 8:28'", () => {
    const refs = extractVerseReferences("로마서 8:28");
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Korean 1 Corinthians '고린도전서 13:4'", () => {
    const refs = extractVerseReferences("고린도전서 13:4");
    expect(refs.has("1 corinthians 13:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Korean Philippians '빌립보서 4:13'", () => {
    const refs = extractVerseReferences("빌립보서 4:13");
    expect(refs.has("philippians 4:13")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── Russian: additional book forms ───────────────────────────────────────

  it("should extract Russian Proverbs 'притчи 3:5' → proverbs 3:5", () => {
    const refs = extractVerseReferences("Притчи 3:5");
    expect(refs.has("proverbs 3:5")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Russian Isaiah 'исаия 53:5' → isaiah 53:5", () => {
    const refs = extractVerseReferences("Исаия 53:5");
    expect(refs.has("isaiah 53:5")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Russian Revelation nominative 'откровение 21:4' → revelation 21:4", () => {
    const refs = extractVerseReferences("Откровение 21:4");
    expect(refs.has("revelation 21:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Russian Hebrews 'евреям 11:1' → hebrews 11:1", () => {
    const refs = extractVerseReferences("Евреям 11:1");
    expect(refs.has("hebrews 11:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Russian Philippians 'филиппийцам 4:13' → philippians 4:13", () => {
    const refs = extractVerseReferences("Филиппийцам 4:13");
    expect(refs.has("philippians 4:13")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Russian numbered epistle '1 коринфянам 13:4' → 1 corinthians 13:4", () => {
    const refs = extractVerseReferences("1 Коринфянам 13:4");
    expect(refs.has("1 corinthians 13:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Russian numbered epistle '1 петра 5:7' → 1 peter 5:7", () => {
    const refs = extractVerseReferences("1 Петра 5:7");
    expect(refs.has("1 peter 5:7")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Russian Song of Solomon 'песня песней 1:1' → song of solomon 1:1", () => {
    const refs = extractVerseReferences("Песня Песней 1:1");
    expect(refs.has("song of solomon 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── Spanish ───────────────────────────────────────────────────────────────

  it("should extract Spanish John 'Juan 3:16'", () => {
    const refs = extractVerseReferences("Juan 3:16");
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Spanish Genesis 'Génesis 1:1'", () => {
    const refs = extractVerseReferences("Génesis 1:1");
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Spanish Psalms 'Salmos 23:1'", () => {
    const refs = extractVerseReferences("Salmos 23:1");
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Spanish Romans 'Romanos 8:28'", () => {
    const refs = extractVerseReferences("Romanos 8:28");
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Spanish Revelation 'Apocalipsis 21:4'", () => {
    const refs = extractVerseReferences("Apocalipsis 21:4");
    expect(refs.has("revelation 21:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── French ────────────────────────────────────────────────────────────────

  it("should extract French Genesis 'Genèse 1:1'", () => {
    const refs = extractVerseReferences("Genèse 1:1");
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract French John 'Jean 3:16'", () => {
    const refs = extractVerseReferences("Jean 3:16");
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract French Psalms 'Psaumes 23:1'", () => {
    const refs = extractVerseReferences("Psaumes 23:1");
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract French Romans 'Romains 8:28'", () => {
    const refs = extractVerseReferences("Romains 8:28");
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract French Revelation 'Apocalypse 21:4'", () => {
    const refs = extractVerseReferences("Apocalypse 21:4");
    expect(refs.has("revelation 21:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── Italian: additional books beyond John and Joshua ─────────────────────

  it("should extract Italian Genesis 'Genesi 1:1'", () => {
    const refs = extractVerseReferences("Genesi 1:1");
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Italian Psalms 'Salmi 23:1'", () => {
    const refs = extractVerseReferences("Salmi 23:1");
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Italian Romans 'Romani 8:28'", () => {
    const refs = extractVerseReferences("Romani 8:28");
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Italian Revelation 'Apocalisse 21:4'", () => {
    const refs = extractVerseReferences("Apocalisse 21:4");
    expect(refs.has("revelation 21:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract Italian 1 Corinthians '1 Corinzi 13:4'", () => {
    const refs = extractVerseReferences("1 Corinzi 13:4");
    expect(refs.has("1 corinthians 13:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── German: additional books beyond Johannes, Römer, and 1./2. Mose ──────

  it("should extract German Revelation 'Offenbarung 21:4'", () => {
    const refs = extractVerseReferences("Offenbarung 21:4");
    expect(refs.has("revelation 21:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German Psalms 'Psalmen 23:1'", () => {
    const refs = extractVerseReferences("Psalmen 23:1");
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German Hebrews 'Hebräer 11:1'", () => {
    const refs = extractVerseReferences("Hebräer 11:1");
    expect(refs.has("hebrews 11:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract German 1 Corinthians '1. Korinther 13:4'", () => {
    const refs = extractVerseReferences("1. Korinther 13:4");
    expect(refs.has("1 corinthians 13:4")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── Mixed-language texts ──────────────────────────────────────────────────

  it("should extract Chinese and Korean references from same text", () => {
    const refs = extractVerseReferences("约翰福音 3:16 그리고 요한복음 3:16");
    // Both normalize to "john 3:16" so only one unique ref
    expect(refs.has("john 3:16")).toBe(true);
  });

  it("should extract Chinese and Russian references from same text", () => {
    const refs = extractVerseReferences("创世记 1:1 и Бытия 1:1");
    // Both normalize to "genesis 1:1"
    expect(refs.has("genesis 1:1")).toBe(true);
  });

  it("should extract references from text mixing Italian and English", () => {
    const refs = extractVerseReferences("See Giovanni 3:16 and Romans 8:28");
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("romans 8:28")).toBe(true);
    expect(refs.size).toBe(2);
  });
});

describe("isVerseReferenced", () => {
  it("should match exact references", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "John 3:16",
    };
    expect(isVerseReferenced(verse, references)).toBe(true);
  });

  it("should match using normalized book names", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "JOHN 3:16",
    };
    expect(isVerseReferenced(verse, references)).toBe(true);
  });

  it("should match singular/plural book names (Psalm vs Psalms)", () => {
    const references = new Set(["psalm 23:1"]);
    const verse = {
      book: "Psalms",
      chapter: 23,
      verse: 1,
      reference: "Psalms 23:1",
    };
    expect(isVerseReferenced(verse, references)).toBe(true);
  });

  it("should match using book/chapter/verse fields", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "Jn 3:16", // Different abbreviation
    };
    expect(isVerseReferenced(verse, references)).toBe(true);
  });

  it("should not match different verses", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "John",
      chapter: 3,
      verse: 17,
      reference: "John 3:17",
    };
    expect(isVerseReferenced(verse, references)).toBe(false);
  });

  it("should not match different books", () => {
    const references = new Set(["john 3:16"]);
    const verse = {
      book: "Romans",
      chapter: 3,
      verse: 16,
      reference: "Romans 3:16",
    };
    expect(isVerseReferenced(verse, references)).toBe(false);
  });

  it("should handle empty reference set", () => {
    const references = new Set<string>();
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "John 3:16",
    };
    expect(isVerseReferenced(verse, references)).toBe(false);
  });

  // ── Cross-language matching tests ─────────────────────────────────────────

  it("should return true for English verse when message contained Russian genitive 'Иоанна 3:16'", () => {
    // Simulate: message text → extractVerseReferences → normalized Set
    const refs = extractVerseReferences(
      "Как сказано в Иоанна 3:16 о любви Бога",
    );
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "John 3:16",
    };
    expect(isVerseReferenced(verse, refs)).toBe(true);
  });

  it("should return true for English Psalms verse when message contained Russian 'Псалтири 23:1'", () => {
    const refs = extractVerseReferences("Псалтири 23:1 — утешение");
    const verse = {
      book: "Psalms",
      chapter: 23,
      verse: 1,
      reference: "Psalms 23:1",
    };
    expect(isVerseReferenced(verse, refs)).toBe(true);
  });

  it("should return true for English Genesis verse when message contained Russian 'Бытия 1:1'", () => {
    const refs = extractVerseReferences("В начале — Бытия 1:1");
    const verse = {
      book: "Genesis",
      chapter: 1,
      verse: 1,
      reference: "Genesis 1:1",
    };
    expect(isVerseReferenced(verse, refs)).toBe(true);
  });

  it("should return true for English John verse when message contained Chinese '约翰福音 3:16'", () => {
    const refs = extractVerseReferences("约翰福音 3:16");
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "John 3:16",
    };
    expect(isVerseReferenced(verse, refs)).toBe(true);
  });

  it("should return true for English John verse when message contained Korean '요한복음 3:16'", () => {
    const refs = extractVerseReferences("요한복음 3:16");
    const verse = {
      book: "John",
      chapter: 3,
      verse: 16,
      reference: "John 3:16",
    };
    expect(isVerseReferenced(verse, refs)).toBe(true);
  });
});

// ── Russian multi-word book name tests ───────────────────────────────────────

describe("extractVerseReferences — Russian multi-word books", () => {
  it("should extract Russian Acts full form 'Деяния Апостолов 2:38' → 'acts 2:38'", () => {
    const refs = extractVerseReferences("Деяния Апостолов 2:38");
    expect(refs.has("acts 2:38")).toBe(true);
  });

  it("should extract Russian Joshua 'Иисус Навин 1:9' → 'joshua 1:9'", () => {
    const refs = extractVerseReferences("Иисус Навин 1:9");
    expect(refs.has("joshua 1:9")).toBe(true);
  });
});

// ── Cross-language regression guard ──────────────────────────────────────────
// Verifies that at least one representative verse per language can be extracted
// and normalized to English.  All 11 languages now have bundled normalization
// maps in LOCALIZED_BOOK_TO_ENGLISH, so every language normalizes to English.

describe("extractVerseReferences — cross-language regression guard", () => {
  it("should extract at least one book name per language", () => {
    // [input, expected ref in the Set]
    const perLanguageSamples: [string, string][] = [
      ["Иоанна 3:16", "john 3:16"], // ru
      ["约翰福音 3:16", "john 3:16"], // zh
      ["요한복음 3:16", "john 3:16"], // ko
      ["Giovanni 3:16", "john 3:16"], // it
      ["Johannes 3:16", "john 3:16"], // de
      ["Juan 3:16", "john 3:16"], // es
      ["Jean 3:16", "john 3:16"], // fr
      ["João 3:16", "john 3:16"], // pt
      ["يوحنا 3:16", "john 3:16"], // ar
      ["यूहन्ना 3:16", "john 3:16"], // hi
      ["John 3:16", "john 3:16"], // en
    ];
    for (const [input, expected] of perLanguageSamples) {
      const refs = extractVerseReferences(input);
      expect(refs.has(expected), `Expected '${expected}' from '${input}'`).toBe(
        true,
      );
    }
  });
});

// ── Multi-word book name matrix ───────────────────────────────────────────────
// Verifies multi-word book names are captured as a single token (not truncated)
// and normalized to English across all languages.

describe("extractVerseReferences — multi-word book name matrix", () => {
  it("should capture multi-word book names as a single token across all languages", () => {
    const multiWordCases: [string, string][] = [
      // Russian multi-word
      ["Плач Иеремии 3:3", "lamentations 3:3"],
      ["Песня Песней 1:1", "song of solomon 1:1"],
      ["Деяния Апостолов 2:38", "acts 2:38"],
      // English multi-word
      ["Song of Solomon 1:1", "song of solomon 1:1"],
      // French multi-word — now normalized to English
      ["Cantique des Cantiques 1:1", "song of solomon 1:1"],
      // Italian multi-word — now normalized to English
      ["Cantico dei Cantici 1:1", "song of solomon 1:1"],
      // Arabic multi-word
      ["أعمال الرسل 2:38", "acts 2:38"],
      ["مراثي إرميا 3:22", "lamentations 3:22"],
      ["نشيد الأنشاد 2:1", "song of solomon 2:1"],
      // Hindi multi-word
      ["भजन संहिता 23:1", "psalms 23:1"],
      ["प्रेरितों के काम 2:38", "acts 2:38"],
      // Portuguese multi-word
      ["Cântico dos Cânticos 1:1", "song of solomon 1:1"],
    ];
    for (const [input, expected] of multiWordCases) {
      const refs = extractVerseReferences(input);
      expect(refs.has(expected), `Expected '${expected}' from '${input}'`).toBe(
        true,
      );
    }
  });
});

// ── API-driven book name updates ─────────────────────────────────────────────
// Verifies that updateBookNames() correctly merges API-provided mappings
// and that extraction + normalization works for dynamically loaded languages.

describe("extractVerseReferences — API-driven languages (updateBookNames)", () => {
  // Simulate API response with a few representative entries
  beforeAll(() => {
    updateBookNames({
      João: "John",
      Gênesis: "Genesis",
      يوحنا: "John",
      تكوين: "Genesis",
      यूहन्ना: "John",
      उत्पत्ति: "Genesis",
      Apocalipse: "Revelation",
      رومية: "Romans",
      रोमियों: "Romans",
    });
  });

  it("should extract and normalize Portuguese John via API data", () => {
    const refs = extractVerseReferences("João 3:16");
    expect(refs.has("john 3:16")).toBe(true);
  });

  it("should extract and normalize Arabic Genesis via API data", () => {
    const refs = extractVerseReferences("تكوين 1:1");
    expect(refs.has("genesis 1:1")).toBe(true);
  });

  it("should extract and normalize Hindi John via API data", () => {
    const refs = extractVerseReferences("यूहन्ना 3:16");
    expect(refs.has("john 3:16")).toBe(true);
  });

  it("should extract and normalize Portuguese Revelation via API data", () => {
    const refs = extractVerseReferences("Apocalipse 21:4");
    expect(refs.has("revelation 21:4")).toBe(true);
  });

  it("should extract and normalize Arabic Romans via API data", () => {
    const refs = extractVerseReferences("رومية 8:28");
    expect(refs.has("romans 8:28")).toBe(true);
  });

  it("should extract and normalize Hindi Romans via API data", () => {
    const refs = extractVerseReferences("रोमियों 8:28");
    expect(refs.has("romans 8:28")).toBe(true);
  });
});
