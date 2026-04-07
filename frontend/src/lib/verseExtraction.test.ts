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

  // ── Chinese guillemet 《》 tests ──────────────────────────────────────────

  it("should extract '《约翰福音》3:16' as 'john 3:16'", () => {
    const refs = extractVerseReferences("《约翰福音》3:16");
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract '《诗篇》23:1' as 'psalms 23:1'", () => {
    const refs = extractVerseReferences("《诗篇》23:1");
    expect(refs.has("psalms 23:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract '《创世记》 1:1' (guillemet with space) as 'genesis 1:1'", () => {
    const refs = extractVerseReferences("《创世记》 1:1");
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  it("should extract guillemet reference in sentence context", () => {
    const refs = extractVerseReferences("请阅读《约翰福音》3:16");
    expect(refs.has("john 3:16")).toBe(true);
  });

  it("should extract '《创世纪》1:1' (variant 纪) as 'genesis 1:1'", () => {
    const refs = extractVerseReferences("《创世纪》1:1");
    expect(refs.has("genesis 1:1")).toBe(true);
    expect(refs.size).toBe(1);
  });

  // ── Chinese 记↔纪 swap variants ──────────────────────────────────────────

  it("should extract 出埃及纪 3:14 (纪 variant) as 'exodus 3:14'", () => {
    const refs = extractVerseReferences("出埃及纪 3:14");
    expect(refs.has("exodus 3:14")).toBe(true);
  });

  it("should extract 利未纪 19:18 (纪 variant) as 'leviticus 19:18'", () => {
    const refs = extractVerseReferences("利未纪 19:18");
    expect(refs.has("leviticus 19:18")).toBe(true);
  });

  it("should extract 民数纪 6:24 (纪 variant) as 'numbers 6:24'", () => {
    const refs = extractVerseReferences("民数纪 6:24");
    expect(refs.has("numbers 6:24")).toBe(true);
  });

  it("should extract 申命纪 6:4 (纪 variant) as 'deuteronomy 6:4'", () => {
    const refs = extractVerseReferences("申命纪 6:4");
    expect(refs.has("deuteronomy 6:4")).toBe(true);
  });

  it("should extract 约书亚纪 1:9 (纪 variant) as 'joshua 1:9'", () => {
    const refs = extractVerseReferences("约书亚纪 1:9");
    expect(refs.has("joshua 1:9")).toBe(true);
  });

  it("should extract 士师纪 6:12 (纪 variant) as 'judges 6:12'", () => {
    const refs = extractVerseReferences("士师纪 6:12");
    expect(refs.has("judges 6:12")).toBe(true);
  });

  it("should extract 路得纪 1:16 (纪 variant) as 'ruth 1:16'", () => {
    const refs = extractVerseReferences("路得纪 1:16");
    expect(refs.has("ruth 1:16")).toBe(true);
  });

  it("should extract 撒母耳纪上 3:10 (纪 variant) as '1 samuel 3:10'", () => {
    const refs = extractVerseReferences("撒母耳纪上 3:10");
    expect(refs.has("1 samuel 3:10")).toBe(true);
  });

  it("should extract 撒母耳纪下 7:16 (纪 variant) as '2 samuel 7:16'", () => {
    const refs = extractVerseReferences("撒母耳纪下 7:16");
    expect(refs.has("2 samuel 7:16")).toBe(true);
  });

  it("should extract 列王记上 18:1 (记 variant) as '1 kings 18:1'", () => {
    const refs = extractVerseReferences("列王记上 18:1");
    expect(refs.has("1 kings 18:1")).toBe(true);
  });

  it("should extract 列王记下 5:14 (记 variant) as '2 kings 5:14'", () => {
    const refs = extractVerseReferences("列王记下 5:14");
    expect(refs.has("2 kings 5:14")).toBe(true);
  });

  it("should extract 以斯拉纪 7:10 (纪 variant) as 'ezra 7:10'", () => {
    const refs = extractVerseReferences("以斯拉纪 7:10");
    expect(refs.has("ezra 7:10")).toBe(true);
  });

  it("should extract 尼希米纪 8:10 (纪 variant) as 'nehemiah 8:10'", () => {
    const refs = extractVerseReferences("尼希米纪 8:10");
    expect(refs.has("nehemiah 8:10")).toBe(true);
  });

  it("should extract 以斯帖纪 4:14 (纪 variant) as 'esther 4:14'", () => {
    const refs = extractVerseReferences("以斯帖纪 4:14");
    expect(refs.has("esther 4:14")).toBe(true);
  });

  it("should extract 约伯纪 1:21 (纪 variant) as 'job 1:21'", () => {
    const refs = extractVerseReferences("约伯纪 1:21");
    expect(refs.has("job 1:21")).toBe(true);
  });

  // ── Chinese Catholic (思高本) name variants ──────────────────────────────

  it("should extract 玛窦福音 5:3 (Catholic Matthew) as 'matthew 5:3'", () => {
    const refs = extractVerseReferences("玛窦福音 5:3");
    expect(refs.has("matthew 5:3")).toBe(true);
  });

  it("should extract 马尔谷福音 1:1 (Catholic Mark) as 'mark 1:1'", () => {
    const refs = extractVerseReferences("马尔谷福音 1:1");
    expect(refs.has("mark 1:1")).toBe(true);
  });

  it("should extract 若望福音 3:16 (Catholic John) as 'john 3:16'", () => {
    const refs = extractVerseReferences("若望福音 3:16");
    expect(refs.has("john 3:16")).toBe(true);
  });

  it("should extract 宗徒大事录 2:38 (Catholic Acts) as 'acts 2:38'", () => {
    const refs = extractVerseReferences("宗徒大事录 2:38");
    expect(refs.has("acts 2:38")).toBe(true);
  });

  it("should extract 默示录 21:4 (Catholic Revelation) as 'revelation 21:4'", () => {
    const refs = extractVerseReferences("默示录 21:4");
    expect(refs.has("revelation 21:4")).toBe(true);
  });

  it("should extract 格林多前书 13:4 (Catholic 1 Cor) as '1 corinthians 13:4'", () => {
    const refs = extractVerseReferences("格林多前书 13:4");
    expect(refs.has("1 corinthians 13:4")).toBe(true);
  });

  it("should extract 格林多后书 5:17 (Catholic 2 Cor) as '2 corinthians 5:17'", () => {
    const refs = extractVerseReferences("格林多后书 5:17");
    expect(refs.has("2 corinthians 5:17")).toBe(true);
  });

  it("should extract 若望一书 4:8 (Catholic 1 John) as '1 john 4:8'", () => {
    const refs = extractVerseReferences("若望一书 4:8");
    expect(refs.has("1 john 4:8")).toBe(true);
  });

  it("should extract 若望二书 1:6 (Catholic 2 John) as '2 john 1:6'", () => {
    const refs = extractVerseReferences("若望二书 1:6");
    expect(refs.has("2 john 1:6")).toBe(true);
  });

  it("should extract 若望三书 1:4 (Catholic 3 John) as '3 john 1:4'", () => {
    const refs = extractVerseReferences("若望三书 1:4");
    expect(refs.has("3 john 1:4")).toBe(true);
  });

  it("should extract 雅各伯书 1:5 (Catholic James) as 'james 1:5'", () => {
    const refs = extractVerseReferences("雅各伯书 1:5");
    expect(refs.has("james 1:5")).toBe(true);
  });

  it("should extract 犹达书 1:3 (Catholic Jude) as 'jude 1:3'", () => {
    const refs = extractVerseReferences("犹达书 1:3");
    expect(refs.has("jude 1:3")).toBe(true);
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

// ═══════════════════════════════════════════════════════════════════════════════
// TDD: Comprehensive non-Latin verse detection tests
// ═══════════════════════════════════════════════════════════════════════════════

// ── Arabic ──────────────────────────────────────────────────────────────────────

describe("extractVerseReferences — Arabic", () => {
  describe("single-word books", () => {
    it("should detect تكوين 1:1 → genesis 1:1", () => {
      const refs = extractVerseReferences("تكوين 1:1");
      expect(refs.has("genesis 1:1")).toBe(true);
    });

    it("should detect يوحنا 3:16 → john 3:16", () => {
      const refs = extractVerseReferences("يوحنا 3:16");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect رومية 8:28 → romans 8:28", () => {
      const refs = extractVerseReferences("رومية 8:28");
      expect(refs.has("romans 8:28")).toBe(true);
    });

    it("should detect متى 5:3 → matthew 5:3", () => {
      const refs = extractVerseReferences("متى 5:3");
      expect(refs.has("matthew 5:3")).toBe(true);
    });
  });

  describe("definite article forms (ال prefix)", () => {
    it("should detect المزامير 23:1 → psalms 23:1", () => {
      const refs = extractVerseReferences("المزامير 23:1");
      expect(refs.has("psalms 23:1")).toBe(true);
    });

    it("should detect citation form مزمور 23:1 → psalms 23:1", () => {
      const refs = extractVerseReferences("مزمور 23:1");
      expect(refs.has("psalms 23:1")).toBe(true);
    });

    it("should detect الرؤيا 21:4 → revelation 21:4", () => {
      const refs = extractVerseReferences("الرؤيا 21:4");
      expect(refs.has("revelation 21:4")).toBe(true);
    });

    it("should detect الأمثال 3:5 → proverbs 3:5", () => {
      const refs = extractVerseReferences("الأمثال 3:5");
      expect(refs.has("proverbs 3:5")).toBe(true);
    });
  });

  describe("numbered books", () => {
    it("should detect 1 صموئيل 3:1 → 1 samuel 3:1", () => {
      const refs = extractVerseReferences("1 صموئيل 3:1");
      expect(refs.has("1 samuel 3:1")).toBe(true);
    });

    it("should detect 2 ملوك 5:14 → 2 kings 5:14", () => {
      const refs = extractVerseReferences("2 ملوك 5:14");
      expect(refs.has("2 kings 5:14")).toBe(true);
    });

    it("should detect 1 كورنثوس 13:4 → 1 corinthians 13:4", () => {
      const refs = extractVerseReferences("1 كورنثوس 13:4");
      expect(refs.has("1 corinthians 13:4")).toBe(true);
    });
  });

  describe("multi-word books", () => {
    it("should detect أعمال الرسل 2:38 → acts 2:38", () => {
      const refs = extractVerseReferences("أعمال الرسل 2:38");
      expect(refs.has("acts 2:38")).toBe(true);
    });

    it("should detect مراثي إرميا 3:22 → lamentations 3:22", () => {
      const refs = extractVerseReferences("مراثي إرميا 3:22");
      expect(refs.has("lamentations 3:22")).toBe(true);
    });

    it("should detect نشيد الأنشاد 2:1 → song of solomon 2:1", () => {
      const refs = extractVerseReferences("نشيد الأنشاد 2:1");
      expect(refs.has("song of solomon 2:1")).toBe(true);
    });
  });

  describe("verse ranges", () => {
    it("should capture starting verse from يوحنا 3:16-18", () => {
      const refs = extractVerseReferences("يوحنا 3:16-18");
      expect(refs.has("john 3:16")).toBe(true);
    });
  });

  describe("multiple refs in same text", () => {
    it("should detect two Arabic refs separated by space", () => {
      // Note: Arabic و (and) attaches to the next word without space.
      // When separated by space or punctuation, both refs are detected.
      const refs = extractVerseReferences("اقرأ يوحنا 3:16 و رومية 8:28");
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.has("romans 8:28")).toBe(true);
    });

    it("should detect first ref when و is attached (known limitation)", () => {
      // Arabic و attaches directly: "ورومية" — regex treats as single word
      const refs = extractVerseReferences("اقرأ يوحنا 3:16 ورومية 8:28");
      expect(refs.has("john 3:16")).toBe(true);
      // Second ref not detected due to attached conjunction (known limitation)
      expect(refs.size).toBeGreaterThanOrEqual(1);
    });
  });

  describe("embedded in longer text", () => {
    it("should detect ref in middle of Arabic sentence", () => {
      const refs = extractVerseReferences(
        "كما جاء في يوحنا 3:16 أن الله أحب العالم",
      );
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.size).toBe(1);
    });
  });
});

// ── Arabic: tashkeel, Eastern numerals, guillemets ──────────────────────────────

describe("extractVerseReferences — Arabic tashkeel and Eastern numerals", () => {
  describe("tashkeel (diacritics) stripping", () => {
    it("should detect \u064A\u064F\u0648\u062D\u064E\u0646\u064E\u0651\u0627 3:16 (with tashkeel) \u2192 john 3:16", () => {
      const refs = extractVerseReferences(
        "\u064A\u064F\u0648\u062D\u064E\u0646\u064E\u0651\u0627 3:16",
      );
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect \u062A\u064E\u0643\u0652\u0648\u0650\u064A\u0646 1:1 (with tashkeel) \u2192 genesis 1:1", () => {
      const refs = extractVerseReferences(
        "\u062A\u064E\u0643\u0652\u0648\u0650\u064A\u0646 1:1",
      );
      expect(refs.has("genesis 1:1")).toBe(true);
    });
  });

  describe("Eastern Arabic numerals", () => {
    it("should detect \u064A\u0648\u062D\u0646\u0627 \u0663:\u0661\u0666 (Eastern Arabic numerals) \u2192 john 3:16", () => {
      const refs = extractVerseReferences(
        "\u064A\u0648\u062D\u0646\u0627 \u0663:\u0661\u0666",
      );
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect \u062A\u0643\u0648\u064A\u0646 \u0661:\u0661 (Eastern Arabic numerals) \u2192 genesis 1:1", () => {
      const refs = extractVerseReferences(
        "\u062A\u0643\u0648\u064A\u0646 \u0661:\u0661",
      );
      expect(refs.has("genesis 1:1")).toBe(true);
    });
  });

  describe("Arabic guillemets \u00AB\u00BB", () => {
    it("should detect \u00AB\u064A\u0648\u062D\u0646\u0627\u00BB 3:16 \u2192 john 3:16", () => {
      const refs = extractVerseReferences(
        "\u00AB\u064A\u0648\u062D\u0646\u0627\u00BB 3:16",
      );
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect \u00AB\u0627\u0644\u0645\u0632\u0627\u0645\u064A\u0631\u00BB 23:1 \u2192 psalms 23:1", () => {
      const refs = extractVerseReferences(
        "\u00AB\u0627\u0644\u0645\u0632\u0627\u0645\u064A\u0631\u00BB 23:1",
      );
      expect(refs.has("psalms 23:1")).toBe(true);
    });
  });
});

// ── Hindi ───────────────────────────────────────────────────────────────────────

describe("extractVerseReferences — Hindi", () => {
  describe("single-word books", () => {
    it("should detect यूहन्ना 3:16 → john 3:16", () => {
      const refs = extractVerseReferences("यूहन्ना 3:16");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect उत्पत्ति 1:1 → genesis 1:1", () => {
      const refs = extractVerseReferences("उत्पत्ति 1:1");
      expect(refs.has("genesis 1:1")).toBe(true);
    });

    it("should detect रोमियों 8:28 → romans 8:28", () => {
      const refs = extractVerseReferences("रोमियों 8:28");
      expect(refs.has("romans 8:28")).toBe(true);
    });

    it("should detect मत्ती 5:3 → matthew 5:3", () => {
      const refs = extractVerseReferences("मत्ती 5:3");
      expect(refs.has("matthew 5:3")).toBe(true);
    });

    it("should detect प्रकाशितवाक्य 21:4 → revelation 21:4", () => {
      const refs = extractVerseReferences("प्रकाशितवाक्य 21:4");
      expect(refs.has("revelation 21:4")).toBe(true);
    });
  });

  describe("numbered books", () => {
    it("should detect 1 शमूएल 3:1 → 1 samuel 3:1", () => {
      const refs = extractVerseReferences("1 शमूएल 3:1");
      expect(refs.has("1 samuel 3:1")).toBe(true);
    });

    it("should detect 1 कुरिन्थियों 13:4 → 1 corinthians 13:4", () => {
      const refs = extractVerseReferences("1 कुरिन्थियों 13:4");
      expect(refs.has("1 corinthians 13:4")).toBe(true);
    });

    it("should detect 2 राजाओं 5:14 → 2 kings 5:14", () => {
      const refs = extractVerseReferences("2 राजाओं 5:14");
      expect(refs.has("2 kings 5:14")).toBe(true);
    });
  });

  describe("multi-word books with के connector", () => {
    it("should detect प्रेरितों के काम 2:38 → acts 2:38", () => {
      const refs = extractVerseReferences("प्रेरितों के काम 2:38");
      expect(refs.has("acts 2:38")).toBe(true);
    });

    it("should detect भजन संहिता 23:1 → psalms 23:1", () => {
      const refs = extractVerseReferences("भजन संहिता 23:1");
      expect(refs.has("psalms 23:1")).toBe(true);
    });
  });

  describe("verse ranges", () => {
    it("should capture starting verse from यूहन्ना 3:16-20", () => {
      const refs = extractVerseReferences("यूहन्ना 3:16-20");
      expect(refs.has("john 3:16")).toBe(true);
    });
  });

  describe("multiple refs in same text", () => {
    it("should detect two Hindi refs in one sentence", () => {
      const refs = extractVerseReferences("यूहन्ना 3:16 और रोमियों 8:28 पढ़ें");
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.has("romans 8:28")).toBe(true);
    });
  });
});

// ── Hindi: no-space and Devanagari numeral improvements ─────────────────────────

describe("extractVerseReferences — Hindi no-space and Devanagari numerals", () => {
  describe("no-space references", () => {
    it("should detect यूहन्ना3:16 (no space) → john 3:16", () => {
      const refs = extractVerseReferences("यूहन्ना3:16");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect उत्पत्ति1:1 (no space) → genesis 1:1", () => {
      const refs = extractVerseReferences("उत्पत्ति1:1");
      expect(refs.has("genesis 1:1")).toBe(true);
    });

    it("should detect प्रकाशितवाक्य21:4 (no space) → revelation 21:4", () => {
      const refs = extractVerseReferences("प्रकाशितवाक्य21:4");
      expect(refs.has("revelation 21:4")).toBe(true);
    });
  });

  describe("Devanagari numerals", () => {
    it("should detect यूहन्ना ३:१६ (Devanagari numerals) → john 3:16", () => {
      const refs = extractVerseReferences("यूहन्ना ३:१६");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect उत्पत्ति १:१ (Devanagari numerals) → genesis 1:1", () => {
      const refs = extractVerseReferences("उत्पत्ति १:१");
      expect(refs.has("genesis 1:1")).toBe(true);
    });
  });

  describe("embedded in Hindi text", () => {
    it("should detect ref in Hindi sentence", () => {
      const refs = extractVerseReferences("कृपया यूहन्ना 3:16 पढ़ें");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect no-space ref in Hindi sentence", () => {
      const refs = extractVerseReferences("बाइबल में यूहन्ना3:16 पढ़ें");
      expect(refs.has("john 3:16")).toBe(true);
    });
  });

  describe("multiple Hindi references", () => {
    it("should detect multiple Hindi refs in one sentence", () => {
      const refs = extractVerseReferences("यूहन्ना 3:16 और रोमियों 8:28 पढ़ें");
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.has("romans 8:28")).toBe(true);
    });
  });
});

// ── Chinese ─────────────────────────────────────────────────────────────────────

describe("extractVerseReferences — Chinese", () => {
  describe("single-token books (CJK)", () => {
    it("should detect 约翰福音 3:16 → john 3:16", () => {
      const refs = extractVerseReferences("约翰福音 3:16");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect 诗篇 23:1 → psalms 23:1", () => {
      const refs = extractVerseReferences("诗篇 23:1");
      expect(refs.has("psalms 23:1")).toBe(true);
    });

    it("should detect 创世记 1:1 → genesis 1:1", () => {
      const refs = extractVerseReferences("创世记 1:1");
      expect(refs.has("genesis 1:1")).toBe(true);
    });

    it("should detect 耶利米哀歌 3:3 → lamentations 3:3", () => {
      const refs = extractVerseReferences("耶利米哀歌 3:3");
      expect(refs.has("lamentations 3:3")).toBe(true);
    });

    it("should detect 使徒行传 2:38 → acts 2:38", () => {
      const refs = extractVerseReferences("使徒行传 2:38");
      expect(refs.has("acts 2:38")).toBe(true);
    });

    it("should detect 启示录 21:4 → revelation 21:4", () => {
      const refs = extractVerseReferences("启示录 21:4");
      expect(refs.has("revelation 21:4")).toBe(true);
    });

    it("should detect 罗马书 8:28 → romans 8:28", () => {
      const refs = extractVerseReferences("罗马书 8:28");
      expect(refs.has("romans 8:28")).toBe(true);
    });
  });

  describe("verse ranges", () => {
    it("should capture starting verse from 约翰福音 3:16-18", () => {
      const refs = extractVerseReferences("约翰福音 3:16-18");
      expect(refs.has("john 3:16")).toBe(true);
    });
  });

  describe("multiple refs in same text", () => {
    it("should detect two Chinese refs separated by comma", () => {
      // Chinese 和 (and) attaches to adjacent CJK chars without space.
      // Using Chinese comma (，) or space ensures both refs are detected.
      const refs = extractVerseReferences("约翰福音 3:16，罗马书 8:28");
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.has("romans 8:28")).toBe(true);
    });
  });

  describe("false positives", () => {
    it("should not match single CJK char 和 as book name", () => {
      // 和 = "and" in Chinese; should not be treated as a book name
      const refs = extractVerseReferences("和 3:16");
      expect(refs.size).toBe(0);
    });
  });
});

// ── Chinese no-space format ─────────────────────────────────────────────────────
// Chinese naturally writes 约翰福音10:28 (no space between book name and chapter).
// The backend already handles this with \s*; the frontend must match.

describe("extractVerseReferences — Chinese no-space format", () => {
  describe("basic no-space detection", () => {
    it("should detect 约翰福音10:28 (no space) → john 10:28", () => {
      const refs = extractVerseReferences("约翰福音10:28");
      expect(refs.has("john 10:28")).toBe(true);
      expect(refs.size).toBe(1);
    });

    it("should detect 约翰一书5:13 (no space, numbered book) → 1 john 5:13", () => {
      const refs = extractVerseReferences("约翰一书5:13");
      expect(refs.has("1 john 5:13")).toBe(true);
      expect(refs.size).toBe(1);
    });

    it("should detect 诗篇23:1 (no space) → psalms 23:1", () => {
      const refs = extractVerseReferences("诗篇23:1");
      expect(refs.has("psalms 23:1")).toBe(true);
      expect(refs.size).toBe(1);
    });

    it("should detect 创世记1:1 (no space) → genesis 1:1", () => {
      const refs = extractVerseReferences("创世记1:1");
      expect(refs.has("genesis 1:1")).toBe(true);
      expect(refs.size).toBe(1);
    });
  });

  describe("no-space with verse range", () => {
    it("should detect 约翰福音3:16-18 (no space, range) → john 3:16", () => {
      const refs = extractVerseReferences("约翰福音3:16-18");
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.size).toBe(1);
    });
  });

  describe("multiple no-space refs", () => {
    it("should detect refs separated by Chinese enumeration comma (、)", () => {
      const refs = extractVerseReferences("约翰福音10:28、约翰福音3:16");
      expect(refs.has("john 10:28")).toBe(true);
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.size).toBe(2);
    });

    it("should detect mixed spaced and no-space refs", () => {
      const refs = extractVerseReferences("约翰福音10:28、约翰一书 5:13");
      expect(refs.has("john 10:28")).toBe(true);
      expect(refs.has("1 john 5:13")).toBe(true);
      expect(refs.size).toBe(2);
    });
  });

  describe("embedded in Chinese text", () => {
    it("should detect no-space ref in natural Chinese sentence", () => {
      const refs = extractVerseReferences("请阅读约翰福音10:28来获得鼓励");
      expect(refs.has("john 10:28")).toBe(true);
      expect(refs.size).toBe(1);
    });

    it("should detect refs from user's real-world example", () => {
      const refs = extractVerseReferences(
        "这来自圣经，具体是约翰福音10:28、约翰福音3:16等章节",
      );
      expect(refs.has("john 10:28")).toBe(true);
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.size).toBe(2);
    });
  });

  describe("regression: Latin no-space must NOT match", () => {
    it("should NOT match John3:16 (Latin without space)", () => {
      const refs = extractVerseReferences("John3:16");
      expect(refs.size).toBe(0);
    });
  });
});

// ── Korean ──────────────────────────────────────────────────────────────────────

describe("extractVerseReferences — Korean", () => {
  describe("single-word books", () => {
    it("should detect 요한복음 3:16 → john 3:16", () => {
      const refs = extractVerseReferences("요한복음 3:16");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect 시편 23:1 → psalms 23:1", () => {
      const refs = extractVerseReferences("시편 23:1");
      expect(refs.has("psalms 23:1")).toBe(true);
    });

    it("should detect 창세기 1:1 → genesis 1:1", () => {
      const refs = extractVerseReferences("창세기 1:1");
      expect(refs.has("genesis 1:1")).toBe(true);
    });

    it("should detect 로마서 8:28 → romans 8:28", () => {
      const refs = extractVerseReferences("로마서 8:28");
      expect(refs.has("romans 8:28")).toBe(true);
    });

    it("should detect 요한계시록 21:4 → revelation 21:4", () => {
      const refs = extractVerseReferences("요한계시록 21:4");
      expect(refs.has("revelation 21:4")).toBe(true);
    });
  });

  describe("compound book names (spacing variants)", () => {
    it("should detect 예레미야애가 3:3 → lamentations (no space)", () => {
      const refs = extractVerseReferences("예레미야애가 3:3");
      expect(refs.has("lamentations 3:3")).toBe(true);
    });

    it("should detect 예레미야 애가 3:3 → lamentations (with space)", () => {
      const refs = extractVerseReferences("예레미야 애가 3:3");
      expect(refs.has("lamentations 3:3")).toBe(true);
    });
  });

  describe("verse ranges", () => {
    it("should capture starting verse from 요한복음 3:16-18", () => {
      const refs = extractVerseReferences("요한복음 3:16-18");
      expect(refs.has("john 3:16")).toBe(true);
    });
  });

  describe("multiple refs in same text", () => {
    it("should detect two Korean refs in one sentence", () => {
      const refs = extractVerseReferences(
        "요한복음 3:16과 로마서 8:28을 읽으세요",
      );
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.has("romans 8:28")).toBe(true);
    });
  });
});

// ── Korean: no-space and alias improvements ─────────────────────────────────────

describe("extractVerseReferences — Korean no-space and aliases", () => {
  describe("no-space references", () => {
    it("should detect 요한복음3:16 (no space) → john 3:16", () => {
      const refs = extractVerseReferences("요한복음3:16");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect 시편23:1 (no space) → psalms 23:1", () => {
      const refs = extractVerseReferences("시편23:1");
      expect(refs.has("psalms 23:1")).toBe(true);
    });

    it("should detect 창세기1:1 (no space) → genesis 1:1", () => {
      const refs = extractVerseReferences("창세기1:1");
      expect(refs.has("genesis 1:1")).toBe(true);
    });

    it("should detect 요한계시록21:4 (no space) → revelation 21:4", () => {
      const refs = extractVerseReferences("요한계시록21:4");
      expect(refs.has("revelation 21:4")).toBe(true);
    });
  });

  describe("corner bracket notation", () => {
    it("should detect 「요한복음」3:16 (corner brackets) → john 3:16", () => {
      const refs = extractVerseReferences("「요한복음」3:16");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect 『시편』23:1 (double corner brackets) → psalms 23:1", () => {
      const refs = extractVerseReferences("『시편』23:1");
      expect(refs.has("psalms 23:1")).toBe(true);
    });
  });

  describe("short-form aliases", () => {
    it("should detect 계시록 21:4 (short Revelation) → revelation 21:4", () => {
      const refs = extractVerseReferences("계시록 21:4");
      expect(refs.has("revelation 21:4")).toBe(true);
    });

    it("should detect 애가 3:3 (short Lamentations) → lamentations 3:3", () => {
      const refs = extractVerseReferences("애가 3:3");
      expect(refs.has("lamentations 3:3")).toBe(true);
    });

    it("should detect 행전 2:38 (short Acts) → acts 2:38", () => {
      const refs = extractVerseReferences("행전 2:38");
      expect(refs.has("acts 2:38")).toBe(true);
    });
  });

  describe("embedded no-space", () => {
    it("should detect 요한복음3:16 embedded in Korean text", () => {
      const refs = extractVerseReferences("성경에서 요한복음3:16을 읽으세요");
      expect(refs.has("john 3:16")).toBe(true);
    });
  });

  describe("multiple no-space references", () => {
    it("should detect 요한복음3:16 그리고 시편23:1 (multiple no-space)", () => {
      const refs = extractVerseReferences("요한복음3:16 그리고 시편23:1");
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.has("psalms 23:1")).toBe(true);
    });
  });
});

// ── Russian (extended) ──────────────────────────────────────────────────────────

describe("extractVerseReferences — Russian extended", () => {
  describe("Synodal dash-format numbered books", () => {
    it("should detect 1-я Царств 1:1 → 1 samuel 1:1", () => {
      const refs = extractVerseReferences("1-я Царств 1:1");
      expect(refs.has("1 samuel 1:1")).toBe(true);
    });

    it("should detect 1-е Коринфянам 13:4 → 1 corinthians 13:4", () => {
      const refs = extractVerseReferences("1-е Коринфянам 13:4");
      expect(refs.has("1 corinthians 13:4")).toBe(true);
    });

    it("should detect 2-я Петра 3:9 → 2 peter 3:9", () => {
      const refs = extractVerseReferences("2-я Петра 3:9");
      expect(refs.has("2 peter 3:9")).toBe(true);
    });

    it("should detect 3-я Царств 17:1 → 1 kings 17:1", () => {
      const refs = extractVerseReferences("3-я Царств 17:1");
      expect(refs.has("1 kings 17:1")).toBe(true);
    });
  });

  describe("verse ranges", () => {
    it("should capture starting verse from Иоанна 3:16-18", () => {
      const refs = extractVerseReferences("Иоанна 3:16-18");
      expect(refs.has("john 3:16")).toBe(true);
    });
  });

  describe("multiple refs in same text", () => {
    it("should detect two Russian refs in one sentence", () => {
      const refs = extractVerseReferences(
        "Иоанна 3:16 и Римлянам 8:28 важные стихи",
      );
      expect(refs.has("john 3:16")).toBe(true);
      expect(refs.has("romans 8:28")).toBe(true);
    });
  });
});

// ── Russian: abbreviations and ё/е normalization ────────────────────────────────

describe("extractVerseReferences — Russian abbreviations and ё/е", () => {
  describe("common abbreviations", () => {
    it("should detect Ин 3:16 → john 3:16", () => {
      const refs = extractVerseReferences("Ин 3:16");
      expect(refs.has("john 3:16")).toBe(true);
    });

    it("should detect Мф 5:3 → matthew 5:3", () => {
      const refs = extractVerseReferences("Мф 5:3");
      expect(refs.has("matthew 5:3")).toBe(true);
    });

    it("should detect Пс 23:1 → psalms 23:1", () => {
      const refs = extractVerseReferences("Пс 23:1");
      expect(refs.has("psalms 23:1")).toBe(true);
    });

    it("should detect Рим 8:28 → romans 8:28", () => {
      const refs = extractVerseReferences("Рим 8:28");
      expect(refs.has("romans 8:28")).toBe(true);
    });

    it("should detect Быт 1:1 → genesis 1:1", () => {
      const refs = extractVerseReferences("Быт 1:1");
      expect(refs.has("genesis 1:1")).toBe(true);
    });

    it("should detect Откр 21:4 → revelation 21:4", () => {
      const refs = extractVerseReferences("Откр 21:4");
      expect(refs.has("revelation 21:4")).toBe(true);
    });

    it("should detect Деян 2:38 → acts 2:38", () => {
      const refs = extractVerseReferences("Деян 2:38");
      expect(refs.has("acts 2:38")).toBe(true);
    });

    it("should detect Евр 11:1 → hebrews 11:1", () => {
      const refs = extractVerseReferences("Евр 11:1");
      expect(refs.has("hebrews 11:1")).toBe(true);
    });
  });

  describe("ё/е normalization", () => {
    it("should detect Иёв 1:1 (ё variant) → job 1:1", () => {
      const refs = extractVerseReferences("Иёв 1:1");
      expect(refs.has("job 1:1")).toBe(true);
    });
  });
});

// ── Mixed-script detection ──────────────────────────────────────────────────────

describe("extractVerseReferences — mixed scripts", () => {
  it("should detect Arabic + English refs in same text", () => {
    const refs = extractVerseReferences(
      "See يوحنا 3:16 and also John 3:16 for comparison",
    );
    expect(refs.has("john 3:16")).toBe(true);
    // Both should normalize to same English form
    expect(refs.size).toBe(1);
  });

  it("should detect Chinese + Korean refs in same text", () => {
    const refs = extractVerseReferences(
      "约翰福音 3:16 그리고 시편 23:1을 읽으세요",
    );
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.has("psalms 23:1")).toBe(true);
  });

  it("should detect Russian + Hindi refs in same text", () => {
    const refs = extractVerseReferences("Иоанна 3:16 और यूहन्ना 3:16 एक ही है");
    expect(refs.has("john 3:16")).toBe(true);
    expect(refs.size).toBe(1);
  });
});

// ── Non-Latin conjunction filtering ─────────────────────────────────────────────

describe("extractVerseReferences — non-Latin conjunction filtering", () => {
  it("should not match Arabic و as a book name", () => {
    // و = "and" in Arabic (single char, below 2-char minimum)
    const refs = extractVerseReferences("يوحنا 3:16 و 5:4");
    expect(refs.has("john 3:16")).toBe(true);
    for (const ref of refs) {
      expect(ref).not.toMatch(/^و\s/);
    }
  });
});

// ── isVerseReferenced: non-Latin verse.book vs. English references Set ──────────
// Regression guard for the bug where a Hindi/Korean/Arabic Bible translation
// returns `verse.book` in the localized script, but the `references` Set (built
// from the backend's `verses_cited`) contains capitalized English book names like
// "Philippians 4:7".  The old fuzzy match failed because
// "फिलिप्पियों".startsWith("philippians") === false.

describe("isVerseReferenced — non-Latin verse.book vs. English references Set", () => {
  // ── Hindi ─────────────────────────────────────────────────────────────────

  it("should match Hindi Philippians verse against English-capitalized Set entry", () => {
    // verse.book comes from a Hindi Bible DB row; Set contains backend verses_cited
    const verse = {
      book: "फिलिप्पियों",
      chapter: 4,
      verse: 7,
      reference: "फिलिप्पियों 4:7",
    };
    expect(isVerseReferenced(verse, new Set(["Philippians 4:7"]))).toBe(true);
  });

  it("should match Hindi Isaiah verse against English-capitalized Set entry", () => {
    const verse = {
      book: "यशायाह",
      chapter: 26,
      verse: 3,
      reference: "यशायाह 26:3",
    };
    expect(isVerseReferenced(verse, new Set(["Isaiah 26:3"]))).toBe(true);
  });

  it("should match Hindi John verse against English-capitalized Set entry", () => {
    const verse = {
      book: "यूहन्ना",
      chapter: 3,
      verse: 16,
      reference: "यूहन्ना 3:16",
    };
    expect(isVerseReferenced(verse, new Set(["John 3:16"]))).toBe(true);
  });

  it("should match Hindi Romans verse when Set contains lowercase English", () => {
    // references Set may also hold lowercase-normalized forms
    const verse = {
      book: "रोमियों",
      chapter: 8,
      verse: 28,
      reference: "रोमियों 8:28",
    };
    expect(isVerseReferenced(verse, new Set(["romans 8:28"]))).toBe(true);
  });

  // ── Korean ────────────────────────────────────────────────────────────────

  it("should match Korean Philippians verse against English-capitalized Set entry", () => {
    const verse = {
      book: "빌립보서",
      chapter: 4,
      verse: 13,
      reference: "빌립보서 4:13",
    };
    expect(isVerseReferenced(verse, new Set(["Philippians 4:13"]))).toBe(true);
  });

  it("should match Korean John verse against English-capitalized Set entry", () => {
    const verse = {
      book: "요한복음",
      chapter: 3,
      verse: 16,
      reference: "요한복음 3:16",
    };
    expect(isVerseReferenced(verse, new Set(["John 3:16"]))).toBe(true);
  });

  it("should match Korean Psalms verse against English-capitalized Set entry", () => {
    const verse = {
      book: "시편",
      chapter: 23,
      verse: 1,
      reference: "시편 23:1",
    };
    expect(isVerseReferenced(verse, new Set(["Psalms 23:1"]))).toBe(true);
  });

  // ── Arabic ────────────────────────────────────────────────────────────────

  it("should match Arabic John verse against English-capitalized Set entry", () => {
    const verse = {
      book: "يوحنا",
      chapter: 3,
      verse: 16,
      reference: "يوحنا 3:16",
    };
    expect(isVerseReferenced(verse, new Set(["John 3:16"]))).toBe(true);
  });

  it("should match Arabic Genesis verse against English-capitalized Set entry", () => {
    const verse = {
      book: "تكوين",
      chapter: 1,
      verse: 1,
      reference: "تكوين 1:1",
    };
    expect(isVerseReferenced(verse, new Set(["Genesis 1:1"]))).toBe(true);
  });

  // ── Chinese ───────────────────────────────────────────────────────────────

  it("should match Chinese John verse against English-capitalized Set entry", () => {
    const verse = {
      book: "约翰福音",
      chapter: 3,
      verse: 16,
      reference: "约翰福音 3:16",
    };
    expect(isVerseReferenced(verse, new Set(["John 3:16"]))).toBe(true);
  });

  it("should match Chinese Philippians verse against English-capitalized Set entry", () => {
    const verse = {
      book: "腓立比书",
      chapter: 4,
      verse: 13,
      reference: "腓立比书 4:13",
    };
    expect(isVerseReferenced(verse, new Set(["Philippians 4:13"]))).toBe(true);
  });

  // ── Russian ───────────────────────────────────────────────────────────────

  it("should match Russian John (genitive) verse against English-capitalized Set entry", () => {
    const verse = {
      book: "Иоанна",
      chapter: 3,
      verse: 16,
      reference: "Иоанна 3:16",
    };
    expect(isVerseReferenced(verse, new Set(["John 3:16"]))).toBe(true);
  });

  // ── Negative: still rejects wrong verse ───────────────────────────────────

  it("should not match Hindi Philippians verse against wrong English Set entry", () => {
    const verse = {
      book: "फिलिप्पियों",
      chapter: 4,
      verse: 7,
      reference: "फिलिप्पियों 4:7",
    };
    // Wrong chapter/verse — must not match
    expect(isVerseReferenced(verse, new Set(["Philippians 4:8"]))).toBe(false);
  });

  it("should not match Hindi Isaiah against unrelated English Set entry", () => {
    const verse = {
      book: "यशायाह",
      chapter: 26,
      verse: 3,
      reference: "यशायाह 26:3",
    };
    expect(isVerseReferenced(verse, new Set(["Romans 8:28"]))).toBe(false);
  });
});
