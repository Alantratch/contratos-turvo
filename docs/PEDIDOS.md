# Registro de pedidos — Contratos Turvo

Cada solicitação de alteração deve gerar entrada rastreável, commit(s), testes e status de implantação. Commits são o histórico imutável; este registro fornece contexto e critérios de aceite. Não gravar segredos.

## CT-0007 — 2026-11-11 — Linguagem visual shadcn/ui

**Pedido:** refatorar os designs para uma interface moderna e estilizada, removendo a aparência genérica de IA.

**Implementação:** a camada HTML/CSS/JS existente recebeu primitives visuais inspirados no shadcn/ui: tokens neutros, sidebar clara, controles compactos, bordas discretas, estados semânticos, ícones SVG inline e calendário com composição mais limpa. Textos de operação foram simplificados para uma linguagem de sistema administrativo.

**Escopo preservado:** nenhuma rota, API, regra de importação, autenticação, dado, volume ou serviço foi alterado; alertas de e-mail permanecem desligados. Não foi introduzido React, Tailwind ou dependência nova porque a aplicação atual já entrega a mesma experiência com HTML/CSS/JS.

**Aceite técnico:** JavaScript válido, diff sem erros de whitespace, smoke test de saúde e validação visual da página publicada.

**Status:** pronto para homologação.

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

## CT-0005 — 2026-11-11 — Histórico de termos e aditivos

**Pedido:** importar todos os contratos de pelo menos cinco anos atrás até hoje e também os aditivos/termos publicados depois do contrato original.

**Implementação:** o worker consulta o endpoint oficial de termos por contrato, persiste cada termo vinculado ao contrato PNCP, exibe os aditivos na listagem e no calendário e aplica a última vigência publicada como vigência efetiva, preservando o JSON original e o contrato-base.

**Limitação de classificação:** o PNCP só permite classificar automaticamente quando publica uma unidade específica. Quando a unidade é apenas PREFEITURA MUNICIPAL DE TURVO - PR, o sistema não inventa secretaria, gestor ou e-mail e mantém o contrato pendente de revisão.

**Aceite técnico:** 12 testes automatizados verdes, adaptador tolerante a HTTP 204, backfill configurado desde 2021 e alertas de e-mail desligados.

## CT-0006 — 2026-11-11 — Completar contratos fora do PNCP

**Pedido:** corrigir a ausência dos contratos Vieira e Retecheski e IDS Software, inclusive quando possuem vencimento próximo e aditivos publicados no portal municipal.

**Implementação:** o worker consulta o relatório público de contratos do Portal de Transparência/Equiplano desde 2021, importa contratos e linhas de aditivo, vincula os aditivos ao contrato-base e deixa a vigência efetiva disponível para a tabela e o calendário. O PNCP e o Compras.gov.br continuam preservados como fontes separadas.

**Limitação conhecida:** o certificado público do Equiplano entrega cadeia incompleta no momento; `EQUIPLANO_VERIFY_TLS=false` é explícito e deve voltar a `true` quando o provedor corrigir a cadeia. A origem é pública e não recebe credenciais.

**Aceite técnico:** backfill temporário validado com parser real, 13 testes automatizados verdes, alertas de e-mail desligados e nenhum serviço/banco existente removido.
