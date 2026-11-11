# Registro de pedidos — Contratos Turvo

Cada solicitação de alteração deve gerar entrada rastreável, commit(s), testes e status de implantação. Commits são o histórico imutável; este registro fornece contexto e critérios de aceite. Não gravar segredos.

## CT-0001 — 2026-11-11 — Versionamento por pedido, interface moderna e calendário

**Meta vinculada:** [Issue #1](https://github.com/Alantratch/contratos-turvo/issues/1).

**Pedido:** versionar todas as alterações feitas a partir da conversa, instruir agentes claramente, estabelecer meta de fazer o sistema funcionar no Coolify localhost e acrescentar calendário mensal de vencimentos.

**Entregáveis:**
- Governança obrigatória em `AGENTS.md`, `docs/PEDIDOS.md`, `CHANGELOG.md`, meta e design system.
- Calendário mensal com navegação, filtros de secretaria, contagens reais por dia e detalhes ao selecionar data.
- Filtro por data exata na listagem de contratos.
- Testes de API, autenticação e consulta agregada; CI e build Docker.
- Documentação de operação para deploy versionado e bloqueios.

**Aceite técnico:** APIs e layout versionados no Git, CI verde com testes pertinentes, sem comprometer outros serviços. **Implantação em produção é um aceite separado**, condicionado à existência do recurso Coolify, acesso seguro, validação PNCP/aditivos e backups.

**Status de produção:** pendente de implantação e homologação.

## CT-0002 — 2026-11-11 — Tolerar resposta vazia do PNCP

**Pedido:** concluir o deploy no Coolify e tornar a sincronização real tolerante ao HTTP 204 do PNCP, que indica uma janela sem contratos publicados.

**Entregáveis:**
- Adaptador PNCP encerra a janela sem tentar decodificar JSON vazio.
- Teste automatizado para resposta HTTP 204.
- Registro operacional e changelog atualizados.

**Aceite técnico:** o worker registra a janela como concluída sem mover dados indevidamente, e o deploy posterior inicia `db`, `worker` e `web` sem habilitar alertas de e-mail.

**Status:** em validação no Coolify `localhost`.

## CT-0003 — 2026-11-11 — Separar contratações e completar calendário

**Pedido:** importar também as contratações do Compras.gov.br, sem misturá-las aos contratos, e mostrar todos os contratos do dia no calendário com objeto.

**Implementação:** tabela/API/tela próprias para contratações; calendário retorna os itens completos do mês e não depende do limite paginado da tabela.

## CT-0004 — 2026-11-11 — Refatoração visual e agenda operacional

**Pedido:** refazer a aplicação com uma experiência UI/UX mais clara, corrigindo principalmente o calendário e mantendo a aplicação instalável no Coolify.

**Implementação:** frontend existente em HTML/CSS/JS reorganizado com primitives visuais inspirados no shadcn, sem introduzir React/Tailwind no backend FastAPI; calendário com seleção automática do primeiro vencimento do mês, painel detalhado por dia, filtro por área, link contextual do PNCP e layout responsivo.

**Aceite técnico:** JavaScript válido, testes automatizados verdes, configuração Compose válida, deploy sem alteração de volumes/serviços e smoke test de saúde, autenticação e assets.

**Status:** pronto para homologação visual e funcional em produção; alertas de e-mail continuam desligados.
