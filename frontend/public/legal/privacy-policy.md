---
lastUpdated: 2026-07-18
---

# Privacy Policy

Last updated: July 18, 2026

## Who We Are

Vox Quieta ("we", "us", "our") is a free Bible inspiration app. Our website is [https://voxquieta.org](https://voxquieta.org).

## What Data We Collect

### Data You Provide

- **Chat messages**: The text you type is sent to our API, which forwards it to third-party
  AI service providers (listed below) solely to generate a Scripture-based response and to
  screen it for safety. We do not store your messages on our servers beyond the time needed
  to generate a response.
- **Feedback ratings**: Optional thumbs-up/thumbs-down ratings you submit on responses.

### How Your Messages Are Processed by AI

To answer your questions, our API sends the text of your message to the following third-party
AI providers:

- **OpenRouter** — receives your message text to generate the Scripture-based response
  (large-language-model completion) and to screen messages for safety (Llama Guard
  content-safety check).
- **Azure OpenAI (Microsoft)** — receives your message text to compute text embeddings used
  to find the most relevant Scripture passages.

Your message text is used by these providers **only** to generate or safety-screen the
response to that message. It is not used by us — or, per each provider's API terms, by the
provider — to train their general-purpose AI models, it is not retained by the provider
beyond what is needed to service the request, and it is never used for advertising or sold.
See [OpenRouter's privacy policy](https://openrouter.ai/privacy) and
[Microsoft's privacy statement](https://privacy.microsoft.com) for each provider's own
data-handling practices.

### Data Collected Automatically

- **Crash reports**: If the app crashes, Firebase Crashlytics collects anonymised diagnostic
  information (device model, OS version, app version, stack trace). No personal identifiers
  are included.
- **Usage analytics**: Firebase Analytics collects anonymised usage events (screen views,
  feature interactions) to help us improve the app. No personal identifiers are included.

### Data We Do NOT Collect

- We do not require account registration.
- We do not collect your name, email address, or phone number.
- We do not track your location.
- We do not sell your data to third parties.

## Conversation History

Conversation history is stored **locally on your device only** using an encrypted on-device
database (Room/SQLite). It is never uploaded to our servers.

## Third-Party Services

| Service                       | Purpose                                             | Privacy Policy                                                     |
| ----------------------------- | --------------------------------------------------- | ------------------------------------------------------------------ |
| Firebase Crashlytics (Google) | Crash reporting                                     | [policies.google.com/privacy](https://policies.google.com/privacy) |
| Firebase Analytics (Google)   | Anonymised usage analytics                          | [policies.google.com/privacy](https://policies.google.com/privacy) |
| OpenRouter                    | AI response generation and content-safety screening | [openrouter.ai/privacy](https://openrouter.ai/privacy)             |
| Azure OpenAI (Microsoft)      | Text embeddings for Scripture search                | [privacy.microsoft.com](https://privacy.microsoft.com)             |

## Data Retention

- **Chat messages**: Not retained on our servers.
- **Messages blocked by our safety system**: When our safety system blocks a
  message, a privacy-minimal record may be kept for a short time (up to 30
  days) so we can improve the filter. The record contains the message text
  (capped in length), which safety stage blocked it, and a one-way hash of
  the session identifier. We do not store your IP address, account, or
  any user-agent string with these records, and they are not used for any
  purpose other than tuning the safety filter.
- **Crash reports & analytics**: Retained by Google for up to 14 months per their standard policy.
- **Local conversation history**: Stored on your device until you delete it via the app or uninstall the app.

## Your Rights (GDPR)

If you are in the European Economic Area, you have the right to:

- Access the personal data we hold about you.
- Request deletion of your data.
- Object to processing of your data.

Since we collect no personally identifiable information, most requests can be fulfilled by
clearing your local conversation history within the app. For crash/analytics data held by
Google, please refer to Google's privacy controls at
[myaccount.google.com](https://myaccount.google.com). For data handled by our AI providers,
see the OpenRouter and Microsoft privacy policies linked above.

For any privacy questions, contact us at: **<privacy@voxquieta.org>**

## Changes to This Policy

We will post any material changes to this page and update the "Last updated" date. Continued
use of the app after changes constitutes acceptance of the updated policy.
