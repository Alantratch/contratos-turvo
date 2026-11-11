# AGENTS.md — contrato de execução para agentes e ChatGPT

Projeto canônico: `Alantratch/contratos-turvo` (privado). Stack: FastAPI, PostgreSQL, worker PNCP e Docker Compose no Coolify, servidor `localhost`.

## Meta permanente (leia primeiro)
Ver `docs/GOAL.md`. A meta é **entregar um sistema funcionando, conferido e seguro no Coolify local** para contratos históricos e futuros de Turvo, com visualização em calendário por secretaria e alertas auditáveis. Código no Git não significa aplicação em produção; cada status deve ser comprovado.

## Regra inegociável: todo pedido de alteração é versionado
Para **cada solicitação de mudança de código, infraestrutura, regra, documentação ou layout**:
1. Verifique o HEAD, leia os arquivos envolvidos e explique o impacto antes de alterar. Não sobrescreva mudanças concorrentes.
2. Registre o objetivo e critérios de aceite em `docs/PEDIDOS.md` (ou Issue GitHub), atribuindo identificador incremental `CT-XXXX`; um pedido pode englobar commits relacionados, mas nunca alterações sem rastreio.
3. Trabalhe em branch `feat/CT-XXXX-descricao` ou `fix/CT-XXXX-descricao` quando viável; solicite revisão via PR para alterações que afetem dados, segurança, produção ou infraestrutura. Alterações menores podem usar commit direto quando explicitamente permitido e os testes estiverem verdes.
4. Commits com Conventional Commits: `feat(calendar): ...`, `fix(sync): ...`, `docs(process): ...`. Não reescreva histórico publicado ou faça force push.
5. Atualize `CHANGELOG.md`, testes, documentação operacional e versão quando aplicável. Nunca invente evidências de testes. Associe o pedido ao commit/PR na resposta final.
6. Execute testes de sintaxe, API, segurança, fluxo de dados e build/Compose necessários; se falhar, corrija antes de considerar pronto.
7. **Deploy apenas com acesso autorizado e recursos identificados.** Primeiro valide GitHub Actions; depois implemente no Coolify; verifique saúde/logs/funcionamento, e registre SHA implantado. Se não houver ferramenta para deploy, declare explicitamente 'não implantado' e forneça o bloqueio exato.
8. Informe ao final: o que mudou, arquivos tocados, SHA e link do commit, resultado de testes, situação no Coolify, riscos remanescentes e rollback. Nenhuma resposta pode afirmar sucesso de implantação sem evidência.

Alterações de produção devem ser reversíveis. Mantenha banco, backups, volumes e segredos fora do Git. Nunca apague dados em uma atualização. Em alterações de banco, use migrações explícitas, compatíveis e com plano de rollback (não confie apenas em `create_all`).

## Padrão visual obrigatório (Ponytail + UI/UX Pro Max como princípios)
Consultar `docs/DESIGN_SYSTEM.md`. Interface administrativa moderna, minimalista, funcional e responsiva. Paleta institucional: azul `#082d53`, verde `#00875a`, branco `#ffffff`, cinza `#f8fafc`. Sem gradientes, emojis decorativos, ícones misturados ou dashboards com números fictícios. Dar prioridade a calendário real de vencimentos, busca, secretaria, data, alertas e ações pendentes. Tipografia e contrastes WCAG AA, navegação por teclado, foco evidente, labels acessíveis, feedback de carregamento/erro/vazio, telas de celular, datas pt-BR, valores BRL. Não introduzir framework ou bibliotecas desnecessárias.

Ferramentas externas Ponytail e UI/UX Pro Max só podem ser declaradas como **executadas/instaladas** se houver evidência; do contrário, aplicar os princípios de design e engenharia equivalentes.

## Segurança e consistência PNCP
- `TARGET_CNPJ` deve ser validado antes de salvar; não incluir contratos de outro órgão.
- Coleta idempotente, tolerante a falhas, e sem excluir contratos existentes após erro.
- Classificação por secretaria e correções humanas não podem ser sobrescritas automaticamente.
- Calendário deve refletir datas do banco e não prometer vencimento jurídico sem validação dos aditivos.
- Alertas externos desabilitados até homologação da secretaria, destinatários e SMTP.
- HTTP Basic é provisório: para produção, exigir acesso restrito por Cloudflare Access, depois RBAC por usuário, auditoria e backup com restauração testada.
- Não publicar portas de PostgreSQL, nem senhas, tokens ou arquivos `.env`.
