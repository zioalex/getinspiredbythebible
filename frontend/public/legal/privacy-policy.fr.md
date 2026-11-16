---
lastUpdated: 2026-11-16
---

# Politique de confidentialité

> _Cette traduction a été générée par intelligence artificielle et est fournie à titre de commodité uniquement. En cas d'omission, d'ambiguïté ou de contradiction avec l'original anglais, la version anglaise fait foi et prévaut._

Dernière mise à jour : 16 novembre 2026

## Qui nous sommes

Vox Quieta (« nous », « notre ») est une application gratuite d'inspiration biblique. Notre site web est [https://voxquieta.org](https://voxquieta.org).

## Quelles données nous collectons

### Données que vous fournissez

- **Messages de chat** : le texte que vous saisissez est envoyé à notre API, qui le transmet à des prestataires tiers de services d'IA (listés ci-dessous) uniquement pour générer une réponse basée sur les Écritures et en vérifier la sécurité. Nous ne conservons pas vos messages sur nos serveurs au-delà du temps nécessaire pour générer une réponse, sauf les messages bloqués par notre système de sécurité, qui peuvent être conservés jusqu'à 30 jours comme décrit dans « Conservation des données ». Les messages que vous évaluez en envoyant un retour sont conservés comme décrit dans « Retours et évaluations ».
- **Retours et évaluations** : évaluations optionnelles pouce levé/pouce baissé que vous soumettez sur les réponses, avec un motif et un commentaire facultatifs. Lorsque vous envoyez un retour, nous conservons votre message, la réponse de l'IA et votre commentaire pendant 30 jours, et l'évaluation, le motif, l'identifiant du message et des détails techniques (modèle, temps de réponse, références de versets) pendant 90 jours, uniquement pour améliorer nos réponses. Votre identifiant de session n'est conservé que sous forme de hachage à sens unique.
- **Formulaire de contact** : si vous nous écrivez via le formulaire de contact, nous conservons l'objet, votre message et l'adresse e-mail que vous indiquez pendant 90 jours, uniquement pour vous répondre. Votre identifiant de session n'est conservé que sous forme de hachage à sens unique, et les informations sur votre navigateur ou votre appareil ne sont pas enregistrées.

### Comment vos messages sont traités par l'IA

Pour répondre à vos questions, notre API envoie le texte de votre message aux fournisseurs d'IA tiers suivants :

- **OpenRouter** — reçoit le texte de votre message pour générer la réponse basée sur les Écritures (complétion par grand modèle de langage) et pour vérifier la sécurité des messages (contrôle de sécurité du contenu Llama Guard).
- **Azure OpenAI (Microsoft)** — reçoit le texte de votre message pour calculer les représentations vectorielles (embeddings) utilisées pour trouver les passages bibliques les plus pertinents.
- **OpenAI** — reçoit le texte de votre message uniquement lorsque notre contrôle de sécurité principal (Llama Guard) est temporairement indisponible, afin d'en vérifier la sécurité (OpenAI Moderation).

Le texte de votre message est utilisé par ces fournisseurs **uniquement** pour générer la réponse à ce message ou en vérifier la sécurité. Il n'est pas utilisé par nous — ni, conformément aux conditions d'utilisation de l'API de chaque fournisseur, par le fournisseur — pour entraîner leurs modèles d'IA à usage général, et il n'est jamais utilisé à des fins publicitaires ni vendu. Chaque fournisseur peut le conserver selon ses propres conditions de traitement des données : OpenAI conserve le texte des messages qu'il reçoit pendant 30 jours au maximum à des fins de détection des abus, après quoi il est supprimé, sauf obligation légale contraire. Consultez la [politique de confidentialité d'OpenRouter](https://openrouter.ai/privacy), la [déclaration de confidentialité de Microsoft](https://privacy.microsoft.com) et les [engagements d'OpenAI sur la confidentialité des données de l'API](https://openai.com/enterprise-privacy/) pour connaître les pratiques de traitement des données de chaque fournisseur.

### Données collectées automatiquement

- **Rapports de plantage** : en cas de plantage de l'application, Firebase Crashlytics collecte des informations de diagnostic anonymisées (modèle de l'appareil, version du système d'exploitation, version de l'application, trace de la pile). Aucun identifiant personnel n'est inclus.
- **Analyses d'utilisation** : Firebase Analytics collecte des événements d'utilisation anonymisés (vues d'écran, interactions avec les fonctionnalités) pour nous aider à améliorer l'application. Aucun identifiant personnel n'est inclus.

### Données que nous ne collectons PAS

- Nous n'exigeons pas d'inscription à un compte.
- Nous ne collectons pas votre nom, adresse e-mail ni numéro de téléphone, à l'exception de l'adresse e-mail que vous choisissez d'indiquer dans le formulaire de contact.
- Nous ne suivons pas votre localisation.
- **Pays approximatif, uniquement pour les numéros d'urgence** : si votre message laisse penser que vous ou quelqu'un d'autre pourriez être en danger, nous déduisons votre pays de votre connexion (l'en-tête de pays de Cloudflare) ou de la langue de votre appareil, uniquement pour afficher les bons numéros d'urgence et d'aide locaux. Il n'est jamais enregistré sur nos serveurs ; la carte n'est conservée qu'avec votre conversation, sur votre appareil. Si vous choisissez un autre pays sur la carte, ce pays nous est envoyé uniquement pour rechercher ses numéros et n'est pas enregistré sur nos serveurs.
- Nous ne vendons pas vos données à des tiers.

## Historique des conversations

L'historique des conversations est stocké **uniquement en local sur votre appareil** et n'est jamais téléchargé sur nos serveurs :

- **Application mobile :** une base de données chiffrée sur l'appareil (Room/SQLite).
- **Application web :** le stockage local de votre navigateur (IndexedDB), sur l'appareil que vous utilisez.

Vous pouvez consulter, renommer, supprimer ou effacer cet historique à tout moment. Vous pouvez également l'exporter sous forme de **fichier chiffré par une phrase secrète** afin de le transférer vers un autre de vos appareils : le fichier est chiffré avec une phrase que vous seul connaissez, il reste donc entre vos mains même pendant le transfert.

## Services tiers

| Service                       | Objectif                                                                                                                                | Politique de confidentialité                                            |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Firebase Crashlytics (Google) | Rapports de plantage                                                                                                                    | [policies.google.com/privacy](https://policies.google.com/privacy)      |
| Firebase Analytics (Google)   | Analyses d'utilisation anonymisées                                                                                                      | [policies.google.com/privacy](https://policies.google.com/privacy)      |
| OpenRouter                    | Génération de réponses IA et contrôle de sécurité du contenu                                                                            | [openrouter.ai/privacy](https://openrouter.ai/privacy)                  |
| Azure OpenAI (Microsoft)      | Embeddings de texte pour la recherche de passages bibliques                                                                             | [privacy.microsoft.com](https://privacy.microsoft.com)                  |
| OpenAI                        | Contrôle de sécurité du contenu de secours (uniquement si le contrôle principal est indisponible)                                       | [openai.com/enterprise-privacy](https://openai.com/enterprise-privacy/) |
| SMTP2GO                       | Notifications par e-mail à l'exploitant au sujet des retours et des messages de contact ; elles ne contiennent aucun contenu de message | [smtp2go.com/privacy](https://www.smtp2go.com/privacy/)                 |

## Lecture à voix haute

Le bouton Écouter lit les réponses à voix haute avec la synthèse vocale intégrée à votre navigateur. Par défaut, il n'utilise que des voix hors ligne installées sur votre appareil ; le texte de la réponse ne quitte donc pas votre appareil pour cette fonction.

Certains navigateurs ne proposent que des voix en ligne pour votre langue. Nous n'utilisons une voix en ligne que si vous choisissez « Autoriser les voix en ligne ». Dans ce cas, votre navigateur envoie le texte de la réponse lue au service vocal de l'éditeur du navigateur (par exemple Google, Microsoft ou Apple), qui le traite selon ses propres conditions ; nous ne le recevons ni ne le conservons. Votre choix est enregistré uniquement sur votre appareil et vous pouvez le révoquer à tout moment avec l'interrupteur « Autoriser les voix en ligne » du menu, ce qui arrête aussi toute lecture en cours.

Nous comptabilisons l'utilisation de la lecture à voix haute de manière anonyme, par langue, famille de navigateur et famille de système d'exploitation (par exemple « Firefox sous Linux »), afin de savoir où la fonction marche et où elle échoue. Ces compteurs ne contiennent aucun texte, nom de voix, chaîne user-agent, adresse IP ni identifiant.

## Conservation des données

- **Messages de chat** : non conservés sur nos serveurs, sauf les messages bloqués par notre système de sécurité (voir ci-dessous). Les messages que vous évaluez en envoyant un retour sont conservés comme décrit dans « Retours et évaluations ».
- **Messages bloqués par notre système de sécurité** : lorsque notre
  système de sécurité bloque un message, un enregistrement minimal du
  point de vue de la confidentialité peut être conservé brièvement
  (jusqu'à 30 jours) pour nous aider à améliorer le filtre.
  L'enregistrement contient le texte du message (avec une longueur
  limitée), l'étape de sécurité qui l'a bloqué et un hachage à sens
  unique de l'identifiant de session. Nous ne stockons ni votre
  adresse IP, ni votre compte, ni aucune chaîne user-agent avec ces
  enregistrements, et ils ne sont utilisés que pour affiner le filtre
  de sécurité.
- **Statistiques anonymes de qualité de recherche** : pour améliorer la
  façon dont nous trouvons les passages bibliques pertinents, nous pouvons
  conserver des enregistrements anonymes jusqu'à 90 jours lorsqu'une
  recherche renvoie des résultats faibles ou aucun résultat. Un
  enregistrement ne contient que des informations dérivées : les thèmes
  détectés, la langue et la traduction biblique, les scores de pertinence,
  les références de versets et un hachage à sens unique de l'identifiant de
  session. Il ne contient jamais le texte de votre message ni de la
  réponse, et nous ne stockons ni votre adresse IP, ni votre compte, ni
  aucune chaîne user-agent avec lui. Ces enregistrements ne sont utilisés
  que pour améliorer la qualité de la recherche.
- **Retours et évaluations** : votre message, la réponse de l'IA et votre commentaire sont conservés 30 jours, puis supprimés. Le reste de l'enregistrement (évaluation, motif, identifiant du message, modèle, temps de réponse, références de versets et un hachage à sens unique de l'identifiant de session) est conservé 90 jours, puis supprimé. Les e-mails de notification que nous recevons ne contiennent aucun texte de message.
- **Messages du formulaire de contact** : l'objet, le message, l'adresse e-mail que vous avez indiquée et un hachage à sens unique de l'identifiant de session sont conservés 90 jours, puis supprimés. Ils servent uniquement à vous répondre.
- **Rapports de plantage et analyses** : conservés par Google jusqu'à 14 mois conformément à leur politique standard.
- **Historique local des conversations** : stocké sur votre appareil jusqu'à ce que vous le supprimiez via l'application ou désinstalliez l'application.

## Vos droits (RGPD)

Si vous vous trouvez dans l'Espace économique européen, vous avez le droit :

- d'accéder aux données personnelles que nous détenons sur vous,
- de demander la suppression de vos données,
- de vous opposer au traitement de vos données.

Nous ne vous demandons pas de compte : la plupart des demandes peuvent donc être satisfaites en effaçant votre historique de conversation local dans l'application. Les données de retours et les messages du formulaire de contact peuvent être retrouvés et supprimés sur demande : envoyez-nous l'identifiant du message (retours) ou l'adresse e-mail utilisée (formulaire de contact) à l'adresse indiquée ci-dessous. Les enregistrements des messages bloqués par notre système de sécurité sont conservés sans votre adresse IP, votre compte ni les informations de votre appareil, et sont supprimés automatiquement sous 30 jours ; comme ils ne sont pas liés à votre identité, nous ne pouvons généralement pas savoir lequel vous concerne, mais vous pouvez nous contacter à ce sujet à l'adresse indiquée ci-dessous. Pour les données de plantage/analyses détenues par Google, veuillez consulter les contrôles de confidentialité de Google sur [myaccount.google.com](https://myaccount.google.com). Pour les données traitées par nos fournisseurs d'IA, consultez les politiques de confidentialité d'OpenRouter, de Microsoft et d'OpenAI mentionnées ci-dessus.

Pour toute question relative à la confidentialité, contactez-nous à : **<privacy@voxquieta.org>**

## Modifications de cette politique

Nous publierons tout changement important sur cette page et mettrons à jour la date de « Dernière mise à jour ». L'utilisation continue de l'application après les modifications constitue l'acceptation de la politique mise à jour.
