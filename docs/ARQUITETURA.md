# Arquitetura e modelo de dados

## Fontes
- Termos de contrato: GET /api/pncp/v1/orgaos/{cnpj}/contratos/{ano}/{sequencial}/termos; retorna aditivos, apostilamentos e outros termos vinculados ao contrato.
- Consulta oficial PNCP: https://pncp.gov.br/api/consulta/swagger-ui/index.html
- Consulta por data de publicação: `GET /v1/contratos` com `dataInicial`, `dataFinal`, `cnpjOrgao`, `pagina`, `tamanhoPagina`.
- Atualização global: `GET /v1/contratos/atualizacao` (confirmar comportamento em testes de integração reais).
- CNPJ de origem obrigatório: `78279973000107`. Não inferir por cidade ou nome.
- Compras.gov.br: contratações publicadas são importadas pelo endpoint de Dados Abertos e ficam separadas dos contratos assinados.

## Serviços
`web` FastAPI (HTTP Basic + opcional Cloudflare Access) → `db` PostgreSQL ← `worker` PNCP e notificações SMTP. Somente `web` deve receber um domínio. Nenhum serviço publica portas no host.

## Tabelas
- contract_terms: termos publicados pelo PNCP vinculados ao contrato-base, com objeto, tipo, valores, prazo e vigência.
- `contracts`: chave PNCP única, fornecedor, objeto, valores, vigência, unidade, classificação e JSON original.
- `procurements`: chave PNCP da contratação, modalidade, situação, objeto, processo, valores e datas do Compras.gov.br.
- `contract_revisions`: snapshots de cada versão distinta observada após a instalação; **não** é o histórico prévio integral de todos os aditivos.
- `secretaries`: secretaria e endereço de alerta validado.
- `sync_state`: cursor do backfill por publicação; só avança após janela processada.
- `sync_runs`: auditoria de cada janela e erros (sem descartar dados anteriores).
- `alert_deliveries`: previne duplicação por contrato + régua + vigência + destinatário.
- `audit_events`: criação de secretaria e associação manual.
- Classificação automática: unidades específicas do PNCP viram áreas sem e-mail e recebem os contratos ainda não classificados; a unidade genérica da Prefeitura permanece pendente de revisão porque a API não informa a secretaria/gestor real.

## API do painel (autenticada)
- `GET /api/summary`: totais e próximos vencimentos;
- `GET /api/contracts?q=&page=&limit=&period=&secretary_id=`: busca paginada;
- `GET /api/procurements?q=&page=&limit=`: busca as contratações publicadas no Compras.gov.br;
- `GET /api/secretaries`; `POST /api/secretaries`;
- `POST /api/contracts/{id}/secretary`: atribuição humana;
- `GET /api/sync`: última sincronização e progresso;
- `GET /healthz`: healthcheck do banco (sem autenticação).

## Regra de datas
Uma data PNCP é uma **informação publicada**, não certificado de vigência jurídica. Contratos encerrados, rescindidos, com aditivos ainda não refletidos ou não publicados devem ser conferidos pelo administrativo. Ausência de vencimento entra em filtro próprio. Atribuição de secretaria **nunca é automática por nome do fornecedor**.

## Trabalhos pendentes de homologação
1. Testar consulta real, paginação e atrasos do PNCP e do Compras.gov.br no ambiente de rede do Coolify.
2. Diferenciar alterações de vigência, acréscimo/supressão, rescisão e apostilamento nos termos importados.
3. Confirmar nomenclatura oficial de secretarias e responsáveis, criar fluxo de revisão de contratos.
4. Autenticação corporativa por usuário individual e RBAC com trilha auditável; HTTP Basic é barreira provisória.
5. Exportações, deduplicação entre órgãos/CNPJs, vencimento por secretaria, regras por tipo de contrato.
6. Migrações Alembic antes de versões com mudanças de schema (MVP usa create_all somente na primeira estrutura).
