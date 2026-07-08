# Simple Web Stack

Painel administrativo multipáginas construído com **Flask** (backend) e **Vue 3 + Tailwind CSS via CDN** (frontend) — sem Node.js, sem bundler, sem build step. Cada página é renderizada pelo Jinja2 e ganha vida com uma instância isolada do Vue.

Além do dashboard "utilitário" original (Pokedex, clima, Spotify), o projeto acumulou algumas vitrines de front-end mais lúdicas: física 2D em canvas, um mini-mundo 3D dirigível e uma simulação de fluidos rodando via shader na GPU — tudo isso ainda dentro da mesma regra de "zero build step".

## Arquitetura

- **Roteamento**: 100% do lado do Flask (MPA clássica). Não há `vue-router` nem SPA.
- **Sem build step**: Vue 3 e Tailwind são injetados via `<script>`/`<link>` direto nos templates, carregados de CDN.
- **Delimitadores do Vue**: como o Jinja2 já usa `{{ }}`, toda instância Vue troca seus delimitadores para `[[ ]]` (`compilerOptions: { delimiters: ['[[', ']]'] }`), evitando conflito de sintaxe.
- **Isolamento por página**: cada template cria seu próprio `createApp(...).mount(...)` — não há estado compartilhado entre páginas.

## Páginas

| Rota | Descrição |
|---|---|
| `/` | **Pokedex 3D** — busca na PokeAPI, visual retrô-futurista com inclinação isométrica (CSS 3D transforms), cores por tipo de Pokémon, barras de status, som do Pokémon (cries) e efeito de scanline na tela. |
| `/weather` | **Weather Monitor** — geolocalização do navegador + proxy Flask para a Open-Meteo API. Mostra temperatura, sensação térmica, vento, pressão, UV, nascer/pôr do sol e nome do local (via geocodificação reversa). |
| `/spotify` | **Spotify Analyzer & Lyrics** — OAuth2 com o Spotify, mostra a faixa atual, artistas, álbum, popularidade, dispositivo/contexto de reprodução, BPM e tonalidade (via ReccoBeats, já que o endpoint oficial `/audio-features` do Spotify foi descontinuado para apps novos), letra embutida via widget oficial do Genius, e fundo dinâmico que extrai a cor dominante da capa do álbum em tempo real. |
| `/player` | **Player Web** — player Spotify completo rodando no navegador via **Web Playback SDK** (exige conta Premium). Visual retrô estilo aparelho de som vintage: visor LCD verde, capa giratória, controles físicos (play/pause, shuffle, repeat), visualizador de EQ decorativo e barra de volume em LEDs. |
| `/liquido` | **Simulação de Líquido (Three.js)** — simulação real de propagação de ondas 2D (equação de onda) rodando em shader GLSL na GPU via ping-pong render targets. Reage ao mouse (ondas ao mover, respingo ao clicar) e gera ondulações automáticas quando ocioso. |
| `/deserto` | **Buggy no Deserto (Three.js)** — veículo controlável (WASD/setas) sobre um terreno procedural com dunas e lombadas periódicas. A física de suspensão (pitch/roll) é calculada a partir da mesma função de altura que gera a malha do terreno, e a câmera segue o carro em terceira pessoa. |
| `/chuva-letras` | **Chuva de Letras** — cada tecla digitada vira uma letra caindo com gravidade real; desenhe barreiras com o mouse/touch e veja as letras colidirem e se acumularem nelas (colisão círculo-vs-segmento com reflexão e atrito). |

## Rodando localmente

### Com Docker (recomendado)

```bash
cp .env.example .env   # preencha as variáveis (veja abaixo)
docker compose up -d --build
```

A aplicação sobe em `http://127.0.0.1:5050` (a porta 5000 padrão do Flask costuma colidir com o AirPlay Receiver do macOS, por isso o mapeamento para 5050 no `docker-compose.yml`).

O `docker-compose.yml` monta `./templates` e `./app.py` como volumes, então alterações nesses arquivos recarregam sozinhas (Flask roda em modo debug com reloader).

### Sem Docker (venv)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

## Variáveis de ambiente

| Variável | Obrigatória para | Onde conseguir |
|---|---|---|
| `FLASK_SECRET_KEY` | Sempre (assina o cookie de sessão) | Qualquer string aleatória — gere com `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | `/spotify` e `/player` | [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) — crie um app |
| `SPOTIFY_REDIRECT_URI` | `/spotify` e `/player` | Precisa bater exatamente com o cadastrado no dashboard do Spotify. Localmente, use um endereço de loopback literal — `http://127.0.0.1:5050/callback` (o Spotify não aceita mais o alias `localhost`) |
| `GENIUS_ACCESS_TOKEN` | Letras em `/spotify` e `/player` | [genius.com/api-clients](https://genius.com/api-clients) — use o **Client Access Token**, não o Client ID/Secret |

Sem as credenciais do Spotify/Genius, o app funciona normalmente — só as páginas que dependem delas ficam limitadas (ex: `/spotify` mostra apenas o botão de conectar).

### Sobre o Spotify

- `/player` exige **conta Premium** — o Web Playback SDK simplesmente não inicializa em conta free.
- Os escopos OAuth incluem `streaming`, `user-modify-playback-state`, `user-read-email` e `user-read-private` além dos de leitura — se você atualizar `SPOTIFY_SCOPES` no `app.py`, será necessário fazer login de novo (`/logout` → `/login`) para que a sessão tenha o novo escopo.
- BPM e tonalidade vêm da [ReccoBeats](https://reccobeats.com) (serviço comunitário, não oficial da Spotify) — o endpoint oficial `/v1/audio-features` do Spotify foi restringido para apps novos desde nov/2024.
- A letra é exibida via **embed oficial do Genius** (`genius.com/songs/{id}/embed.js`) carregado dentro de um iframe isolado — não fazemos scraping da página de letras (o Genius bloqueia isso via proteção anti-bot para requisições vindas de servidores/datacenters).

## Estrutura do projeto

```
simple_web_stack/
├── app.py                  # Rotas Flask + integrações (Spotify, Genius, ReccoBeats, Open-Meteo)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── templates/
    ├── base.html            # Layout global, menu lateral, CDNs
    ├── pokedex.html          # /
    ├── weather.html          # /weather
    ├── spotify.html          # /spotify
    ├── player.html           # /player
    ├── liquido.html          # /liquido
    ├── deserto.html          # /deserto
    └── chuva_letras.html     # /chuva-letras
```

## APIs externas usadas

- [PokeAPI](https://pokeapi.co/) — dados de Pokémon (sem chave)
- [Open-Meteo](https://open-meteo.com/) — previsão do tempo (sem chave)
- [BigDataCloud](https://www.bigdatacloud.com/) — geocodificação reversa (sem chave)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api) + [Web Playback SDK](https://developer.spotify.com/documentation/web-playback-sdk)
- [Genius API](https://docs.genius.com/) — busca de letras + widget de embed
- [ReccoBeats](https://reccobeats.com/) — BPM/tonalidade (substituto comunitário do endpoint descontinuado do Spotify)
- [Three.js](https://threejs.org/) (via CDN) — renderização 3D em `/liquido` e `/deserto`
