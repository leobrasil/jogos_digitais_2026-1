# Jogos Digitais 2026 — controle de commits

Neste projeto, **cada aluno deve fazer pelo menos um commit por semana** (segunda a domingo) no repositório do seu grupo. A contagem é automática, por aluno, em todas as branches.

## Para os alunos: como cadastrar o projeto

Faça **um cadastro por grupo**.

1. Se o repositório do projeto for **privado**, adicione o professor (`leobrasil`) como colaborador: no repositório, *Settings → Collaborators → Add people*.
2. Abra a aba **Issues** deste repositório e clique em **New issue → Cadastrar projeto**.
3. Escolha a turma, cole o link do repositório e liste os integrantes, um por linha:
   ```
   Maria da Silva; mariasilva
   João Souza; joaosouza-dev
   ```
4. Envie. Em cerca de um minuto aparece a resposta na própria issue:
   - ✅ **Cadastro confirmado**: a issue é fechada e pronto.
   - ❌ **Cadastro não concluído**: corrija o que for apontado **editando a issue** (menu `···` → *Edit*). A verificação roda de novo sozinha.

Para trocar integrantes ou o repositório depois, edite a mesma issue.

### Para o commit contar para você

- Faça os commits com **a sua própria conta** do GitHub.
- O e-mail configurado no Git (`git config user.email`) precisa estar cadastrado na sua conta, em *Settings → Emails*. Se não estiver, o commit aparece como "não identificado" e não conta para ninguém.
- Commits de merge não contam.

---

## Para o professor

### Como funciona

| Arquivo | O que faz |
|---|---|
| `.github/ISSUE_TEMPLATE/cadastro.yml` | Formulário de cadastro (turma, repositório, nome do jogo, integrantes). |
| `.github/workflows/cadastro.yml` | Valida cada issue de cadastro, aceita o convite de colaborador, grava `cadastro.json` e responde ao aluno. |
| `.github/workflows/relatorio.yml` | Toda segunda-feira às 08:47 gera o relatório da semana anterior e publica no repositório privado de relatórios. |
| `cadastro.json` | Lista de grupos cadastrados (sem dados sensíveis, porque este repositório é público). |

### Configuração inicial (uma vez só)

1. **Repositório privado para os relatórios.** Crie um repositório **privado** chamado `jogos_digitais_2026-1-relatorios`. Marque a opção *Add a README file*, para ele não ficar vazio.
2. **Token de acesso.** Em *Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token (classic)*:
   - Nome: `controle-commits`
   - Validade: até o fim do semestre
   - Permissão: marque **`repo`** (inteira)

   O token *fine-grained* não serve aqui, porque ele não enxerga repositórios de outros donos, mesmo quando você é colaborador.
3. **Salvar o token.** Neste repositório, vá em *Settings → Secrets and variables → Actions → New repository secret*. Nome: `COMMITS_TOKEN`. Valor: o token gerado.
4. **(Opcional) Variáveis.** Em *Settings → Secrets and variables → Actions → Variables*:
   - `INICIO`: primeira semana que conta, no formato `2026-10-05`. Esse é o padrão.
   - `REPORT_REPO`: use se der outro nome ao repositório de relatórios.

### Gerar o relatório na hora

Aba **Actions → Relatório semanal de commits → Run workflow**.

O relatório fica no README do repositório privado, com:

- gráfico da semana;
- gráfico acumulado;
- tabela por turma;
- lista de commits não identificados;
- histórico em `historico/`.

Também é aberta uma issue lá com quem ficou sem commit, e você recebe uma notificação por e-mail.
