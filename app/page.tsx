// Landing focused on the live Joker agent execution
"use client";

import Image from "next/image";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Activity, PlayCircle } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import nightOwl from "react-syntax-highlighter/dist/esm/styles/prism/night-owl";

type AgentMethod = "joker.execute" | "translator.execute" | "image.generate";

type JokerExecutionData = { response: string };

type TranslatorExecutionData = {
  texto_traduzido: string;
  metadados: {
    modelo_utilizado: string;
    tempo_processamento: number;
    confianca: number;
    idiomas_suportados: string[];
  };
};

type ImageExecutionData = {
  image_url: string;
  image_base64?: string;
  media_type?: string;
  prompt_utilizado: string;
  metadados: {
    modelo_utilizado: string;
    tempo_processamento: number;
    estilo: string;
    resolucao: string;
  };
};

type ExecutionResultData =
  | JokerExecutionData
  | TranslatorExecutionData
  | ImageExecutionData;

type ExecutionResult = {
  success: boolean;
  data?: ExecutionResultData;
  error?: string;
  executionTime?: number;
  agent?: AgentMethod;
};

const graphqlMutation = `
mutation ExecuteAgent($methodName: String!, $params: JSON!, $props: JSON!) {
  executeMethod(methodName: $methodName, params: $params, props: $props) {
    success
    data
    error
    executionTime
  }
}
`.trim();

const jokerAgentYaml = `# Joker Agent - Gemini Flash powered humorist
# Route: /agents/joker
# Method: joker.execute

agent:
  id: joker
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Joker Agent"
  description: "Conta piadas usando Gemini Flash"
  category: "utility"
  route: "/agents/joker"

schema:
  input:
    type: "object"
    properties: {}
    required: []

  output:
    type: "object"
    properties:
      response:
        type: "string"
    required: ["response"]

logic:
  workflow:
    - name: "generate-joke"
      type: "genkit-joke"
      action:
        type: "joke"
        prompt: "Conte uma piada curta e original que funcione para qualquer público."
        result: "jokerResult"

    - name: "deliver-response"
      type: "output-generator"
      action:
        type: "generate"
        output:
          response: "$jokerResult.texto"
`;

const translatorAgentYaml = `# Translator Agent - Gemini Flash translation workflow
# Route: /agents/translator
# Method: translator.execute

agent:
  id: translator
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Translator Agent"
  description: "Traduz textos entre idiomas usando Gemini Flash via Genkit"
  category: "public"
  route: "/agents/translator"

schema:
  input:
    type: "object"
    properties:
      texto:
        type: "string"
        minLength: 1
        maxLength: 10000
      idioma_origem:
        type: "string"
        pattern: "^[a-z]{2}$"
      idioma_destino:
        type: "string"
        pattern: "^[a-z]{2}$"
    required: ["texto", "idioma_origem", "idioma_destino"]

  output:
    type: "object"
    properties:
      texto_traduzido:
        type: "string"
      metadados:
        type: "object"
        properties:
          modelo_utilizado:
            type: "string"
          tempo_processamento:
            type: "number"
          confianca:
            type: "number"
          idiomas_suportados:
            type: "array"
            items:
              type: "string"
        required:
          ["modelo_utilizado", "tempo_processamento", "confianca", "idiomas_suportados"]
    required: ["texto_traduzido", "metadados"]

logic:
  workflow:
    - name: "translate"
      type: "genkit-translation"
      action:
        type: "translate"
        result: "translationResult"

`;

const imageAgentYaml = `# Image Generator Agent - Gemini Flash powered imagery
# Route: /agents/image
# Method: image.generate

agent:
  id: image
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Image Generator Agent"
  description: "Gera imagens usando Gemini Flash com estilos curados"
  category: "creative"
  route: "/agents/image"

schema:
  input:
    type: "object"
    properties:
      descricao:
        type: "string"
        minLength: 5
        maxLength: 500
      estilo:
        type: "string"
        enum: ["watercolor", "neon", "sketch"]
      resolucao:
        type: "string"
        pattern: "^[0-9]{3,4}x[0-9]{3,4}$"
    required: ["descricao", "estilo", "resolucao"]

  output:
    type: "object"
    properties:
      image_url:
        type: "string"
      image_base64:
        type: "string"
      media_type:
        type: "string"
      prompt_utilizado:
        type: "string"
      metadados:
        type: "object"
        properties:
          modelo_utilizado:
            type: "string"
          tempo_processamento:
            type: "number"
          estilo:
            type: "string"
          resolucao:
            type: "string"
        required: ["modelo_utilizado", "tempo_processamento", "estilo", "resolucao"]
    required: ["image_url", "prompt_utilizado", "metadados"]

logic:
  workflow:
    - name: "generate-image"
      type: "genkit-image"
      action:
        type: "image"
        result: "imageResult"
        promptTemplate: "Crie uma imagem em estilo {{estilo}} com foco em: {{descricao}}"

    - name: "deliver-image"
      type: "output-generator"
      action:
        type: "generate"
        output:
          image_url: "$imageResult.image_url"
          image_base64: "$imageResult.image_base64"
          media_type: "$imageResult.media_type"
          prompt_utilizado: "$imageResult.prompt_utilizado"
          metadados: "$imageResult.metadados"
`;

const AGENT_OPTIONS: Record<
  AgentMethod,
  {
    label: string;
    description: string;
    yaml: string;
  }
> = {
  "joker.execute": {
    label: "Joker Agent",
    description: "Conta piadas originais com o Gemini Flash.",
    yaml: jokerAgentYaml,
  },
  "translator.execute": {
    label: "Translator Agent",
    description: "Tradução declarativa com o helper Genkit + Gemini Flash.",
    yaml: translatorAgentYaml,
  },
  "image.generate": {
    label: "Image Generator Agent",
    description: "Gera imagens nos estilos watercolor, neon ou sketch.",
    yaml: imageAgentYaml,
  },
};

const AGENT_HANDLER_SNIPPETS: Record<AgentMethod, string> = {
  "joker.execute": `const JokerResponse: React.FC<{ data: JokerExecutionData }> = ({ data }) => (
  <p className="text-base text-slate-100">{data.response}</p>
);`,
  "translator.execute": `const TranslatorResponse: React.FC<{ data: TranslatorExecutionData }> = ({ data }) => (
  <div className="space-y-2">
    <p className="text-xs text-slate-400">{data.metadados.modelo_utilizado}</p>
    <p className="whitespace-pre-wrap text-sm text-slate-100">{data.texto_traduzido}</p>
  </div>
);`,
  "image.generate": `const ImageResponse: React.FC<{ data: ImageExecutionData }> = ({ data }) => (
  <figure className="flex flex-col items-center gap-2">
    <img src={data.image_url} alt="Preview" className="h-auto w-full max-w-[320px] rounded-xl object-contain" />
    <figcaption className="text-xs text-slate-400">Thumbnail no canvas; use o botão para baixar em alta.</figcaption>
  </figure>
);`,
};

export default function HomePage() {
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(
    null
  );
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [selectedAgent, setSelectedAgent] =
    useState<AgentMethod>("joker.execute");
  const [jokerForm, setJokerForm] = useState({
    gemini_api_key: "",
  });
  const [translatorForm, setTranslatorForm] = useState({
    texto: "",
    idioma_origem: "pt",
    idioma_destino: "en",
    gemini_api_key: "",
  });
  const [imageForm, setImageForm] = useState({
    descricao: "",
    estilo: "watercolor",
    resolucao: "768x768",
    gemini_api_key: "",
  });
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [imagePreviewError, setImagePreviewError] = useState<string | null>(null);
  const imageExecutionData =
    executionResult?.agent === "image.generate" && executionResult.data
      ? (executionResult.data as ImageExecutionData)
      : null;
  const imageMetadataHighlights = useMemo(
    () =>
      imageExecutionData
        ? [
            {
              label: "Modelo",
              value: imageExecutionData.metadados.modelo_utilizado,
            },
            {
              label: "Estilo",
              value: imageExecutionData.metadados.estilo,
            },
            {
              label: "Resolução",
              value: imageExecutionData.metadados.resolucao,
            },
            {
              label: "Tempo (ms)",
              value: `${imageExecutionData.metadados.tempo_processamento}`,
            },
          ]
        : [],
    [imageExecutionData]
  );

  const activeHandlerSnippet = useMemo(() => {
    const agentKey = executionResult?.agent ?? selectedAgent;
    return AGENT_HANDLER_SNIPPETS[agentKey];
  }, [executionResult?.agent, selectedAgent]);

  const handleDownloadImage = useCallback(() => {
    if (!imageExecutionData?.image_url) return;
    const link = document.createElement("a");
    link.href = imageExecutionData.image_url;
    link.download = "beddel-image.png";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [imageExecutionData?.image_url]);

  const activeManifest = useMemo(
    () => AGENT_OPTIONS[selectedAgent].yaml,
    [selectedAgent]
  );

  useEffect(() => {
    let blobUrl: string | null = null;

    if (imageExecutionData?.image_url) {
      const normalizedBase64 =
        imageExecutionData.image_base64?.replace(/\s+/g, "");

      if (normalizedBase64) {
        try {
          const byteCharacters = atob(normalizedBase64);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i += 1) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const blob = new Blob([new Uint8Array(byteNumbers)], {
            type: imageExecutionData.media_type || "image/png",
          });
          blobUrl = URL.createObjectURL(blob);
          setImagePreviewUrl(blobUrl);
          setImagePreviewError(null);
        } catch (error) {
          console.error("Failed to decode base64 image payload", error);
          setImagePreviewError(
            "Não foi possível decodificar o base64 retornado. Tentando exibir o data URL bruto."
          );
          setImagePreviewUrl(imageExecutionData.image_url ?? null);
        }
      } else {
        setImagePreviewUrl(imageExecutionData.image_url ?? null);
        setImagePreviewError(null);
      }
    } else {
      setImagePreviewUrl(null);
      setImagePreviewError(null);
    }

    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [imageExecutionData]);

  const renderFormattedResponse = useCallback(() => {
    if (!executionResult?.success || !executionResult.data) {
      return (
        <p className="text-sm text-slate-400">
          Execute um agente para ver a resposta formatada neste painel.
        </p>
      );
    }

    if (executionResult.agent === "translator.execute") {
      const translatorData = executionResult.data as TranslatorExecutionData;
      return (
        <div className="space-y-3 rounded-2xl border border-emerald-500/30 bg-slate-950/50 p-4">
          <p className="text-xs uppercase tracking-wide text-emerald-200">
            Texto traduzido
          </p>
          <p className="text-sm whitespace-pre-wrap text-slate-100">
            {translatorData.texto_traduzido}
          </p>
          <p className="text-xs text-slate-400">
            Modelo: {translatorData.metadados.modelo_utilizado} · Tempo:{" "}
            {translatorData.metadados.tempo_processamento}ms
          </p>
        </div>
      );
    }

    if (executionResult.agent === "joker.execute") {
      const jokerData = executionResult.data as JokerExecutionData;
      return (
        <div className="rounded-2xl border border-emerald-500/30 bg-slate-950/50 p-4 text-sm text-slate-100">
          <p className="text-xs uppercase tracking-wide text-emerald-200">
            Piada gerada
          </p>
          <p className="mt-2">{jokerData.response}</p>
        </div>
      );
    }

    if (executionResult.agent === "image.generate" && imageExecutionData) {
      return (
        <div className="space-y-4">
          <p className="text-sm text-slate-300">
            Thumbnail reduzido no canvas para inspeção rápida. Use o botão para
            baixar em resolução completa.
          </p>
          <figure className="mx-auto flex w-full max-w-[360px] flex-col items-center gap-3 rounded-2xl border border-slate-900 bg-slate-950/60 p-4">
            {imagePreviewUrl ? (
              <img
                src={imagePreviewUrl}
                alt="Resultado do Image Generator"
                className="h-auto w-full max-w-[320px] rounded-xl border border-slate-800 object-contain"
              />
            ) : (
              <div className="flex h-40 w-full items-center justify-center rounded-xl border border-dashed border-slate-800 text-xs text-slate-500">
                Não foi possível carregar o preview da imagem.
              </div>
            )}
            <figcaption className="text-xs text-slate-400">
              Preview reduzido enviado pelo runtime declarativo.
            </figcaption>
            {imagePreviewError && (
              <p className="text-xs text-amber-400">{imagePreviewError}</p>
            )}
          </figure>
          <div className="space-y-3">
            <div className="rounded-2xl border border-slate-900 bg-slate-950/60 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-400">
                Prompt utilizado
              </p>
              <p className="mt-2 text-sm text-slate-100">
                {imageExecutionData.prompt_utilizado}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {imageMetadataHighlights.map((item) => (
                <div
                  key={item.label}
                  className="rounded-xl border border-slate-900 bg-slate-950/40 p-3"
                >
                  <p className="text-xs text-slate-400">{item.label}</p>
                  <p className="text-sm font-semibold text-slate-100">
                    {item.value}
                  </p>
                </div>
              ))}
            </div>
            <Button
              onClick={handleDownloadImage}
              className="w-full bg-emerald-600 text-white hover:bg-emerald-500"
            >
              Baixar imagem original
            </Button>
          </div>
        </div>
      );
    }

    return (
      <p className="text-sm text-slate-400">
        Resposta recebida, mas não há formatação específica para este agente.
      </p>
    );
  }, [
    executionResult,
    handleDownloadImage,
    imageExecutionData,
    imageMetadataHighlights,
    imagePreviewError,
    imagePreviewUrl,
  ]);

  const handleMouseMove = (e: React.MouseEvent<HTMLElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setMousePosition({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  };

  const handleExecuteAgent = useCallback(async () => {
    setIsExecuting(true);
    setExecutionResult(null);
    const started = Date.now();

    const runTranslatorValidation = (): {
      error?: string;
      params?: {
        texto: string;
        idioma_origem: string;
        idioma_destino: string;
      };
    } => {
      const texto = translatorForm.texto.trim();
      const idiomaOrigem = translatorForm.idioma_origem.trim().toLowerCase();
      const idiomaDestino = translatorForm.idioma_destino.trim().toLowerCase();

      if (!texto) {
        return { error: "Digite um texto para traduzir." };
      }
      if (texto.length > 10000) {
        return { error: "O texto não pode exceder 10.000 caracteres." };
      }
      if (!/^[a-z]{2}$/.test(idiomaOrigem) || !/^[a-z]{2}$/.test(idiomaDestino)) {
        return { error: "Idiomas devem seguir o padrão ISO-639-1 (ex: pt, en)." };
      }
      if (idiomaOrigem === idiomaDestino) {
        return { error: "Escolha idiomas de origem e destino diferentes." };
      }
      if (!translatorForm.gemini_api_key.trim()) {
        return { error: "Informe a sua Gemini API key para executar o tradutor." };
      }

      return {
        params: {
          texto,
          idioma_origem: idiomaOrigem,
          idioma_destino: idiomaDestino,
        },
      };
    };

    const runImageValidation = (): {
      error?: string;
      params?: {
        descricao: string;
        estilo: string;
        resolucao: string;
      };
    } => {
      const descricao = imageForm.descricao.trim();
      const estilo = imageForm.estilo.trim().toLowerCase();
      const resolucao = imageForm.resolucao.trim().toLowerCase();

      if (!descricao) {
        return { error: "Descreva a cena que deseja gerar." };
      }
      if (descricao.length > 500) {
        return { error: "A descrição deve ter no máximo 500 caracteres." };
      }
      if (!["watercolor", "neon", "sketch"].includes(estilo)) {
        return {
          error: "Escolha um estilo válido: watercolor, neon ou sketch.",
        };
      }
      if (!/^[0-9]{3,4}x[0-9]{3,4}$/.test(resolucao)) {
        return {
          error: "Use uma resolução no formato 1024x1024 ou similar.",
        };
      }
      if (!imageForm.gemini_api_key.trim()) {
        return {
          error: "Informe a sua Gemini API key para gerar imagens.",
        };
      }

      return {
        params: {
          descricao,
          estilo,
          resolucao,
        },
      };
    };

    let params: Record<string, unknown> = {};
    let props: Record<string, string> = {};

    if (selectedAgent === "joker.execute") {
      const apiKey = jokerForm.gemini_api_key.trim();
      if (!apiKey) {
        setExecutionResult({
          success: false,
          error: "Informe a sua Gemini API key para gerar piadas.",
          agent: selectedAgent,
        });
        setIsExecuting(false);
        return;
      }
      props = { gemini_api_key: apiKey };
    } else if (selectedAgent === "translator.execute") {
      const validation = runTranslatorValidation();
      if (validation.error || !validation.params) {
        setExecutionResult({
          success: false,
          error: validation.error ?? "Invalid translator parameters.",
          agent: selectedAgent,
        });
        setIsExecuting(false);
        return;
      }

      params = validation.params;
      props = { gemini_api_key: translatorForm.gemini_api_key.trim() };
    } else if (selectedAgent === "image.generate") {
      const validation = runImageValidation();
      if (validation.error || !validation.params) {
        setExecutionResult({
          success: false,
          error: validation.error ?? "Invalid image parameters.",
          agent: selectedAgent,
        });
        setIsExecuting(false);
        return;
      }

      params = validation.params;
      props = { gemini_api_key: imageForm.gemini_api_key.trim() };
    }

    try {
      const response = await fetch("/api/graphql", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-admin-tenant": "true",
        },
        body: JSON.stringify({
          query: graphqlMutation,
          variables: {
            methodName: selectedAgent,
            params,
            props,
          },
        }),
      });

      const json = await response.json();

      if (json.errors?.length) {
        throw new Error(json.errors[0].message);
      }

      const executionData = json.data?.executeMethod;
      const totalTime = Date.now() - started;

      setExecutionResult({
        success: executionData?.success ?? false,
        data: executionData?.data,
        error: executionData?.error,
        executionTime: executionData?.executionTime ?? totalTime,
        agent: selectedAgent,
      });
    } catch (error) {
      setExecutionResult({
        success: false,
        error:
          error instanceof Error
            ? error.message
            : "Unknown error executing agent.",
        agent: selectedAgent,
      });
    } finally {
      setIsExecuting(false);
    }
  }, [selectedAgent, jokerForm, translatorForm, imageForm]);

  return (
    <div className="bg-slate-950 text-slate-100 overflow-x-hidden">
      <section
        className="relative isolate mt-6 w-full bg-white/95 px-6 py-8 shadow-[0_35px_120px_rgba(15,23,42,0.35)] transition-shadow duration-500"
        aria-label="Beddel identity banner"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setMousePosition({ x: 0, y: 0 })}
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300"
          style={{
            background: `radial-gradient(circle 300px at ${mousePosition.x}px ${mousePosition.y}px, rgba(16, 185, 129, 0.4), rgba(16, 185, 129, 0.2), transparent 70%)`,
            opacity: mousePosition.x > 0 && mousePosition.y > 0 ? 1 : 0,
          }}
        />
        <div className="mx-auto flex max-w-[1400px] items-center justify-center relative z-10">
          <Image
            src="/images/marca.png"
            alt="Beddel logo"
            width={320}
            height={88}
            className="h-16 w-auto"
            priority
          />
        </div>
      </section>
      <main className="container mx-auto px-4 pb-24 pt-12">
        <section className="space-y-6 text-center" aria-labelledby="runtime-heading">
          <Badge className="mx-auto w-fit bg-slate-800 text-slate-200">
            Live declarative demo
          </Badge>
          <div className="space-y-4">
            <h1
              id="runtime-heading"
              className="text-4xl font-semibold tracking-tight text-white md:text-5xl"
            >
              Run the Beddel runtime in real time
            </h1>
            <p className="mx-auto max-w-3xl text-lg text-slate-300 md:text-xl">
              Execute os agentes declarativos Joker, Translator e Image Generator direto
              pelo `/api/graphql`, usando o cabeçalho `x-admin-tenant` e vendo o mesmo
              payload registrado pelos dashboards internos.
            </p>
          </div>
        </section>

        <section className="mt-12 grid gap-6 lg:grid-cols-[0.55fr_1fr]">
          <Card className="border-slate-800 bg-slate-950/80">
            <CardHeader>
              <div className="flex items-center gap-3">
                <PlayCircle className="h-5 w-5 text-emerald-300" />
                <div>
                  <CardTitle>Execute um agente declarativo</CardTitle>
                  <CardDescription>
                    Direct call to `/api/graphql` com `x-admin-tenant: true`.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-100">
                A faixa admin dispensa API keys de tenants e permite validar rapidamente
                tanto o fluxo estático do Joker quanto os helpers Translator e Image
                Generator integrados ao Genkit.
              </div>
              <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                <div className="space-y-2 text-left">
                  <Label htmlFor="agent-select" className="text-slate-200">
                    Agente ativo
                  </Label>
                  <Select
                    value={selectedAgent}
                    onValueChange={(value) =>
                      setSelectedAgent(value as AgentMethod)
                    }
                  >
                    <SelectTrigger
                      id="agent-select"
                      className="w-full border border-slate-800 bg-slate-900/70 text-left text-slate-100 transition-colors hover:border-emerald-400/60 focus-visible:border-emerald-400/80 focus-visible:ring-emerald-400/30"
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="border border-slate-800 bg-slate-950 text-slate-100">
                      <SelectItem
                        value="joker.execute"
                        className="data-[state=checked]:bg-emerald-500/20 data-[state=checked]:text-emerald-200"
                      >
                        {AGENT_OPTIONS["joker.execute"].label}
                      </SelectItem>
                      <SelectItem
                        value="translator.execute"
                        className="data-[state=checked]:bg-emerald-500/20 data-[state=checked]:text-emerald-200"
                      >
                        {AGENT_OPTIONS["translator.execute"].label}
                      </SelectItem>
                      <SelectItem
                        value="image.generate"
                        className="data-[state=checked]:bg-emerald-500/20 data-[state=checked]:text-emerald-200"
                      >
                        {AGENT_OPTIONS["image.generate"].label}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-400">
                    <p className="font-mono text-[0.65rem] uppercase tracking-wide text-emerald-300">
                      {selectedAgent}
                    </p>
                    <p className="mt-1 text-slate-300">
                      {AGENT_OPTIONS[selectedAgent].description}
                    </p>
                  </div>
                </div>

                {selectedAgent === "joker.execute" && (
                  <div className="space-y-4">
                    <p className="text-sm text-slate-400">
                      O Joker usa o Gemini Flash e precisa da sua chave apenas para esta
                      sessão.
                    </p>
                    <div className="space-y-2">
                      <Label htmlFor="joker-key" className="text-slate-200">
                        Gemini API key
                      </Label>
                      <Input
                        id="joker-key"
                        type="password"
                        value={jokerForm.gemini_api_key}
                        onChange={(event) =>
                          setJokerForm({ gemini_api_key: event.target.value })
                        }
                        placeholder="sk-..."
                        className="bg-slate-900/50 text-slate-100"
                      />
                    </div>
                    <p className="text-xs text-slate-500">
                      Nada é salvo no servidor — o header admin só encaminha o payload.
                    </p>
                  </div>
                )}

                {selectedAgent === "translator.execute" && (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="translator-texto" className="text-slate-200">
                        Texto
                      </Label>
                      <Textarea
                        id="translator-texto"
                        rows={5}
                        placeholder="Digite o texto para tradução..."
                        value={translatorForm.texto}
                        onChange={(event) =>
                          setTranslatorForm((prev) => ({
                            ...prev,
                            texto: event.target.value,
                          }))
                        }
                        className="bg-slate-900/50 text-sm text-slate-100"
                      />
                    </div>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-2">
                        <Label
                          htmlFor="translator-origem"
                          className="text-slate-200"
                        >
                          Idioma origem
                        </Label>
                        <Input
                          id="translator-origem"
                          value={translatorForm.idioma_origem}
                          onChange={(event) =>
                            setTranslatorForm((prev) => ({
                              ...prev,
                              idioma_origem: event.target.value,
                            }))
                          }
                          placeholder="pt"
                          className="bg-slate-900/50 text-slate-100"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label
                          htmlFor="translator-destino"
                          className="text-slate-200"
                        >
                          Idioma destino
                        </Label>
                        <Input
                          id="translator-destino"
                          value={translatorForm.idioma_destino}
                          onChange={(event) =>
                            setTranslatorForm((prev) => ({
                              ...prev,
                              idioma_destino: event.target.value,
                            }))
                          }
                          placeholder="en"
                          className="bg-slate-900/50 text-slate-100"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="translator-key" className="text-slate-200">
                          Gemini API key
                        </Label>
                        <Input
                          id="translator-key"
                          type="password"
                          value={translatorForm.gemini_api_key}
                          onChange={(event) =>
                            setTranslatorForm((prev) => ({
                              ...prev,
                              gemini_api_key: event.target.value,
                            }))
                          }
                          placeholder="sk-..."
                          className="bg-slate-900/50 text-slate-100"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-slate-500">
                      A chave é usada somente para essa chamada e não sai do seu navegador.
                    </p>
                  </div>
                )}

                {selectedAgent === "image.generate" && (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="image-descricao" className="text-slate-200">
                        Descrição da cena
                      </Label>
                      <Textarea
                        id="image-descricao"
                        rows={4}
                        placeholder="Ex: Uma raposa lendo em uma biblioteca futurista..."
                        value={imageForm.descricao}
                        onChange={(event) =>
                          setImageForm((prev) => ({
                            ...prev,
                            descricao: event.target.value,
                          }))
                        }
                        className="bg-slate-900/50 text-sm text-slate-100"
                      />
                    </div>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-2">
                        <Label htmlFor="image-estilo" className="text-slate-200">
                          Estilo
                        </Label>
                        <Select
                          value={imageForm.estilo}
                          onValueChange={(value) =>
                            setImageForm((prev) => ({
                              ...prev,
                              estilo: value,
                            }))
                          }
                        >
                          <SelectTrigger
                            id="image-estilo"
                            className="w-full border border-slate-800 bg-slate-900/70 text-left text-slate-100"
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="border border-slate-800 bg-slate-950 text-slate-100">
                            <SelectItem value="watercolor">Watercolor</SelectItem>
                            <SelectItem value="neon">Neon</SelectItem>
                            <SelectItem value="sketch">Sketch</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="image-resolucao" className="text-slate-200">
                          Resolução
                        </Label>
                        <Input
                          id="image-resolucao"
                          value={imageForm.resolucao}
                          onChange={(event) =>
                            setImageForm((prev) => ({
                              ...prev,
                              resolucao: event.target.value,
                            }))
                          }
                          placeholder="768x768"
                          className="bg-slate-900/50 text-slate-100"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="image-key" className="text-slate-200">
                          Gemini API key
                        </Label>
                        <Input
                          id="image-key"
                          type="password"
                          value={imageForm.gemini_api_key}
                          onChange={(event) =>
                            setImageForm((prev) => ({
                              ...prev,
                              gemini_api_key: event.target.value,
                            }))
                          }
                          placeholder="sk-..."
                          className="bg-slate-900/50 text-slate-100"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-slate-500">
                      Combine descrições ricas + estilo para orientar o helper do Gemini
                      Flash. O resultado chega em base64 e pode ser inspecionado abaixo.
                    </p>
                  </div>
                )}
              </div>
              <Button
                onClick={handleExecuteAgent}
                disabled={isExecuting}
                className="w-full gap-2 bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500"
              >
                {isExecuting ? (
                  <>
                    <Activity className="h-4 w-4 animate-spin" />
                    Executing...
                  </>
                ) : (
                  <>
                    <PlayCircle className="h-4 w-4" />
                    {selectedAgent === "joker.execute"
                      ? "Executar Joker"
                      : selectedAgent === "translator.execute"
                        ? "Executar Translator"
                        : "Gerar imagem"}
                  </>
                )}
              </Button>
              <p className="text-xs text-slate-500">
                Need tenant-scoped API keys instead? Use the `/beddel-alpha` path.
              </p>
            </CardContent>
          </Card>

          <Card className="border-slate-800 bg-slate-950/40">
            <CardHeader>
              <CardTitle>Execution result</CardTitle>
              <CardDescription>
                Mirrors exactly what our internal dashboards record from the runtime.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {executionResult ? (
                executionResult.success && executionResult.data ? (
                  <div className="space-y-6">
                    <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4">
                      <p className="text-sm font-semibold text-emerald-200">
                        Success ({executionResult.agent})
                      </p>
                      <p className="mt-1 text-xs text-emerald-100">
                        Resposta recebida do runtime declarativo. Valide o JSON,
                        veja o handler TSX e pré-visualize a diagramação final.
                      </p>
                    </div>
                    {executionResult.executionTime && (
                      <Badge className="w-fit bg-slate-900 text-emerald-300">
                        Execution time: {executionResult.executionTime}ms
                      </Badge>
                    )}
                    <div className="grid gap-6 lg:grid-cols-3">
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <p className="text-sm font-semibold text-slate-100">
                          JSON resposta
                        </p>
                        <pre className="mt-3 max-h-[360px] overflow-auto rounded-xl bg-slate-950/80 p-3 text-xs text-emerald-100">
                          <code className="font-mono">
                            {JSON.stringify(executionResult.data, null, 2)}
                          </code>
                        </pre>
                      </div>
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <p className="text-sm font-semibold text-slate-100">
                          TSX que trata a resposta
                        </p>
                        {activeHandlerSnippet ? (
                          <div className="mt-3 overflow-auto rounded-xl">
                            <SyntaxHighlighter
                              language="tsx"
                              style={nightOwl}
                              customStyle={{
                                background: "rgba(2,6,23,0.8)",
                                borderRadius: "0.75rem",
                              }}
                            >
                              {activeHandlerSnippet}
                            </SyntaxHighlighter>
                          </div>
                        ) : (
                          <p className="mt-3 text-xs text-slate-400">
                            Sem snippet disponível para este agente.
                          </p>
                        )}
                      </div>
                      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <p className="text-sm font-semibold text-slate-100">
                          Resposta formatada
                        </p>
                        <div className="mt-3 text-sm text-slate-200">
                          {renderFormattedResponse()}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
                    {executionResult.error ?? "Agent execution failed."}
                  </div>
                )
              ) : (
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 text-center text-sm text-slate-400">
                  Escolha um agente e pressione “Executar” para ver a resposta.
                </div>
              )}
            </CardContent>
          </Card>
        </section>

        <section className="mt-12 space-y-6" aria-labelledby="yaml-heading">
          <div className="flex items-center gap-3">
            <Badge className="bg-slate-800 text-slate-200">Manifest</Badge>
            <div>
              <h2 id="yaml-heading" className="text-2xl font-semibold text-white">
                {selectedAgent === "joker.execute"
                  ? "`joker/joker.yaml`"
                  : selectedAgent === "translator.execute"
                    ? "`translator/translator.yaml`"
                    : "`image/image.yaml`"}
              </h2>
              <p className="text-sm text-slate-400">
                Highlighted directly from the manifest loaded in production to mirror the
                same contract interpreted by the runtime.
              </p>
            </div>
          </div>
          <Card className="border-slate-800 bg-slate-950/70">
            <CardContent className="p-0">
              <SyntaxHighlighter
                language="yaml"
                style={nightOwl}
                customStyle={{
                  margin: 0,
                  borderRadius: "1.5rem",
                  background: "transparent",
                  padding: "1.5rem",
                  fontSize: "0.85rem",
                }}
              >
                {activeManifest}
              </SyntaxHighlighter>
            </CardContent>
          </Card>
        </section>
      </main>
    </div>
  );
}
