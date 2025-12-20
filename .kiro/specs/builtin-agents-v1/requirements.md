# Requirements Document

## Introduction

Este documento define os requisitos para internalizar os agentes externos (atualmente em `/agents`) como agentes builtin do Beddel, mantendo a funcionalidade de custom actions para agentes externos futuros. A primeira versão foca em uma abordagem simples e incremental, sem grandes mudanças estruturais.

## Glossary

- **Beddel**: Runtime declarativo para agentes YAML com segurança enterprise-grade
- **Agent_Registry**: Serviço singleton que gerencia registro e execução de agentes declarativos
- **Declarative_Interpreter**: Interpretador que executa definições YAML de agentes sem execução dinâmica de código
- **Builtin_Agent**: Agente que vem empacotado com o Beddel e é registrado automaticamente na inicialização
- **Custom_Agent**: Agente definido pelo usuário no diretório `/agents` da aplicação
- **Custom_Action**: Tipo de workflow step que executa código TypeScript externo via função registrada
- **Workflow_Step_Type**: Tipo de ação suportada pelo Declarative_Interpreter (ex: genkit-joke, genkit-translation, custom-action)
- **MCP**: Model Context Protocol - protocolo para comunicação com servidores de contexto
- **ChromaDB**: Banco de dados vetorial para armazenamento e busca de embeddings
- **RAG**: Retrieval-Augmented Generation - técnica que combina busca vetorial com geração de texto
- **Embedding**: Representação vetorial de texto para busca semântica

## Requirements

### Requirement 1: Internalização do MCP Tool Agent

**User Story:** Como desenvolvedor usando Beddel, quero ter acesso nativo a ferramentas MCP, para que eu possa integrar com servidores MCP sem precisar de agentes externos.

#### Acceptance Criteria

1. THE Agent_Registry SHALL register a builtin agent named "mcp-tool" on initialization
2. WHEN the mcp-tool agent is executed, THE Declarative_Interpreter SHALL connect to the specified MCP server via SSE transport
3. WHEN a tool_name is provided, THE mcp-tool agent SHALL invoke the specified tool with the provided arguments
4. WHEN tool_name is "list_tools", THE mcp-tool agent SHALL return the list of available tools from the MCP server
5. IF the MCP connection fails, THEN THE mcp-tool agent SHALL return an error response with the failure message
6. IF the specified tool does not exist, THEN THE mcp-tool agent SHALL return an error listing available tools

### Requirement 2: Internalização do Gemini Vectorize Agent

**User Story:** Como desenvolvedor usando Beddel, quero gerar embeddings de texto nativamente, para que eu possa implementar funcionalidades de busca semântica sem dependências externas.

#### Acceptance Criteria

1. THE Agent_Registry SHALL register a builtin agent named "gemini-vectorize" on initialization
2. WHEN a single text is provided, THE gemini-vectorize agent SHALL generate an embedding vector using Gemini text-embedding-004
3. WHEN multiple texts are provided, THE gemini-vectorize agent SHALL generate embedding vectors em batch
4. THE gemini-vectorize agent SHALL require the prop "gemini_api_key" for authentication
5. IF the embedding generation fails, THEN THE gemini-vectorize agent SHALL return an error response with the failure message

### Requirement 3: Internalização do ChromaDB Agent

**User Story:** Como desenvolvedor usando Beddel, quero armazenar e buscar vetores nativamente, para que eu possa implementar RAG sem configurar agentes externos.

#### Acceptance Criteria

1. THE Agent_Registry SHALL register a builtin agent named "chromadb" on initialization
2. WHEN action "hasData" is requested, THE chromadb agent SHALL check if a collection exists and has sufficient documents
3. WHEN action "store" is requested, THE chromadb agent SHALL store vectors, documents and metadata in the specified collection
4. WHEN action "search" is requested, THE chromadb agent SHALL perform similarity search using the provided query vector
5. THE chromadb agent SHALL support both local ChromaDB and Chroma Cloud via environment variables
6. IF the ChromaDB operation fails, THEN THE chromadb agent SHALL return an error response with the failure message

### Requirement 4: Internalização do GitMCP Agent

**User Story:** Como desenvolvedor usando Beddel, quero buscar documentação de repositórios via GitMCP nativamente, para que eu possa indexar conhecimento de repositórios GitHub.

#### Acceptance Criteria

1. THE Agent_Registry SHALL register a builtin agent named "gitmcp" on initialization
2. WHEN a gitmcp_url is provided, THE gitmcp agent SHALL discover available tools via SSE connection
3. WHEN content is fetched, THE gitmcp agent SHALL split the content into chunks for vectorization
4. THE gitmcp agent SHALL use the mcp-tool builtin agent for MCP communication
5. IF the content fetch fails, THEN THE gitmcp agent SHALL return an error response with the failure message

### Requirement 5: Internalização do RAG Agent

**User Story:** Como desenvolvedor usando Beddel, quero gerar respostas baseadas em contexto nativamente, para que eu possa implementar Q&A sobre documentação.

#### Acceptance Criteria

1. THE Agent_Registry SHALL register a builtin agent named "rag" on initialization
2. WHEN query and documents are provided, THE rag agent SHALL generate an answer using Gemini based on the context
3. WHEN conversation history is provided, THE rag agent SHALL consider previous messages for context continuity
4. THE rag agent SHALL require the prop "gemini_api_key" for authentication
5. IF the answer generation fails, THEN THE rag agent SHALL return an error response with the failure message

### Requirement 6: Internalização do Chat Agent (Orquestrador)

**User Story:** Como desenvolvedor usando Beddel, quero um agente de chat Q&A completo nativamente, para que eu possa implementar assistentes de documentação sem configuração adicional.

#### Acceptance Criteria

1. THE Agent_Registry SHALL register a builtin agent named "chat" on initialization
2. WHEN messages are provided, THE chat agent SHALL orchestrate the flow between vectorize, chromadb, gitmcp and rag agents
3. WHEN knowledge_sources are configured, THE chat agent SHALL fetch and index documentation from those sources
4. THE chat agent SHALL return execution steps detailing each agent action for observability
5. IF no relevant documents are found, THEN THE chat agent SHALL return an appropriate message
6. IF any orchestrated agent fails, THEN THE chat agent SHALL handle the error gracefully and continue or report

### Requirement 7: Novo Workflow Step Type para Agentes Builtin

**User Story:** Como desenvolvedor do Beddel, quero invocar agentes builtin diretamente do workflow YAML, para que agentes possam compor funcionalidades sem código TypeScript.

#### Acceptance Criteria

1. THE Declarative_Interpreter SHALL support a new workflow step type "builtin-agent"
2. WHEN a builtin-agent step is executed, THE Declarative_Interpreter SHALL invoke the specified builtin agent via Agent_Registry
3. THE builtin-agent step SHALL pass input, props and context to the invoked agent
4. THE builtin-agent step SHALL store the result in the specified variable
5. IF the builtin agent is not found, THEN THE Declarative_Interpreter SHALL throw an error with the agent name

### Requirement 8: Manutenção da Compatibilidade com Custom Actions

**User Story:** Como desenvolvedor usando Beddel, quero continuar usando custom actions para meus agentes externos, para que a migração para builtin não quebre funcionalidades existentes.

#### Acceptance Criteria

1. THE Declarative_Interpreter SHALL continue to support the "custom-action" workflow step type
2. WHEN a custom-action references a function, THE Declarative_Interpreter SHALL look up the function in the custom functions registry
3. THE Agent_Registry SHALL continue to load custom agents from the /agents directory
4. THE Agent_Registry SHALL continue to load custom TypeScript functions from the /agents directory
5. WHEN a custom agent has the same route as a builtin, THE custom agent SHALL override the builtin (priority: custom > builtin)
