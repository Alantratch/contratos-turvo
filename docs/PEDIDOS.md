# Registro de pedidos — Contratos Turvo

Cada solicitação de alteração deve gerar entrada rastreável, commit(s), testes e status de implantação. Commits são o histórico imutável; este registro fornece contexto e critérios de aceite. Não gravar segredos.

## CT-0011 — 2026-11-11 — Agenda de licitações

**Pedido:** criar um módulo separado para acompanhar licitações por data, com sessão realizada ou futura, resultado, impugnações e contratos vinculados.

**Implementação:** adicionada a agenda mensal de licitações do Compras.gov.br, com filtros de próximas, realizadas, com resultado e anuladas/suspensas. A data usada é a abertura oficial de propostas; o resultado usa `existeResultado` e `valorTotalHomologado`; o contrato usa a chave oficial `numeroControlePncpCompra` quando o PNCP a fornece.

**Transparência de fonte:** a API pública não entrega um booleano confiável “houve impugnação”. Quando há `informacaoComplementar`, o painel mostra o quadro oficial para consulta; caso contrário, informa que a fonte não declarou essa ocorrência. Não são criados status jurídicos por inferência.

**Escopo preservado:** licitações continuam separadas de contratos e contratações; alertas de e-mail permanecem desligados. A migração de schema é aditiva e preserva dados existentes.

**Aceite técnico:** 16 testes automatizados verdes, API mensal agrupada por data, vínculo de teste com contrato PNCP, JavaScript válido, Compose válido e deploy no Coolify acompanhado de smoke test.

**Status:** pronto para homologação.

## CT-0012 — 2026-11-11 — Catálogo anual e detalhe em modal

**Pedido:** ao clicar na licitação abrir um popup, catalogar o ano inteiro e refinar a classificação visual e de resultado.

**Implementação:** `/api/licitacoes?year=YYYY` passou a retornar o catálogo anual completo, inclusive registros sem data de abertura; a agenda mensal usa os mesmos itens e o clique em qualquer evento ou linha abre modal com objeto, datas, valores, situação, contrato e fontes oficiais. As etapas agora distinguem sessão futura, sessão de hoje, em andamento, aguardando resultado, resultado publicado, contrato publicado e anulada/revogada/suspensa.

**Consistência:** “Aguardando resultado” só aparece depois do encerramento da janela de propostas; enquanto ela estiver aberta, o item fica “Em andamento”. O campo oficial `existeResultado`, valor homologado e contrato vinculado continuam preservados para auditoria.

**Aceite técnico:** 17 testes automatizados verdes, JavaScript/Python válidos e catálogo anual coberto por teste com registro sem data.

**Status:** pronto para homologação e publicação.

## CT-0010 — 2026-11-11 — Calendário em formato de agenda móvel

**Pedido:** aproximar o calendário da agenda pública de licitações de Turvo, usar Bootstrap e melhorar a leitura no celular sem apresentar dados inconsistentes.

**Implementação:** calendário reorganizado em cabeçalho mensal, navegação, caixa preta de alto contraste para filtros, contagens de todos/próximos/encerrados, prévias do objeto nos dias e painel completo do dia selecionado. Bootstrap 5.3.3 foi empacotado localmente, sem dependência de CDN em produção.

**Consistência:** todos os contadores, filtros, células e detalhes derivam da mesma lista de itens retornada por `/api/calendar`; a API e as fontes PNCP/Compras.gov.br/Equiplano não foram duplicadas nem alteradas.

**Aceite técnico:** JavaScript válido, teste do asset Bootstrap, suíte automatizada verde, Compose válido, deploy no Coolify e smoke test de saúde, autenticação, calendário e sincronização.

**Status:** pronto para homologação.

## CT-0009 — 2026-11-11 — Priorizar contratos ativos

**Pedido:** contratos encerrados não devem aparecer na frente da aba Contratos; contratos ativos precisam de maior visibilidade.

**Implementação:** a API agora ordena explicitamente contratos em vigência primeiro, demais registros não encerrados em seguida, contratos sem data depois e encerrados por último. Nenhum registro foi ocultado ou excluído.

**Aceite técnico:** teste automatizado de prioridade ativo versus encerrado, suíte existente verde, Compose válido e smoke test da API.

**Status:** pronto para deploy.

## CT-0008 — 2026-11-11 — Logo vertical colorida

**Pedido:** trocar a logo horizontal pela versão vertical colorida do Turvo.

**Implementação:** substituído o asset por `Logo Turvo.png` do Drive e ajustado o enquadramento da marca na sidebar; removido o filtro monocromático aplicado à versão anterior.

**Escopo preservado:** nenhuma rota, API, regra de importação, dado, autenticação, volume ou serviço foi alterado.

**Aceite técnico:** asset PNG válido, JavaScript preservado, teste de saúde e validação visual da sidebar publicada.

**Status:** pronto para homologação.

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

## CT-0013 — Revisão responsiva por módulo

- **Solicitação:** revisar a visualização no celular e corrigir bugs de design em todos os módulos.
- **Implementado:** menu móvel com fechamento por fundo, tabelas transformadas em cartões legíveis em telas estreitas, filtros e paginação reorganizados, catálogo de licitações sem rolagem horizontal interna e preservação do calendário como grade compacta com painel de detalhes.
- **Validação:** viewport de 390 px em produção, sem overflow horizontal no documento; módulos de visão geral, contratos, contratações, licitações, calendário, secretarias e sincronização conferidos.

## CT-0014 — Vigência efetiva e acervo inicial de contratos

**Pedido:** corrigir contratos cuja vigência publicada foi alterada por aditivos e evitar que contratos encerrados ocupem a visão inicial do acervo, sem apagar o histórico.

**Escopo:** recalcular a vigência desde os campos do contrato-base e reaplicar somente termos não excluídos, inclusive após atualização do contrato-base, incluindo reversão quando o último termo for anulado/excluído; preservar campos em atualizações parciais e interpretar booleanos/qualificações da fonte; adicionar filtro explícito de contratos em vigência e deixar essa visão como padrão da interface. Os filtros `Todos` e `Encerrados` continuam disponíveis para consulta histórica.

**Aceite técnico:** testes de recomputação após exclusão e atualização do contrato-base, atualização parcial de termo, booleanos textuais e qualificações de vigência/valor; filtro API `active`, JavaScript/Python válidos, suíte automatizada executada quando as dependências estiverem disponíveis e smoke test no Coolify após revisão.

**Status:** implementado na branch `fix/CT-0014-vigencia-efetiva-acervo`; aguardando revisão e deploy.

**Commit:** `49077ec` — `fix(contracts): [CT-0014] recalculate effective validity`.
