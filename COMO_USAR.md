# Como colocar isso no seu perfil

O resultado é aquele card estilo terminal que aparece no topo do seu perfil do
GitHub, com os números (repos, stars, commits, seguidores, linhas de código)
**atualizando sozinhos** todo dia.

## 1. Crie o repositório especial
Crie um repositório **público** com o nome **exatamente igual ao seu usuário**:

> `brunohcorreia/brunohcorreia`

Pode marcar "Add a README file" na criação (a gente substitui depois).

## 2. Suba estes arquivos pro repositório
Mantendo a mesma estrutura de pastas:

```
brunohcorreia/
├─ today.py
├─ README.md
├─ requirements.txt
├─ dark_mode.svg
├─ light_mode.svg
├─ cache/              (pasta vazia, com o .gitkeep)
└─ .github/
   └─ workflows/
      └─ profile.yml
```

## 3. Crie um token de acesso (PAT)
O robô precisa de um token pra ler suas estatísticas.

1. GitHub → **Settings** (do seu perfil) → **Developer settings**
2. **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
3. Dê um nome (ex.: `profile-fetch`), validade longa.
4. Marque os escopos: **`repo`** e **`read:user`**
5. Gere e **copie o token** (só aparece uma vez).

## 4. Guarde o token como secret no repositório
No repositório `brunohcorreia`:

1. **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**
3. Nome: **`ACCESS_TOKEN`**  (tem que ser esse nome exato)
4. Cole o token no valor e salve.

## 5. Rode a primeira vez
1. Vá na aba **Actions** do repositório.
2. Abra o workflow **"Update profile fetch"**.
3. Clique em **Run workflow**.

A primeira execução é a mais lenta (ele conta linha por linha de cada repo e
guarda em `cache/` pra ficar rápido nas próximas). Quando terminar, ele já faz
commit dos SVGs com os números reais, e o card aparece no seu perfil. 🎉

Depois disso ele roda sozinho todo dia às 3h (UTC).

---

## Testar o visual no seu PC (opcional)
Não precisa de token só pra ver o layout (os números vêm como 0):

```bash
pip install requests
python today.py
```

Com token, pra ver os números reais localmente:

```bash
# Linux / macOS
export ACCESS_TOKEN=ghp_seutoken
export USER_NAME=brunohcorreia
python today.py
```

## Mudar seus dados
Tudo que é texto fixo (OS, linguagens, hobbies, contato, cores...) está no topo
do `today.py`, no bloco `CONFIG` e em `THEMES`. Edite, rode de novo e pronto.

A arte da esquerda (hoje é um octocat provisório) vai virar a **sua foto em
ASCII** assim que você mandar a imagem.

---

## Trocar a arte (sua foto em ASCII)
A arte vem de **`ascii_art.txt`** (hoje: a sua, em linha, com a camisa).
Alternativas inclusas, todas sem fundo:

- `ascii_art_L.txt`  -> linha/contorno (gerada aqui)
- `ascii_art_N.txt`  -> sombreado, rosto
- `ascii_art_H.txt`  -> blocos, denso

Pra trocar, copie o conteudo da opcao desejada pra dentro de `ascii_art.txt`.
A fonte e a largura do card se ajustam sozinhas.
