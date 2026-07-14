import { useCallback, useMemo } from 'react'

import { SignInEmailCode } from '../../core/useCases/auth/SignInEmailCode'
import { SignInEmailPassword } from '../../core/useCases/auth/SignInEmailPassword'
import { SignInOAuth } from '../../core/useCases/auth/SignInOAuth'
import { SignOut } from '../../core/useCases/auth/SignOut'
import type { LoginResult, OAuthProvider, OAuthSignInOptions } from '../../core/types'
import { useBonarJsContext } from './useBonarJsContext'

/** Return shape of {@link useAuth}. */
export interface UseAuthApi {
  user: ReturnType<typeof useBonarJsContext>['user']
  loading: boolean
  signInEmailPassword: (email: string, password: string) => Promise<LoginResult>
  signInEmailCode: (email: string, code?: number) => Promise<LoginResult>
  signInOAuth: (
    provider: OAuthProvider,
    options?: OAuthSignInOptions,
  ) => Promise<LoginResult>
  signOut: () => Promise<void>
}

/**
 * React binding for the auth use cases. Requires {@link BonarJsProvider}
 * somewhere above in the tree.
 */
export function useAuth(): UseAuthApi {
  const { adapters, user, loading } = useBonarJsContext()

  const emailPassword = useMemo(
    () => new SignInEmailPassword(adapters.auth),
    [adapters.auth],
  )
  const emailCode = useMemo(
    () => new SignInEmailCode(adapters.auth),
    [adapters.auth],
  )
  const oauth = useMemo(() => new SignInOAuth(adapters.auth), [adapters.auth])
  const signOutUseCase = useMemo(() => new SignOut(adapters.auth), [adapters.auth])

  const signInEmailPassword = useCallback(
    (email: string, password: string) => emailPassword.execute(email, password),
    [emailPassword],
  )
  const signInEmailCode = useCallback(
    (email: string, code?: number) => emailCode.execute(email, code),
    [emailCode],
  )
  const signInOAuth = useCallback(
    (provider: OAuthProvider, options?: OAuthSignInOptions) =>
      oauth.execute(provider, options),
    [oauth],
  )
  const signOut = useCallback(() => signOutUseCase.execute(), [signOutUseCase])

  return {
    user,
    loading,
    signInEmailPassword,
    signInEmailCode,
    signInOAuth,
    signOut,
  }
}
