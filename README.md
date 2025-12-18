# Beddel Alpha Example

Aplicação Next.js que demonstra o uso do pacote `beddel` publicado no npm (`beddel@0.1.0`), com páginas de showcase (`/`, `/beddel-alpha`), Storybook e APIs de exemplo.

## Repositórios
- Pacote core: https://github.com/botanarede/beddel-alpha
- App de exemplo: https://github.com/botanarede/beddel-alpha-example

## Pré-requisitos
- Node.js 18+
- Credenciais Upstash KV (`KV_REST_API_URL`, `KV_REST_API_TOKEN`) se for usar as rotas de API/GraphQL.
- API key Gemini em `.env` se quiser exercitar o agente Joker na rota `/beddel-alpha`.

## Setup rápido
1) Instalar dependências
```bash
pnpm install
```

2) Criar `.env` na raiz (exemplo mínimo):
```
KV_REST_API_URL="YOUR_KV_REST_API_URL"
KV_REST_API_TOKEN="YOUR_KV_REST_API_TOKEN"
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
```

3) Rodar em desenvolvimento
```bash
pnpm dev
```
Acesse http://localhost:3000 e a demo em http://localhost:3000/beddel-alpha.

4) Storybook (opcional)
```bash
pnpm storybook
```

## Notas
- Por padrão o app usa o `beddel` publicado no npm. Para usar o código local em `packages/beddel` defina `BEDDEL_LOCAL=1` (ex.: `pnpm dev:local` ou `pnpm build:local`). A pasta `packages/` está no `.gitignore`.
- `pnpm test` ainda não está configurado aqui (scripts são placeholders). Use os testes end-to-end/manual via UI ou adapte conforme suas ferramentas.
