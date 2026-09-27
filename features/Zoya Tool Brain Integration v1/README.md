# Zoya Tool Brain Integration v1

This feature connects the existing semantic Brain to the already-verified Tool Execution Layer.

Flow:

User -> ZoyaChatService -> ZoyaBrain -> ToolExecutionPolicy/ToolExecutor -> ToolRegistry -> tool

Scope:
- Adds structured tool decision fields to BrainDecision.
- Gives Brain the registered tool manifest catalog.
- Lets Brain return a tool name + arguments without executing anything itself.
- Routes tool decisions through ToolExecutor.
- Preserves confirmation handling through the execution layer.
- Keeps non-tool chat, research, memory, provider and streaming paths intact.
- Tool responses are surfaced as direct chat/stream responses; no extra model call is used after a successful tool action.
