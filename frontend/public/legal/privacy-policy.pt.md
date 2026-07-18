---
lastUpdated: 2026-07-18
---

# Política de Privacidade

> _Esta tradução foi gerada por inteligência artificial e é fornecida apenas como conveniência. Em caso de omissão, ambiguidade ou contradição com o original em inglês, prevalece a versão em inglês, que é a canônica._

Última atualização: 18 de julho de 2026

## Quem somos

Vox Quieta ("nós", "nos", "nosso") é um aplicativo gratuito de inspiração bíblica. Nosso site é [https://voxquieta.org](https://voxquieta.org).

## Quais dados coletamos

### Dados que você fornece

- **Mensagens do chat**: o texto que você digita é enviado para nossa API, que o encaminha a provedores terceirizados de serviços de IA (listados abaixo) exclusivamente para gerar uma resposta baseada nas Escrituras e verificar sua segurança. Não armazenamos suas mensagens em nossos servidores além do tempo necessário para gerar uma resposta.
- **Avaliações de feedback**: avaliações opcionais de polegar para cima/para baixo que você envia sobre as respostas.

### Como suas mensagens são processadas por IA

Para responder às suas perguntas, nossa API envia o texto da sua mensagem aos seguintes provedores terceirizados de IA:

- **OpenRouter** — recebe o texto da sua mensagem para gerar a resposta baseada nas Escrituras (geração por modelo de linguagem) e para verificar a segurança das mensagens (verificação de segurança de conteúdo Llama Guard).
- **Azure OpenAI (Microsoft)** — recebe o texto da sua mensagem para calcular os embeddings de texto usados para encontrar as passagens bíblicas mais relevantes.

O texto da sua mensagem é usado por esses provedores **exclusivamente** para gerar ou verificar a segurança da resposta àquela mensagem. Ele não é usado por nós — nem, conforme os termos de API de cada provedor, pelo provedor — para treinar seus modelos de IA de uso geral, não é retido pelo provedor além do necessário para atender à solicitação e nunca é usado para publicidade nem vendido. Consulte a [política de privacidade da OpenRouter](https://openrouter.ai/privacy) e a [declaração de privacidade da Microsoft](https://privacy.microsoft.com) para conhecer as práticas de tratamento de dados de cada provedor.

### Dados coletados automaticamente

- **Relatórios de falhas**: se o aplicativo travar, o Firebase Crashlytics coleta informações de diagnóstico anonimizadas (modelo do dispositivo, versão do sistema operacional, versão do aplicativo, rastreamento de pilha). Nenhum identificador pessoal é incluído.
- **Análises de uso**: o Firebase Analytics coleta eventos de uso anonimizados (visualizações de tela, interações com recursos) para nos ajudar a melhorar o aplicativo. Nenhum identificador pessoal é incluído.

### Dados que NÃO coletamos

- Não exigimos cadastro de conta.
- Não coletamos seu nome, endereço de e-mail ou número de telefone.
- Não rastreamos sua localização.
- Não vendemos seus dados a terceiros.

## Histórico de conversas

O histórico de conversas é armazenado **apenas localmente em seu dispositivo** em um banco de dados criptografado no dispositivo (Room/SQLite). Ele nunca é enviado para nossos servidores.

## Serviços de terceiros

| Serviço                       | Finalidade                                                        | Política de Privacidade                                            |
| ----------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------ |
| Firebase Crashlytics (Google) | Relatórios de falhas                                              | [policies.google.com/privacy](https://policies.google.com/privacy) |
| Firebase Analytics (Google)   | Análises de uso anonimizadas                                      | [policies.google.com/privacy](https://policies.google.com/privacy) |
| OpenRouter                    | Geração de respostas de IA e verificação de segurança de conteúdo | [openrouter.ai/privacy](https://openrouter.ai/privacy)             |
| Azure OpenAI (Microsoft)      | Embeddings de texto para busca de passagens bíblicas              | [privacy.microsoft.com](https://privacy.microsoft.com)             |

## Retenção de dados

- **Mensagens do chat**: não retidas em nossos servidores.
- **Mensagens bloqueadas pelo nosso sistema de segurança**: quando nosso
  sistema de segurança bloqueia uma mensagem, um registro com privacidade
  mínima pode ser mantido por um curto período (até 30 dias) para nos
  ajudar a aprimorar o filtro. O registro contém o texto da mensagem
  (com comprimento limitado), qual etapa de segurança a bloqueou e um
  hash unidirecional do identificador de sessão. Não armazenamos seu
  endereço IP, sua conta ou qualquer string de user-agent junto a esses
  registros, e eles não são usados para nenhuma finalidade além de
  ajustar o filtro de segurança.
- **Relatórios de falhas e análises**: retidos pelo Google por até 14 meses conforme sua política padrão.
- **Histórico local de conversas**: armazenado em seu dispositivo até que você o exclua pelo aplicativo ou desinstale o aplicativo.

## Seus direitos (LGPD / RGPD)

Se você estiver no Espaço Econômico Europeu, tem o direito de:

- acessar os dados pessoais que mantemos sobre você,
- solicitar a exclusão de seus dados,
- opor-se ao processamento de seus dados.

Como não coletamos informações de identificação pessoal, a maioria das solicitações pode ser atendida limpando seu histórico de conversas local no aplicativo. Para dados de falhas/análises mantidos pelo Google, consulte os controles de privacidade do Google em [myaccount.google.com](https://myaccount.google.com). Para dados tratados por nossos provedores de IA, consulte as políticas de privacidade da OpenRouter e da Microsoft indicadas acima.

Para quaisquer dúvidas sobre privacidade, entre em contato conosco em: **<privacy@voxquieta.org>**

## Alterações nesta política

Publicaremos quaisquer alterações importantes nesta página e atualizaremos a data de "Última atualização". O uso continuado do aplicativo após as alterações constitui aceitação da política atualizada.
