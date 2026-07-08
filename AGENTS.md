# Diretrizes do Projeto Template: Flask + Vue.js CDN + Tailwind

Este documento serve como especificação técnica e guia de desenvolvimento para agentes de IA e desenvolvedores. O objetivo é construir um painel administrativo/dashboard multipáginas utilizando **Flask** no backend e uma abordagem leve de **Vue.js 3 e Tailwind CSS via CDN** no frontend.

---

## General Approach

Prefer the simplest working approach and confirm scope before scaffolding large amounts of code.

---

## 1. Princípios Arquiteturais

* **Roteamento:** O controle de rotas de páginas e arquivos físicos HTML é de responsabilidade exclusiva do **Flask** (Multi-Page Application - MPA). Não utilizar `vue-router`.
* **Ausência de Build Step:** O frontend não deve utilizar Node.js, npm, Webpack, Vite ou qualquer processo de compilação. Todas as dependências de interface são injetadas via tags `<script>` e `<link>` diretamente nos templates do Jinja2.
* **Evitar Conflito de Sintaxe (Crucial):** Como o Jinja2 e o Vue.js utilizam as mesmas chaves duplas `{{ }}` para renderização, **todas** as instâncias do Vue devem ser configuradas obrigatoriamente para alterar seus delimitadores para `[[ ]]`:
    ```javascript
    compilerOptions: { delimiters: ['[[', ']]'] }
    ```
* **Isolamento de Estado:** Cada página HTML possui sua própria instância isolada do Vue (`createApp`), montada em um ID de container específico.

---

## 2. Estrutura de Diretórios Alvo

```text
projeto-template/
├── app.py                  # Servidor Flask e rotas (Backend)
├── Dockerfile              # Empacotamento do ambiente Python 3.11-slim
├── docker-compose.yml      # Orquestração local com espelhamento de volumes
├── requirements.txt        # Dependências Python (Flask, requests, etc.)
└── templates/              # Camada de Visão (Jinja2)
    ├── base.html           # Layout global, Menu Lateral e injeção de CDNs
    ├── pokedex.html        # Página Base (Rota: /) - Pokedex 3D
    ├── weather.html        # Rota: /weather - Clima via Geolocalização
    └── spotify.html        # Rota: /spotify - Integração e Player Metrics
```

---

## 3. Especificação das Páginas

### 3.1. Layout Base (`templates/base.html`)

**Responsabilidade:** Renderizar a casca global da aplicação.

**UI/UX:** Um menu lateral fixo (`<aside>`) contendo a navegação do sistema usando links nativos do Flask (`href="{{ url_for('rota') }}"`).

**CDNs Obrigatórias no `<head>`:**

* Tailwind CSS (`https://cdn.tailwindcss.com`)
* Vue 3 (`https://unpkg.com/vue@3/dist/vue.global.js`)

### 3.2. Página Base: Scanner Pokémon (`templates/pokedex.html`)

**Rota Flask:** `/`

**Objetivo:** Consumir a PokeAPI pública (`https://pokeapi.co/api/v2/pokemon/{id_ou_nome}`).

**UI/UX (Pokedex 3D):** Estilização retrô-futurista de anime usando Tailwind. A tela deve simular profundidade (usando sombras densas `shadow-[Xpx_Xpx_0px_0px_rgba(0,0,0,n)]`, gradientes e bordas grossas estilo skeuomórfico/físico).

**Lógica Vue:** Gerenciar estados de `loading`, `erro` e `pokemon` utilizando a API nativa do `fetch` do navegador no submit do formulário.

### 3.3. Página 1: Weather Monitor (`templates/weather.html`)

**Rota Flask:** `/weather`

**Objetivo:** Mostrar o clima atual baseado na localização em tempo real do usuário.

**Fluxo Técnico:**

1. O Vue.js deve disparar a API de Geolocalização nativa do navegador (`navigator.geolocation.getCurrentPosition`) logo ao carregar a página para obter latitude e longitude.
2. O Vue envia as coordenadas via `fetch` para uma rota interna do Flask (ex: `/api/clima?lat=X&lon=Y`).
3. O Flask atua como um proxy seguro, faz a chamada para uma API pública (sugestão: Open-Meteo API ou OpenWeatherMap) usando sua chave de API protegida no backend e devolve o JSON mastigado para o Vue.

**UI/UX:** Cards minimalistas mostrando temperatura, umidade e condições gerais.

### 3.4. Página 2: Spotify Analyzer & Lyrics (`templates/spotify.html`)

**Rota Flask:** `/spotify`

**Objetivo:** Autenticar o usuário via OAuth2 do Spotify, identificar a música tocando no momento (Now Playing) e enriquecer a tela com métricas avançadas (BPM, Tonalidade) e a Letra.

**Fluxo Técnico:**

* **OAuth2:** O Flask gerencia o fluxo de login com o Spotify (`/login`, `/callback`) e armazena de forma segura o `access_token` na sessão do usuário.
* **Música Atual:** O Flask disponibiliza um endpoint interno `/api/spotify/now-playing` que consome as rotas do Spotify:
  * `GET /v1/me/player/currently-playing` (Dados da faixa atual).
  * `GET /v1/audio-features/{id_da_musica}` (Para extrair o BPM (`tempo`) e Key (tonalidade)).
* **Letras (Lyrics):** Como o Spotify não fornece letras abertamente em sua API oficial, o Flask deve usar uma biblioteca Python auxiliar (ex: `lyricsgenius` consumindo a API gratuita do Genius) para buscar a letra baseada no nome da música e do artista encontrados no passo anterior.
* **Vue.js:** Faz um polling (ex: requisição a cada 5 segundos) para o endpoint do Flask para atualizar o player e as métricas reativamente na tela caso a música mude.

---

## 4. Diretrizes para o Agente de Implementação

Ao codificar o backend (`app.py`), certifique-se de configurar as variáveis de ambiente necessárias para o Spotify (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`) e Genius. No ambiente Docker, mapeie sempre a pasta `./templates` como um volume de desenvolvimento para permitir o hot-reload dos arquivos HTML e códigos Vue sem necessidade de reinicialização do container.

---

### Dica de ouro: Tonalidade do Spotify

Como o Spotify trabalha com IDs matemáticos para a tonalidade (ex: `0 = C`, `1 = C♯/D♭`, `2 = D`), vale a pena deixar um dicionário/mapa no código para traduzir o número da API para texto legível antes de mandar o JSON para o Vue.

---

## Development & Testing

This project uses Docker for running and testing. Always verify changes by running services via `docker compose up` rather than running Flask/Vue directly on the host.

---

## Debugging

Before diagnosing container or build issues, first read the README and check the current Docker state (`docker ps`, `docker compose config`).
