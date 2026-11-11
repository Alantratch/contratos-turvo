# Histórico de versões

## [0.9.0] — 2026-11-11
- Aba de contratos passa a priorizar contratos ativos e não encerrados; registros encerrados continuam acessíveis, mas ficam no final da listagem.
- Texto da aba esclarece a ordem de prioridade e teste automatizado cobre a ordenação ativa versus encerrada.

## [0.8.0] — 2026-11-11
- Logo institucional substituída pela versão vertical colorida do Turvo, com enquadramento próprio para a sidebar clara.

## [0.7.0] — 2026-11-11
- Refatoração visual completa da camada administrativa com primitives inspirados no shadcn/ui: superfícies neutras, bordas sutis, controles compactos, estados semânticos e navegação com ícones SVG acessíveis.
- Calendário, tabelas, filtros, indicadores e estados de sincronização receberam a mesma linguagem visual responsiva, sem alterar rotas, dados, autenticação ou alertas.
- Nenhuma dependência nova foi adicionada; a aplicação continua servida pelo HTML/CSS/JS existente.

## [0.6.0] — 2026-11-11
- Integração do Portal de Transparência/Equiplano, que contém contratos e aditivos não publicados no PNCP.
- Backfill desde 2021, com vigência, objeto, fornecedor e aditivos vinculados ao contrato-base.
- Alertas de e-mail continuam desabilitados por padrão.

## [0.5.0] — 2026-11-11
- Sincronização dos termos de cada contrato pelo endpoint oficial do PNCP, incluindo aditivos, apostilamentos e rescisões publicados.
- Aditivos ficam vinculados ao contrato original, aparecem na busca/calendário e atualizam a vigência efetiva quando o termo informa prorrogação.
- Histórico de contratos permanece iniciado em 2021; termos são consultados para todos os contratos importados até o ciclo atual.

## [0.4.0] — 2026-11-11
- Interface administrativa refeita com layout responsivo, hierarquia visual e estados de carregamento/vazio mais claros.
- Calendário reorganizado como agenda operacional: primeiro vencimento real selecionado, contagem por dia e painel lateral com objeto, fornecedor, área, valor, status e link do PNCP.
- Menu móvel, foco visível e componentes de filtros/tabelas ajustados para uso em desktop e celular.

Cada pedido atendido gera registro em `docs/PEDIDOS.md`, alteração rastreável por commit e testes.

## [0.3.0] — 2026-11-11
- Contratações do Compras.gov.br importadas em acervo separado de contratos.
- Calendário retorna e exibe todos os contratos do dia com objeto, fornecedor e valor.
- Brasão oficial do Turvo aplicado à identificação do painel.
- Áreas responsáveis sugeridas automaticamente pela unidade oficial do contrato, sem inventar gestores ou e-mails.

## [0.2.1] — 2026-11-11
- Sincronização PNCP tolerante a respostas HTTP 204 sem conteúdo.
- Teste do adaptador para janelas sem contratos.

## [0.2.0] — 2026-11-11
- Calendário mensal com contagem de vencimentos por dia, filtros por secretaria e abertura de contratos.
- Filtro por data de vencimento exata e API agregada para calendário.
- Diretrizes de versionamento por solicitação, meta de implantação local e padrões de design institucional.
- Testes para calendário, autorização e consistência de contagens.
- **Implantação no Coolify:** não realizada nesta versão; pendente de recurso e homologação.

## [0.1.0] — 2026-11-11
- MVP inicial com coleta PNCP, dashboard, PostgreSQL, alertas desabilitados por padrão e Compose.
