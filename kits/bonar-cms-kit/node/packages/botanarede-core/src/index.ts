export const PACKAGE_NAME = '@botanarede/core';

// --- Server-safe exports (no React runtime dependency) ---

export type { ManifestEntry, ComponentManifest } from './manifest';
export { createManifest, isAllowed, validateManifestCompatibility } from './manifest';

export type { ComponentMap, ComponentRegistry } from './registry';
export { buildRegistry, resolveComponent } from './registry';

export type { BehaviorContract, BehaviorDispatcher } from './behaviors';
export { BehaviorContractSchema, isBehavior, dispatchBehavior } from './behaviors';

export type { InterpolationContext } from './interpolation';
export { interpolate, interpolateProps } from './interpolation';

export { resolveToken, resolveTokensInProps } from './tokens';

export type { ResolvedPage, SlotMap, ResolvedPageTree } from './resolver';
export { resolvePage, resolveLayout, resolveSlots, resolvePageTree } from './resolver';

export type { Row, CollectionDataAdapter } from './data/collection-reader';
export { resolveCollectionQuery } from './data/collection-reader';
export { StubCollectionAdapter } from './data/stub-collection-adapter';

export type { DocumentDataAdapter } from './data/document-binding';
export { resolveDocumentQuery } from './data/document-binding';
export { StubDocumentAdapter } from './data/stub-document-adapter';
