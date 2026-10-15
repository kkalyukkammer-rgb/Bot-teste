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

## Excluir um cassino

O dono pode usar `/excluir_cassino` no servidor. O bot pede confirmação;
ao confirmar, transfere o caixa restante para o saldo global do dono na
proporção de 1:1 e apaga os saldos locais dos jogadores e o histórico daquele
cassino. Essa exclusão é permanente.
