# Cecília - Assistente Desktop Inteligente (Screen Pet & Jarvis Local)

Assistente pessoal de desktop com física Shimeji, controle multimídia, automação de T.I. e integração remota via Telegram (mobile).

## 🚀 Funcionalidades

- **Pet Flutuante (UI Shimeji):** Janela sem bordas e transparente, física de gravidade e inércia, drag & drop com arremesso, máquina de estados autônoma (idle/andando/piscando) e colisão com suporte a múltiplos monitores.
- **Dock de Controle Multimídia:** Clique duplo ou botão direito no pet para abrir a mini-barra flutuante com botões visuais (`⏮`, `⏯`, `⏭`) e controle de volume do Windows via `pycaw`.
- **Balão de Notificação Visual:** O pet se comunica na tela através de um balão de fala dinâmico (`SpeechBubble`) para alertas do sistema e confirmação de comandos.
- **Cérebro IA (Gemini):** Suporte técnico de T.I., respostas rápidas e execução de ações locais via Function Calling.
- **Controle Remoto via Telegram Bot:** Envie comandos pelo celular para pausar músicas, verificar CPU/RAM, agendar alarmes ou travar a máquina.
- **Servidores MCP Locais:** Exposição de ferramentas do sistema (`assistente-os`) e IA (`assistente-ai`) via protocolo FastMCP.

## 🛠️ Instalação e Execução

1. **Clonar o repositório:**
   ```bash
   git clone https://github.com/thigxs1/cecilia.git
   cd cecilia
   ```

2. **Criar e ativar o ambiente virtual:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configurar variáveis de ambiente:**
   Copie `.env.example` para `.env` e preencha conforme necessário:
   ```env
   GEMINI_API_KEY=sua_chave_gemini_opcional
   TELEGRAM_BOT_TOKEN=token_do_seu_bot_opcional
   TELEGRAM_ALLOWED_CHAT_ID=seu_chat_id
   ```

4. **Executar:**
   ```powershell
   $env:PYTHONPATH="src"
   python -m assistente
   ```
