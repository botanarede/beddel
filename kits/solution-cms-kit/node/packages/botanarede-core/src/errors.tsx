import React from 'react';
import type { CSSProperties, ReactNode } from 'react';

// Declare process.env for NODE_ENV check without requiring @types/node
declare const process: { env: { NODE_ENV?: string } } | undefined;

// --- Styles ---

const hiddenStyle: CSSProperties = { display: 'none' };

const devWarningStyle: CSSProperties = {
  padding: '8px 12px',
  border: '1px dashed #b8860b',
  backgroundColor: '#fff8dc',
  color: '#8b6914',
  fontSize: '13px',
  fontFamily: 'monospace',
};

const devErrorStyle: CSSProperties = {
  padding: '8px 12px',
  border: '1px solid #cd5c5c',
  backgroundColor: '#fff0f0',
  color: '#8b0000',
  fontSize: '13px',
  fontFamily: 'monospace',
};

// --- Fallback Components ---

interface UnknownComponentFallbackProps {
  type: string;
}

export function UnknownComponentFallback({ type }: UnknownComponentFallbackProps) {
  const isDev = typeof process !== 'undefined' && process.env.NODE_ENV !== 'production';
  return (
    <div data-unknown-component={type} style={isDev ? devWarningStyle : hiddenStyle}>
      {isDev ? `Unknown component: ${type}` : null}
    </div>
  );
}

interface ComponentErrorFallbackProps {
  type: string;
}

export function ComponentErrorFallback({ type }: ComponentErrorFallbackProps) {
  const isDev = typeof process !== 'undefined' && process.env.NODE_ENV !== 'production';
  return (
    <div data-error-component={type} style={isDev ? devErrorStyle : hiddenStyle}>
      {isDev ? `Component "${type}" failed to render` : null}
    </div>
  );
}

// --- Error Boundary ---

interface ComponentErrorBoundaryProps {
  componentType: string;
  onError?: (error: Error, componentType: string) => void;
  children: ReactNode;
}

interface ComponentErrorBoundaryState {
  hasError: boolean;
}

export class ComponentErrorBoundary extends React.Component<
  ComponentErrorBoundaryProps,
  ComponentErrorBoundaryState
> {
  constructor(props: ComponentErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ComponentErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error): void {
    this.props.onError?.(error, this.props.componentType);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return <ComponentErrorFallback type={this.props.componentType} />;
    }
    return this.props.children;
  }
}
