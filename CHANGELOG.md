# Histórico de versões

## [0.13.0] — 2026-11-12
- `GET /api/summary` aceita filtros retrocompatíveis `secretary_id` e `window` (`30`, `60`, `90`) e retorna a distribuição real por faixas de prazo (`by_window`).
- Visão geral (`#overview`) ganhou filtros de área responsável e janela de vencimento, gráfico interativo por secretaria e gráfico de distribuição por prazos em HTML/CSS/JS vanilla, sem novas dependências.

## [0.12.3] — 2026-11-12
- Validação do CNPJ-alvo e preservação de campos em payloads parciais.
- Snapshots de alterações de termos, rollback por contrato e paginação Equiplano.
- Retries e resposta 204 tratados no sincronizador Compras.gov.

## [0.12.2] — 2026-11-12
- Recalculo da vigência efetiva desde o contrato-base e termos não excluídos, evitando datas stale após aditivos ou anulações.
- Atualizações da base reaplicam termos ativos, preservam termos parciais e interpretam qualificações/booleanos da fonte.
- Filtro `Em vigência` como visão inicial do acervo; contratos históricos continuam acessíveis em `Todos` e `Encerrados`.

## [0.12.1] — 2026-11-12
- Revisão responsiva por módulo para telas de celular.
- Tabelas de contratos, contratações, licitações e sincronização viram cartões empilhados, sem rolagem horizontal interna.
- Menu móvel ganhou fundo de fechamento e os controles de calendário mantêm leitura e toque adequados em telas estreitas.

## [0.12.0] — 2026-11-11
- Catálogo anual de licitações pela rota `GET /api/licitacoes?year=YYYY`, preservando registros sem data de abertura.
- Clique em evento ou linha do catálogo abre modal com objeto, datas, valores, situação, contrato e links oficiais.
- Classificação revisada por cores: próxima, em andamento, aguardando resultado, resultado/contrato e anulada/suspensa.
- “Aguardando resultado” só é aplicado após o encerramento da janela de propostas; alertas continuam desligados.

## [0.11.0] — 2026-11-11
- Novo módulo “Agenda de licitações”, separado do acervo de contratos.
- Calendário por abertura de propostas com filtros de próximas, realizadas, resultado publicado e anuladas/suspensas.
- Vínculo automático com contrato PNCP pela chave oficial da compra; quadro de impugnações/esclarecimentos fica disponível quando a fonte fornece o link.
- Migração aditiva do PostgreSQL/SQLite e alertas de e-mail preservados desligados.

## [0.10.0] — 2026-11-11
- Calendário refeito no formato de agenda mensal de Turvo, com prévias do objeto, navegação e painel de detalhes do dia.
- Filtros de todos, próximos e encerrados calculados a partir dos mesmos itens da API, sem contagens independentes ou dados de exemplo.
- Bootstrap 5.3.3 empacotado localmente e caixa preta de alto contraste adicionada para uso em celular; alertas de e-mail permanecem desligados.

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
