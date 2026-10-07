# Mensa Assembleia

Primeiro incremento funcional, baseado no [PRD](../PRD_Mensa_Assembleia.md). O módulo de governança usa Django e React e mantém integração com Meet/Docs separada da apuração. Todo dado de demonstração é fictício.

## Executar localmente

Python 3.12 ou 3.13, Node compatível com Vite 7 e pnpm 11.

1. Criar ambiente Python: `python -m venv .venv`.
2. Instalar: `.venv/Scripts/python.exe -m pip install -r backend/requirements.txt` (Windows) ou `.venv/bin/python -m pip install -r backend/requirements.txt` (Linux).
3. Aplicar migrations e dados fictícios: `python backend/manage.py migrate` e `python backend/manage.py seed_demo`, usando o Python do ambiente.
4. Iniciar backend: `python backend/manage.py runserver 127.0.0.1:8000 --noreload`.
5. Em `frontend`, executar `pnpm install --frozen-lockfile` e `pnpm dev`.
6. Abrir http://127.0.0.1:5173.

O seed é idempotente e não apaga histórico. O simulado não se reinicia automaticamente. Para outro ensaio, criar outro banco ou uma nova assembleia por procedimento de desenvolvimento; não apagar votos ou eventos em um banco existente.

Opcional: `docker compose up --build` cria backend e PostgreSQL de desenvolvimento; definir previamente DJANGO_SECRET_KEY e POSTGRES_PASSWORD com valores aleatórios. O frontend continua iniciado separadamente. Este compose ainda precisa ser validado em ambiente com Docker e não é implantação de produção.

## Roteiro para experimentar

- Entrar como Carla, criar uma procuração para Diego e consultar o código na própria caixa de teste.
- Trocar para Diego, confirmar presença e aceitar o código recebido. Trocar de pessoa encerra presença da sessão anterior.
- Repetir com Elisa para verificar o limite de duas procurações. Uma terceira aceitação é recusada.
- Entrar como Ana, confirmar presença e instalar em segunda convocação. A primeira exige cinco presenças próprias no colégio fictício de sete.
- Abrir uma pauta ordinária. Votar, pedir a palavra e experimentar a cédula de representante em sessões distintas.
- Antes de instalação, preparar todas as procurações necessárias; após instalação a emissão e a aceitação ficam bloqueadas.
- Encerrar votação para revelar resultado e votos nominais. O placar permanece oculto antes disso.
- Finalizar assembleia e baixar a minuta estruturada de teste.
- A matéria especial permanece bloqueada, sem regra estatutária cadastrada.

Para vários participantes simultâneos, usar perfis de navegador isolados. Múltiplas abas do mesmo perfil compartilham identidade e contam como uma pessoa.

## Implementado

Persistência e migrations; snapshot fictício; autenticação por sessão com CSRF; validação de domínio; preparação do login OIDC institucional com vínculo issuer/sub e ACR MFA; presença expressa de simulação, leases de 60 segundos e intervalos consolidados; primeira/segunda convocação; procuração com token aleatório, HMAC, entrega cifrada em caixa local só ao outorgante, limite de duas, controle de escopo e revogação; prevalência do titular presente; voto próprio ou representado por pauta; cédula única, recibo, retry idempotente e resultado SIM > NÃO; fila normal e questão de ordem; minuta determinística; encadeamento de auditoria e triggers contra alteração de votos/eventos.

Confirmações de presença/outorga no simulado são **DEMO_CONFIRMATION**, não WebAuthn nem assinatura avançada. Recibos têm hash interno, ainda sem assinatura institucional. Minuta JSON não é documento registral. Caixa local não envia e-mail real. Nenhuma assembleia oficial pode usar essas substituições: comandos oficiais são bloqueados incondicionalmente.

## Validação

`python backend/manage.py test governance --verbosity 2` executa testes de autorização, quórum, presença, procuração, voto, prazo, idempotência, integridade, privacidade do placar e bloqueio de uso oficial. `pnpm build` verifica TypeScript e empacotamento React.

O banco local SQLite serve apenas para desenvolvimento e testes sequenciais. Locks e desempenho para votação concorrente precisam ser homologados com PostgreSQL. Este incremento usa lock exclusivo por assembleia para correção inicial; não foi homologado para 8.000 usuários. A evolução para barreiras compartilhadas, outbox, gateway WebSocket e jobs está no backlog.

## La Suite

Fonte oficial do Meet em `upstream/meet`, sem modificações, com commit registrado em `upstream.lock.json`. A cópia não é incluída no repositório principal; preservar licenças ao distribuir alterações. Meet 1.33.0 exige Python >=3.13 e possui seu próprio ambiente/runtime. Não instalar suas dependências no ambiente Python do módulo de governança.

O primeiro incremento ainda não executa Meet, LiveKit ou Docs e não emite tokens de mídia. A próxima etapa é criar adaptadores autenticados com o IdP compartilhado, concessão de palco e documento privado; nunca usar URL de sala pública como prova de presença.

## Bloqueios antes de uso oficial

Conectar e testar IdP e cadastro reais; WebAuthn e cerimônia de outorga; snapshot aprovado e regras normativas; aprovação dupla da mesa e comandos; motor de matérias especiais; assinatura ICP-Brasil e PDF/A; TSA/WORM e verificador independente; homologação RCPJ; entrega real de e-mail; proteção contra falha sistêmica de presença; pausa/prorrogação/anulação; observabilidade, Kubernetes/DR e CI/CD; testes PostgreSQL de concorrência, acessibilidade, segurança e carga de 8.000.

Não desabilitar o bloqueio de assembleia oficial sem concluir e revisar esses itens. `DEBUG=false` não habilita produção automaticamente: exige segredos, PostgreSQL e desliga login de simulação.
