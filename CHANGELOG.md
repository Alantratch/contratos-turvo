# Histórico de versões

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
