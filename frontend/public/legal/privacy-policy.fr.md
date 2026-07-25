---
lastUpdated: 2026-07-18
---

# Politique de confidentialité

> _Cette traduction a été générée par intelligence artificielle et est fournie à titre de commodité uniquement. En cas d'omission, d'ambiguïté ou de contradiction avec l'original anglais, la version anglaise fait foi et prévaut._

Dernière mise à jour : 18 juillet 2026

## Qui nous sommes

Vox Quieta (« nous », « notre ») est une application gratuite d'inspiration biblique. Notre site web est [https://voxquieta.org](https://voxquieta.org).

## Quelles données nous collectons

### Données que vous fournissez

- **Messages de chat** : le texte que vous saisissez est envoyé à notre API, qui le transmet à des prestataires tiers de services d'IA (listés ci-dessous) uniquement pour générer une réponse basée sur les Écritures et en vérifier la sécurité. Nous ne conservons pas vos messages sur nos serveurs au-delà du temps nécessaire pour générer une réponse.
- **Évaluations de commentaires** : évaluations optionnelles pouce levé/pouce baissé que vous soumettez sur les réponses.

### Comment vos messages sont traités par l'IA

Pour répondre à vos questions, notre API envoie le texte de votre message aux fournisseurs d'IA tiers suivants :

- **OpenRouter** — reçoit le texte de votre message pour générer la réponse basée sur les Écritures (complétion par grand modèle de langage) et pour vérifier la sécurité des messages (contrôle de sécurité du contenu Llama Guard).
- **Azure OpenAI (Microsoft)** — reçoit le texte de votre message pour calculer les représentations vectorielles (embeddings) utilisées pour trouver les passages bibliques les plus pertinents.

Le texte de votre message est utilisé par ces fournisseurs **uniquement** pour générer la réponse à ce message ou en vérifier la sécurité. Il n'est pas utilisé par nous — ni, conformément aux conditions d'utilisation de l'API de chaque fournisseur, par le fournisseur — pour entraîner leurs modèles d'IA à usage général, il n'est pas conservé par le fournisseur au-delà de ce qui est nécessaire pour traiter la demande, et il n'est jamais utilisé à des fins publicitaires ni vendu. Consultez la [politique de confidentialité d'OpenRouter](https://openrouter.ai/privacy) et la [déclaration de confidentialité de Microsoft](https://privacy.microsoft.com) pour connaître les pratiques de traitement des données de chaque fournisseur.

### Données collectées automatiquement

- **Rapports de plantage** : en cas de plantage de l'application, Firebase Crashlytics collecte des informations de diagnostic anonymisées (modèle de l'appareil, version du système d'exploitation, version de l'application, trace de la pile). Aucun identifiant personnel n'est inclus.
- **Analyses d'utilisation** : Firebase Analytics collecte des événements d'utilisation anonymisés (vues d'écran, interactions avec les fonctionnalités) pour nous aider à améliorer l'application. Aucun identifiant personnel n'est inclus.

### Données que nous ne collectons PAS

- Nous n'exigeons pas d'inscription à un compte.
- Nous ne collectons pas votre nom, adresse e-mail ni numéro de téléphone.
- Nous ne suivons pas votre localisation.
- Nous ne vendons pas vos données à des tiers.

## Historique des conversations

L'historique des conversations est stocké **uniquement en local sur votre appareil** et n'est jamais téléchargé sur nos serveurs :

- **Application mobile :** une base de données chiffrée sur l'appareil (Room/SQLite).
- **Application web :** le stockage local de votre navigateur (IndexedDB), sur l'appareil que vous utilisez.

Vous pouvez consulter, renommer, supprimer ou effacer cet historique à tout moment. Vous pouvez également l'exporter sous forme de **fichier chiffré par une phrase secrète** afin de le transférer vers un autre de vos appareils : le fichier est chiffré avec une phrase que vous seul connaissez, il reste donc entre vos mains même pendant le transfert.

## Services tiers

| Service                       | Objectif                                                     | Politique de confidentialité                                       |
| ----------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------ |
| Firebase Crashlytics (Google) | Rapports de plantage                                         | [policies.google.com/privacy](https://policies.google.com/privacy) |
| Firebase Analytics (Google)   | Analyses d'utilisation anonymisées                           | [policies.google.com/privacy](https://policies.google.com/privacy) |
| OpenRouter                    | Génération de réponses IA et contrôle de sécurité du contenu | [openrouter.ai/privacy](https://openrouter.ai/privacy)             |
| Azure OpenAI (Microsoft)      | Embeddings de texte pour la recherche de passages bibliques  | [privacy.microsoft.com](https://privacy.microsoft.com)             |

## Conservation des données

- **Messages de chat** : non conservés sur nos serveurs.
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
- **Rapports de plantage et analyses** : conservés par Google jusqu'à 14 mois conformément à leur politique standard.
- **Historique local des conversations** : stocké sur votre appareil jusqu'à ce que vous le supprimiez via l'application ou désinstalliez l'application.

## Vos droits (RGPD)

Si vous vous trouvez dans l'Espace économique européen, vous avez le droit :

- d'accéder aux données personnelles que nous détenons sur vous,
- de demander la suppression de vos données,
- de vous opposer au traitement de vos données.

Comme nous ne collectons aucune information personnellement identifiable, la plupart des demandes peuvent être satisfaites en effaçant votre historique de conversation local dans l'application. Pour les données de plantage/analyses détenues par Google, veuillez consulter les contrôles de confidentialité de Google sur [myaccount.google.com](https://myaccount.google.com). Pour les données traitées par nos fournisseurs d'IA, consultez les politiques de confidentialité d'OpenRouter et de Microsoft mentionnées ci-dessus.

Pour toute question relative à la confidentialité, contactez-nous à : **<privacy@voxquieta.org>**

## Modifications de cette politique

Nous publierons tout changement important sur cette page et mettrons à jour la date de « Dernière mise à jour ». L'utilisation continue de l'application après les modifications constitue l'acceptation de la politique mise à jour.
