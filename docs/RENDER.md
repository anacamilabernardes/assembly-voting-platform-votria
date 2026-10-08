# Publicar o simulado no Render

Esta configuração publica somente a demonstração com sete pessoas fictícias, sem validade registral. Meet, Docs e login institucional real ainda não estão integrados. O ambiente não foi homologado para 8.000 participantes.

## 1. Enviar as alterações ao GitHub

No GitHub Desktop, registre as alterações com o resumo `Preparar simulado online no Render` e clique em **Push origin**. Se o repositório ainda não foi publicado, use **Publish repository**.

Na página do repositório, confirme que `render.yaml`, `Dockerfile` e `deploy/start.sh` estão na raiz. A raiz esperada é a pasta mensa-assembleia, com backend e frontend logo abaixo, não a pasta inteira do projeto Visao.

## 2. Criar pelo Blueprint

1. Entre em https://dashboard.render.com/ usando sua conta GitHub.
2. Escolha **New → Blueprint**.
3. Conecte o repositório mensa-assembleia. Se ele for privado, permita acesso a esse repositório na integração GitHub do Render.
4. Escolha a branch **main** e mantenha `render.yaml` como Blueprint Path.
5. Dê um nome ao Blueprint, por exemplo `mensa-simulado`.
6. Em `MENSA_DEMO_ACCESS_PASSWORD`, informe uma senha exclusiva de pelo menos 16 caracteres; prefira uma frase longa ou uma senha gerada por gerenciador. Não coloque essa senha no GitHub. Ela será compartilhada somente com o grupo de teste.
7. Confira os recursos e os preços mostrados: um Web Service e um banco PostgreSQL, ambos com plano **Free** no arquivo fornecido.
8. Confirme em **Deploy Blueprint / Apply**, conforme o botão apresentado pelo Render.

A implantação cria uma chave interna aleatória, conecta o banco pela rede interna, compila a interface e aplica as migrations. Na inicialização, carrega os dados fictícios apenas se ainda não existirem. Não há comandos para copiar manualmente nem configuração de um site separado.

Não use uma opção de plano pago sem conferir o valor exibido. Os nomes e a disponibilidade dos planos podem mudar: se Free não estiver disponível, revise a escolha antes de confirmar.

## 3. Abrir e testar

Abra o serviço **mensa-assembleia-demo**. Aguarde o estado **Live** e abra a URL HTTPS indicada pelo Render, normalmente terminada em `.onrender.com`.

Na página, informe a senha do simulado e selecione uma pessoa fictícia. Cada participante deve usar um perfil diferente: escolha nomes distintos para representar participantes distintos. A troca de pessoa encerra a presença anterior; várias abas no mesmo perfil compartilham a identidade.

Roteiro para um grupo pequeno:

1. Cada pessoa escolhe uma identidade fictícia diferente e confirma presença.
2. Antes de instalar, Carla cria uma procuração para Diego. Carla consulta sua própria caixa de teste e transmite o código a Diego; Diego aceita o código.
3. Ana Presidente confirma presença e instala em segunda convocação, ou em primeira se houver cinco presenças próprias.
4. Ana abre uma pauta ordinária. Os participantes votam e testam o pedido de palavra.
5. Ana encerra a votação. Confiram votos nominais, SIM > NÃO, abstenções e resultado.
6. Ana finaliza a assembleia e baixa a minuta JSON. O resultado é somente de demonstração.

O ensaio usa uma assembleia compartilhada. Votos e histórico não são apagados ao reiniciar ou publicar uma atualização. Após finalizar, Ana Presidente pode clicar em **Iniciar novo simulado**. O histórico permanece na assembleia anterior. Participantes já conectados são encaminhados ao novo teste pela atualização periódica da tela; se necessário, recarreguem a página. Todos precisam confirmar presença e criar procurações novamente. A senha de acesso permanece a mesma.

## 4. Compartilhar

Envie ao grupo a URL HTTPS e a senha por um canal privado escolhido por você. A senha dá acesso a todos os perfis fictícios, inclusive à presidência; não é autenticação de associados reais. Não use cadastro, documentos ou dados reais neste ambiente.

## Atualizações, limites e diagnóstico

Para atualizar o código, faça Commit e Push origin. Verifique o novo deploy no Render. Preserve DJANGO_SECRET_KEY: ela também protege os códigos da caixa de teste; trocá-la invalida sessões e a leitura dos códigos existentes.

O serviço Free pausa após 15 minutos sem tráfego e pode levar cerca de um minuto para abrir novamente. O PostgreSQL Free expira após 30 dias e não oferece backups. Para manter histórico por mais tempo, escolha um banco pago antes da expiração e estabeleça backups. O preço final é o exibido pelo Render.

Se houver erro, abra **Logs** no serviço. “Senha de acesso” exige valor com pelo menos 16 caracteres; falha de conexão exige verificar o banco; erro de build deve ser corrigido antes de compartilhar o link. Não habilite DEBUG para contornar erros. Depois de trocar a senha, reinicie o serviço e invalide sessões existentes por procedimento administrativo se precisar remover acessos já autenticados: a troca sozinha não encerra sessões.

A publicação real, a compilação Docker/Linux e a concorrência PostgreSQL precisam ser verificadas no primeiro deploy. Nenhum endereço público é criado pelo preparo local dos arquivos.

Referências oficiais:
- https://render.com/docs/infrastructure-as-code
- https://render.com/docs/blueprint-spec
- https://render.com/docs/free
