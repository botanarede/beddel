export { makeGetItems } from './getItems'
export { makeGetItemById } from './getItemById'
export { makeGetItemChildById } from './getItemChildById'
export { makeSetItem } from './setItem'
export { makeDeleteItemById } from './deleteItemById'
export type { HandlerDeps, FirestoreTimestamp } from './types'

// Auth handler factories and types
export {
  makeEmailCodeAuth,
  makeVerifyAppCheck,
  makeCheckUserInDatabase,
  type AuthHandlerDeps,
  type AdminAuth,
  type AppCheckIssuer,
  type EmailSender,
} from './auth'
