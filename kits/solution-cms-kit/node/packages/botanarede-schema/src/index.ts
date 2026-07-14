export const PACKAGE_NAME = '@botanarede/schema';

export { TenantMetadataSchema, type TenantMetadata } from './metadata';
export { PageDefinitionSchema, type PageDefinition, SectionSchema, type Section } from './page';
export {
  LayoutDefinitionSchema,
  type LayoutDefinition,
  SlotDefinitionSchema,
  type SlotDefinition,
} from './layout';
export { ComponentDefinitionSchema, type ComponentDefinition } from './component';
export {
  DesignTokensSchema,
  type DesignTokens,
  ColorTokensSchema,
  type ColorTokens,
  TypographyTokensSchema,
  type TypographyTokens,
  SpacingTokensSchema,
  type SpacingTokens,
  BreakpointsSchema,
  type Breakpoints,
} from './design-tokens';
export {
  NavigationConfigSchema,
  type NavigationConfig,
  NavItemSchema,
  type NavItem,
  MenuDefinitionSchema,
  type MenuDefinition,
  RouteNavItemSchema,
  type RouteNavItem,
  ExternalNavItemSchema,
  type ExternalNavItem,
  HashNavItemSchema,
  type HashNavItem,
  GroupNavItemSchema,
  type GroupNavItem,
  validateRouteRefs,
  type RouteRefError,
} from './navigation';
export { TenantConfigSchema, type TenantConfig, CacheConfigSchema, type CacheConfig } from './tenant-config';
export {
  SiteDefaultsSchema,
  type SiteDefaults,
  AddressSchema,
  type Address,
  BrandingSchema,
  type Branding,
  OpeningHoursSchema,
  type OpeningHours,
  FAQItemSchema,
  type FAQItem,
  GeoSchema,
  ReservationConfigSchema,
} from './site-defaults';
export {
  validateLayoutRefs,
  type LayoutRefError,
  type LayoutRefValidationResult,
} from './validate-refs';
export {
  PublicTenantConfigSchema,
  type PublicTenantConfig,
  AdminTenantConfigSchema,
  type AdminTenantConfig,
  PublicMetadataSchema,
  type PublicMetadata,
  AdminMetadataSchema,
  type AdminMetadata,
  toPublicDTO,
  toAdminDTO,
} from './dto';
export {
  validateTenantConfig,
  runStructuralValidation,
  runSemanticValidation,
  runManifestValidation,
  type ValidationError,
  type ValidationWarning,
  type ValidationResult,
  type ValidationStage,
} from './validation';
export type {
  ReleaseMetadata,
  VersionId,
} from './release';
export {
  ReleaseMetadataSchema,
  VersionIdSchema,
  isValidNextVersion,
} from './release';
export {
  FilterClauseSchema,
  type FilterClause,
  OrderClauseSchema,
  type OrderClause,
  CollectionQuerySchema,
  type CollectionQuery,
  DocumentQuerySchema,
  type DocumentQuery,
  ContentBindingSchema,
  type ContentBinding,
  DataBindingSchema,
  type DataBinding,
  QueryNotPublicError,
  assertPublicRead,
} from './query';
export {
  FormFieldSchema,
  type FormField,
  SubmitBehaviorSchema,
  type SubmitBehavior,
  FormBindingConfigSchema,
  type FormBindingConfig,
} from './form';
export {
  TimeSlotSchema,
  type TimeSlot,
  ReservationAvailabilityQuerySchema,
  type ReservationAvailabilityQuery,
  ReservationBookingRequestSchema,
  type ReservationBookingRequest,
  ReservationAvailabilityResultSchema,
  type ReservationAvailabilityResult,
  ReservationWorkflowStateSchema,
  type ReservationWorkflowState,
} from './reservation';
export { type TenantRole, ROLE_HIERARCHY, hasMinimumRole } from './tenant-role';
