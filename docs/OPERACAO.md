# Operação e instalação segura no Coolify

## Criar recurso
- Configuração inspecionada em 11/11/2026: Coolify 4.7.5; servidor local `localhost` (`host.docker.internal`), UUID `od7tqmhuvqtt6jrxyhokgqly`, destino `iu1iu9ouhbmx88cposqbog0u`.
- Conectar repositório privado com GitHub App autorizada no repositório ou deploy key somente-leitura. A origem `Public GitHub` isolada NÃO dá acesso a repositório privado.
- Novo Application usando Git Source -> Docker Compose, Compose `/compose.yaml`.
- Vincular domínio HTTPS apenas ao serviço `web` na porta interna `8000`. Opcionalmente usar domínio privado atrás do Cloudflare Tunnel + Access.
- Coolify gera `SERVICE_PASSWORD_64_DB`, `SERVICE_USER_ADMIN` e `SERVICE_PASSWORD_64_ADMIN`; confira Environment Variables antes do deploy.
- Nunca liberar portas `5432` ou `8000` com `ports:`. Nunca habilitar modo Raw Compose sem gerenciar manualmente proxy e redes.

## Verificações pós-deploy
- Banco PostgreSQL: healthy.
- Web: healthy; `GET /healthz` deve retornar `{"status":"ok"}`.
- Dashboard: primeiro acesso deve pedir login HTTP Basic (credenciais do Coolify).
- Sincronização: painel mostra `next_publication_day`; evolui por janelas de 30 dias a cada ciclo. Erros não devem mover o cursor.
- Equiplano: confira uma execução `equiplano` no painel. `EQUIPLANO_START_YEAR=2021` faz o backfill dos contratos e aditivos desde 2021; `EQUIPLANO_VERIFY_TLS=false` é uma exceção temporária porque o portal público entrega cadeia TLS incompleta.
- Conferir amostra de pelo menos 10 contratos no PNCP, inclusive datas de vigência, aditivos e órgão.
- Validar quem são os fiscais e os endereços da secretaria antes de ativar alertas.

## Alertas
`ALERTS_ENABLED` inicia em `false`. Só habilitar após cadastrar secretarias/recipientes e SMTP (TLS porta 587), testar recebimento e aprovação dos responsáveis. Régua: 120/90/60/30/15/7/0 dias, e o histórico evita envios repetidos da mesma etapa/vigência/destinatário.

## Backups
Executar dump PostgreSQL recorrente com retenção e cópia em outro host. Verificar restauração isolada antes de produção. Volume `contratos_postgres` é persistente, mas **não é backup**.

## Falhas
- PNCP 429 ou 5xx: coleta recua e tenta novamente, não remove contratos já importados.
- PNCP 204: a janela não tem contratos; ela é concluída sem tentar ler JSON.
- Falha de e-mail: não registra envio como concluído; tenta de novo no próximo ciclo.
- Backend e worker rodam separados; falhas de API externa não interrompem visualização dos dados existentes.
- Frontend sem domínio/Cloudflare: verificar configuração de roteamento do serviço `web` na porta 8000.

## Controle de versões, calendário e liberação
Cada mudança solicitada segue `AGENTS.md` e ganha entrada em `docs/PEDIDOS.md`, commit e `CHANGELOG.md`. Confirme os checks na branch antes do deploy. Em produção, registrar o SHA implantado, a hora, saúde dos serviços e procedimento de rollback; nunca apagar o volume PostgreSQL ao reverter código.

A aba **Calendário** consulta `GET /api/calendar?month=YYYY-MM&secretary_id=...`, que agrega vencimentos registrados, e `GET /api/contracts?due_date=YYYY-MM-DD`, que retorna os contratos daquele dia. O calendário não conclui a validade jurídica do contrato e pode precisar de atualização de termos/aditivos. Segurança e homologação seguem pendentes até comprovadas em `docs/GOAL.md`.
