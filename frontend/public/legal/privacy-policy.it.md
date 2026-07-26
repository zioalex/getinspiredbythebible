---
lastUpdated: 2026-07-18
---

# Informativa sulla privacy

> _Questa traduzione è stata generata dall'intelligenza artificiale ed è fornita esclusivamente per comodità. In caso di omissioni, ambiguità o contraddizioni rispetto all'originale inglese, prevale la versione inglese, che resta canonica._

Ultimo aggiornamento: 18 luglio 2026

## Chi siamo

Vox Quieta ("noi", "ci", "nostro") è un'app gratuita di ispirazione biblica. Il nostro sito è [https://voxquieta.org](https://voxquieta.org).

## Dati che raccogliamo

### Dati che fornisci tu

- **Messaggi della chat**: il testo che digiti viene inviato alla nostra API, che lo inoltra a fornitori terzi di servizi di IA (elencati di seguito) esclusivamente per generare una risposta basata sulle Scritture e verificarne la sicurezza. Non conserviamo i tuoi messaggi sui nostri server oltre il tempo necessario a generare la risposta.
- **Valutazioni del feedback**: le valutazioni opzionali (pollice su/pollice giù) che invii sulle risposte.

### Come i tuoi messaggi vengono elaborati dall'IA

Per rispondere alle tue domande, la nostra API invia il testo del tuo messaggio ai seguenti fornitori terzi di IA:

- **OpenRouter** — riceve il testo del tuo messaggio per generare la risposta basata sulle Scritture (completamento tramite modello linguistico) e per verificare la sicurezza dei messaggi (controllo di sicurezza dei contenuti Llama Guard).
- **Azure OpenAI (Microsoft)** — riceve il testo del tuo messaggio per calcolare gli embedding testuali usati per trovare i passi biblici più pertinenti.

Il testo del tuo messaggio viene utilizzato da questi fornitori **esclusivamente** per generare la risposta a quel messaggio o verificarne la sicurezza. Non viene utilizzato da noi — né, secondo i termini API di ciascun fornitore, dal fornitore — per addestrare i loro modelli di IA generici, non viene conservato dal fornitore oltre quanto necessario per elaborare la richiesta e non viene mai usato a fini pubblicitari né venduto. Consulta l'[informativa sulla privacy di OpenRouter](https://openrouter.ai/privacy) e l'[informativa sulla privacy di Microsoft](https://privacy.microsoft.com) per le rispettive pratiche di trattamento dei dati.

### Dati raccolti automaticamente

- **Segnalazioni di crash**: in caso di arresto anomalo dell'app, Firebase Crashlytics raccoglie informazioni diagnostiche anonime (modello del dispositivo, versione del sistema operativo, versione dell'app, stack trace). Non sono inclusi identificatori personali.
- **Analisi dell'utilizzo**: Firebase Analytics raccoglie eventi di utilizzo anonimi (visualizzazioni di schermata, interazioni con le funzionalità) per aiutarci a migliorare l'app. Non sono inclusi identificatori personali.

### Dati che NON raccogliamo

- Non richiediamo la registrazione di un account.
- Non raccogliamo nome, indirizzo e-mail o numero di telefono.
- Non tracciamo la tua posizione.
- Non vendiamo i tuoi dati a terze parti.

## Cronologia delle conversazioni

La cronologia delle conversazioni è archiviata **solo localmente sul tuo dispositivo** e non viene mai caricata sui nostri server:

- **App mobile:** un database cifrato on-device (Room/SQLite).
- **App web:** l'archiviazione locale del browser (IndexedDB), sul dispositivo che usi.

Puoi visualizzare, rinominare, eliminare o cancellare questa cronologia in qualsiasi momento. Puoi anche esportarla come **file cifrato con passphrase** per spostarla su un altro dei tuoi dispositivi: il file è cifrato con una passphrase che conosci solo tu, quindi resta nelle tue mani anche durante il trasferimento.

## Servizi di terze parti

| Servizio                      | Scopo                                                             | Informativa sulla privacy                                          |
| ----------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------ |
| Firebase Crashlytics (Google) | Segnalazione di crash                                             | [policies.google.com/privacy](https://policies.google.com/privacy) |
| Firebase Analytics (Google)   | Analisi anonima dell'utilizzo                                     | [policies.google.com/privacy](https://policies.google.com/privacy) |
| OpenRouter                    | Generazione di risposte IA e controllo di sicurezza dei contenuti | [openrouter.ai/privacy](https://openrouter.ai/privacy)             |
| Azure OpenAI (Microsoft)      | Embedding testuali per la ricerca dei passi biblici               | [privacy.microsoft.com](https://privacy.microsoft.com)             |

## Conservazione dei dati

- **Messaggi della chat**: non conservati sui nostri server.
- **Messaggi bloccati dal nostro sistema di sicurezza**: quando il nostro
  sistema di sicurezza blocca un messaggio, può essere conservato un record
  minimo dal punto di vista della privacy per un breve periodo (fino a 30
  giorni) per aiutarci a migliorare il filtro. Il record contiene il testo
  del messaggio (con lunghezza massima), quale stadio di sicurezza lo ha
  bloccato e un hash unidirezionale dell'identificatore di sessione. Non
  memorizziamo il tuo indirizzo IP, il tuo account né alcuna stringa
  user-agent con questi record, e non vengono utilizzati per scopi diversi
  dalla messa a punto del filtro di sicurezza.
- **Segnalazioni di crash e analisi**: conservati da Google fino a 14 mesi secondo la loro policy standard.
- **Cronologia locale delle conversazioni**: archiviata sul tuo dispositivo fino a quando non la elimini tramite l'app o disinstalli l'app.

## I tuoi diritti (GDPR)

Se ti trovi nello Spazio Economico Europeo, hai il diritto di:

- Accedere ai dati personali che deteniamo su di te.
- Richiedere la cancellazione dei tuoi dati.
- Opporti al trattamento dei tuoi dati.

Poiché non raccogliamo informazioni personali identificabili, la maggior parte delle richieste può essere soddisfatta cancellando la cronologia locale delle conversazioni nell'app. Per i dati di crash/analisi detenuti da Google, consulta i controlli sulla privacy di Google su [myaccount.google.com](https://myaccount.google.com). Per i dati trattati dai nostri fornitori di IA, consulta le informative sulla privacy di OpenRouter e Microsoft linkate sopra.

Per qualsiasi domanda sulla privacy, contattaci a: **<privacy@voxquieta.org>**

## Modifiche a questa policy

Pubblicheremo eventuali modifiche sostanziali in questa pagina e aggiorneremo la data di "Ultimo aggiornamento". L'uso continuato dell'app dopo le modifiche costituisce accettazione della policy aggiornata.
