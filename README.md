# Controlar seus serviços AWS com o Telegram

Este script é para ser utilizado com os serviços da AWS:
  - Funções do IAM
  - DynamoDB
  - Lambda
  - API Gateway

## Como configurar

Primeiro precisamos criar um BOT no telegram, para isto utilizaremos um bot chamado @botfather basta buscar por seu username no Telegram para encontra-lo e após abrir sua conversa clique em "COMEÇAR" ou mande o comando "/start" no seu chat caso o botão não seja apresentado.
![Image1](https://i.imgur.com/ZoMhEcX.png)

Agora vamos criar um novo bot, para isto envie o comando "/newbot" e preencha as informações como nome e usuário do bot conforme o bot vai lhe solicitando e no fim ele irá lhe passar o token do seu BOT.

![Image2](https://i.imgur.com/IweBluu.png)

Agora precisaremos pegar o ID do seu usuário ou do seu grupo para o BOT enviar as mensagens, pasta isto acesse a URL abaixo lembrando de alterar o <TOKEN> pelo token do teu BOT.
```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

Feito isto, se você deseja que o BOT envie as mensagens somente para seu usuário basta você iniciar uma conversa com o BOT e enviar uma mensagem qualquer para ele apenas para coletarmos o seu ID, já se você deseja que as mensagens vão para um grupo no Telegram será preciso que você crie o grupo e coloque o BOT como membro, e então envie a mensagem dentro do grupo feito isto acesse a URL novamente, a URL que antes estava vazia agora deve estar com um JSON.

Segue abaixo como criar um novo grupo que será para receber as mensagens de usuários que tentaram acessar e também as mensagens de retorno da AWS em relação aos comandos que foram executados. Mas antes precisar ter iniciado a conversa com o bot e enviar uma mensagem para ele para gerar atualização no log dele.

![Image3](https://i.imgur.com/JQYzP1am.png)
![Image3a](https://i.imgur.com/7yS7Ymgm.png)

![Image3b](https://i.imgur.com/iEXEVBTm.png)

Salve estas informações pois usaremos posteriormente.

Para configurar um tópico SNS e também criar uma função Lambda que o recebimento de notificações no Telegram você poderá fazer através do reposítorio da Comunidade Cloud a partir da configuração do Tópico SNS.
```
https://gitlab.com/comunidade-cloud/aws/notificacoes-via-telegram.git
```

Seguindo então o repositório acima já criei o ***TelegramSNSNotifier***

Agora vamos para o console da AWS e vamos criar as funções no IAM que vamos precisar que o Lambda tenha para acessar os outros serviços da AWS: 
```
AWS Management Console > IAM > Roles > Create role
```
Vamos criar a função em que o Lambda possa acessar as EC2 e o DynamoDB bem como outros serviços que posteriormente você for acrescentando na aplicação. Feito isto selecione Lambda e clique em Next:Permissions.
![Image4](https://i.imgur.com/agd7KBF.png)

Nós vamos dar a permissão de Acesso Completo para os serviços, porém em produção você vai precisar verificar quais serviços essa função poderá ter acesso por questão de segurança. Então a princípio nós sabemos que essa função precisará acessar as EC2 para ter conseguir ter acesso e também ao DynamoDB que vai guardar as sessões dos usuários e também o cadastro de usuários.
Vamos marcar então AmazonEC2FullAccess e AmazomDynamoDBFullAccess e clicar em Next:Tags

![Image5](https://i.imgur.com/7xnU6e7.png)
![Image5a](https://i.imgur.com/8ZdbG1E.png)

Aqui podemos cololar a tag ***Name*** com o nome de ***LambdaEC2DynamoDBFullAccess***, sempre utilize nomes que possam indicar facilmente o que tem nessa função e clique em Next:Review.
![Image6](https://i.imgur.com/luxRNab.png)

Revise se está tudo correto conforme o indicado e clique em Create role
![Image6a](https://i.imgur.com/Jya5bV5.png)

Agora vamos criar as tabelas que vão armazenar os usuários e também a sessão de usuários no DynamoDB, começando com a de usuários para isto siga este caminho:
```
AWS Management Console > DynamoDB > Tables > Create table
```
Feito isto coloque o nome ***request-telegram-user***, coloque como Partition Key ***user_id***, selecione Default settings e clique em Create table

![Image7](https://i.imgur.com/yVO6UGB.png)
![Image7a](https://i.imgur.com/HpzK9S2.png)

Feito isto agora vamos clicar na tabela ***request-telegram-user*** cadastrar o index e também o primeiro usuário que será o seu usuário como administrador.

```
AWS Management Console > DynamoDB > Tables > request-telegram-user
```

Agora dentro da tabela vamos clicar em **Indexes** e Create index:
![Image8](https://i.imgur.com/aMUMGtx.png)

Dentro do Create index vamos configurar conforme abaixo e clicar no botão Create index:

![Image8a](https://i.imgur.com/g8RIOz1.png)
![Image8b](https://i.imgur.com/Ux0i9C8.png)

Feito isto agora vamos cadastrar o primeiro usuário que será o seu usuário como administrador clicando em Item e no botão Create item.
![Image9](https://i.imgur.com/YENjoeT.png)

Conforme a configuração abaixo crie um novo item que será o usuário administrador, esse usuário poderá liberar os demais usuários na aplicação posteriormente.

![Image9a](https://i.imgur.com/YWgM6P8.png)

E clicando no botão Add new attribute você poderá inserir os demais campos e clique em Create item:

![Image9b](https://i.imgur.com/cZSJW5G.png)

terá o resultado:

![Image9c](https://i.imgur.com/ake7Fpx.png)

Agora vamos criar a tabela que vai armazenar a sessão de usuários no DynamoDB, para isto siga este caminho:
```
AWS Management Console > DynamoDB > Tables > Create table
```
Feito isto coloque o nome ***request-telegram-session***, coloque como Partition Key ***user_id*** e Sort Key ***session_id***, selecione Default settings e clique em Create table

![Image10](https://i.imgur.com/zIT33uj.png)
![Image10a](https://i.imgur.com/HpzK9S2.png)

Agora vamos criar a função Lambda que será a nossa aplicação:
```
AWS Management Console > Lambda > Functions > Create function
```
Coloque as configurações conforme abaixo com nome ***commandTelegramBot***, selecione Python 3.7, selecione a função que criamos anteriormente ***LambdaEC2DynamoDBFullAccess*** e clique em Create function:

![Image11](https://i.imgur.com/tEOlaED.png)
![Image11a](https://i.imgur.com/nvRFNfb.png)

Agora dentro da sua função Lambda desça até a parte de "Environment variables" e clique em "Manage environment variables".
![Image12](https://i.imgur.com/BDmS35Z.png)

Então clique em "Add environment variable" 6 vezes para adicionar 6 variaveis de ambiente.
As váriaveis que iremos criar são INFRA_GROUP_ID, REGION_DB, SESSION_TABLE, TOKEN, USER_TABLE e SESSION_TIMEOUT_HOUR que são os valores que coletamos anteriormente, o token do BOT e o ID do grupo e os nomes das tabelas criadas anteriormente, criadas as váriaveis clique para salvar.
![Image13](https://i.imgur.com/oBfMpeP.png)

Agora subindo novamente no item **Function code** dê dois clique no arquivo *lambda_function.py* e substitua o conteúdo na janela à esquerda pelo código disponibilizado no arquivo lambda.py, feito isto clique em Deploy.
![Image14](https://i.imgur.com/jdllKki.png)

Agora vamos configurar o tempo de timeout da função para não termos problema:
![Image14a](https://i.imgur.com/yxWMz7o.png)

E na tela de Basic settings vamos setar 15 segundos e clicar em Save:
![Image14b](https://i.imgur.com/OMosKqn.png)

Feito isto agora vamos adicionar o gatilho da API que vai ser acessada através do bot do Telegram, para isto vá até o topo do seu Lambda e clique em "Add trigger".
![Image15](https://i.imgur.com/VHQQpwu.png)

Agora na proxima tela no campo "Select a trigger" selecione a API Gateway.
![Image15a](https://i.imgur.com/WdppcN3.png)

Feito isto agora vamos criar uma API Gateway, conforme configuração abaixo e clique em "Add".
![Image15b](https://i.imgur.com/XIIg3lE.png)

Agora vamos o endpoint $default da API que acabamos de criar:
```
AWS Management Console > Api Gateway > APIs > commandTelegramBot-API
```
![Image16](https://i.imgur.com/9O89QCK.png)

Agora precisamos colocar o endpoint no webhook do bot no Telegram. Utilizando o link abaixo:
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://5o5pyu95ph.execute-api.us-east-1.amazonaws.com/commandTelegramBot
```
Você deverá o retorno JSON abaixo:

![Image17](https://i.imgur.com/52WS2YUm.png)

E agora está pronto, vamos no bot do Telegram e vamos digitar **/start** para iniciar a aplicação.
