# Registro de pedidos — Contratos Turvo

Cada solicitação de alteração deve gerar entrada rastreável, commit(s), testes e status de implantação. Commits são o histórico imutável; este registro fornece contexto e critérios de aceite. Não gravar segredos.

## CT-0001 — 2026-11-11 — Versionamento por pedido, interface moderna e calendário

**Pedido:** versionar todas as alterações feitas a partir da conversa, instruir agentes claramente, estabelecer meta de fazer o sistema funcionar no Coolify localhost e acrescentar calendário mensal de vencimentos.

**Entregáveis:**
- Governança obrigatória em `AGENTS.md`, `docs/PEDIDOS.md`, `CHANGELOG.md`, meta e design system.
- Calendário mensal com navegação, filtros de secretaria, contagens reais por dia e detalhes ao selecionar data.
- Filtro por data exata na listagem de contratos.
- Testes de API, autenticação e consulta agregada; CI e build Docker.
- Documentação de operação para deploy versionado e bloqueios.

**Aceite técnico:** APIs e layout versionados no Git, CI verde com testes pertinentes, sem comprometer outros serviços. **Implantação em produção é um aceite separado**, condicionado à existência do recurso Coolify, acesso seguro, validação PNCP/aditivos e backups.

**Status de produção:** pendente de implantação e homologação.
