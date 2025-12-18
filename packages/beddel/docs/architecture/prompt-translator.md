# Prompt: Implementação Beta do Agente Tradutor Beddel

## Objetivo

Implementar uma versão beta simplificada do agente tradutor Beddel com frontend em `/beddel/translator` e backend fallback integrado ao `/api/graphql`.

## Arquitetura Simplificada

Frontend (React) → `/api/graphql` (com parâmetro `translator=fallback`) → Função Traduzir com Fallback → Resposta JSON

## 1. Frontend: Página de Tradução (`/beddel/translator`)

### Arquivo: `app/beddel/translator/page.tsx`

```typescript
"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface TranslationRequest {
  texto: string;
  idioma_origem: string;
  idioma_destino: string;
}

interface TranslationResponse {
  texto_traduzido: string;
  metadados: {
    modelo_utilizado: string;
    tempo_processamento: number;
    confianca: number;
  };
}

export default function TranslatorPage() {
  const [request, setRequest] = useState<TranslationRequest>({
    texto: "",
    idioma_origem: "pt",
    idioma_destino: "en",
  });
  const [response, setResponse] = useState<TranslationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleTraduzir = async () => {
    try {
      setLoading(true);
      setError(null);

      const graphqlQuery = {
        query: `
          query($texto: String!, $idioma_origem: String!, $idioma_destino: String!) {
            translate(texto: $texto, idioma_origem: $idioma_origem, idioma_destino: $idioma_destino) {
              texto_traduzido
              metadados {
                modelo_utilizado
                tempo_processamento
                confianca
              }
            }
          }
        `,
        variables: request,
      };

      const res = await fetch("/api/graphql", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(graphqlQuery),
      });

      const data = await res.json();

      if (data.errors) {
        throw new Error(data.errors[0].message);
      }

      setResponse(data.data.translate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao traduzir");
      setResponse(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto max-w-4xl p-6">
      <Card>
        <CardHeader>
          <CardTitle>Tradutor Beddel - Beta</CardTitle>
          <CardDescription>Tradução com fallback inteligente</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            placeholder="Digite o texto para traduzir..."
            value={request.texto}
            onChange={(e) => setRequest({ ...request, texto: e.target.value })}
            className="min-h-[120px]"
          />

          <div className="flex gap-4">
            <Select
              value={request.idioma_origem}
              onValueChange={(v) =>
                setRequest({ ...request, idioma_origem: v })
              }
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Idioma origem" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pt">Português</SelectItem>
                <SelectItem value="en">Inglês</SelectItem>
                <SelectItem value="es">Espanhol</SelectItem>
                <SelectItem value="fr">Francês</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={request.idioma_destino}
              onValueChange={(v) =>
                setRequest({ ...request, idioma_destino: v })
              }
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Idioma destino" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pt">Português</SelectItem>
                <SelectItem value="en">Inglês</SelectItem>
                <SelectItem value="es">Espanhol</SelectItem>
                <SelectItem value="fr">Francês</SelectItem>
              </SelectContent>
            </Select>

            <Button
              onClick={handleTraduzir}
              disabled={loading || !request.texto}
            >
              {loading ? "Traduzindo..." : "Traduzir"}
            </Button>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {response && (
            <div className="space-y-4">
              <div>
                <h4 className="font-medium mb-2">Tradução:</h4>
                <div className="p-3 bg-muted rounded-md">
                  {response.texto_traduzido}
                </div>
              </div>
              <div className="text-sm text-muted-foreground">
                <p>Modelo: {response.metadados.modelo_utilizado}</p>
                <p>Tempo: {response.metadados.tempo_processamento}ms</p>
                <p>
                  Confiança: {(response.metadados.confianca * 100).toFixed(1)}%
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

## 2. Backend: Integração GraphQL com Fallback

### Arquivo: `app/api/graphql/route.ts` (Adicionar ao existente)

```typescript
// Adicionar typeDefs e resolvers ao esquema GraphQL existente

export const dynamic = 'force-dynamic';

interface TranslationArgs {
  texto: string;
  idioma_origem: string;
  idioma_destino: string;
}

const typeDefs = `
  type Translation {
    texto_traduzido: String!
    metadados: TranslationMetadata!
  }

  type TranslationMetadata {
    modelo_utilizado: String!
    tempo_processamento: Int!
    confianca: Float!
  }

  extend type Query {
    translate(texto: String!, idioma_origem: String!, idioma_destino: String!): Translation!
  }
`;

const resolvers = {
  Query: {
    translate: async (_: any, args: TranslationArgs) => {
      const startTime = Date.now();

      try {
        // Validação
        if (!args.texto || args.texto.length < 1 || args.texto.length > 10000) {
          throw new Error('Texto inválido: deve ter entre 1 e 10000 caracteres');
        }

        if (!/^PT|EN|ES|FR$/i.test(args.idioma_origem)) {
          throw new Error('Idioma de origem inválido');
        }

        if (!/^PT|EN|ES|FR$/i.test(args.idioma_destino)) {
          throw new Error('Idioma de destino inválido');
        }

        // Tradução com Fallback
        const textoTradu = translateWithFallback(
          args.texto,
          args.idioma_origem,
          args.idioma_destino
        );

        const tempoProcessamento = Date.now() - startTime;

        return {
          texto_traduzido: textoTradu,
          metadados: {
            modelo_utilizado: 'beddel-fallback-translator',
            tempo_processamento: tempoProcessamento,
            confianca: 0.8
          }
        };

      } catch (error) {
        throw new Error(`Erro na tradução: ${error instanceof Error ? error.message : 'Erro desconhecido'}`);
      }
    }
  }
};

function translateWithFallback(texto: string, origem: string, destino: string): string {
  // Fallback simples - mantém o texto original com pequenas modificações

  const dicionarioBasico = new Map([
    ['olá', 'hello'], ['Olá', 'Hello'], ['OLÁ', 'HELLO'],
    ['mundo', 'world'], ['Mundo', 'World'], ['MUNDO', 'WORLD'],
    ['bom dia', 'good morning'], ['Bom dia', 'Good morning'],
    ['boa tarde', 'good afternoon'], ['Boa tarde', 'Good afternoon'],
    ['boa noite', 'good evening'], ['Boa noite', 'Good evening'],
    ['como vai', 'how are you'], ['Como vai', 'How are you'],
    ['obrigado', 'thank you'], ['Obrigado', 'Thank you'],
    ['por favor', 'please'], ['Por favor', 'Please'],
    ['desculpe', 'sorry'], ['Desculpe', 'Sorry'],
    ['sim', 'yes'], ['Sim', 'Yes'],
    ['não', 'no'], ['Não', 'No'], ['NÃO', 'NO']
  ]);

  return texto.replace(
    new RegExp(`\\b(${Array.from(dicionarioBasico.keys()).join('|')})\\b`, 'gi'),
    match => dicionarioBasico.get(match) || match
  );
}
`;
```

## 3. Validations e Tipos

### Arquivo: `lib/types.ts` (Adicionar ou criar)

```typescript
export interface TranslationRequest {
  texto: string;
  idioma_origem: string;
  idioma_destino: string;
}

export interface TranslationResult {
  texto_traduzido: string;
  metadados: {
    modelo_utilizado: string;
    tempo_processamento: number;
    confianca: number;
  };
}
```

## 4. Teste de Integração

### Comando para testar:

```bash
curl -X POST http://localhost:3000/api/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { translate(texto: \"Olá mundo\", idioma_origem: \"pt\", idioma_destino: \"en\") { texto_traduzido metadados { modelo_utilizado tempo_processamento confianca } } }"
  }'
```

## Requisitos de Implementação

### 1. Validar entrada:

- Texto entre 1 e 10000 caracteres
- Idiomas suportados: PT, EN, ES, FR
- Parâmetros obrigatórios

### 2. Fallback de Tradução:

- Usar dicionário básico para palavras conhecidas
- Manter estrutura do texto original
- Retornar confiança fixa de 0.8
- Modelo identificado como "beddel-fallback-translator"

### 3. Formatação:

- Tempo de processamento em milissegundos
- Resposta GraphQL padronizada
- Tratamento de erros com mensagens claras

### 4. Interface Responsiva:

- Layout container com max-w-4xl
- Cards com sombra padrão Beddel
- Botões primários azuis
- Estados de loading e erro visuais
- Suporte dark mode via ThemeProvider

### 5. Segurança:

- Rate limiting básico (implementar no GraphQL existente)
- Sanitização de inputs
- Limite de caracteres

### 6. Performance:

- Carregar apenas componentes necessários
- Lazy loading para traduções grandes
- Cache de componentes React

## Testes Recomendados

1. Testar tradução básica PT→EN
2. Testar com idioma inválido
3. Testar texto vazio
4. Testar texto com mais de 10000 caracteres
5. Testar múltiplas traduções em sequência

## Documentação Adicional

Adicionar ao arquivo criado:

- README com instruções de uso
- Exemplos de chamadas curl
- Lista de palavras do dicionário
- Limitações do fallback

## Next Steps

Após implementação bem-sucedida:

1. Adicionar mais palavras ao dicionário
2. Implementar cache Redis
3. Adicionar suporte a mais idiomas
4. Melhorar algoritmo de fallback
5. Preparar integração com Genkit real

## Notas Importantes

⚠️ **Este é um MVP com fallback simples** - não é tradução real
✅ Use como base para testar a arquitetura antes de integrar Genkit
📝 Manter código limpo e bem documentado
🚀 Priorizar simplicidade e rapidez de implementação

````

```markdown
## Instruções de Uso

Copie este prompt completo e envie para o desenvolvedor responsável pela implementação. O prompt inclui:

- Código completo do frontend React
- Código completo do backend GraphQL
- Tipos TypeScript necessários
- Comandos de teste
- Requisitos e validações
- Testes e próximos passos

O desenvolvedor deve implementar exatamente conforme especificado, mantendo a simplicidade para MVP.
````
