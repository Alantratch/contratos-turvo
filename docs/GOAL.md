# Meta operacional — Contratos Turvo

**Acompanhamento contínuo:** [Meta de implantação no Coolify — Issue #1](https://github.com/Alantratch/contratos-turvo/issues/1).

**Estado em 11/11/2026:** código versionado, MVP e testes de CI; implantação em `localhost` ainda não comprovada. Os testes de integração com dados reais do PNCP e a conferência dos aditivos ainda são pendências. Não rotular como produção homologada sem satisfazer os critérios.

## Resultado almejado
Uma central web moderna e acessível, em instalação versionada no Coolify local, que mostre **todos os contratos disponíveis do PNCP** para Turvo/PR (CNPJ 78279973000107), com histórico importado, atualização incremental, calendário mensal de vencimentos, filtros por secretaria, trilha de auditoria e alertas antecipados verificados.

## Definição de sucesso (checklist de aceite)
- [x] Repositório privado, Docker Compose e worker/base definidos.
- [x] Painel de resumo e listagem; visão em calendário com consulta SQL agrupada e detalhe por dia.
- [x] Regras de versionamento por pedido, registro da meta e padrão visual documentados.
- [ ] Aplicação criada no Coolify **localhost**, Docker Compose, repositório privado conectado com credencial de leitura, domínio interno seguro e recurso implantado.
- [ ] Banco persistentemente saudável e restauração de backup em ambiente isolado demonstrada.
- [ ] Worker consultou o PNCP real, importou amostra verificável, avançou cursor e lidou com paginação/limites/erros.
- [ ] Contratos históricos e novos conferidos por amostragem com datas, aditivos/termos e identificação do órgão.
- [ ] Secretarias e destinatários conferidos; alertas testados em modo controlado antes de habilitar envio externo.
- [ ] Integração de termos/aditivos e classificação de situações especiais implementadas.
- [ ] Autenticação e permissão por usuário e trilha de auditoria adequadas para uso administrativo.
- [ ] Acesso mobile, teclado, contraste, filtros e calendário validados no domínio real; métricas e tarefas de sincronização monitoradas.
- [ ] Deploy e rollback documentados com versão/SHA e avaliação dos responsáveis.

## Caminho prioritário
1. Entregar MVP versionado com CI verde, sem dados simulados apresentados como reais.
2. Conectar repositório privado ao Coolify localhost, criar recurso Compose com PostgreSQL sem exposição externa, configurar HTTPS/Access.
3. Validar sincronização PNCP e amostras históricas contra os registros oficiais; corrigir importador se necessário.
4. Conferir aditivos, classificar secretarias, configurar alertas em homologação.
5. Concluir controles de produção e formalizar aceite administrativo.

## Regra para qualquer agente
Não confundir **objetivo** com **estado atual**. Se alguma etapa não puder ser executada por limitação de ferramentas ou permissões, registre o bloqueio e avance no que puder sem comprometer os outros serviços do Coolify.
