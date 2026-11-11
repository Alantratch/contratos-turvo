# Instruções para Codex e demais agentes

Projeto: contratos-turvo. Prioridade: sistema auditável, barato, mantenível e seguro para a Prefeitura de Turvo/PR.

## Ponytail — simplicidade com segurança
Antes de escrever, verificar se a função já existe; escolher a menor mudança que preserva validações, tratamento de erro, segurança e testes. Não adicionar microserviços, filas, Redis ou estruturas duplicadas sem necessidade. Não modificar produção diretamente: código -> PR -> CI -> revisão -> deploy Coolify.

## UI/UX Pro Max — critérios aplicados
Sistema administrativo institucional: tipografia legível, hierarquia clara, contraste WCAG AA, navegação por teclado, sem animações gratuitas, layouts responsivos e acesso rápido a pendências. Paleta municipal: azul #082d53, verde #00875a, fundo branco #ffffff e #f8fafc; vermelho somente para risco real; sem gradientes/emoji na interface. Datas em pt-BR e valores em BRL. Nunca usar dados simulados como números reais.

## Skills opcionais no ambiente Codex
- Ponytail: https://github.com/DietrichGebert/ponytail (instalar pela forma oficial compatível com Codex).
- UI/UX Pro Max: `npx ui-ux-pro-max-cli init --ai codex` (revisar arquivos gerados antes de incluir no Git).

## Segurança
- Nunca registrar credenciais ou .env no repositório.
- `TARGET_CNPJ` deve ser validado antes de gravar qualquer contrato.
- Toda sincronização deve ser idempotente e preservar classificação manual.
- Nenhum dado novo deve sobrescrever um valor validado por servidor sem confirmação.
- Nunca enviar alerta sem responsável/email confirmado e flag de envio.
- Não tornar GitHub privado público, não publicar PostgreSQL na rede.
- Revisar mudanças em esquema e testes antes do deploy.
