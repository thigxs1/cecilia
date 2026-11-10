# Implementação Multi-Node WebSocket Hub (Etapa 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o Hub WebSocket e o Cliente de Rede Multi-Nós da Cecília para comunicação segura e remota via internet pública, integrando múltiplos computadores ao bot do Telegram.

**Architecture:** Servidor Hub WebSocket assíncrono (FastAPI/WebSockets) com autenticação por token pré-compartilhado; módulo Cliente Node com reconexão automática e despacho de comandos locais; e integração com o Telegram Bridge para comando remoto direcionado por nó.

**Tech Stack:** Python 3.12+, FastAPI, Uvicorn, WebSockets, Pytest, Python-Telegram-Bot.

**Spec:** [docs/design/01_multi_node_hub.md](file:///c:/00_Thigago/00_projetos/03_assistente/assistente_desktop/docs/design/01_multi_node_hub.md)

## Global Constraints
- Comunicação segura com cabeçalho de autenticação por token compartilhado (`CECILIA_HUB_SECRET`).
- Protocolo de mensagens serializado em JSON com validação e `request_id` para correlação assíncrona.
- Reconexão resiliente com backoff exponencial no cliente de nó.
- Não quebrar o funcionamento standalone local existente quando nenhum Hub estiver configurado.

## Review Focus
1. Falha de autenticação do handshake WebSocket (token ausente ou inválido deve fechar a conexão com código de erro 4001 / 4003).
2. Queda de conexão de rede durante execução de comando (o cliente deve reconectar automaticamente e o Hub deve marcar o nó como offline).
3. Tentativa de envio de comando para nó inexistente ou desconectado (deve retornar erro claro no Telegram/Hub).
4. Timeout de execução de comando local (não travar o loop de eventos).
5. Sanitização de payloads maliciosos ou comandos inválidos vindos da rede pública.

---

### Task 1: Protocolo de Mensagens e Validação (`assistente.network.protocol`)

**Files:**
- Create: `src/assistente/network/__init__.py`
- Create: `src/assistente/network/protocol.py`
- Test: `tests/test_protocol.py`

- [ ] **Step 1:** Escrever teste de serialização e desserialização das mensagens (`NodeRegister`, `Heartbeat`, `CommandDispatch`, `CommandResult`).
- [ ] **Step 2:** Executar `pytest tests/test_protocol.py` e verificar falha.
- [ ] **Step 3:** Implementar `protocol.py` com tipos Pydantic / Dataclasses e validação de schema.
- [ ] **Step 4:** Executar `pytest tests/test_protocol.py` e garantir 100% de sucesso.

---

### Task 2: Servidor Hub WebSocket (`assistente.network.server`)

**Files:**
- Create: `src/assistente/network/server.py`
- Modify: `src/assistente/config.py` (adicionar configurações de Hub: porta, host, secret)
- Test: `tests/test_hub_server.py`

- [ ] **Step 1:** Escrever testes de integração para o Hub: handshake com token válido vs inválido, registro de nós, lista de nós conectados e envio/recebimento de comandos.
- [ ] **Step 2:** Executar `pytest tests/test_hub_server.py` e verificar falha.
- [ ] **Step 3:** Implementar `CeciliaHub` com FastAPI/WebSockets gerenciando conexões ativas (`dict[node_id, WebSocket]`), ping/pong e fila de respostas correlacionadas por `request_id`.
- [ ] **Step 4:** Executar `pytest tests/test_hub_server.py` e validar aprovação de todos os testes.

---

### Task 3: Cliente de Nó Resiliente (`assistente.network.client`)

**Files:**
- Create: `src/assistente/network/client.py`
- Test: `tests/test_node_client.py`

- [ ] **Step 1:** Escrever testes para o cliente de nó: conexão, envio de registro de nó, execução de handlers locais e reconexão em caso de desconexão.
- [ ] **Step 2:** Executar `pytest tests/test_node_client.py` e verificar falha.
- [ ] **Step 3:** Implementar `CeciliaNodeClient` com loop assíncrono em thread separada (ou integrado ao asyncio), com heartbeat e execução de comandos locais via callbacks.
- [ ] **Step 4:** Executar `pytest tests/test_node_client.py` e validar sucesso.

---

### Task 4: Integração com Cérebro, Telegram e Inicialização Multi-Modo

**Files:**
- Modify: `src/assistente/telegram/bot.py` (suporte a comando `/nodes`, roteamento de comando com sintaxe `@node_name comando` e consulta via Hub)
- Modify: `src/assistente/ai/brain.py` (suporte a execução remota de ferramentas)
- Modify: `src/assistente/main.py` (argumentos CLI `--mode hub|node|standalone` e `--node-id`)
- Modify: `.env.example` e `README.md`
- Test: `tests/test_integration_multi_node.py`

- [ ] **Step 1:** Escrever testes de integração simulando um nó conectado, recebendo mensagem do bot do Telegram e executando no nó remoto.
- [ ] **Step 2:** Atualizar `bot.py` para listar nós conectados e rotear chamadas.
- [ ] **Step 3:** Atualizar `main.py` para permitir inicialização flexível de cada computador.
- [ ] **Step 4:** Executar bateria completa de testes: `pytest tests/` e verificar conformidade.

