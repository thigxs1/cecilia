# Design Doc: Cecília Mesh Hub & Multi-Node Architecture (Etapa 1)

**Autor:** Assistente (Cecília AI / Antigravity)  
**Data:** 10/11/2026  
**Status:** Proposto  

---

## 1. Visão Geral e Objetivo
Permitir que a **Cecília** opere como um assistente distribuído estilo J.A.R.V.I.S., coordenando múltiplos dispositivos (Desktop, Notebook, Servidores) e canais mobile (Telegram Bot) através da internet pública, utilizando um **Hub WebSocket Seguro em Python**.

---

## 2. Requisitos Arquiteturais

1. **Hub Central (Servidor):**
   - Servidor FastAPI / WebSockets assíncrono.
   - Autenticação obrigatória por token pré-compartilhado (`CECILIA_HUB_SECRET`) em cabeçalhos/handshake.
   - Registro de nós ativos com metadados (nome da máquina, OS, IP público/privado, status, capabilities/ferramentas disponíveis).
   - Gerenciamento de heartbeat (ping/pong) para detecção de nós offline.
   - Exposição para a internet pública (suporte nativo para rodar em VPS com SSL/TLS ou túnel Cloudflare/Ngrok/Localtunnel).

2. **Nó Local (Node Client):**
   - Roda em cada máquina onde a Cecília estiver instalada.
   - Reconexão automática com backoff exponencial se a conexão com o Hub cair.
   - Executa comandos locais enviados pelo Hub (`control_media`, `get_system_metrics`, `open_app`, `lock_pc`, etc.) e devolve o resultado assíncrono.
   - Notifica a interface do Pet local (`pet.say(...)`) caso a ação afete a máquina.

3. **Ponte Telegram Inteligente:**
   - O Telegram Bot se comunica diretamente com o Hub ou opera acoplado ao Hub central.
   - Suporte a roteamento por alvo:
     - `/nodes` ou "quais máquinas estão online?": lista os nós conectados.
     - "Bloquear notebook": direciona a ação para o nó `notebook`.
     - "Pause a música": direciona para o nó padrão ou para o nó onde houver reprodução ativa.

4. **Protocolo de Mensagens (JSON padronizado):**
   - `NODE_REGISTER`: Nó se apresenta ao Hub (`node_id`, `hostname`, `capabilities`).
   - `HEARTBEAT`: Pulso periódico a cada 15s.
   - `DISPATCH_COMMAND`: Hub envia comando para um nó específico.
   - `COMMAND_RESULT`: Nó devolve resultado com `request_id`, status e payload.
   - `BROADCAST_ALERT`: Notificação para todos os nós (ex: alarme/lembrete global).

---

## 3. Estrutura de Arquivos Proposta

```
src/
├── assistente/
│   ├── network/
│   │   ├── __init__.py
│   │   ├── protocol.py       # Dataclasses e schemas das mensagens do protocolo
│   │   ├── client.py         # Cliente WebSocket do Nó (com reconexão resiliente)
│   │   └── server.py         # Servidor Hub WebSocket (FastAPI + WebSockets)
│   ├── ai/
│   │   └── brain.py          # Atualizado com roteamento de nós
│   ├── telegram/
│   │   └── bot.py            # Atualizado para interagir com o Hub/Nós
│   └── main.py               # Flags CLI para iniciar em modo 'hub', 'node' ou 'standalone'
tests/
└── test_network.py           # Testes unitários do handshake, protocolo e despacho
```

---

## 4. Segurança na Internet Pública
- **WSS (WebSocket Seguro com TLS):** Encriptação ponta a ponta.
- **Token Secret Bearer:** Handshake recusado imediatamente sem token válido.
- **Rate Limiting & Proteção contra conexões não autorizadas.**

