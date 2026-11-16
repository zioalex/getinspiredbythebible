---
lastUpdated: 2026-11-16
---

# Política de Privacidade

> _Esta tradução foi gerada por inteligência artificial e é fornecida apenas como conveniência. Em caso de omissão, ambiguidade ou contradição com o original em inglês, prevalece a versão em inglês, que é a canônica._

Última atualização: 16 de novembro de 2026

## Quem somos

Vox Quieta ("nós", "nos", "nosso") é um aplicativo gratuito de inspiração bíblica. Nosso site é [https://voxquieta.org](https://voxquieta.org).

## Quais dados coletamos

### Dados que você fornece

- **Mensagens do chat**: o texto que você digita é enviado para nossa API, que o encaminha a provedores terceirizados de serviços de IA (listados abaixo) exclusivamente para gerar uma resposta baseada nas Escrituras e verificar sua segurança. Não armazenamos suas mensagens em nossos servidores além do tempo necessário para gerar uma resposta, exceto mensagens bloqueadas pelo nosso sistema de segurança, que podem ser mantidas por até 30 dias, conforme descrito em "Retenção de dados". As mensagens que você avalia ao enviar feedback são mantidas conforme descrito em "Feedback".
- **Feedback**: avaliações opcionais de polegar para cima/para baixo que você envia sobre as respostas, com motivo e comentário opcionais. Quando você envia feedback, armazenamos sua mensagem, a resposta da IA e seu comentário por 30 dias, e a avaliação, o motivo, o identificador da mensagem e detalhes técnicos (modelo, tempo de resposta, referências de versículos) por 90 dias, apenas para melhorar nossas respostas. Seu identificador de sessão é armazenado somente como um hash unidirecional.
- **Formulário de contato**: se você nos escreve pelo formulário de contato, armazenamos o assunto, sua mensagem e o endereço de e-mail que você informar por 90 dias, apenas para responder a você. Seu identificador de sessão é armazenado somente como um hash unidirecional, e os dados do seu navegador ou dispositivo não são armazenados.

### Como suas mensagens são processadas por IA

Para responder às suas perguntas, nossa API envia o texto da sua mensagem aos seguintes provedores terceirizados de IA:

- **OpenRouter** — recebe o texto da sua mensagem para gerar a resposta baseada nas Escrituras (geração por modelo de linguagem) e para verificar a segurança das mensagens (verificação de segurança de conteúdo Llama Guard).
- **Azure OpenAI (Microsoft)** — recebe o texto da sua mensagem para calcular os embeddings de texto usados para encontrar as passagens bíblicas mais relevantes.
- **OpenAI** — recebe o texto da sua mensagem apenas quando a nossa verificação de segurança principal (Llama Guard) está temporariamente indisponível, para verificar a sua segurança (OpenAI Moderation).

O texto da sua mensagem é usado por esses provedores **exclusivamente** para gerar ou verificar a segurança da resposta àquela mensagem. Ele não é usado por nós — nem, conforme os termos de API de cada provedor, pelo provedor — para treinar seus modelos de IA de uso geral e nunca é usado para publicidade nem vendido. Cada provedor pode retê-lo segundo seus próprios termos de tratamento de dados: a OpenAI mantém o texto das mensagens que recebe por até 30 dias para monitoramento de abusos e, depois disso, o exclui, salvo se a lei exigir de outra forma. Consulte a [política de privacidade da OpenRouter](https://openrouter.ai/privacy), a [declaração de privacidade da Microsoft](https://privacy.microsoft.com) e os [compromissos de privacidade de dados da API da OpenAI](https://openai.com/enterprise-privacy/) para conhecer as práticas de tratamento de dados de cada provedor.

### Dados coletados automaticamente

- **Relatórios de falhas**: se o aplicativo travar, o Firebase Crashlytics coleta informações de diagnóstico anonimizadas (modelo do dispositivo, versão do sistema operacional, versão do aplicativo, rastreamento de pilha). Nenhum identificador pessoal é incluído.
- **Análises de uso**: o Firebase Analytics coleta eventos de uso anonimizados (visualizações de tela, interações com recursos) para nos ajudar a melhorar o aplicativo. Nenhum identificador pessoal é incluído.

### Dados que NÃO coletamos

- Não exigimos cadastro de conta.
- Não coletamos seu nome, endereço de e-mail ou número de telefone, exceto o endereço de e-mail que você optar por informar no formulário de contato.
- Não rastreamos sua localização.
- **País aproximado, apenas para números de emergência**: se a sua mensagem sugerir que você ou outra pessoa pode estar em perigo, deduzimos o seu país a partir da sua conexão (o cabeçalho de país da Cloudflare) ou do idioma do seu dispositivo, somente para mostrar os números locais corretos de emergência e de apoio. Ele nunca é armazenado em nossos servidores; o cartão é salvo apenas junto com a sua conversa, no seu dispositivo. Se você escolher outro país no cartão, esse país é enviado a nós somente para consultar os números dele e não é armazenado em nossos servidores.
- Não vendemos seus dados a terceiros.

## Histórico de conversas

O histórico de conversas é armazenado **apenas localmente em seu dispositivo** e nunca é enviado para nossos servidores, exceto uma mensagem e a resposta que você escolhe avaliar (veja "Feedback"):

- **Aplicativo móvel:** um banco de dados criptografado no dispositivo (Room/SQLite).
- **Aplicativo web:** o armazenamento local do seu navegador (IndexedDB), no dispositivo que você usa.

Você pode visualizar, renomear, excluir ou limpar esse histórico a qualquer momento. Você também pode exportá-lo como um **arquivo criptografado com uma frase secreta** para movê-lo para outro dos seus dispositivos: o arquivo é criptografado com uma frase que só você conhece, de modo que permanece em suas mãos mesmo durante a transferência.

## Serviços de terceiros

| Serviço                       | Finalidade                                                                                                     | Política de Privacidade                                                 |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Firebase Crashlytics (Google) | Relatórios de falhas                                                                                           | [policies.google.com/privacy](https://policies.google.com/privacy)      |
| Firebase Analytics (Google)   | Análises de uso anonimizadas                                                                                   | [policies.google.com/privacy](https://policies.google.com/privacy)      |
| OpenRouter                    | Geração de respostas de IA e verificação de segurança de conteúdo                                              | [openrouter.ai/privacy](https://openrouter.ai/privacy)                  |
| Azure OpenAI (Microsoft)      | Embeddings de texto para busca de passagens bíblicas                                                           | [privacy.microsoft.com](https://privacy.microsoft.com)                  |
| OpenAI                        | Verificação de segurança de conteúdo de reserva (somente quando a verificação principal está indisponível)     | [openai.com/enterprise-privacy](https://openai.com/enterprise-privacy/) |
| SMTP2GO                       | Notificações por e-mail ao operador sobre feedback e mensagens de contato; não contêm o conteúdo das mensagens | [smtp2go.com/privacy](https://www.smtp2go.com/privacy/)                 |

## Leitura em voz alta

O botão Ouvir lê as respostas em voz alta com a síntese de voz integrada ao seu navegador. Por padrão, ele usa apenas vozes offline instaladas no seu dispositivo, portanto o texto da resposta não sai do seu dispositivo para este recurso.

Alguns navegadores oferecem apenas vozes online para o seu idioma. Só usamos uma voz online se você escolher "Permitir vozes online". Nesse caso, o seu navegador envia o texto da resposta lida ao serviço de voz do fabricante do navegador (por exemplo, Google, Microsoft ou Apple), que o trata conforme os próprios termos; nós não o recebemos nem o armazenamos. A sua escolha é salva somente no seu dispositivo e você pode revogá-la a qualquer momento com a chave "Permitir vozes online" no menu, o que também interrompe qualquer leitura em andamento.

Contamos o uso da leitura em voz alta de forma anônima, por idioma, família de navegador e família de sistema operacional (por exemplo, "Firefox no Linux"), para saber onde o recurso funciona e onde falha. Essas contagens não contêm texto, nomes de vozes, strings de user-agent, endereços IP nem identificadores.

## Retenção de dados

- **Mensagens do chat**: não retidas em nossos servidores, exceto mensagens bloqueadas pelo nosso sistema de segurança (veja abaixo). As mensagens que você avalia ao enviar feedback são mantidas conforme descrito em "Feedback".
- **Mensagens bloqueadas pelo nosso sistema de segurança**: quando nosso
  sistema de segurança bloqueia uma mensagem, um registro com privacidade
  mínima pode ser mantido por um curto período (até 30 dias) para nos
  ajudar a aprimorar o filtro. O registro contém o texto da mensagem
  (com comprimento limitado), qual etapa de segurança a bloqueou e um
  hash unidirecional do identificador de sessão. Não armazenamos seu
  endereço IP, sua conta ou qualquer string de user-agent junto a esses
  registros, e eles não são usados para nenhuma finalidade além de
  ajustar o filtro de segurança.
- **Estatísticas anônimas de qualidade de busca**: para melhorar como
  encontramos passagens bíblicas relevantes, podemos manter registros
  anônimos por até 90 dias quando uma busca retorna resultados fracos ou
  nenhum resultado. Um registro contém apenas informações derivadas: os
  temas detectados, o idioma e a tradução bíblica, as pontuações de
  relevância, as referências de versículos e um hash unidirecional do
  identificador de sessão. Ele nunca contém o texto da sua mensagem nem da
  resposta, e não armazenamos seu endereço IP, sua conta ou qualquer string
  de user-agent junto a ele. Esses registros são usados apenas para
  melhorar a qualidade da busca.
- **Feedback**: sua mensagem, a resposta da IA e seu comentário são mantidos por 30 dias e depois excluídos. O restante do registro de feedback (avaliação, motivo, identificador da mensagem, modelo, tempo de resposta, referências de versículos e um hash unidirecional do identificador de sessão) é mantido por 90 dias e depois excluído. Os e-mails de notificação que recebemos não contêm o texto das mensagens.
- **Mensagens do formulário de contato**: o assunto, a mensagem, o endereço de e-mail informado e um hash unidirecional do identificador de sessão são mantidos por 90 dias e depois excluídos. São usados apenas para responder a você.
- **Relatórios de falhas e análises**: retidos pelo Google por até 14 meses conforme sua política padrão.
- **Histórico local de conversas**: armazenado em seu dispositivo até que você o exclua pelo aplicativo ou desinstale o aplicativo.

## Seus direitos (LGPD / RGPD)

Se você estiver no Espaço Econômico Europeu, tem o direito de:

- acessar os dados pessoais que mantemos sobre você,
- solicitar a exclusão de seus dados,
- opor-se ao processamento de seus dados.

Não pedimos uma conta, por isso a maioria das solicitações pode ser atendida limpando seu histórico de conversas local no aplicativo. Os dados de feedback e das mensagens do formulário de contato podem ser localizados e excluídos mediante solicitação: envie-nos o identificador da mensagem ou a data e a hora aproximadas do envio (feedback) ou o endereço de e-mail usado (formulário de contato) para o endereço abaixo. Os registros de mensagens bloqueadas pelo nosso sistema de segurança são armazenados sem seu endereço IP, conta ou dados do dispositivo e são excluídos automaticamente em até 30 dias; como não estão vinculados à sua identidade, normalmente não conseguimos identificar qual registro é seu, mas você pode entrar em contato conosco sobre eles no endereço abaixo. Para dados de falhas/análises mantidos pelo Google, consulte os controles de privacidade do Google em [myaccount.google.com](https://myaccount.google.com). Para dados tratados por nossos provedores de IA, consulte as políticas de privacidade da OpenRouter, da Microsoft e da OpenAI indicadas acima.

Para quaisquer dúvidas sobre privacidade, entre em contato conosco em: **<privacy@voxquieta.org>**

## Alterações nesta política

Publicaremos quaisquer alterações importantes nesta página e atualizaremos a data de "Última atualização". O uso continuado do aplicativo após as alterações constitui aceitação da política atualizada.
