# Design System — Contratos Turvo (shadcn/ui-inspired)

## Linguagem visual
- Produto: administrativo público, moderno, calmo, preciso, sem aparência de template genérico.
- Primário quase preto `#18181b`; superfícies `#ffffff` e `#f8fafc`; cinzas neutros e cores semânticas apenas para sucesso, atenção e erro.
- Cards com borda sutil e raio entre 7–10px, grid consistente, tipografia legível, títulos com hierarquia e amplo espaço de respiro.
- Primitives visuais seguem a linguagem do [shadcn/ui](https://ui.shadcn.com/), mas permanecem implementados no HTML/CSS/JS já existente para evitar dependências e migração estrutural.
- Não usar gradientes, emojis, números fictícios, textos ambíguos, efeitos que desviem da tarefa ou mais de um ícone sem significado.

## Jornadas principais
1. **Administração:** entrar e ver vencimentos críticos, pendências de secretaria, status da sincronização e alertas.
2. **Secretaria:** filtrar contratos, identificar vencimento e conferir detalhes e data.
3. **Calendário:** navegar entre meses, aplicar filtro de secretaria, clicar num dia e abrir seus contratos sem perder o contexto.
4. **TI:** verificar erros, cursor histórico e dados pendentes sem que o sistema esconda falhas.

## UX de calendário
- Semana inicia segunda-feira, rótulos em português.
- Dia atual distinguível, dia selecionado destacado, prazo dentro de 30 dias com sinalização discreta.
- Em desktop, calendário + painel lateral; em celular, conteúdo empilhado e indicadores compactos.
- Botões de dias acessíveis por teclado e texto para leitores de tela. Contagem é obtida da API agregada, não limitada a uma página.
- Estado vazio é explícito; nunca criar eventos fictícios. Mostrar que são **datas publicadas**, não juízo jurídico definitivo.

## Qualidade antes de publicar
- Componentes responsivos desde 320px, nenhuma rolagem horizontal da página principal.
- Contraste WCAG AA, foco visível, labels reais, navegação por teclado, sem comunicação baseada apenas em cor.
- Erros e carregamento tratados; todas as chamadas preservam autenticação e dados internos.
- Revisão visual desktop/mobile, teste API, smoke test Docker e CI verde.
