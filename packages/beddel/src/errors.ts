/**
 * Tipos de erro específicos para o parser YAML seguro
 */

export class YAMLBaseError extends Error {
  constructor(message: string, public code?: string) {
    super(message);
    this.name = 'YAMLBaseError';
    Object.setPrototypeOf(this, YAMLBaseError.prototype);
  }
}

export class YAMLParseError extends YAMLBaseError {
  constructor(message: string, code?: string) {
    super(message, code);
    this.name = 'YAMLParseError';
    Object.setPrototypeOf(this, YAMLParseError.prototype);
  }
}

export class YAMLSecurityError extends YAMLBaseError {
  constructor(message: string, code?: string) {
    super(message, code);
    this.name = 'YAMLSecurityError';
    Object.setPrototypeOf(this, YAMLSecurityError.prototype);
  }
}

export class YAMLPerformanceError extends YAMLBaseError {
  constructor(message: string, code?: string) {
    super(message, code);
    this.name = 'YAMLPerformanceError';
    Object.setPrototypeOf(this, YAMLPerformanceError.prototype);
  }
}
