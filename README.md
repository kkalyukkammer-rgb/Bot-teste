# Bot-teste

## Persistência dos dados

O bot salva automaticamente saldos, estatísticas, cassinos e configurações em
`backup/economy.sqlite3`, dentro desta pasta do projeto. Esse mesmo banco é
reaberto sempre que o bot inicia, então os dados continuam disponíveis depois
de reiniciar o processo ou o computador.

Na primeira inicialização com esta versão, se o banco ainda não existir em
`backup/` e `economy.sqlite3` existir na raiz do projeto, o bot copia o banco
usando o mecanismo de backup do SQLite. O arquivo original permanece intacto.
Depois dessa migração, `backup/economy.sqlite3` é a fonte principal dos dados;
guarde a pasta `backup/` ao mover ou restaurar o projeto. Ela é ignorada pelo
Git para não publicar dados dos usuários.

Para usar outro local para o banco, defina a variável de ambiente
`ECONOMY_DB_PATH` antes de iniciar o bot.

## Status e upgrades

`/status_casa_principal` separa o volume e a quantidade de apostas dos
jogadores dos dados de atividade de NPCs; também mostra o resultado líquido
das apostas e taxas recebidas de cassinos locais. `/status_cassino` mostra,
em categorias distintas, as apostas de jogadores e a operação de NPCs.

`/status_apostador` mostra em uma resposta privada o próprio saldo,
ganhos/perdas acumulados, volume e quantidade de apostas, prestígio,
upgrades e disponibilidade das recompensas. Quando usado em um servidor
com cassino próprio, também inclui saldo, apostas e recompensas locais.

As apostas vencedoras de NPCs nos cassinos de jogadores são dimensionadas
para deixar pelo menos 1.000 moedas líquidas no caixa local, após a taxa
devida à casa principal.

O owner do bot pode usar `/resetar_dados_jogadores` para escolher entre
zerar os saldos globais e locais dos jogadores ou liberar os cooldowns de
recompensas globais e locais. O comando pede confirmação; os caixas dos
cassinos e o histórico estatístico são preservados ao zerar saldos.
A recompensa mensal global varia de 1.000 a 20.000 moedas.

Qualquer apostador pode usar `/feedback` para enviar uma sugestão ou opinião
diretamente por mensagem privada ao owner do bot. O bot confirma em uma
resposta privada se a entrega foi concluída.

Quando iniciar com novos commits Git, o bot publica os títulos desses commits
no canal `1560451788254216343` do servidor `1467549007932030998`. Se ainda não
houver um commit anunciado salvo, publica somente o commit mais recente para
evitar enviar o histórico inteiro. O processo precisa ter Git e o repositório
disponível, além de permissão para enviar mensagens e embeds nesse canal.
O owner também pode usar `/anunciar_update` para publicar manualmente os
commits disponíveis e mencionar o cargo `1559362476921987072`. Se não houver
commits novos, o comando permite reenviar o commit mais recente. O cargo deve
estar no servidor de anúncios e ser mencionável pelo bot.

Os comandos `/upgrade_casa_principal`, `/upgrade_cassino` e
`/upgrade_prestigio` exibem uma confirmação antes da compra. Depois de cada
compra, a mensagem oferece o próximo nível do mesmo upgrade para confirmação
quando houver saldo suficiente.

## Excluir um cassino

O dono pode usar `/excluir_cassino` no servidor. O bot pede confirmação;
ao confirmar, transfere o caixa restante para o saldo global do dono na
proporção de 1:1 e apaga os saldos locais dos jogadores e o histórico daquele
cassino. Essa exclusão é permanente.
