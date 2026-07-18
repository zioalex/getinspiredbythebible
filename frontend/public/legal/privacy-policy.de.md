---
lastUpdated: 2026-07-18
---

# Datenschutzrichtlinie

> _Diese Übersetzung wurde von einer KI erstellt und dient ausschließlich der Bequemlichkeit. Bei Auslassungen, Unklarheiten oder Widersprüchen zum englischen Original ist die englische Fassung verbindlich und vorrangig._

Letzte Aktualisierung: 18. Juli 2026

## Wer wir sind

Vox Quieta („wir", „uns", „unser") ist eine kostenlose App zur Bibelinspiration. Unsere Website ist [https://voxquieta.org](https://voxquieta.org).

## Welche Daten wir erheben

### Von dir bereitgestellte Daten

- **Chat-Nachrichten**: Der von dir eingegebene Text wird an unsere API gesendet, die ihn ausschließlich zur Erzeugung einer auf der Heiligen Schrift basierenden Antwort und zur Sicherheitsprüfung an Dritt-KI-Dienstleister (siehe unten) weiterleitet. Wir speichern deine Nachrichten nicht länger auf unseren Servern, als es zur Generierung einer Antwort notwendig ist.
- **Feedback-Bewertungen**: Optionale Daumen-hoch-/Daumen-runter-Bewertungen, die du für Antworten abgibst.

### Wie deine Nachrichten durch KI verarbeitet werden

Um deine Fragen zu beantworten, sendet unsere API den Text deiner Nachricht an die folgenden Dritt-KI-Anbieter:

- **OpenRouter** — erhält deinen Nachrichtentext, um die auf der Heiligen Schrift basierende Antwort zu erzeugen (Sprachmodell-Vervollständigung) und um Nachrichten auf Sicherheit zu prüfen (Llama-Guard-Inhaltssicherheitsprüfung).
- **Azure OpenAI (Microsoft)** — erhält deinen Nachrichtentext, um Text-Embeddings zu berechnen, mit denen die relevantesten Bibelstellen gefunden werden.

Dein Nachrichtentext wird von diesen Anbietern **ausschließlich** verwendet, um die Antwort auf diese Nachricht zu erzeugen oder auf Sicherheit zu prüfen. Er wird weder von uns noch — gemäß den API-Bedingungen des jeweiligen Anbieters — vom Anbieter zum Training ihrer allgemeinen KI-Modelle verwendet, nicht länger vom Anbieter aufbewahrt, als zur Bearbeitung der Anfrage nötig ist, und niemals für Werbung genutzt oder verkauft. Siehe die [Datenschutzrichtlinie von OpenRouter](https://openrouter.ai/privacy) und die [Datenschutzerklärung von Microsoft](https://privacy.microsoft.com) für die jeweiligen Datenverarbeitungspraktiken.

### Automatisch erhobene Daten

- **Absturzberichte**: Wenn die App abstürzt, erfasst Firebase Crashlytics anonymisierte Diagnosedaten (Gerätemodell, Betriebssystemversion, App-Version, Stack-Trace). Persönliche Kennzeichen sind nicht enthalten.
- **Nutzungsanalysen**: Firebase Analytics erfasst anonymisierte Nutzungsereignisse (Bildschirmaufrufe, Funktionsinteraktionen), um uns bei der Verbesserung der App zu helfen. Persönliche Kennzeichen sind nicht enthalten.

### Daten, die wir NICHT erheben

- Wir verlangen keine Kontoregistrierung.
- Wir erheben nicht deinen Namen, deine E-Mail-Adresse oder Telefonnummer.
- Wir verfolgen deinen Standort nicht.
- Wir verkaufen deine Daten nicht an Dritte.

## Gesprächsverlauf

Der Gesprächsverlauf wird **ausschließlich lokal auf deinem Gerät** in einer verschlüsselten On-Device-Datenbank (Room/SQLite) gespeichert. Er wird niemals auf unsere Server hochgeladen.

## Drittanbieterdienste

| Dienst                        | Zweck                                             | Datenschutzrichtlinie                                              |
| ----------------------------- | ------------------------------------------------- | ------------------------------------------------------------------ |
| Firebase Crashlytics (Google) | Absturzberichte                                   | [policies.google.com/privacy](https://policies.google.com/privacy) |
| Firebase Analytics (Google)   | Anonymisierte Nutzungsanalysen                    | [policies.google.com/privacy](https://policies.google.com/privacy) |
| OpenRouter                    | KI-Antworterzeugung und Inhaltssicherheitsprüfung | [openrouter.ai/privacy](https://openrouter.ai/privacy)             |
| Azure OpenAI (Microsoft)      | Text-Embeddings für die Bibelstellensuche         | [privacy.microsoft.com](https://privacy.microsoft.com)             |

## Datenspeicherung

- **Chat-Nachrichten**: nicht auf unseren Servern gespeichert.
- **Vom Sicherheitssystem blockierte Nachrichten**: Wenn unser
  Sicherheitssystem eine Nachricht blockiert, kann ein
  datenschutzminimaler Eintrag kurzzeitig (bis zu 30 Tage) aufbewahrt
  werden, damit wir den Filter verbessern können. Der Eintrag enthält
  den Nachrichtentext (in der Länge begrenzt), welche Sicherheitsstufe
  ihn blockiert hat, und einen Einweg-Hash der Sitzungs-ID. Wir
  speichern weder deine IP-Adresse noch deinen Account noch einen
  User-Agent-String mit diesen Einträgen, und sie werden ausschließlich
  zur Verbesserung des Sicherheitsfilters verwendet.
- **Absturzberichte und Analysen**: von Google bis zu 14 Monate gemäß deren Standardrichtlinie aufbewahrt.
- **Lokaler Gesprächsverlauf**: auf deinem Gerät gespeichert, bis du ihn über die App löschst oder die App deinstallierst.

## Deine Rechte (DSGVO)

Wenn du dich im Europäischen Wirtschaftsraum befindest, hast du das Recht:

- auf die über dich gespeicherten personenbezogenen Daten zuzugreifen,
- die Löschung deiner Daten zu verlangen,
- der Verarbeitung deiner Daten zu widersprechen.

Da wir keine personenbezogenen Daten erheben, können die meisten Anfragen durch das Löschen deines lokalen Gesprächsverlaufs in der App erfüllt werden. Für Absturz-/Analysedaten bei Google konsultiere bitte die Datenschutzeinstellungen von Google unter [myaccount.google.com](https://myaccount.google.com). Für Daten, die von unseren KI-Anbietern verarbeitet werden, siehe die oben verlinkten Datenschutzrichtlinien von OpenRouter und Microsoft.

Bei Fragen zum Datenschutz erreichst du uns unter: **<privacy@voxquieta.org>**

## Änderungen dieser Richtlinie

Wesentliche Änderungen werden auf dieser Seite veröffentlicht und das Datum „Letzte Aktualisierung" wird angepasst. Die weitere Nutzung der App nach Änderungen gilt als Zustimmung zur aktualisierten Richtlinie.
