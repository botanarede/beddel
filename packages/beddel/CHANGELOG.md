# Changelog

## [0.2.2] - 2025-12-19

### Changed
- Maintenance release (no functional changes)

## [0.2.0] - 2025-12-18

### Added
- **TypeScript Code-Behind for Custom Agents**: Custom agents can now include TypeScript implementations alongside YAML definitions
  - Place `.ts` files in `/agents` directory
  - Export functions are automatically registered with namespaced keys
  - New `custom-action` workflow type for executing TypeScript functions
  - Full access to input, variables, execution context, and Beddel helpers
- **Enhanced Agent Registry**: 
  - `loadCustomFunctions()` method for dynamic TypeScript module loading
  - `getCustomFunction()` method for runtime function retrieval
  - Async agent loading with proper error handling
- **Complete Documentation**: Added comprehensive guide for TypeScript code-behind in README.md

### Changed
- `AgentRegistry.loadCustomAgents()` is now async to support dynamic imports
- Updated agent loading flow to include TypeScript module discovery

### Backward Compatibility
- All existing agents (joker, translator, image-generator) continue to work without changes
- YAML-only agents are fully supported
- No breaking changes to existing APIs

---


All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-18

### Added
- Initial release of Beddel package
- Secure YAML parser with FAILSAFE schema
- Declarative agent runtime (protocol v2.0)
- Agent registry with custom agent support
- Built-in agents: joker, translator, image generator
- Schema validation with Zod
- Isolated runtime with security profiles
- Multi-tenant Firebase support
- GDPR/LGPD compliance utilities
- Performance monitoring and autoscaling
- Security scanning and threat detection
- Server utilities (KV store, runtime security)
- GraphQL API integration
- Comprehensive documentation and guides

### Features
- Custom agents auto-discovery from `/agents` directory
- Agent override mechanism (custom > built-in)
- Variable interpolation in YAML workflows
- Nested property access in output schemas
- Gemini Flash integration for AI capabilities
- TypeScript support with full type definitions
