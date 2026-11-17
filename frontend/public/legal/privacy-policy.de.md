---
lastUpdated: 2026-11-16
---

# Datenschutzrichtlinie

> _Diese Übersetzung wurde von einer KI erstellt und dient ausschließlich der Bequemlichkeit. Bei Auslassungen, Unklarheiten oder Widersprüchen zum englischen Original ist die englische Fassung verbindlich und vorrangig._

Letzte Aktualisierung: 16. November 2026

## Wer wir sind

Vox Quieta („wir", „uns", „unser") ist eine kostenlose App zur Bibelinspiration. Unsere Website ist [https://voxquieta.org](https://voxquieta.org).

## Welche Daten wir erheben

### Von dir bereitgestellte Daten

- **Chat-Nachrichten**: Der von dir eingegebene Text wird an unsere API gesendet, die ihn ausschließlich zur Erzeugung einer auf der Heiligen Schrift basierenden Antwort und zur Sicherheitsprüfung an Dritt-KI-Dienstleister (siehe unten) weiterleitet. Wir speichern deine Nachrichten nicht länger auf unseren Servern, als es zur Generierung einer Antwort notwendig ist – ausgenommen Nachrichten, die unser Sicherheitssystem blockiert; diese können bis zu 30 Tage gespeichert werden, wie unter „Datenspeicherung“ beschrieben. Nachrichten, die du durch das Absenden von Feedback bewertest, werden wie unter „Feedback“ beschrieben gespeichert.
- **Feedback**: Optionale Daumen-hoch-/Daumen-runter-Bewertungen, die du für Antworten abgibst, mit optionalem Grund und Kommentar. Wenn du Feedback sendest, speichern wir deine Nachricht, die KI-Antwort und deinen Kommentar 30 Tage lang sowie die Bewertung, den Grund, die Nachrichten-ID und technische Angaben (Modell, Antwortzeit, Bibelstellenangaben) 90 Tage lang – ausschließlich, um unsere Antworten zu verbessern. Deine Sitzungs-ID wird nur als Einweg-Hash gespeichert.
- **Kontaktformular**: Wenn du uns über das Kontaktformular schreibst, speichern wir den Betreff, deine Nachricht und die von dir angegebene E-Mail-Adresse 90 Tage lang – ausschließlich, um dir zu antworten. Deine Sitzungs-ID wird nur als Einweg-Hash gespeichert; Angaben zu deinem Browser oder Gerät werden nicht gespeichert.

### Wie deine Nachrichten durch KI verarbeitet werden

Um deine Fragen zu beantworten, sendet unsere API den Text deiner Nachricht an die folgenden Dritt-KI-Anbieter:

- **OpenRouter** — erhält deinen Nachrichtentext, um die auf der Heiligen Schrift basierende Antwort zu erzeugen (Sprachmodell-Vervollständigung) und um Nachrichten auf Sicherheit zu prüfen (Llama-Guard-Inhaltssicherheitsprüfung).
- **Azure OpenAI (Microsoft)** — erhält deinen Nachrichtentext, um Text-Embeddings zu berechnen, mit denen die relevantesten Bibelstellen gefunden werden.
- **OpenAI** — erhält deinen Nachrichtentext nur dann, wenn unsere primäre Sicherheitsprüfung (Llama Guard) vorübergehend nicht verfügbar ist, um ihn auf Sicherheit zu prüfen (OpenAI Moderation).

Dein Nachrichtentext wird von diesen Anbietern **ausschließlich** verwendet, um die Antwort auf diese Nachricht zu erzeugen oder auf Sicherheit zu prüfen. Er wird weder von uns noch — gemäß den API-Bedingungen des jeweiligen Anbieters — vom Anbieter zum Training ihrer allgemeinen KI-Modelle verwendet und niemals für Werbung genutzt oder verkauft. Jeder Anbieter darf ihn nach seinen eigenen Datenverarbeitungsbedingungen speichern: OpenAI bewahrt den Nachrichtentext, den es erhält, bis zu 30 Tage zur Missbrauchsüberwachung auf; danach wird er gelöscht, sofern das Gesetz nichts anderes verlangt. Siehe die [Datenschutzrichtlinie von OpenRouter](https://openrouter.ai/privacy), die [Datenschutzerklärung von Microsoft](https://privacy.microsoft.com) und die [Datenschutzzusagen von OpenAI für die API](https://openai.com/enterprise-privacy/) für die jeweiligen Datenverarbeitungspraktiken.

### Automatisch erhobene Daten

- **Absturzberichte**: Wenn die App abstürzt, erfasst Firebase Crashlytics anonymisierte Diagnosedaten (Gerätemodell, Betriebssystemversion, App-Version, Stack-Trace). Persönliche Kennzeichen sind nicht enthalten.
- **Nutzungsanalysen**: Firebase Analytics erfasst anonymisierte Nutzungsereignisse (Bildschirmaufrufe, Funktionsinteraktionen), um uns bei der Verbesserung der App zu helfen. Persönliche Kennzeichen sind nicht enthalten.

### Daten, die wir NICHT erheben

- Wir verlangen keine Kontoregistrierung.
- Wir erheben nicht deinen Namen, deine E-Mail-Adresse oder Telefonnummer – mit Ausnahme der E-Mail-Adresse, die du selbst im Kontaktformular angibst.
- Wir verfolgen deinen Standort nicht.
- **Ungefähres Land, nur für Notrufnummern**: Wenn deine Nachricht darauf hindeutet, dass du oder jemand anderes in Gefahr sein könnte, leiten wir dein Land aus deiner Verbindung (dem Länder-Header von Cloudflare) oder der Sprache deines Geräts ab – ausschließlich, um die richtigen örtlichen Notruf- und Krisennummern anzuzeigen. Es wird niemals auf unseren Servern gespeichert; die Karte wird nur zusammen mit deiner Unterhaltung auf deinem Gerät gespeichert. Wählst du auf der Karte ein anderes Land aus, wird dieses nur an uns gesendet, um dessen Nummern nachzuschlagen, und nicht auf unseren Servern gespeichert.
- Wir verkaufen deine Daten nicht an Dritte.

## Gesprächsverlauf

Der Gesprächsverlauf wird **ausschließlich lokal auf deinem Gerät** gespeichert und niemals auf unsere Server hochgeladen – ausgenommen eine Nachricht und Antwort, die du bewertest (siehe „Feedback“):

- **Mobile App:** eine verschlüsselte On-Device-Datenbank (Room/SQLite).
- **Web-App:** der lokale Speicher deines Browsers (IndexedDB) auf dem von dir genutzten Gerät.

Du kannst diesen Verlauf jederzeit ansehen, umbenennen, löschen oder vollständig entfernen. Du kannst ihn außerdem als **mit einer Passphrase verschlüsselte Datei** exportieren, um ihn auf ein anderes deiner Geräte zu übertragen – die Datei ist mit einer nur dir bekannten Passphrase verschlüsselt und bleibt so auch bei der Übertragung in deiner Hand.

## Drittanbieterdienste

| Dienst                        | Zweck                                                                                                                 | Datenschutzrichtlinie                                                   |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Firebase Crashlytics (Google) | Absturzberichte                                                                                                       | [policies.google.com/privacy](https://policies.google.com/privacy)      |
| Firebase Analytics (Google)   | Anonymisierte Nutzungsanalysen                                                                                        | [policies.google.com/privacy](https://policies.google.com/privacy)      |
| OpenRouter                    | KI-Antworterzeugung und Inhaltssicherheitsprüfung                                                                     | [openrouter.ai/privacy](https://openrouter.ai/privacy)                  |
| Azure OpenAI (Microsoft)      | Text-Embeddings für die Bibelstellensuche                                                                             | [privacy.microsoft.com](https://privacy.microsoft.com)                  |
| OpenAI                        | Ersatz-Inhaltssicherheitsprüfung (nur wenn die primäre Prüfung nicht verfügbar ist)                                   | [openai.com/enterprise-privacy](https://openai.com/enterprise-privacy/) |
| SMTP2GO                       | E-Mail-Benachrichtigungen an den Betreiber zu Feedback und Kontaktnachrichten; sie enthalten keine Nachrichteninhalte | [smtp2go.com/privacy](https://www.smtp2go.com/privacy/)                 |

## Vorlesen

Die Schaltfläche „Anhören“ liest Antworten mit der in deinem Browser eingebauten Sprachsynthese vor. Standardmäßig werden nur Offline-Stimmen verwendet, die auf deinem Gerät installiert sind. Der Text der Antwort verlässt dein Gerät für diese Funktion also nicht.

Einige Browser bieten für deine Sprache nur Online-Stimmen an. Eine Online-Stimme verwenden wir nur, wenn du „Online-Stimmen erlauben“ wählst. Dann sendet dein Browser den Text der vorgelesenen Antwort an den Sprachdienst des Browser-Herstellers (zum Beispiel Google, Microsoft oder Apple), der ihn nach seinen eigenen Bedingungen verarbeitet; wir erhalten oder speichern ihn nicht. Deine Entscheidung wird nur auf deinem Gerät gespeichert und kann jederzeit mit dem Schalter „Online-Stimmen erlauben“ im Menü widerrufen werden; dadurch wird auch ein laufendes Vorlesen beendet.

Wir zählen die Nutzung der Vorlesefunktion anonym nach Sprache, Browser-Familie und Betriebssystem-Familie (zum Beispiel „Firefox unter Linux“), um zu erkennen, wo die Funktion funktioniert und wo nicht. Diese Zählungen enthalten weder Text noch Stimmnamen, User-Agent-Zeichenfolgen, IP-Adressen oder Kennungen.

## Datenspeicherung

- **Chat-Nachrichten**: nicht auf unseren Servern gespeichert, ausgenommen von unserem Sicherheitssystem blockierte Nachrichten (siehe unten). Nachrichten, die du durch das Absenden von Feedback bewertest, werden wie unter „Feedback“ beschrieben gespeichert.
- **Vom Sicherheitssystem blockierte Nachrichten**: Wenn unser
  Sicherheitssystem eine Nachricht blockiert, kann ein
  datenschutzminimaler Eintrag kurzzeitig (bis zu 30 Tage) aufbewahrt
  werden, damit wir den Filter verbessern können. Der Eintrag enthält
  den Nachrichtentext (in der Länge begrenzt), welche Sicherheitsstufe
  ihn blockiert hat, und einen Einweg-Hash der Sitzungs-ID. Wir
  speichern weder deine IP-Adresse noch deinen Account noch einen
  User-Agent-String mit diesen Einträgen, und sie werden ausschließlich
  zur Verbesserung des Sicherheitsfilters verwendet.
- **Anonyme Statistiken zur Suchqualität**: um zu verbessern, wie wir
  passende Bibelstellen finden, können wir anonyme Einträge bis zu 90 Tage
  aufbewahren, wenn eine Suche schwache oder keine Ergebnisse liefert. Ein
  Eintrag enthält nur abgeleitete Informationen: die erkannten Themen, die
  Sprache und die Bibelübersetzung, Relevanzwerte, Bibelstellenangaben und
  einen Einweg-Hash der Sitzungs-ID. Er enthält niemals den Text deiner
  Nachricht oder der Antwort, und wir speichern weder deine IP-Adresse noch
  deinen Account noch einen User-Agent-String damit. Diese Einträge werden
  ausschließlich zur Verbesserung der Suchqualität verwendet.
- **Feedback**: Deine Nachricht, die KI-Antwort und dein Kommentar werden 30 Tage lang aufbewahrt und danach gelöscht. Der übrige Feedback-Eintrag (Bewertung, Grund, Nachrichten-ID, Modell, Antwortzeit, Bibelstellenangaben und ein Einweg-Hash der Sitzungs-ID) wird 90 Tage lang aufbewahrt und danach gelöscht. Die Benachrichtigungs-E-Mails, die wir erhalten, enthalten keinen Nachrichtentext.
- **Nachrichten über das Kontaktformular**: Betreff, Nachricht, die von dir angegebene E-Mail-Adresse und ein Einweg-Hash der Sitzungs-ID werden 90 Tage lang aufbewahrt und danach gelöscht. Sie werden ausschließlich verwendet, um dir zu antworten.
- **Absturzberichte und Analysen**: von Google bis zu 14 Monate gemäß deren Standardrichtlinie aufbewahrt.
- **Lokaler Gesprächsverlauf**: auf deinem Gerät gespeichert, bis du ihn über die App löschst oder die App deinstallierst.

## Deine Rechte (DSGVO)

Wenn du dich im Europäischen Wirtschaftsraum befindest, hast du das Recht:

- auf die über dich gespeicherten personenbezogenen Daten zuzugreifen,
- die Löschung deiner Daten zu verlangen,
- der Verarbeitung deiner Daten zu widersprechen.

Wir verlangen kein Konto, daher können die meisten Anfragen durch das Löschen deines lokalen Gesprächsverlaufs in der App erfüllt werden. Feedback-Daten und Nachrichten aus dem Kontaktformular können wir auf Anfrage finden und löschen: Sende uns die Nachrichten-ID oder Datum und ungefähre Uhrzeit des Absendens (Feedback) oder die verwendete E-Mail-Adresse (Kontaktformular) an die unten genannte Adresse. Einträge zu Nachrichten, die unser Sicherheitssystem blockiert hat, werden ohne IP-Adresse, Konto oder Geräteangaben gespeichert und innerhalb von 30 Tagen automatisch gelöscht; da sie nicht mit deiner Identität verknüpft sind, können wir in der Regel nicht erkennen, welcher Eintrag von dir stammt – du kannst uns dazu aber unter der unten genannten Adresse kontaktieren. Für Absturz-/Analysedaten bei Google konsultiere bitte die Datenschutzeinstellungen von Google unter [myaccount.google.com](https://myaccount.google.com). Für Daten, die von unseren KI-Anbietern verarbeitet werden, siehe die oben verlinkten Datenschutzrichtlinien von OpenRouter, Microsoft und OpenAI.

Bei Fragen zum Datenschutz erreichst du uns unter: **<privacy@voxquieta.org>**

## Änderungen dieser Richtlinie

Wesentliche Änderungen werden auf dieser Seite veröffentlicht und das Datum „Letzte Aktualisierung" wird angepasst. Die weitere Nutzung der App nach Änderungen gilt als Zustimmung zur aktualisierten Richtlinie.
