# Validação do incremento 0.1

Data: 7 de outubro de 2026.

- Backend: 32 testes aprovados em SQLite, incluindo fluxo HTTP com CSRF e Origin da interface.
- Migrations: verificação sem alterações pendentes.
- Interface: TypeScript e build Vite aprovados; 30 módulos empacotados.
- Fonte Meet: commit 0a6724e7ada25b90fdf24f9dfca40056a0da0ba3 fixado; código baixado sem modificações.
- Navegador: acesso como Ana Presidente fictícia e registro de presença confirmados na interface, com atualização de 0/7 para 1/7 e recibo visual. Prévia mantida aberta para experimentação.

Não executados: PostgreSQL concorrente, testes de carga 8.000, Docker/CI remoto, IdP institucional real, WebAuthn, vídeo Meet/LiveKit, edição Docs, PDF/A, ICP-Brasil, TSA, WORM e homologação RCPJ.

Este relatório se refere ao incremento de simulação, sem aceite de produção.


## Preparação para publicação no Render — 07/10/2026

- 47 testes Django passaram em SQLite, incluindo autenticação online por senha, CSRF, cookies seguros, bloqueio oficial, limitação de tentativas e preservação do seed.
- Compilação final TypeScript/Vite passou, com campo de senha na tela.
- Roteiro docs/RENDER.md e Blueprint render.yaml preparados para um único serviço Docker mais PostgreSQL.
- Corrigida sintaxe do corpo da função PL/pgSQL na migration de fatos imutáveis. Isso ainda exige execução em PostgreSQL.
- Acrescentados à CI testes com PostgreSQL e construção Docker; esses novos jobs ainda não foram executados no GitHub.
- Não executados localmente: Docker/Linux, PostgreSQL e publicação real no Render. Não existe link público criado por esta preparação.
