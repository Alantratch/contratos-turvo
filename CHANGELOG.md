# Histórico de versões

Cada pedido atendido gera registro em `docs/PEDIDOS.md`, alteração rastreável por commit e testes.

## [0.3.0] — 2026-11-11
- Contratações do Compras.gov.br importadas em acervo separado de contratos.
- Calendário retorna e exibe todos os contratos do dia com objeto, fornecedor e valor.
- Brasão oficial do Turvo aplicado à identificação do painel.

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
