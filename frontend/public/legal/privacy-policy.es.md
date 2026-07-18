---
lastUpdated: 2026-07-18
---

# Política de privacidad

> _Esta traducción ha sido generada por inteligencia artificial y se proporciona únicamente como cortesía. En caso de omisión, ambigüedad o contradicción con el original en inglés, prevalece la versión en inglés, que es la canónica._

Última actualización: 18 de julio de 2026

## Quiénes somos

Vox Quieta ("nosotros", "nos", "nuestro") es una aplicación gratuita de inspiración bíblica. Nuestro sitio web es [https://voxquieta.org](https://voxquieta.org).

## Qué datos recopilamos

### Datos que tú proporcionas

- **Mensajes del chat**: el texto que escribes se envía a nuestra API, que lo reenvía a proveedores externos de servicios de IA (indicados más abajo) únicamente para generar una respuesta basada en las Escrituras y comprobar su seguridad. No almacenamos tus mensajes en nuestros servidores más allá del tiempo necesario para generar una respuesta.
- **Valoraciones de comentarios**: valoraciones opcionales de pulgar arriba/pulgar abajo que envías sobre las respuestas.

### Cómo la IA procesa tus mensajes

Para responder a tus preguntas, nuestra API envía el texto de tu mensaje a los siguientes proveedores externos de IA:

- **OpenRouter** — recibe el texto de tu mensaje para generar la respuesta basada en las Escrituras (modelo de lenguaje) y para comprobar la seguridad de los mensajes (verificación de seguridad de contenido Llama Guard).
- **Azure OpenAI (Microsoft)** — recibe el texto de tu mensaje para calcular las representaciones vectoriales (embeddings) que permiten encontrar los pasajes bíblicos más relevantes.

Estos proveedores utilizan el texto de tu mensaje **únicamente** para generar la respuesta a ese mensaje o comprobar su seguridad. Ni nosotros ni —según los términos de la API de cada proveedor— el proveedor lo utilizamos para entrenar sus modelos de IA de propósito general, el proveedor no lo conserva más allá de lo necesario para atender la solicitud, y nunca se usa con fines publicitarios ni se vende. Consulta la [política de privacidad de OpenRouter](https://openrouter.ai/privacy) y la [declaración de privacidad de Microsoft](https://privacy.microsoft.com) para conocer las prácticas de tratamiento de datos de cada proveedor.

### Datos recopilados automáticamente

- **Informes de fallos**: si la aplicación falla, Firebase Crashlytics recopila información de diagnóstico anonimizada (modelo del dispositivo, versión del sistema operativo, versión de la aplicación, seguimiento de la pila). No se incluyen identificadores personales.
- **Análisis de uso**: Firebase Analytics recopila eventos de uso anonimizados (vistas de pantalla, interacciones con funciones) para ayudarnos a mejorar la aplicación. No se incluyen identificadores personales.

### Datos que NO recopilamos

- No requerimos registro de cuenta.
- No recopilamos tu nombre, dirección de correo electrónico ni número de teléfono.
- No rastreamos tu ubicación.
- No vendemos tus datos a terceros.

## Historial de conversaciones

El historial de conversaciones se almacena **solo localmente en tu dispositivo** en una base de datos cifrada en el dispositivo (Room/SQLite). Nunca se sube a nuestros servidores.

## Servicios de terceros

| Servicio                      | Propósito                                                                | Política de privacidad                                             |
| ----------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Firebase Crashlytics (Google) | Informes de fallos                                                       | [policies.google.com/privacy](https://policies.google.com/privacy) |
| Firebase Analytics (Google)   | Análisis de uso anonimizado                                              | [policies.google.com/privacy](https://policies.google.com/privacy) |
| OpenRouter                    | Generación de respuestas de IA y comprobación de seguridad del contenido | [openrouter.ai/privacy](https://openrouter.ai/privacy)             |
| Azure OpenAI (Microsoft)      | Embeddings de texto para la búsqueda de pasajes bíblicos                 | [privacy.microsoft.com](https://privacy.microsoft.com)             |

## Retención de datos

- **Mensajes del chat**: no se conservan en nuestros servidores.
- **Mensajes bloqueados por nuestro sistema de seguridad**: cuando nuestro
  sistema de seguridad bloquea un mensaje, puede conservarse un registro
  mínimo en cuanto a privacidad durante un breve período (hasta 30 días)
  para ayudarnos a mejorar el filtro. El registro contiene el texto del
  mensaje (con longitud limitada), la etapa de seguridad que lo bloqueó
  y un hash unidireccional del identificador de sesión. No almacenamos
  tu dirección IP, tu cuenta ni ninguna cadena user-agent junto con
  estos registros, y solo se usan para ajustar el filtro de seguridad.
- **Informes de fallos y análisis**: conservados por Google hasta 14 meses según su política estándar.
- **Historial local de conversaciones**: almacenado en tu dispositivo hasta que lo elimines mediante la aplicación o desinstales la aplicación.

## Tus derechos (RGPD)

Si te encuentras en el Espacio Económico Europeo, tienes derecho a:

- acceder a los datos personales que conservamos sobre ti,
- solicitar la eliminación de tus datos,
- oponerte al tratamiento de tus datos.

Dado que no recopilamos información de identificación personal, la mayoría de las solicitudes pueden atenderse eliminando tu historial de conversaciones local dentro de la aplicación. Para los datos de fallos/análisis en manos de Google, consulta los controles de privacidad de Google en [myaccount.google.com](https://myaccount.google.com). Para los datos tratados por nuestros proveedores de IA, consulta las políticas de privacidad de OpenRouter y Microsoft enlazadas más arriba.

Para cualquier pregunta sobre privacidad, contáctanos en: **<privacy@voxquieta.org>**

## Cambios en esta política

Publicaremos cualquier cambio sustancial en esta página y actualizaremos la fecha de "Última actualización". El uso continuado de la aplicación tras los cambios constituye la aceptación de la política actualizada.
