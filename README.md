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

## Trabalho, roubo e apostas

`/workshift` paga o salário do trabalho atual por um período aleatório de
30 minutos a 8 horas. O limite acumulado é de 8 horas e se renova a cada
8 horas. Use `/mudar_trabalho` para escolher uma profissão; cada uma tem taxa
de inscrição e salário por hora próprios. Os salários por hora são 3.000 no
bico, 7.500 como entregador, 12.000 como segurança, 18.000 como programador
e 27.000 como influenciador. Donos de cassino não podem trocar de trabalho.

`/roubar` tem 65% de chance de sucesso e paga de 2.500 a 15.000 moedas em
caso de êxito. Uma tentativa bem-sucedida consome uma das 5 tentativas
disponíveis; uma tentativa fracassada consome todas. As tentativas voltam
8 horas após o esgotamento.

`/ajuda` agrupa os comandos por área, incluindo renda e economia, jogos,
cassinos, upgrades, status, moderação e utilidades do bot.

Os resultados das apostas oferecem um botão para repetir na mesma mensagem
com o mesmo valor e escolha. Em desafios entre jogadores, o botão reinicia o
desafio para os mesmos participantes. Valores monetários usam ponto como
separador de milhares.

## Jogos e balanceamento

Além de `/moeda`, `/dados`, `/roleta`, `/jogo_do_bixo` e `/cacaniquel`, foram
adicionados `/maior_menor` e `/jokenpo`, que também podem ser jogados com
moedas locais por `/jogar_cassino` quando o nível do cassino liberar cada
jogo. O comando antigo `/corrida` foi renomeado para `/jogo_do_bixo`, com 16
animais disponíveis para escolha. As apostas exibem imagens ilustrativas
geradas para cada resultado; dados, roleta e caça-níquel têm animações em GIF.
No blackjack, as cartas 10, J, Q e K têm metade do peso das demais: juntas,
passam de 30,8% para aproximadamente 18,2% das cartas sorteadas. Cada vitória
consecutiva no blackjack aumenta em 10% o bônus sobre o lucro, até +200%; uma
derrota zera a sequência e um empate a mantém. A sequência é salva entre
reinicializações. No maior/menor, tirar 7 devolve a aposta; no jokenpô, um
empate também devolve a aposta.

Os pagamentos de moeda, dados, roleta, jogo do bicho, caça-níquel, maior/menor e
jokenpô foram ajustados para aproximadamente 95% de retorno esperado antes
dos bônus de prestígio. O retorno é calculado para os jogos de chance fixa;
blackjack e desafios entre jogadores seguem suas próprias regras. Os bônus
de prestígio podem elevar o retorno real acima desse valor. Como os prêmios
são inteiros, apostas muito pequenas podem se afastar mais do alvo por causa
do arredondamento.

O owner do bot pode usar `/resetar_dados_jogadores` para escolher entre
zerar os saldos globais e locais dos jogadores ou liberar os cooldowns de
recompensas globais e locais. O comando pede confirmação; os caixas dos
cassinos e o histórico estatístico são preservados ao zerar saldos.
A recompensa mensal global varia de 1.000 a 20.000 moedas.

Qualquer apostador pode usar `/feedback` para enviar uma sugestão ou opinião
diretamente por mensagem privada ao owner do bot. O bot confirma em uma
resposta privada se a entrega foi concluída.

Ao iniciar, o bot publica no canal `1560451788254216343` do servidor
`1467549007932030998` o texto de atualização definido em
`UPDATE_ANNOUNCEMENT_MESSAGE` no código e menciona o cargo
`1559362476921987072`. O texto é enviado automaticamente quando muda e seu
envio fica registrado no banco, sem consultar commits Git. Ao preparar uma
atualização, ajuste esse texto para resumir novidades e também correções em
comandos e mecânicas. Esta versão anuncia trabalho e roubo, os jogos
`/maior_menor` e `/jokenpo`, as imagens dos resultados, a renomeação para
`/jogo_do_bixo` e seus 16 animais, a redução dos cooldowns de trabalho e roubo
para 8 horas, o aumento dos salários e ganhos de roubo, o balanceamento de
pagamentos, os botões para repetir apostas na mesma mensagem e a organização
de `/ajuda` por funcionalidade, além das correções em jogos globais e
cassinos locais. O owner também pode usar `/anunciar_update` para reenviar
manualmente a mensagem atual. O bot
precisa ter permissão para enviar mensagens e embeds; o cargo deve existir no
servidor e ser mencionável pelo bot.

Os comandos `/upgrade_casa_principal`, `/upgrade_cassino` e
`/upgrade_prestigio` exibem uma confirmação antes da compra. Depois de cada
compra, a mensagem oferece o próximo nível do mesmo upgrade para confirmação
quando houver saldo suficiente.

## Excluir um cassino

O dono pode usar `/excluir_cassino` no servidor. O bot pede confirmação;
ao confirmar, transfere o caixa restante para o saldo global do dono na
proporção de 1:1 e apaga os saldos locais dos jogadores e o histórico daquele
cassino. Essa exclusão é permanente.
