# Contratos Turvo

Painel interno da Prefeitura de Turvo/PR para monitoramento de contratos publicados no PNCP e contratações publicadas no Compras.gov.br, com histórico importado, atualização incremental, classificação por secretaria e alertas de vigência.

**Estado:** MVP funcional sujeito a homologação de dados, destinatários, autenticação e deploy. O sistema não substitui a validação de contratos/aditivos pela área responsável.

## Meta e versionamento

Meta: implantar e homologar o sistema no Coolify **localhost**. Cada pedido de alteração deve ser registrado em `docs/PEDIDOS.md` e rastreado por commit, testes e atualização do `CHANGELOG.md`. Ver `docs/GOAL.md` e `AGENTS.md`.

O painel inclui **calendário de vencimentos** por mês e secretaria, mostrando todos os contratos do dia com objeto, fornecedor, valor e situação. Contratações do Compras.gov.br ficam em acervo separado e não são contadas como contratos.

## Instalação Coolify

1. Em **Projects > New Resource > Git Repository** selecione este repositório **privado** via GitHub App autorizada ou SSH Deploy Key somente-leitura.
2. Servidor: **localhost**; método **Docker Compose**; Base Directory `/`, Compose Location `/compose.yaml`.
3. Crie domínio HTTPS no serviço `web` com **porta interna 8000**, sem publicar portas do banco.
4. Use o Cloudflare Access para limitar o acesso institucional. O app tem HTTP Basic como segunda barreira: as credenciais são geradas pelo Coolify.
5. Faça o deploy, teste `/healthz`, abra o dashboard, verifique **Sincronização** e valide amostras no PNCP.
6. Cadastre secretarias e seus emails, classifique os contratos. **Só então** habilite `ALERTS_ENABLED=true` e configure SMTP.
7. Configure backup recorrente do volume PostgreSQL, cópia externa e teste restauração.

Variáveis geradas automaticamente pelo Coolify: `SERVICE_PASSWORD_64_DB`, `SERVICE_USER_ADMIN`, `SERVICE_PASSWORD_64_ADMIN`. O arquivo `.env.example` documenta o uso fora do Coolify. Não comite `.env`.

### Desenvolvimento
```bash
cp .env.example .env
# Troque todas as credenciais, depois:
docker compose up --build -d
docker compose logs -f worker
```

O primeiro carregamento histórico avança por janelas de 30 dias desde `SYNC_START_DATE`. Futuras execuções verificam as atualizações e preservam versões brutas quando os registros mudam. Nenhum contrato é apagado quando o PNCP falha.

### Documentação
- `docs/OPERACAO.md`: validação, deploy, alertas e recuperação.
- `docs/ARQUITETURA.md`: modelo, API e limitações.
- `AGENTS.md`: normas obrigatórias para agentes.
- `docs/PEDIDOS.md`: registro de cada pedido e critérios de aceite.
- `docs/GOAL.md`: meta de chegar à produção segura.
- `docs/DESIGN_SYSTEM.md`: identidade moderna e diretrizes de acessibilidade.
- `CHANGELOG.md`: histórico de versões.
